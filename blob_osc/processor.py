"""Image processing, blob detection, and tracking."""

import cv2
import numpy as np
import logging
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from collections import defaultdict
import time

# Using simple OpenCV tracking instead of ByteTrack for better Pi compatibility


@dataclass
class BlobInfo:
    """Information about a detected blob."""
    id: int
    contour: np.ndarray
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    center: Tuple[float, float]  # cx, cy
    area: float
    polygon: List[Tuple[int, int]]  # Simplified contour points
    
    def get_center_normalized(self, roi_width: int, roi_height: int) -> Tuple[float, float]:
        """Get normalized center coordinates (0-1)."""
        return (round(self.center[0] / roi_width, 3), round(self.center[1] / roi_height, 3))
    
    def get_bbox_normalized(self, roi_width: int, roi_height: int) -> Tuple[float, float, float, float]:
        """Get normalized bounding box (0-1)."""
        x, y, w, h = self.bbox
        return (round(x / roi_width, 3), round(y / roi_height, 3), 
                round(w / roi_width, 3), round(h / roi_height, 3))


class BlobTracker:
    """Simple blob tracker using centroid matching."""
    
    def __init__(self, max_distance: float = 50.0, max_age: int = 5):
        self.max_distance = max_distance
        self.max_age = max_age
        self.next_id = 0
        self.tracked_blobs: Dict[int, dict] = {}
        self.logger = logging.getLogger(__name__)
    
    def update(self, detections: List[Tuple[float, float, float]]) -> Dict[int, Tuple[float, float]]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of (cx, cy, area) tuples
            
        Returns:
            Dictionary mapping blob_id to (cx, cy)
        """
        current_time = time.time()
        
        # Age existing tracks
        for blob_id in list(self.tracked_blobs.keys()):
            self.tracked_blobs[blob_id]['age'] += 1
            if self.tracked_blobs[blob_id]['age'] > self.max_age:
                del self.tracked_blobs[blob_id]
        
        # Match detections to existing tracks
        assignments = self._match_detections(detections)
        
        # Update existing tracks and create new ones
        active_tracks = {}
        
        for i, (cx, cy, area) in enumerate(detections):
            if i in assignments:
                # Update existing track
                blob_id = assignments[i]
                self.tracked_blobs[blob_id].update({
                    'center': (cx, cy),
                    'area': area,
                    'age': 0,
                    'last_seen': current_time
                })
                active_tracks[blob_id] = (cx, cy)
            else:
                # Create new track
                blob_id = self.next_id
                self.next_id += 1
                self.tracked_blobs[blob_id] = {
                    'center': (cx, cy),
                    'area': area,
                    'age': 0,
                    'last_seen': current_time
                }
                active_tracks[blob_id] = (cx, cy)
        
        return active_tracks
    
    def _match_detections(self, detections: List[Tuple[float, float, float]]) -> Dict[int, int]:
        """Match detections to existing tracks using distance."""
        assignments = {}
        
        if not self.tracked_blobs or not detections:
            return assignments
        
        # Calculate distance matrix
        track_ids = list(self.tracked_blobs.keys())
        distances = np.full((len(detections), len(track_ids)), float('inf'))
        
        for i, (cx, cy, _) in enumerate(detections):
            for j, track_id in enumerate(track_ids):
                track_cx, track_cy = self.tracked_blobs[track_id]['center']
                dist = np.sqrt((cx - track_cx)**2 + (cy - track_cy)**2)
                if dist <= self.max_distance:
                    distances[i, j] = dist
        
        # Simple greedy assignment (could use Hungarian algorithm for optimal)
        used_tracks = set()
        for i in range(len(detections)):
            if len(used_tracks) >= len(track_ids):
                break
            
            # Find closest available track
            min_dist = float('inf')
            best_track_idx = -1
            
            for j in range(len(track_ids)):
                if j not in used_tracks and distances[i, j] < min_dist:
                    min_dist = distances[i, j]
                    best_track_idx = j
            
            if best_track_idx >= 0:
                assignments[i] = track_ids[best_track_idx]
                used_tracks.add(best_track_idx)
        
        return assignments
    
    def reset(self) -> None:
        """Reset all tracks."""
        self.tracked_blobs.clear()
        self.next_id = 0


class ImageProcessor:
    """Image processing pipeline for blob detection."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.tracker = BlobTracker()
    
    def convert_to_gray(self, image: np.ndarray, channel: str = 'gray') -> np.ndarray:
        """Convert image to grayscale."""
        if len(image.shape) == 2:
            return image
        
        if channel == 'gray':
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        elif channel == 'red':
            return image[:, :, 2]
        elif channel == 'green':
            return image[:, :, 1]
        elif channel == 'blue':
            return image[:, :, 0]
        else:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    def apply_blur(self, image: np.ndarray, kernel_size: int) -> np.ndarray:
        """Apply Gaussian blur."""
        if kernel_size <= 0:
            return image
        
        # Ensure kernel size is odd
        if kernel_size % 2 == 0:
            kernel_size += 1
        
        return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
    
    def threshold_global(self, image: np.ndarray, threshold_value: int, invert: bool = False) -> np.ndarray:
        """Apply global thresholding."""
        if invert:
            _, binary = cv2.threshold(image, threshold_value, 255, cv2.THRESH_BINARY_INV)
        else:
            _, binary = cv2.threshold(image, threshold_value, 255, cv2.THRESH_BINARY)
        return binary
    
    def threshold_adaptive(self, image: np.ndarray, method: str = 'gaussian', 
                          block_size: int = 11, C: float = 2, invert: bool = False) -> np.ndarray:
        """Apply adaptive thresholding."""
        # Ensure block size is odd and >= 3
        if block_size % 2 == 0:
            block_size += 1
        block_size = max(3, block_size)
        
        adaptive_method = cv2.ADAPTIVE_THRESH_GAUSSIAN_C if method == 'gaussian' else cv2.ADAPTIVE_THRESH_MEAN_C
        
        # Choose threshold type
        threshold_type = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
        
        return cv2.adaptiveThreshold(
            image, 255, adaptive_method, threshold_type, block_size, C
        )
    
    def apply_morphology(self, image: np.ndarray, open_kernel: int = 0, 
                        close_kernel: int = 0) -> np.ndarray:
        """Apply morphological operations."""
        result = image.copy()
        
        if open_kernel > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_kernel, open_kernel))
            result = cv2.morphologyEx(result, cv2.MORPH_OPEN, kernel)
        
        if close_kernel > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_kernel, close_kernel))
            result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel)
        
        return result
    
    def find_contours(self, binary_image: np.ndarray) -> List[np.ndarray]:
        """Find contours in binary image."""
        contours, _ = cv2.findContours(binary_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours
    
    def contour_to_bbox(self, contour: np.ndarray) -> Tuple[int, int, int, int]:
        """Convert contour to bounding box."""
        return cv2.boundingRect(contour)
    
    def contour_area(self, contour: np.ndarray) -> float:
        """Calculate contour area."""
        return cv2.contourArea(contour)
    
    def contour_center(self, contour: np.ndarray) -> Tuple[float, float]:
        """Calculate contour centroid."""
        M = cv2.moments(contour)
        if M['m00'] == 0:
            # Fallback to bounding box center
            x, y, w, h = self.contour_to_bbox(contour)
            return (x + w / 2, y + h / 2)
        
        cx = M['m10'] / M['m00']
        cy = M['m01'] / M['m00']
        return (cx, cy)
    
    def simplify_polygon(self, contour: np.ndarray, epsilon_factor: float = 0.02) -> List[Tuple[int, int]]:
        """Simplify contour to polygon."""
        epsilon = epsilon_factor * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        return [(point[0][0], point[0][1]) for point in approx]
    
    def filter_blobs_by_area(self, contours: List[np.ndarray], min_area: float, 
                           max_area: float) -> List[np.ndarray]:
        """Filter contours by area."""
        filtered = []
        for contour in contours:
            area = self.contour_area(contour)
            if min_area <= area <= max_area:
                filtered.append(contour)
        return filtered
    
    def process_image(self, image: np.ndarray, threshold_config: dict, morph_config: dict,
                     blob_config: dict, track_ids: bool = True) -> Tuple[np.ndarray, List[BlobInfo]]:
        """
        Complete image processing pipeline.
        
        Args:
            image: Input image
            threshold_config: Thresholding parameters
            morph_config: Morphological operation parameters
            blob_config: Blob detection parameters
            track_ids: Whether to track blob IDs
            
        Returns:
            Tuple of (binary_image, blob_list)
        """
        # Convert to grayscale
        gray = self.convert_to_gray(image, threshold_config.get('channel', 'gray'))
        
        # Apply blur
        blur_kernel = threshold_config.get('blur', 0)
        if blur_kernel > 0:
            gray = self.apply_blur(gray, blur_kernel)
        
        # Apply thresholding
        threshold_mode = threshold_config.get('mode', 'global')
        invert = threshold_config.get('invert', False)
        if threshold_mode == 'global':
            binary = self.threshold_global(gray, threshold_config.get('value', 127), invert)
        else:  # adaptive
            adaptive_params = threshold_config.get('adaptive', {})
            binary = self.threshold_adaptive(
                gray,
                adaptive_params.get('method', 'gaussian'),
                adaptive_params.get('blocksize', 11),
                adaptive_params.get('C', 2),
                invert
            )
        
        # Apply morphological operations
        binary = self.apply_morphology(
            binary,
            morph_config.get('open', 0),
            morph_config.get('close', 0)
        )
        
        # Find contours
        contours = self.find_contours(binary)
        
        # Filter by area
        min_area = blob_config.get('min_area', 200)
        max_area = blob_config.get('max_area', 20000)
        filtered_contours = self.filter_blobs_by_area(contours, min_area, max_area)
        
        # Create blob info
        blobs = []
        detections = []
        
        for contour in filtered_contours:
            bbox = self.contour_to_bbox(contour)
            center = self.contour_center(contour)
            area = self.contour_area(contour)
            polygon = self.simplify_polygon(contour)
            
            detections.append((center[0], center[1], area))
            
            # Create blob info with temporary ID
            blob = BlobInfo(
                id=-1,  # Will be assigned by tracker
                contour=contour,
                bbox=bbox,
                center=center,
                area=area,
                polygon=polygon
            )
            blobs.append(blob)
        
        # Track blobs if enabled
        if track_ids and blob_config.get('track_ids', True):
            # Use simple tracking
            tracked = self.tracker.update(detections)
            self._assign_simple_ids(blobs, detections, tracked)
        else:
            # Assign simple sequential IDs
            for i, blob in enumerate(blobs):
                blob.id = i
        
        return binary, blobs
    
    def draw_blob_overlay(self, image: np.ndarray, blobs: List[BlobInfo], 
                         color: Tuple[int, int, int] = (0, 0, 255), thickness: int = 2) -> np.ndarray:
        """Draw blob detection overlay on image."""
        overlay = image.copy()
        
        for blob in blobs:
            # Draw bounding box
            x, y, w, h = blob.bbox
            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, thickness)
            
            # Draw center point
            cx, cy = int(blob.center[0]), int(blob.center[1])
            cv2.circle(overlay, (cx, cy), 3, color, -1)
            
            # Draw blob ID only in green text
            label = f"ID:{blob.id}"
            cv2.putText(overlay, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        return overlay
    
    def _assign_simple_ids(self, blobs: List[BlobInfo], detections: List[Tuple[float, float, float]], tracked: Dict[int, Tuple[float, float]]) -> None:
        """Assign IDs using simple tracking."""
        for i, blob in enumerate(blobs):
            # Find the tracked ID that corresponds to this blob
            blob_center = (detections[i][0], detections[i][1])
            for blob_id, tracked_center in tracked.items():
                if abs(blob_center[0] - tracked_center[0]) < 1 and abs(blob_center[1] - tracked_center[1]) < 1:
                    blob.id = blob_id
                    break
            
            # Fallback: assign a temporary ID if tracking failed
            if blob.id == -1:
                blob.id = i
    
    def reset_tracker(self) -> None:
        """Reset the blob tracker."""
        self.tracker.reset()
    
    def get_tracker_stats(self) -> dict:
        """Get tracker statistics."""
        return {
            'active_tracks': len(self.tracker.tracked_blobs),
            'next_id': self.tracker.next_id,
            'tracker_type': 'Simple'
        }