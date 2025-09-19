"""Camera management for webcam enumeration and capture."""

import cv2
import logging
import platform
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple
from queue import Queue, Empty
import numpy as np


@dataclass
class CameraInfo:
    """Information about an available camera."""
    id: int
    friendly_name: str
    backend_id: str
    
    def __str__(self):
        return self.friendly_name or f"Camera {self.id}"


class CameraManager:
    """Manages camera enumeration and capture."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cap: Optional[cv2.VideoCapture] = None
        self.current_camera_id: Optional[int] = None
        self.frame_queue: Queue = Queue(maxsize=2)
        self.capture_thread: Optional[threading.Thread] = None
        self.capture_running = False
        self.fps = 30.0
        self.frame_count = 0
        self.dropped_frames = 0
        
    def list_cameras(self) -> List[CameraInfo]:
        """Enumerate available cameras with friendly names."""
        cameras = []
        
        # Test up to 10 camera indices
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # Try to read a frame to confirm the camera works
                ret, _ = cap.read()
                if ret:
                    friendly_name = self._get_camera_friendly_name(i)
                    backend_id = f"camera://{i}"
                    cameras.append(CameraInfo(i, friendly_name, backend_id))
                cap.release()
        
        self.logger.info(f"Found {len(cameras)} cameras")
        return cameras
    
    def _get_camera_friendly_name(self, camera_id: int) -> str:
        """Get friendly name for camera (platform-specific)."""
        system = platform.system()
        
        if system == "Windows":
            return self._get_windows_camera_name(camera_id)
        elif system == "Darwin":  # macOS
            return self._get_macos_camera_name(camera_id)
        elif system == "Linux":
            return self._get_linux_camera_name(camera_id)
        else:
            return f"Camera {camera_id}"
    
    def _get_windows_camera_name(self, camera_id: int) -> str:
        """Get Windows camera friendly name."""
        try:
            # Try to get camera name from DirectShow backend
            cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            if cap.isOpened():
                # Unfortunately, OpenCV doesn't expose device names directly
                # This is a limitation we'll work with
                cap.release()
                return f"Camera {camera_id}"
        except Exception:
            pass
        return f"Camera {camera_id}"
    
    def _get_macos_camera_name(self, camera_id: int) -> str:
        """Get macOS camera friendly name."""
        # macOS typically has built-in cameras with recognizable names
        if camera_id == 0:
            return "FaceTime HD Camera"
        return f"Camera {camera_id}"
    
    def _get_linux_camera_name(self, camera_id: int) -> str:
        """Get Linux camera friendly name."""
        try:
            # Try to read from /sys/class/video4linux/
            import os
            video_device = f"/sys/class/video4linux/video{camera_id}/name"
            if os.path.exists(video_device):
                with open(video_device, 'r') as f:
                    name = f.read().strip()
                    if name:
                        return name
        except Exception:
            pass
        return f"Camera {camera_id}"
    
    def open_camera(self, camera_id: int) -> bool:
        """Open a camera for capture."""
        if self.cap is not None:
            self.close_camera()
        
        try:
            # Try different backends for better compatibility
            backends = [cv2.CAP_DSHOW, cv2.CAP_V4L2, cv2.CAP_ANY]
            
            for backend in backends:
                self.cap = cv2.VideoCapture(camera_id, backend)
                if self.cap.isOpened():
                    # Test if we can actually read frames
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        self.current_camera_id = camera_id
                        self.logger.info(f"Opened camera {camera_id} with backend {backend}")
                        return True
                    else:
                        self.cap.release()
                        self.cap = None
            
            self.logger.error(f"Failed to open camera {camera_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"Exception opening camera {camera_id}: {e}")
            if self.cap:
                self.cap.release()
                self.cap = None
            return False
    
    def close_camera(self) -> None:
        """Close the current camera."""
        self.stop_capture()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.current_camera_id = None
        self.logger.info("Camera closed")
    
    def set_resolution(self, width: int, height: int) -> bool:
        """Set camera resolution."""
        if not self.cap or not self.cap.isOpened():
            return False
        
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            # Verify the resolution was set
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            self.logger.info(f"Set resolution to {actual_width}x{actual_height} (requested: {width}x{height})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set resolution: {e}")
            return False
    
    def get_resolution(self) -> Tuple[int, int]:
        """Get current camera resolution."""
        if not self.cap or not self.cap.isOpened():
            return (0, 0)
        
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (width, height)
    
    def start_capture(self) -> bool:
        """Start continuous frame capture in a separate thread."""
        if not self.cap or not self.cap.isOpened():
            self.logger.error("Cannot start capture: no camera opened")
            return False
        
        if self.capture_running:
            return True
        
        self.capture_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        self.logger.info("Started camera capture thread")
        return True
    
    def stop_capture(self) -> None:
        """Stop the capture thread."""
        if self.capture_running:
            self.capture_running = False
            if self.capture_thread:
                self.capture_thread.join(timeout=1.0)
            self.logger.info("Stopped camera capture thread")
    
    def _capture_loop(self) -> None:
        """Main capture loop running in separate thread."""
        last_fps_time = time.time()
        fps_frame_count = 0
        
        while self.capture_running and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    self.logger.warning("Failed to read frame from camera")
                    time.sleep(0.01)  # Small delay to prevent busy waiting
                    continue
                
                # Try to put frame in queue (non-blocking)
                try:
                    self.frame_queue.put_nowait(frame.copy())
                    self.frame_count += 1
                    fps_frame_count += 1
                except:
                    # Queue is full, drop the frame
                    self.dropped_frames += 1
                
                # Calculate FPS every second
                current_time = time.time()
                if current_time - last_fps_time >= 1.0:
                    self.fps = fps_frame_count / (current_time - last_fps_time)
                    last_fps_time = current_time
                    fps_frame_count = 0
                
                # Small delay to control frame rate
                time.sleep(1.0 / 60.0)  # Target 60 FPS max
                
            except Exception as e:
                self.logger.error(f"Error in capture loop: {e}")
                break
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame (non-blocking)."""
        try:
            # Get the most recent frame, discard older ones
            frame = None
            while not self.frame_queue.empty():
                try:
                    frame = self.frame_queue.get_nowait()
                except Empty:
                    break
            return frame
        except Exception as e:
            self.logger.error(f"Error getting frame: {e}")
            return None
    
    def get_single_frame(self) -> Optional[np.ndarray]:
        """Get a single frame directly (blocking)."""
        if not self.cap or not self.cap.isOpened():
            return None
        
        try:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return frame.copy()
            return None
        except Exception as e:
            self.logger.error(f"Error getting single frame: {e}")
            return None
    
    def get_fps(self) -> float:
        """Get current capture FPS."""
        return self.fps
    
    def get_stats(self) -> dict:
        """Get capture statistics."""
        return {
            'fps': self.fps,
            'frame_count': self.frame_count,
            'dropped_frames': self.dropped_frames,
            'queue_size': self.frame_queue.qsize(),
            'is_capturing': self.capture_running
        }
    
    def is_opened(self) -> bool:
        """Check if a camera is currently opened."""
        return self.cap is not None and self.cap.isOpened()
    
    def __del__(self):
        """Cleanup on destruction."""
        self.close_camera()
