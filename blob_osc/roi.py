"""ROI (Region of Interest) management and interactive overlay."""

import cv2
import numpy as np
from typing import Tuple, Optional, List
from dataclasses import dataclass
from PyQt6.QtCore import QRect, QPoint


@dataclass
class ROI:
    """Region of Interest rectangle."""
    x: int
    y: int
    w: int
    h: int
    
    def __post_init__(self):
        # Ensure positive dimensions
        if self.w < 0:
            self.x += self.w
            self.w = abs(self.w)
        if self.h < 0:
            self.y += self.h
            self.h = abs(self.h)
    
    @classmethod
    def from_percentages(cls, left_pct: float, top_pct: float, right_pct: float, bottom_pct: float, 
                        image_width: int, image_height: int) -> 'ROI':
        """Create ROI from percentage values (0-100)."""
        left = int((left_pct / 100.0) * image_width)
        top = int((top_pct / 100.0) * image_height)
        right = int((right_pct / 100.0) * image_width)
        bottom = int((bottom_pct / 100.0) * image_height)
        
        x = left
        y = top
        w = right - left
        h = bottom - top
        
        return cls(x, y, w, h)
    
    def to_percentages(self, image_width: int, image_height: int) -> tuple[float, float, float, float]:
        """Convert ROI to percentage values (left, top, right, bottom)."""
        if image_width == 0 or image_height == 0:
            return (0.0, 0.0, 100.0, 100.0)
        
        left_pct = (self.x / image_width) * 100.0
        top_pct = (self.y / image_height) * 100.0
        right_pct = ((self.x + self.w) / image_width) * 100.0
        bottom_pct = ((self.y + self.h) / image_height) * 100.0
        
        return (left_pct, top_pct, right_pct, bottom_pct)
    
    def to_rect(self) -> QRect:
        """Convert to QRect."""
        return QRect(self.x, self.y, self.w, self.h)
    
    def to_tuple(self) -> Tuple[int, int, int, int]:
        """Convert to tuple (x, y, w, h)."""
        return (self.x, self.y, self.w, self.h)
    
    def contains_point(self, x: int, y: int) -> bool:
        """Check if point is inside ROI."""
        return (self.x <= x <= self.x + self.w and 
                self.y <= y <= self.y + self.h)
    
    def get_corners(self) -> List[Tuple[int, int]]:
        """Get corner points of ROI."""
        return [
            (self.x, self.y),  # top-left
            (self.x + self.w, self.y),  # top-right
            (self.x + self.w, self.y + self.h),  # bottom-right
            (self.x, self.y + self.h)  # bottom-left
        ]
    
    def get_handles(self) -> List[Tuple[int, int]]:
        """Get handle positions for resizing (8 handles around the rectangle)."""
        cx, cy = self.x + self.w // 2, self.y + self.h // 2
        return [
            (self.x, self.y),  # top-left
            (cx, self.y),  # top-center
            (self.x + self.w, self.y),  # top-right
            (self.x + self.w, cy),  # middle-right
            (self.x + self.w, self.y + self.h),  # bottom-right
            (cx, self.y + self.h),  # bottom-center
            (self.x, self.y + self.h),  # bottom-left
            (self.x, cy)  # middle-left
        ]
    
    def area(self) -> int:
        """Calculate ROI area."""
        return self.w * self.h
    
    def is_valid(self) -> bool:
        """Check if ROI has valid dimensions."""
        return self.w > 0 and self.h > 0
    
    def constrain_to_bounds(self, max_width: int, max_height: int) -> 'ROI':
        """Constrain ROI to image bounds."""
        x = max(0, min(self.x, max_width - 1))
        y = max(0, min(self.y, max_height - 1))
        w = min(self.w, max_width - x)
        h = min(self.h, max_height - y)
        return ROI(x, y, w, h)


class ROIManager:
    """Manages Region of Interest selection and manipulation."""
    
    def __init__(self):
        self.roi: Optional[ROI] = None
        self.image_width = 0
        self.image_height = 0
        self.locked = False
        
        # Default crop pixels from edges (left, top, right, bottom)
        self.left_crop = 0
        self.top_crop = 0
        self.right_crop = 0
        self.bottom_crop = 0
    
    def set_image_size(self, width: int, height: int) -> None:
        """Set the image dimensions."""
        self.image_width = width
        self.image_height = height
        
        # Update ROI from crop values
        self.update_roi_from_crop()
    
    def set_crop_pixels(self, left: int, top: int, right: int, bottom: int) -> None:
        """Set crop pixels from edges and update ROI."""
        if self.locked:
            return
        
        # Store the exact values from sliders - no modification
        self.left_crop = left
        self.top_crop = top
        self.right_crop = right
        self.bottom_crop = bottom
        
        self.update_roi_from_crop()
    
    def get_crop_pixels(self) -> tuple[int, int, int, int]:
        """Get current crop pixels (left, top, right, bottom)."""
        return (self.left_crop, self.top_crop, self.right_crop, self.bottom_crop)
    
    def update_roi_from_crop(self) -> None:
        """Update ROI from current crop pixel values."""
        if self.image_width > 0 and self.image_height > 0:
            # Use the raw crop values directly - no modification
            # Apply constraints only to the final ROI, not the stored values
            
            x = max(0, self.left_crop)
            y = max(0, self.top_crop)
            
            # Calculate width and height
            right_edge = self.image_width - max(0, self.right_crop)
            bottom_edge = self.image_height - max(0, self.bottom_crop)
            
            w = right_edge - x
            h = bottom_edge - y
            
            # Ensure minimum size and bounds
            if x >= self.image_width - 10:
                x = max(0, self.image_width - 10)
            if y >= self.image_height - 10:
                y = max(0, self.image_height - 10)
            
            w = max(10, min(w, self.image_width - x))
            h = max(10, min(h, self.image_height - y))
            
            self.roi = ROI(x, y, w, h)
    
    def reset_roi(self) -> None:
        """Reset ROI to full image."""
        self.left_crop = 0
        self.top_crop = 0
        self.right_crop = 0
        self.bottom_crop = 0
        self.update_roi_from_crop()
    
    def set_roi(self, x: int, y: int, w: int, h: int, update_crop_values: bool = False) -> None:
        """Set ROI to specific coordinates. Optionally update crop values."""
        self.roi = ROI(x, y, w, h)
        if self.image_width > 0 and self.image_height > 0:
            self.roi = self.roi.constrain_to_bounds(self.image_width, self.image_height)
            
            # Only update crop values if explicitly requested (to avoid accumulation)
            if update_crop_values:
                self.left_crop = self.roi.x
                self.top_crop = self.roi.y
                self.right_crop = self.image_width - (self.roi.x + self.roi.w)
                self.bottom_crop = self.image_height - (self.roi.y + self.roi.h)
    
    def get_roi(self) -> Optional[ROI]:
        """Get current ROI."""
        return self.roi
    
    def apply_roi(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Apply ROI to crop an image."""
        if self.roi is None or not self.roi.is_valid():
            return image
        
        h, w = image.shape[:2]
        roi = self.roi.constrain_to_bounds(w, h)
        
        if roi.is_valid():
            return image[roi.y:roi.y + roi.h, roi.x:roi.x + roi.w]
        return image
    
    def draw_overlay(self, image: np.ndarray, color: Tuple[int, int, int] = (0, 255, 0), 
                    thickness: int = 2) -> np.ndarray:
        """Draw visual crop preview overlay - shows what WOULD be cropped without affecting the image."""
        overlay = image.copy()
        h, w = image.shape[:2]
        
        # Draw semi-transparent crop preview rectangles
        crop_color = (50, 50, 200)  # Red for areas that would be cropped
        border_color = (0, 255, 0)  # Green borders
        
        # Left crop rectangle (width = left_crop)
        if self.left_crop > 0:
            rect_width = min(self.left_crop, w)
            cv2.rectangle(overlay, (0, 0), (rect_width, h), crop_color, -1)
            cv2.rectangle(overlay, (0, 0), (rect_width, h), border_color, 2)
        
        # Right crop rectangle (width = right_crop)
        if self.right_crop > 0:
            rect_width = min(self.right_crop, w)
            start_x = w - rect_width
            cv2.rectangle(overlay, (start_x, 0), (w, h), crop_color, -1)
            cv2.rectangle(overlay, (start_x, 0), (w, h), border_color, 2)
        
        # Top crop rectangle (height = top_crop)
        if self.top_crop > 0:
            rect_height = min(self.top_crop, h)
            cv2.rectangle(overlay, (0, 0), (w, rect_height), crop_color, -1)
            cv2.rectangle(overlay, (0, 0), (w, rect_height), border_color, 2)
        
        # Bottom crop rectangle (height = bottom_crop)
        if self.bottom_crop > 0:
            rect_height = min(self.bottom_crop, h)
            start_y = h - rect_height
            cv2.rectangle(overlay, (0, start_y), (w, h), crop_color, -1)
            cv2.rectangle(overlay, (0, start_y), (w, h), border_color, 2)
        
        # Draw the resulting ROI border (yellow outline of remaining area)
        if self.roi and self.roi.is_valid():
            cv2.rectangle(overlay, 
                         (self.roi.x, self.roi.y), 
                         (self.roi.x + self.roi.w, self.roi.y + self.roi.h),
                         (0, 255, 255), 3)  # Yellow border for final ROI
        
        # Blend with original image for semi-transparency
        alpha = 0.4
        result = cv2.addWeighted(image, 1 - alpha, overlay, alpha, 0)
        
        # Draw text info with better positioning
        info_y = 25
        text = f"Preview - Crop Rectangles: L:{self.left_crop}px T:{self.top_crop}px R:{self.right_crop}px B:{self.bottom_crop}px"
        roi_text = f"Resulting ROI: {self.roi.w if self.roi else w}x{self.roi.h if self.roi else h}"
        
        # White outline + black text for readability
        cv2.putText(result, text, (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(result, text, (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        
        cv2.putText(result, roi_text, (10, info_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        cv2.putText(result, roi_text, (10, info_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        return result
    
    def set_locked(self, locked: bool) -> None:
        """Lock or unlock ROI editing."""
        self.locked = locked
    
    def is_locked(self) -> bool:
        """Check if ROI is locked."""
        return self.locked
