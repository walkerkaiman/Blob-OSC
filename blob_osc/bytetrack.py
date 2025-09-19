"""
ByteTrack implementation for blob tracking.
Adapted from: https://github.com/FoundationVision/ByteTrack

This module provides robust multi-object tracking using the ByteTrack algorithm,
which handles occlusions, crossovers, and noisy detections better than simple tracking.
"""

import numpy as np
import logging
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from collections import OrderedDict
import time

try:
    from lap import lapjv
    LAP_AVAILABLE = True
except ImportError:
    LAP_AVAILABLE = False
    logging.warning("LAP not available, using fallback assignment")

try:
    from scipy.spatial.distance import cdist
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logging.warning("SciPy not available, using basic distance calculation")


@dataclass
class TrackState:
    """Track state enumeration."""
    NEW = 0
    TRACKED = 1
    LOST = 2
    REMOVED = 3


@dataclass
class Detection:
    """Detection data structure for ByteTrack."""
    bbox: np.ndarray  # [x1, y1, x2, y2]
    score: float
    class_id: int = 0


@dataclass 
class Track:
    """Track data structure."""
    track_id: int
    bbox: np.ndarray  # [x1, y1, x2, y2]
    score: float
    state: int = TrackState.NEW
    frame_id: int = 0
    start_frame: int = 0
    tracklet_len: int = 0
    
    # Kalman filter state (simplified)
    mean: Optional[np.ndarray] = None
    covariance: Optional[np.ndarray] = None
    
    def __post_init__(self):
        if self.mean is None:
            # Initialize state: [cx, cy, w, h, vx, vy, vw, vh]
            cx = (self.bbox[0] + self.bbox[2]) / 2
            cy = (self.bbox[1] + self.bbox[3]) / 2
            w = self.bbox[2] - self.bbox[0]
            h = self.bbox[3] - self.bbox[1]
            self.mean = np.array([cx, cy, w, h, 0, 0, 0, 0], dtype=np.float32)
            
        if self.covariance is None:
            # Simple covariance initialization
            self.covariance = np.eye(8, dtype=np.float32) * 1000
    
    def predict(self):
        """Predict next state using simple motion model."""
        # Simple constant velocity model
        self.mean[0] += self.mean[4]  # cx += vx
        self.mean[1] += self.mean[5]  # cy += vy
        self.mean[2] += self.mean[6]  # w += vw
        self.mean[3] += self.mean[7]  # h += vh
        
        # Increase uncertainty
        self.covariance *= 1.1
    
    def update(self, detection: Detection):
        """Update track with new detection."""
        # Extract detection bbox
        x1, y1, x2, y2 = detection.bbox
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        w = x2 - x1
        h = y2 - y1
        
        # Simple update (simplified Kalman filter)
        if self.mean is not None:
            # Calculate velocity
            dt = 1.0  # Assume 1 frame time step
            vx = (cx - self.mean[0]) / dt
            vy = (cy - self.mean[1]) / dt
            vw = (w - self.mean[2]) / dt
            vh = (h - self.mean[3]) / dt
            
            # Update state
            self.mean = np.array([cx, cy, w, h, vx, vy, vw, vh], dtype=np.float32)
        
        # Update bbox and score
        self.bbox = detection.bbox.copy()
        self.score = detection.score
        self.tracklet_len += 1
    
    def get_bbox(self) -> np.ndarray:
        """Get current bounding box in [x1, y1, x2, y2] format."""
        if self.mean is not None:
            cx, cy, w, h = self.mean[:4]
            x1 = cx - w / 2
            y1 = cy - h / 2
            x2 = cx + w / 2
            y2 = cy + h / 2
            return np.array([x1, y1, x2, y2])
        return self.bbox
    
    def get_center(self) -> Tuple[float, float]:
        """Get track center."""
        if self.mean is not None:
            return (self.mean[0], self.mean[1])
        else:
            bbox = self.get_bbox()
            return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


class BYTETracker:
    """
    ByteTrack multi-object tracker.
    
    Simplified implementation focusing on the core ByteTrack algorithm
    without requiring YOLOX dependencies.
    """
    
    def __init__(self, 
                 track_thresh: float = 0.5,
                 track_buffer: int = 30,
                 match_thresh: float = 0.8,
                 min_box_area: float = 10,
                 mot20: bool = False):
        """
        Initialize ByteTracker.
        
        Args:
            track_thresh: Detection confidence threshold for tracking
            track_buffer: Number of frames to keep lost tracks
            match_thresh: Matching threshold for association
            min_box_area: Minimum bounding box area
            mot20: Whether to use MOT20 specific settings
        """
        self.track_thresh = track_thresh
        self.track_buffer = track_buffer
        self.match_thresh = match_thresh
        self.min_box_area = min_box_area
        self.mot20 = mot20
        
        self.frame_id = 0
        self.tracked_tracks: List[Track] = []
        self.lost_tracks: List[Track] = []
        self.removed_tracks: List[Track] = []
        
        self.track_id_count = 0
        self.logger = logging.getLogger(__name__)
        
    def update(self, detections: List[Detection], img_info: Optional[Dict] = None, img_size: Optional[Tuple[int, int]] = None) -> List[Track]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of Detection objects
            img_info: Optional image info (for compatibility)
            img_size: Optional image size (for compatibility)
            
        Returns:
            List of active tracks
        """
        self.frame_id += 1
        
        # Filter detections by score and area
        valid_detections = []
        low_score_detections = []
        
        for det in detections:
            bbox_area = (det.bbox[2] - det.bbox[0]) * (det.bbox[3] - det.bbox[1])
            if bbox_area >= self.min_box_area:
                if det.score >= self.track_thresh:
                    valid_detections.append(det)
                else:
                    low_score_detections.append(det)
        
        # Predict all tracks
        for track in self.tracked_tracks:
            track.predict()
        
        # Associate high score detections with tracks
        matched_tracks, unmatched_detections, unmatched_tracks = self._associate(
            self.tracked_tracks, valid_detections, self.match_thresh
        )
        
        # Update matched tracks
        for track_idx, det_idx in matched_tracks:
            track = self.tracked_tracks[track_idx]
            track.update(valid_detections[det_idx])
            track.state = TrackState.TRACKED
            track.frame_id = self.frame_id
        
        # Handle unmatched tracks - try to match with low score detections
        unmatched_tracked_tracks = [self.tracked_tracks[i] for i in unmatched_tracks]
        
        if low_score_detections:
            matched_tracks_low, unmatched_detections_low, unmatched_tracks_low = self._associate(
                unmatched_tracked_tracks, low_score_detections, 0.5  # Lower threshold for second association
            )
            
            # Update tracks matched with low score detections
            for track_idx, det_idx in matched_tracks_low:
                track = unmatched_tracked_tracks[track_idx]
                track.update(low_score_detections[det_idx])
                track.state = TrackState.TRACKED
                track.frame_id = self.frame_id
            
            # Update unmatched detections list
            remaining_detections = [valid_detections[i] for i in unmatched_detections]
            remaining_detections.extend([low_score_detections[i] for i in unmatched_detections_low])
        else:
            remaining_detections = [valid_detections[i] for i in unmatched_detections]
            unmatched_tracks_low = list(range(len(unmatched_tracked_tracks)))
        
        # Mark unmatched tracks as lost
        for track_idx in unmatched_tracks_low:
            track = unmatched_tracked_tracks[track_idx]
            track.state = TrackState.LOST
        
        # Create new tracks for unmatched detections
        for detection in remaining_detections:
            if detection.score >= self.track_thresh:
                new_track = Track(
                    track_id=self.track_id_count,
                    bbox=detection.bbox.copy(),
                    score=detection.score,
                    state=TrackState.TRACKED,
                    frame_id=self.frame_id,
                    start_frame=self.frame_id,
                    tracklet_len=1
                )
                self.tracked_tracks.append(new_track)
                self.track_id_count += 1
        
        # Move lost tracks to lost_tracks list
        self.tracked_tracks = [t for t in self.tracked_tracks if t.state == TrackState.TRACKED]
        self.lost_tracks.extend([t for t in self.tracked_tracks if t.state == TrackState.LOST])
        
        # Try to re-associate lost tracks with remaining detections
        if self.lost_tracks and remaining_detections:
            matched_tracks_lost, _, _ = self._associate(
                self.lost_tracks, remaining_detections, 0.5
            )
            
            for track_idx, det_idx in matched_tracks_lost:
                track = self.lost_tracks[track_idx]
                track.update(remaining_detections[det_idx])
                track.state = TrackState.TRACKED
                track.frame_id = self.frame_id
                self.tracked_tracks.append(track)
        
        # Remove lost tracks from lost_tracks list
        self.lost_tracks = [t for t in self.lost_tracks if t.state == TrackState.LOST]
        
        # Remove old lost tracks
        current_lost_tracks = []
        for track in self.lost_tracks:
            if self.frame_id - track.frame_id <= self.track_buffer:
                current_lost_tracks.append(track)
            else:
                track.state = TrackState.REMOVED
                self.removed_tracks.append(track)
        self.lost_tracks = current_lost_tracks
        
        # Return all active tracks
        return [t for t in self.tracked_tracks if t.state == TrackState.TRACKED]
    
    def _associate(self, tracks: List[Track], detections: List[Detection], thresh: float) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Associate tracks with detections using IoU or distance.
        
        Returns:
            (matched_pairs, unmatched_detections, unmatched_tracks)
        """
        if not tracks or not detections:
            return [], list(range(len(detections))), list(range(len(tracks)))
        
        # Calculate cost matrix using IoU or distance
        cost_matrix = self._calculate_cost_matrix(tracks, detections)
        
        # Perform assignment
        if LAP_AVAILABLE and cost_matrix.size > 0:
            try:
                # Use LAP for optimal assignment
                row_indices, col_indices, _ = lapjv(cost_matrix, extend_cost=True, cost_limit=thresh)
                
                matched_pairs = []
                unmatched_tracks = []
                unmatched_detections = []
                
                for i, j in enumerate(col_indices):
                    if j >= 0 and cost_matrix[i, j] <= thresh:
                        matched_pairs.append((i, j))
                    else:
                        unmatched_tracks.append(i)
                
                for j in range(len(detections)):
                    if j not in col_indices:
                        unmatched_detections.append(j)
                        
                return matched_pairs, unmatched_detections, unmatched_tracks
                
            except Exception as e:
                self.logger.warning(f"LAP assignment failed: {e}, using greedy fallback")
        
        # Fallback to greedy assignment
        return self._greedy_assignment(cost_matrix, thresh)
    
    def _calculate_cost_matrix(self, tracks: List[Track], detections: List[Detection]) -> np.ndarray:
        """Calculate cost matrix between tracks and detections."""
        if not tracks or not detections:
            return np.empty((0, 0))
        
        # Get track bboxes
        track_bboxes = np.array([track.get_bbox() for track in tracks])
        det_bboxes = np.array([det.bbox for det in detections])
        
        # Calculate IoU matrix
        ious = self._calculate_ious(track_bboxes, det_bboxes)
        
        # Convert IoU to cost (1 - IoU)
        cost_matrix = 1 - ious
        
        return cost_matrix
    
    def _calculate_ious(self, bboxes1: np.ndarray, bboxes2: np.ndarray) -> np.ndarray:
        """Calculate IoU between two sets of bounding boxes."""
        if bboxes1.size == 0 or bboxes2.size == 0:
            return np.empty((0, 0))
        
        # Expand dimensions for broadcasting
        bboxes1 = np.expand_dims(bboxes1, axis=1)  # (N, 1, 4)
        bboxes2 = np.expand_dims(bboxes2, axis=0)  # (1, M, 4)
        
        # Calculate intersection
        x1 = np.maximum(bboxes1[:, :, 0], bboxes2[:, :, 0])
        y1 = np.maximum(bboxes1[:, :, 1], bboxes2[:, :, 1])
        x2 = np.minimum(bboxes1[:, :, 2], bboxes2[:, :, 2])
        y2 = np.minimum(bboxes1[:, :, 3], bboxes2[:, :, 3])
        
        intersection = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
        
        # Calculate areas
        area1 = (bboxes1[:, :, 2] - bboxes1[:, :, 0]) * (bboxes1[:, :, 3] - bboxes1[:, :, 1])
        area2 = (bboxes2[:, :, 2] - bboxes2[:, :, 0]) * (bboxes2[:, :, 3] - bboxes2[:, :, 1])
        
        # Calculate union
        union = area1 + area2 - intersection
        
        # Calculate IoU
        iou = intersection / np.maximum(union, 1e-6)
        
        return iou
    
    def _greedy_assignment(self, cost_matrix: np.ndarray, thresh: float) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """Greedy assignment fallback when LAP is not available."""
        if cost_matrix.size == 0:
            return [], [], []
        
        matched_pairs = []
        unmatched_tracks = list(range(cost_matrix.shape[0]))
        unmatched_detections = list(range(cost_matrix.shape[1]))
        
        # Find best matches greedily
        while unmatched_tracks and unmatched_detections:
            # Find minimum cost
            min_cost = float('inf')
            best_track = -1
            best_det = -1
            
            for t in unmatched_tracks:
                for d in unmatched_detections:
                    if cost_matrix[t, d] < min_cost:
                        min_cost = cost_matrix[t, d]
                        best_track = t
                        best_det = d
            
            # If best match is below threshold, add it
            if min_cost <= thresh:
                matched_pairs.append((best_track, best_det))
                unmatched_tracks.remove(best_track)
                unmatched_detections.remove(best_det)
            else:
                break
        
        return matched_pairs, unmatched_detections, unmatched_tracks
    
    def reset(self):
        """Reset the tracker."""
        self.frame_id = 0
        self.tracked_tracks.clear()
        self.lost_tracks.clear()
        self.removed_tracks.clear()
        self.track_id_count = 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get tracker statistics."""
        return {
            'active_tracks': len(self.tracked_tracks),
            'lost_tracks': len(self.lost_tracks),
            'total_tracks': self.track_id_count,
            'frame_id': self.frame_id
        }


def create_bytetrack_tracker(track_thresh: float = 0.5,
                           track_buffer: int = 30,
                           match_thresh: float = 0.8,
                           min_box_area: float = 10) -> BYTETracker:
    """
    Create a ByteTrack tracker with specified parameters.
    
    Args:
        track_thresh: Detection confidence threshold for tracking
        track_buffer: Number of frames to keep lost tracks
        match_thresh: Matching threshold for association  
        min_box_area: Minimum bounding box area
        
    Returns:
        BYTETracker instance
    """
    return BYTETracker(
        track_thresh=track_thresh,
        track_buffer=track_buffer,
        match_thresh=match_thresh,
        min_box_area=min_box_area
    )
