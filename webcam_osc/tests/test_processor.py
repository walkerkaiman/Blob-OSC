"""Tests for image processor module."""

import unittest
import numpy as np
import cv2
from ..processor import ImageProcessor, BlobTracker, BlobInfo


class TestImageProcessor(unittest.TestCase):
    """Test cases for ImageProcessor."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.processor = ImageProcessor()
        
        # Create test image with simple shapes
        self.test_image = np.zeros((200, 200, 3), dtype=np.uint8)
        
        # Add white rectangles (blobs)
        cv2.rectangle(self.test_image, (50, 50), (100, 100), (255, 255, 255), -1)
        cv2.rectangle(self.test_image, (120, 120), (150, 150), (255, 255, 255), -1)
    
    def test_convert_to_gray(self):
        """Test grayscale conversion."""
        gray = self.processor.convert_to_gray(self.test_image)
        self.assertEqual(len(gray.shape), 2)
        self.assertEqual(gray.shape, (200, 200))
        
        # Test channel extraction
        red = self.processor.convert_to_gray(self.test_image, 'red')
        self.assertEqual(len(red.shape), 2)
    
    def test_apply_blur(self):
        """Test blur application."""
        gray = self.processor.convert_to_gray(self.test_image)
        
        # No blur
        no_blur = self.processor.apply_blur(gray, 0)
        np.testing.assert_array_equal(gray, no_blur)
        
        # With blur
        blurred = self.processor.apply_blur(gray, 5)
        self.assertEqual(blurred.shape, gray.shape)
        # Blurred image should be different
        self.assertFalse(np.array_equal(gray, blurred))
    
    def test_threshold_global(self):
        """Test global thresholding."""
        gray = self.processor.convert_to_gray(self.test_image)
        binary = self.processor.threshold_global(gray, 127)
        
        self.assertEqual(len(binary.shape), 2)
        self.assertEqual(binary.shape, gray.shape)
        
        # Should only contain 0 and 255
        unique_values = np.unique(binary)
        self.assertTrue(all(val in [0, 255] for val in unique_values))
    
    def test_threshold_adaptive(self):
        """Test adaptive thresholding."""
        gray = self.processor.convert_to_gray(self.test_image)
        binary = self.processor.threshold_adaptive(gray)
        
        self.assertEqual(len(binary.shape), 2)
        self.assertEqual(binary.shape, gray.shape)
        
        # Should only contain 0 and 255
        unique_values = np.unique(binary)
        self.assertTrue(all(val in [0, 255] for val in unique_values))
    
    def test_find_contours(self):
        """Test contour detection."""
        gray = self.processor.convert_to_gray(self.test_image)
        binary = self.processor.threshold_global(gray, 127)
        contours = self.processor.find_contours(binary)
        
        # Should find 2 rectangles
        self.assertEqual(len(contours), 2)
        
        for contour in contours:
            self.assertGreater(len(contour), 0)
    
    def test_contour_properties(self):
        """Test contour property calculations."""
        gray = self.processor.convert_to_gray(self.test_image)
        binary = self.processor.threshold_global(gray, 127)
        contours = self.processor.find_contours(binary)
        
        for contour in contours:
            # Test bounding box
            bbox = self.processor.contour_to_bbox(contour)
            self.assertEqual(len(bbox), 4)
            x, y, w, h = bbox
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)
            
            # Test area
            area = self.processor.contour_area(contour)
            self.assertGreater(area, 0)
            
            # Test center
            center = self.processor.contour_center(contour)
            self.assertEqual(len(center), 2)
            cx, cy = center
            self.assertGreaterEqual(cx, 0)
            self.assertGreaterEqual(cy, 0)
            
            # Test polygon simplification
            polygon = self.processor.simplify_polygon(contour)
            self.assertGreater(len(polygon), 2)  # At least 3 points for a polygon
    
    def test_filter_blobs_by_area(self):
        """Test blob filtering by area."""
        gray = self.processor.convert_to_gray(self.test_image)
        binary = self.processor.threshold_global(gray, 127)
        contours = self.processor.find_contours(binary)
        
        # Filter with very restrictive area (should remove all)
        filtered = self.processor.filter_blobs_by_area(contours, 10000, 20000)
        self.assertEqual(len(filtered), 0)
        
        # Filter with permissive area (should keep all)
        filtered = self.processor.filter_blobs_by_area(contours, 100, 5000)
        self.assertEqual(len(filtered), 2)
    
    def test_process_image_complete(self):
        """Test complete image processing pipeline."""
        threshold_config = {
            'mode': 'global',
            'value': 127,
            'blur': 3,
            'channel': 'gray'
        }
        
        morph_config = {
            'open': 0,
            'close': 0
        }
        
        blob_config = {
            'min_area': 100,
            'max_area': 5000,
            'track_ids': True
        }
        
        binary, blobs = self.processor.process_image(
            self.test_image, threshold_config, morph_config, blob_config
        )
        
        # Check binary image
        self.assertEqual(len(binary.shape), 2)
        self.assertEqual(binary.shape[:2], self.test_image.shape[:2])
        
        # Check blobs
        self.assertEqual(len(blobs), 2)
        
        for blob in blobs:
            self.assertIsInstance(blob, BlobInfo)
            self.assertGreaterEqual(blob.id, 0)
            self.assertGreater(blob.area, 0)
            self.assertEqual(len(blob.center), 2)
            self.assertEqual(len(blob.bbox), 4)
            self.assertGreater(len(blob.polygon), 2)


class TestBlobTracker(unittest.TestCase):
    """Test cases for BlobTracker."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tracker = BlobTracker(max_distance=50.0, max_age=3)
    
    def test_single_detection(self):
        """Test tracking a single detection."""
        detections = [(100, 100, 1000)]  # cx, cy, area
        tracks = self.tracker.update(detections)
        
        self.assertEqual(len(tracks), 1)
        self.assertIn(0, tracks)  # First ID should be 0
        self.assertEqual(tracks[0], (100, 100))
    
    def test_multiple_detections(self):
        """Test tracking multiple detections."""
        detections = [(100, 100, 1000), (200, 200, 1500)]
        tracks = self.tracker.update(detections)
        
        self.assertEqual(len(tracks), 2)
        self.assertIn(0, tracks)
        self.assertIn(1, tracks)
    
    def test_tracking_consistency(self):
        """Test that tracks remain consistent across frames."""
        # Frame 1
        detections1 = [(100, 100, 1000), (200, 200, 1500)]
        tracks1 = self.tracker.update(detections1)
        
        # Frame 2 - slightly moved
        detections2 = [(105, 105, 1000), (195, 195, 1500)]
        tracks2 = self.tracker.update(detections2)
        
        # Should maintain same IDs
        self.assertEqual(set(tracks1.keys()), set(tracks2.keys()))
    
    def test_track_loss(self):
        """Test track loss when detections disappear."""
        # Frame 1
        detections1 = [(100, 100, 1000)]
        tracks1 = self.tracker.update(detections1)
        self.assertEqual(len(tracks1), 1)
        
        # Several frames with no detections
        for _ in range(5):
            tracks = self.tracker.update([])
        
        # Track should be lost
        self.assertEqual(len(tracks), 0)
    
    def test_new_detection_after_loss(self):
        """Test new detection gets new ID after track loss."""
        # Frame 1
        detections1 = [(100, 100, 1000)]
        tracks1 = self.tracker.update(detections1)
        first_id = list(tracks1.keys())[0]
        
        # Lose track
        for _ in range(5):
            self.tracker.update([])
        
        # New detection
        detections2 = [(100, 100, 1000)]
        tracks2 = self.tracker.update(detections2)
        second_id = list(tracks2.keys())[0]
        
        # Should get new ID
        self.assertNotEqual(first_id, second_id)
    
    def test_reset(self):
        """Test tracker reset."""
        detections = [(100, 100, 1000), (200, 200, 1500)]
        self.tracker.update(detections)
        
        self.tracker.reset()
        
        # Should have no active tracks
        tracks = self.tracker.update([])
        self.assertEqual(len(tracks), 0)
        
        # Next ID should reset
        new_tracks = self.tracker.update(detections)
        self.assertIn(0, new_tracks)


if __name__ == '__main__':
    unittest.main()
