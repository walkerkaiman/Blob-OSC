"""Web-based Flask application for Blob OSC."""

import os
import json
import base64
import logging
import threading
import time
from io import BytesIO
from typing import Dict, Any, Optional, List
from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit
import cv2
import numpy as np
from PIL import Image

from .cameras import CameraManager, CameraInfo
from .simple_roi import SimpleROI
from .processor import ImageProcessor, BlobInfo
from .osc_client import OSCClient
from .settings_manager import SettingsManager, AppConfig


class WebBlobApp:
    """Main web application class."""
    
    def __init__(self, config_path: str = "config.json"):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'blob_osc_secret_key'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Core components
        self.camera_manager = CameraManager()
        self.roi_manager = SimpleROI()
        self.processor = ImageProcessor()
        self.osc_client: Optional[OSCClient] = None
        self.settings_manager = SettingsManager()
        
        # Processing state
        self.processing_enabled = True
        self.current_frame = None
        self.current_roi_frame = None
        self.current_binary = None
        self.current_blobs: List[BlobInfo] = []
        self.cameras: List[CameraInfo] = []
        
        # Performance settings
        self.target_fps = 5.0  # Default 5 FPS for Pi
        self.last_frame_time = 0
        self.frame_interval = 1.0 / self.target_fps
        
        # OSC rate limiting
        self.last_osc_send_time = 0.0
        self.osc_send_interval = 1.0 / 30.0  # 30 FPS for OSC
        
        # Processing thread
        self.processing_thread: Optional[threading.Thread] = None
        self.running = False
        
        self.logger = logging.getLogger(__name__)
        
        # Setup routes and socket handlers
        self._setup_routes()
        self._setup_socket_handlers()
    
    def _setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            """Main page."""
            return render_template('index.html')
        
        @self.app.route('/api/config', methods=['GET'])
        def get_config():
            """Get current configuration."""
            try:
                config_dict = {
                    'camera': {
                        'friendly_name': self.settings_manager.config.camera.friendly_name,
                        'resolution': self.settings_manager.config.camera.resolution
                    },
                    'roi': {
                        'x': self.settings_manager.config.roi.x,
                        'y': self.settings_manager.config.roi.y,
                        'w': self.settings_manager.config.roi.w,
                        'h': self.settings_manager.config.roi.h,
                        'locked': self.settings_manager.config.roi.locked,
                        'left_crop': self.settings_manager.config.roi.left_crop,
                        'top_crop': self.settings_manager.config.roi.top_crop,
                        'right_crop': self.settings_manager.config.roi.right_crop,
                        'bottom_crop': self.settings_manager.config.roi.bottom_crop
                    },
                    'threshold': {
                        'mode': self.settings_manager.config.threshold.mode,
                        'channel': self.settings_manager.config.threshold.channel,
                        'value': self.settings_manager.config.threshold.value,
                        'blur': self.settings_manager.config.threshold.blur,
                        'invert': self.settings_manager.config.threshold.invert
                    },
                    'morph': {
                        'open': self.settings_manager.config.morph.open,
                        'close': self.settings_manager.config.morph.close
                    },
                    'blob': {
                        'min_area': self.settings_manager.config.blob.min_area,
                        'max_area': self.settings_manager.config.blob.max_area,
                        'track_ids': self.settings_manager.config.blob.track_ids,
                        'use_bytetrack': self.settings_manager.config.blob.use_bytetrack
                    },
                    'bytetrack': {
                        'track_thresh': self.settings_manager.config.bytetrack.track_thresh,
                        'track_buffer': self.settings_manager.config.bytetrack.track_buffer
                    },
                    'osc': {
                        'ip': self.settings_manager.config.osc.ip,
                        'port': self.settings_manager.config.osc.port,
                        'protocol': self.settings_manager.config.osc.protocol,
                        'normalize_coords': self.settings_manager.config.osc.normalize_coords,
                        'send_on_detect': self.settings_manager.config.osc.send_on_detect,
                        'send_center': self.settings_manager.config.osc.send_center,
                        'send_position': self.settings_manager.config.osc.send_position,
                        'send_size': self.settings_manager.config.osc.send_size,
                        'send_area': self.settings_manager.config.osc.send_area,
                        'send_polygon': self.settings_manager.config.osc.send_polygon,
                        'mappings': self.settings_manager.config.osc.mappings
                    },
                    'performance': {
                        'target_fps': self.target_fps
                    }
                }
                return jsonify(config_dict)
            except Exception as e:
                self.logger.error(f"Error getting config: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/config', methods=['POST'])
        def update_config():
            """Update configuration."""
            try:
                data = request.json
                
                # Update camera config
                if 'camera' in data:
                    cam_data = data['camera']
                    self.settings_manager.update_camera_config(**cam_data)
                
                # Update ROI config
                if 'roi' in data:
                    roi_data = data['roi']
                    self.settings_manager.update_roi_config(**roi_data)
                
                # Update threshold config
                if 'threshold' in data:
                    thresh_data = data['threshold']
                    self.settings_manager.update_threshold_config(**thresh_data)
                
                # Update morph config
                if 'morph' in data:
                    morph_data = data['morph']
                    self.settings_manager.update_morph_config(**morph_data)
                
                # Update blob config
                if 'blob' in data:
                    blob_data = data['blob']
                    self.settings_manager.update_blob_config(**blob_data)
                
                # Update ByteTrack config
                if 'bytetrack' in data:
                    bytetrack_data = data['bytetrack']
                    self.settings_manager.update_bytetrack_config(**bytetrack_data)
                
                # Update OSC config
                if 'osc' in data:
                    osc_data = data['osc']
                    self.settings_manager.update_osc_config(**osc_data)
                
                # Update performance settings
                if 'performance' in data:
                    perf_data = data['performance']
                    if 'target_fps' in perf_data:
                        self.target_fps = perf_data['target_fps']
                        self.frame_interval = 1.0 / self.target_fps
                        self.settings_manager.config.performance = perf_data
                
                return jsonify({'status': 'success'})
            except Exception as e:
                self.logger.error(f"Error updating config: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cameras', methods=['GET'])
        def get_cameras():
            """Get available cameras."""
            try:
                self.cameras = self.camera_manager.list_cameras()
                cameras_data = []
                for camera in self.cameras:
                    cameras_data.append({
                        'id': camera.id,
                        'name': camera.friendly_name,
                        'backend_id': camera.backend_id
                    })
                return jsonify(cameras_data)
            except Exception as e:
                self.logger.error(f"Error getting cameras: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/camera/<int:camera_id>', methods=['POST'])
        def select_camera(camera_id):
            """Select a camera."""
            try:
                if self.camera_manager.open_camera(camera_id):
                    self.camera_manager.start_capture()
                    
                    # Update settings
                    camera = next((c for c in self.cameras if c.id == camera_id), None)
                    if camera:
                        self.settings_manager.update_camera_config(
                            friendly_name=camera.friendly_name,
                            backend_id=camera.backend_id
                        )
                    
                    return jsonify({'status': 'success'})
                else:
                    return jsonify({'error': 'Failed to open camera'}), 500
            except Exception as e:
                self.logger.error(f"Error selecting camera: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/camera/resolution', methods=['POST'])
        def set_resolution():
            """Set camera resolution."""
            try:
                data = request.json
                width = data.get('width')
                height = data.get('height')
                
                if width and height:
                    if self.camera_manager.set_resolution(width, height):
                        self.settings_manager.update_camera_config(resolution=[width, height])
                        return jsonify({'status': 'success'})
                    else:
                        return jsonify({'error': 'Failed to set resolution'}), 500
                else:
                    return jsonify({'error': 'Missing width or height'}), 400
            except Exception as e:
                self.logger.error(f"Error setting resolution: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/osc/connect', methods=['POST'])
        def connect_osc():
            """Connect to OSC destination."""
            try:
                data = request.json
                ip = data.get('ip', '127.0.0.1')
                port = data.get('port', 8000)
                protocol = data.get('protocol', 'udp')
                
                if self.osc_client:
                    self.osc_client.close()
                
                self.osc_client = OSCClient(ip, port, protocol, async_mode=False)
                
                if self.osc_client.test_connection():
                    self.settings_manager.update_osc_config(ip=ip, port=port, protocol=protocol)
                    return jsonify({'status': 'connected'})
                else:
                    return jsonify({'error': 'Failed to connect'}), 500
            except Exception as e:
                self.logger.error(f"Error connecting OSC: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/osc/disconnect', methods=['POST'])
        def disconnect_osc():
            """Disconnect from OSC."""
            try:
                if self.osc_client:
                    self.osc_client.close()
                    self.osc_client = None
                return jsonify({'status': 'disconnected'})
            except Exception as e:
                self.logger.error(f"Error disconnecting OSC: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/osc/test', methods=['POST'])
        def test_osc():
            """Send test OSC message."""
            try:
                if self.osc_client:
                    self.osc_client.send_test_message()
                    return jsonify({'status': 'test_sent'})
                else:
                    return jsonify({'error': 'OSC not connected'}), 400
            except Exception as e:
                self.logger.error(f"Error testing OSC: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/processing/pause', methods=['POST'])
        def pause_processing():
            """Pause/resume processing."""
            try:
                data = request.json
                self.processing_enabled = not data.get('paused', False)
                return jsonify({'status': 'paused' if not self.processing_enabled else 'resumed'})
            except Exception as e:
                self.logger.error(f"Error pausing processing: {e}")
                return jsonify({'error': str(e)}), 500
    
    def _setup_socket_handlers(self):
        """Setup SocketIO event handlers."""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            self.logger.info('Client connected')
            emit('status', {'message': 'Connected to Blob OSC'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            self.logger.info('Client disconnected')
        
        @self.socketio.on('request_frame')
        def handle_frame_request():
            """Handle frame request from client."""
            if self.current_frame is not None:
                # Convert frame to base64
                frame_data = self._frame_to_base64(self.current_frame)
                emit('frame_data', {'image': frame_data})
        
        @self.socketio.on('request_binary')
        def handle_binary_request():
            """Handle binary frame request from client."""
            if self.current_binary is not None:
                binary_data = self._frame_to_base64(self.current_binary)
                emit('binary_data', {'image': binary_data})
        
        @self.socketio.on('request_overlay')
        def handle_overlay_request():
            """Handle overlay frame request from client."""
            if self.current_roi_frame is not None and self.current_blobs:
                overlay_image = self.processor.draw_blob_overlay(self.current_roi_frame, self.current_blobs)
                overlay_data = self._frame_to_base64(overlay_image)
                emit('overlay_data', {'image': overlay_data})
    
    def _frame_to_base64(self, frame: np.ndarray) -> str:
        """Convert OpenCV frame to base64 string."""
        try:
            # Convert BGR to RGB
            if len(frame.shape) == 3:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = frame
            
            # Convert to PIL Image
            pil_image = Image.fromarray(frame_rgb)
            
            # Convert to base64
            buffer = BytesIO()
            pil_image.save(buffer, format='JPEG', quality=85)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
        except Exception as e:
            self.logger.error(f"Error converting frame to base64: {e}")
            return ""
    
    def _processing_loop(self):
        """Main processing loop running in separate thread."""
        while self.running:
            if not self.processing_enabled or not self.camera_manager.is_opened():
                time.sleep(0.1)
                continue
            
            current_time = time.time()
            
            # FPS limiting
            if current_time - self.last_frame_time < self.frame_interval:
                time.sleep(0.01)
                continue
            
            # Get frame from camera
            frame = self.camera_manager.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            
            try:
                # Apply ROI
                roi_frame = self.roi_manager.apply_crop(frame) if self.roi_manager else frame
                if roi_frame is None:
                    continue
                
                # Process image
                threshold_config = self.settings_manager.get_threshold_config()
                morph_config = self.settings_manager.get_morph_config()
                blob_config = self.settings_manager.get_blob_config()
                
                binary_frame, blobs = self.processor.process_image(
                    roi_frame,
                    threshold_config.__dict__,
                    morph_config.__dict__,
                    blob_config.__dict__
                )
                
                # Update current frames
                self.current_frame = frame
                self.current_roi_frame = roi_frame
                self.current_binary = binary_frame
                self.current_blobs = blobs
                
                # Send OSC data if enabled
                if (self.settings_manager.config.osc.send_on_detect and 
                    self.osc_client and blobs and frame is not None):
                    self._send_blob_data_rate_limited()
                
                # Emit frame data to connected clients
                frame_data = self._frame_to_base64(frame)
                binary_data = self._frame_to_base64(binary_frame)
                
                if blobs:
                    overlay_image = self.processor.draw_blob_overlay(roi_frame, blobs)
                    overlay_data = self._frame_to_base64(overlay_image)
                else:
                    overlay_data = binary_data
                
                self.socketio.emit('frames_update', {
                    'frame': frame_data,
                    'binary': binary_data,
                    'overlay': overlay_data,
                    'blobs': [{'id': b.id, 'center': b.center, 'area': b.area} for b in blobs]
                })
                
                self.last_frame_time = current_time
                
            except Exception as e:
                self.logger.error(f"Processing error: {e}")
            
            time.sleep(0.01)
    
    def _send_blob_data_rate_limited(self):
        """Send blob data with rate limiting."""
        current_time = time.time()
        
        if current_time - self.last_osc_send_time >= self.osc_send_interval:
            try:
                # Get ROI dimensions for normalization
                x, y, roi_width, roi_height = self.roi_manager.get_roi_bounds()
                
                # Get mappings and enabled fields
                mappings = self.settings_manager.config.osc.mappings
                enabled_fields = {
                    'center': self.settings_manager.config.osc.send_center,
                    'position': self.settings_manager.config.osc.send_position,
                    'size': self.settings_manager.config.osc.send_size,
                    'area': self.settings_manager.config.osc.send_area,
                    'polygon': self.settings_manager.config.osc.send_polygon
                }
                
                # Send data for all blobs
                self.osc_client.send_multiple_blobs(
                    self.current_blobs,
                    mappings,
                    roi_width,
                    roi_height,
                    self.settings_manager.config.osc.normalize_coords,
                    enabled_fields
                )
                
                self.last_osc_send_time = current_time
                
            except Exception as e:
                self.logger.error(f"OSC send error: {e}")
    
    def start(self, host='0.0.0.0', port=5000, debug=False):
        """Start the web application."""
        try:
            # Load settings
            self.settings_manager.load_config()
            
            # Load performance settings
            if hasattr(self.settings_manager.config, 'performance'):
                perf_config = self.settings_manager.config.performance
                if hasattr(perf_config, 'target_fps'):
                    self.target_fps = perf_config.target_fps
                    self.frame_interval = 1.0 / self.target_fps
            
            # Initialize ByteTrack if available
            bytetrack_config = self.settings_manager.get_bytetrack_config()
            blob_config = self.settings_manager.get_blob_config()
            
            if blob_config.use_bytetrack:
                success = self.processor.initialize_bytetrack(
                    track_thresh=bytetrack_config.track_thresh,
                    track_buffer=bytetrack_config.track_buffer,
                    match_thresh=bytetrack_config.match_thresh,
                    min_box_area=bytetrack_config.min_box_area
                )
                if success:
                    self.processor.set_tracking_mode(True)
                    self.logger.info("ByteTrack initialized")
                else:
                    self.logger.warning("ByteTrack failed to initialize, using simple tracking")
            
            # Start processing thread
            self.running = True
            self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
            self.processing_thread.start()
            
            # Start web server
            self.logger.info(f"Starting Blob OSC web server on {host}:{port}")
            self.socketio.run(self.app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
            
        except KeyboardInterrupt:
            self.logger.info("Application interrupted by user")
        except Exception as e:
            self.logger.error(f"Application error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the application."""
        self.running = False
        
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
        
        self.camera_manager.close_camera()
        
        if self.osc_client:
            self.osc_client.close()
        
        self.settings_manager.save_config()
        self.logger.info("Application stopped")


def create_app(config_path: str = "config.json") -> WebBlobApp:
    """Create and return a WebBlobApp instance."""
    return WebBlobApp(config_path)


if __name__ == "__main__":
    app = create_app()
    app.start()
