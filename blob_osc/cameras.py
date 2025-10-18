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

# Raspberry Pi Camera Module support
try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    PICAMERA_AVAILABLE = False


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
        self.picam: Optional[Picamera2] = None  # Raspberry Pi Camera Module
        self.current_camera_id: Optional[int] = None
        self.current_camera_type: str = "usb"  # "usb" or "picam"
        self.frame_queue: Queue = Queue(maxsize=2)
        self.capture_thread: Optional[threading.Thread] = None
        self.capture_running = False
        self.fps = 30.0
        self.frame_count = 0
        self.dropped_frames = 0
        
    def list_cameras(self) -> List[CameraInfo]:
        """Enumerate available cameras with friendly names."""
        cameras = []
        
        # Check for Raspberry Pi Camera Module first (Linux only)
        if platform.system() == "Linux" and PICAMERA_AVAILABLE:
            try:
                # Try to initialize Pi Camera to check if it's available
                test_picam = Picamera2()
                camera_info = test_picam.camera_properties
                test_picam.close()
                
                # Add Pi Camera Module as camera 0
                cameras.append(CameraInfo(0, "Raspberry Pi Camera Module", "picam"))
                self.logger.info("Found Raspberry Pi Camera Module")
            except Exception as e:
                self.logger.debug(f"Pi Camera Module not available: {e}")
        
        # For Windows, try pygrabber first for accurate device names
        if platform.system() == "Windows":
            try:
                from pygrabber.dshow_graph import FilterGraph
                
                # Get actual device names from DirectShow
                graph = FilterGraph()
                devices = graph.get_input_devices()
                
                # Find video devices
                video_devices = []
                for device_name in devices:
                    device_lower = device_name.lower()
                    if any(keyword in device_lower for keyword in ['camera', 'webcam', 'video', 'capture', 'cam']):
                        video_devices.append(device_name)
                
                # Create camera info for each video device found
                # Don't test frame reading here as it might fail due to permissions/usage
                for i, device_name in enumerate(video_devices):
                    backend_id = f"camera://{i}"
                    cameras.append(CameraInfo(i, device_name, backend_id))
                
                if cameras:
                    self.logger.info(f"Found {len(cameras)} cameras using pygrabber")
                    return cameras
                    
            except ImportError:
                self.logger.debug("pygrabber not available, using OpenCV enumeration")
            except Exception as e:
                self.logger.debug(f"pygrabber enumeration failed: {e}")
        
        # Fallback: Standard OpenCV enumeration for all platforms
        for i in range(10):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    # Try to read a frame to confirm the camera works
                    ret, _ = cap.read()
                    if ret:
                        friendly_name = self._get_camera_friendly_name(i)
                        backend_id = f"camera://{i}"
                        cameras.append(CameraInfo(i, friendly_name, backend_id))
                    cap.release()
            except Exception as e:
                self.logger.debug(f"Failed to test camera {i}: {e}")
        
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
        """Get Windows camera friendly name using accurate device enumeration."""
        # Method 1: Use pygrabber for accurate DirectShow device enumeration
        try:
            from pygrabber.dshow_graph import FilterGraph
            
            # Create filter graph to enumerate video input devices
            graph = FilterGraph()
            devices = graph.get_input_devices()
            
            # Find devices that contain video/camera keywords
            video_devices = []
            for device_name in devices:
                device_lower = device_name.lower()
                if any(keyword in device_lower for keyword in ['camera', 'webcam', 'video', 'capture', 'cam']):
                    video_devices.append(device_name)
            
            # Return the device name if we have one for this camera_id
            if camera_id < len(video_devices):
                device_name = video_devices[camera_id]
                # Clean up common generic names
                if device_name == "USB Video Device":
                    return f"USB Camera #{camera_id}"
                elif "Integrated" in device_name:
                    return device_name.replace("Integrated", "Built-in")
                else:
                    return device_name
                    
        except ImportError:
            self.logger.debug("pygrabber not available, using fallback detection")
        except Exception as e:
            self.logger.debug(f"pygrabber device enumeration failed: {e}")
        
        # Method 2: Try Windows Registry approach for device names
        try:
            import winreg
            
            # Look in Windows Registry for video devices
            registry_path = r"SYSTEM\CurrentControlSet\Control\DeviceClasses\{65e8773d-8f56-11d0-a3b9-00a0c9223196}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                device_count = 0
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        if "video" in subkey_name.lower():
                            if device_count == camera_id:
                                # Try to extract meaningful name from registry path
                                if "usb" in subkey_name.lower():
                                    return f"USB Camera #{camera_id}"
                                else:
                                    return f"Video Device #{camera_id}"
                            device_count += 1
                        i += 1
                    except WindowsError:
                        break
        except ImportError:
            pass  # winreg not available (not Windows)
        except Exception as e:
            self.logger.debug(f"Registry camera lookup failed: {e}")
        
        # Method 3: Enhanced WMI with better parsing
        try:
            import subprocess
            result = subprocess.run([
                'wmic', 'path', 'Win32_PnPEntity', 'where', 
                '"Name like \'%camera%\' or Name like \'%webcam%\' or Name like \'%video%\' or PNPClass=\'Camera\'"',
                'get', 'Name,Description', '/format:csv'
            ], capture_output=True, text=True, timeout=3, shell=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                device_entries = []
                
                for line in lines[1:]:  # Skip header
                    if ',' in line and line.strip():
                        parts = line.split(',')
                        if len(parts) >= 2:
                            description = parts[0].strip()
                            name = parts[1].strip()
                            # Use the more descriptive field
                            device_name = name if name and len(name) > len(description) else description
                            if device_name and len(device_name) > 3:
                                device_entries.append(device_name)
                
                if camera_id < len(device_entries):
                    device_name = device_entries[camera_id]
                    # Clean up the name
                    device_name = device_name.replace('USB Video Device', 'USB Webcam')
                    device_name = device_name.replace('Integrated Camera', 'Integrated Webcam')
                    return device_name
                    
        except Exception as e:
            self.logger.debug(f"Enhanced WMI lookup failed: {e}")
        
        # Method 4: Fallback with camera properties
        try:
            cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                
                # Create descriptive name based on resolution
                if width >= 1920:
                    return f"HD Camera #{camera_id} (1080p+)"
                elif width >= 1280:
                    return f"HD Camera #{camera_id} (720p)"
                else:
                    return f"Standard Camera #{camera_id} ({width}x{height})"
        except Exception:
            pass
        
        return f"Camera {camera_id}"
    
    def _get_macos_camera_name(self, camera_id: int) -> str:
        """Get macOS camera friendly name."""
        try:
            # Try to get camera properties for better identification
            cap = cv2.VideoCapture(camera_id)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                
                # macOS built-in cameras
                if camera_id == 0:
                    if width >= 1920:
                        return "FaceTime HD Camera (1080p)"
                    elif width >= 1280:
                        return "FaceTime HD Camera (720p)"
                    else:
                        return "FaceTime Camera"
                else:
                    return f"External Camera {camera_id} ({width}x{height})"
        except Exception:
            pass
        
        # Fallback names
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
                    if name and name != f"video{camera_id}":
                        # Clean up common generic names
                        if 'USB' in name and 'Camera' not in name:
                            return f"{name} (USB Camera)"
                        elif 'UVC' in name:
                            return name.replace('UVC', 'USB')
                        return name
        except Exception:
            pass
        
        # Try v4l2-ctl if available
        try:
            import subprocess
            result = subprocess.run([
                'v4l2-ctl', '--list-devices'
            ], capture_output=True, text=True, timeout=2)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                device_count = 0
                for i, line in enumerate(lines):
                    if line.strip() and not line.startswith('\t') and not line.startswith(' '):
                        if device_count == camera_id:
                            device_name = line.strip().rstrip(':')
                            if device_name and 'video' not in device_name.lower():
                                return device_name
                        device_count += 1
        except Exception:
            pass
        
        return f"Camera {camera_id}"
    
    def open_camera(self, camera_id: int) -> bool:
        """Open a camera for capture."""
        if self.cap is not None or self.picam is not None:
            self.close_camera()
        
        try:
            # Check if this is a Pi Camera Module
            if (camera_id == 0 and platform.system() == "Linux" and PICAMERA_AVAILABLE and
                len([c for c in self.list_cameras() if c.backend_id == "picam"]) > 0):
                
                try:
                    self.picam = Picamera2()
                    
                    # Configure camera with reasonable defaults for blob detection
                    camera_config = self.picam.create_video_configuration(
                        main={"size": (1280, 720), "format": "RGB888"},
                        buffer_count=2
                    )
                    self.picam.configure(camera_config)
                    self.picam.start()
                    
                    # Test if we can read frames
                    test_frame = self.picam.capture_array()
                    if test_frame is not None and test_frame.size > 0:
                        self.current_camera_id = camera_id
                        self.current_camera_type = "picam"
                        self.logger.info(f"Opened Raspberry Pi Camera Module")
                        return True
                    else:
                        self.picam.close()
                        self.picam = None
                        
                except Exception as e:
                    self.logger.error(f"Failed to open Pi Camera Module: {e}")
                    if self.picam:
                        self.picam.close()
                        self.picam = None
                    return False
            
            # Try USB cameras with different backends
            backends = [cv2.CAP_DSHOW, cv2.CAP_V4L2, cv2.CAP_ANY]
            
            for backend in backends:
                self.cap = cv2.VideoCapture(camera_id, backend)
                if self.cap.isOpened():
                    # Test if we can actually read frames
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        self.current_camera_id = camera_id
                        self.current_camera_type = "usb"
                        self.logger.info(f"Opened USB camera {camera_id} with backend {backend}")
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
            if self.picam:
                self.picam.close()
                self.picam = None
            return False
    
    def close_camera(self) -> None:
        """Close the current camera."""
        self.stop_capture()
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.picam:
            self.picam.close()
            self.picam = None
        self.current_camera_id = None
        self.current_camera_type = "usb"
        self.logger.info("Camera closed")
    
    def set_resolution(self, width: int, height: int) -> bool:
        """Set camera resolution."""
        try:
            if self.current_camera_type == "picam" and self.picam:
                # For Pi Camera Module, reconfigure the camera
                camera_config = self.picam.create_video_configuration(
                    main={"size": (width, height), "format": "RGB888"},
                    buffer_count=2
                )
                self.picam.stop()
                self.picam.configure(camera_config)
                self.picam.start()
                self.logger.info(f"Set Pi Camera resolution to {width}x{height}")
                return True
                
            elif self.cap and self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                
                # Verify the resolution was set
                actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                self.logger.info(f"Set USB camera resolution to {actual_width}x{actual_height} (requested: {width}x{height})")
                return True
            else:
                return False
            
        except Exception as e:
            self.logger.error(f"Failed to set resolution: {e}")
            return False
    
    def get_resolution(self) -> Tuple[int, int]:
        """Get current camera resolution."""
        try:
            if self.current_camera_type == "picam" and self.picam:
                # Get resolution from Pi Camera configuration
                config = self.picam.camera_config
                if 'main' in config and 'size' in config['main']:
                    size = config['main']['size']
                    return (size[0], size[1])
                return (1280, 720)  # Default for Pi Camera
                
            elif self.cap and self.cap.isOpened():
                width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                return (width, height)
            else:
                return (0, 0)
        except Exception as e:
            self.logger.error(f"Failed to get resolution: {e}")
            return (0, 0)
    
    def start_capture(self) -> bool:
        """Start continuous frame capture in a separate thread."""
        if not ((self.cap and self.cap.isOpened()) or (self.picam)):
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
        
        while self.capture_running:
            try:
                frame = None
                
                if self.current_camera_type == "picam" and self.picam:
                    # Capture from Pi Camera Module
                    try:
                        frame = self.picam.capture_array()
                        if frame is not None:
                            # Convert RGB to BGR for OpenCV compatibility
                            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    except Exception as e:
                        self.logger.warning(f"Failed to read frame from Pi Camera: {e}")
                        time.sleep(0.01)
                        continue
                        
                elif self.cap and self.cap.isOpened():
                    # Capture from USB camera
                    ret, frame = self.cap.read()
                    if not ret or frame is None:
                        self.logger.warning("Failed to read frame from USB camera")
                        time.sleep(0.01)
                        continue
                
                if frame is None:
                    time.sleep(0.01)
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
        return (self.cap is not None and self.cap.isOpened()) or (self.picam is not None)
    
    def __del__(self):
        """Cleanup on destruction."""
        self.close_camera()
