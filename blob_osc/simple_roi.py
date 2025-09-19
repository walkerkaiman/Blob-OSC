"""Simple ROI system with visual crop overlays."""

import cv2
import numpy as np
from typing import Tuple, Optional


class SimpleROI:
    """Simple ROI manager with visual crop rectangles."""
    
    def __init__(self):
        # Image dimensions
        self.image_width = 0
        self.image_height = 0
        
        # Crop values in pixels from each edge
        self.left_crop = 0
        self.top_crop = 0
        self.right_crop = 0
        self.bottom_crop = 0
    
    def set_image_size(self, width: int, height: int) -> None:
        """Set the image dimensions."""
        self.image_width = width
        self.image_height = height
    
    def set_crop_values(self, left: int, top: int, right: int, bottom: int) -> None:
        """Set crop values in pixels from each edge."""
        self.left_crop = max(0, left)
        self.top_crop = max(0, top)
        self.right_crop = max(0, right)
        self.bottom_crop = max(0, bottom)
    
    def get_crop_values(self) -> Tuple[int, int, int, int]:
        """Get current crop values."""
        return (self.left_crop, self.top_crop, self.right_crop, self.bottom_crop)
    
    def get_roi_bounds(self) -> Tuple[int, int, int, int]:
        """Get the actual ROI coordinates (x, y, width, height)."""
        if self.image_width == 0 or self.image_height == 0:
            return (0, 0, 0, 0)
        
        x = self.left_crop
        y = self.top_crop
        w = self.image_width - self.left_crop - self.right_crop
        h = self.image_height - self.top_crop - self.bottom_crop
        
        # Ensure minimum size
        w = max(10, w)
        h = max(10, h)
        
        # Ensure bounds
        x = min(x, self.image_width - w)
        y = min(y, self.image_height - h)
        
        return (x, y, w, h)
    
    def apply_crop(self, image: np.ndarray) -> np.ndarray:
        """Apply the crop to an image and return the cropped region."""
        if image is None:
            return image
        
        x, y, w, h = self.get_roi_bounds()
        
        # Apply crop
        if w > 0 and h > 0:
            return image[y:y+h, x:x+w]
        else:
            return image
    
    def draw_crop_overlay(self, image: np.ndarray) -> np.ndarray:
        """Draw black rectangles controlled by sliders."""
        if image is None:
            return image

        result = image.copy()
        h, w = image.shape[:2]

        # Black rectangles - no blending, just solid black
        black = (0, 0, 0)

        # Left rectangle
        if self.left_crop > 0:
            width = min(self.left_crop, w)
            cv2.rectangle(result, (0, 0), (width, h), black, -1)

        # Right rectangle
        if self.right_crop > 0:
            width = min(self.right_crop, w)
            start_x = max(0, w - width)
            cv2.rectangle(result, (start_x, 0), (w, h), black, -1)

        # Top rectangle
        if self.top_crop > 0:
            height = min(self.top_crop, h)
            cv2.rectangle(result, (0, 0), (w, height), black, -1)

        # Bottom rectangle
        if self.bottom_crop > 0:
            height = min(self.bottom_crop, h)
            start_y = max(0, h - height)
            cv2.rectangle(result, (0, start_y), (w, h), black, -1)

        return result
    
    def reset(self) -> None:
        """Reset all crop values to zero."""
        self.left_crop = 0
        self.top_crop = 0
        self.right_crop = 0
        self.bottom_crop = 0
