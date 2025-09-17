"""OSC client for sending blob data over UDP/TCP."""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Tuple, Callable
from pythonosc import udp_client, tcp_client
from pythonosc.osc_message_builder import OscMessageBuilder
from .processor import BlobInfo


class OSCClient:
    """OSC client wrapper for sending blob data."""
    
    def __init__(self, ip: str = "127.0.0.1", port: int = 8000, protocol: str = "udp"):
        self.ip = ip
        self.port = port
        self.protocol = protocol.lower()
        self.client = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.logger = logging.getLogger(__name__)
        self.message_log: List[Dict[str, Any]] = []
        self.max_log_size = 1000
        self.stats = {
            'messages_sent': 0,
            'messages_failed': 0,
            'last_send_time': 0,
            'connection_status': 'disconnected'
        }
        
        # Callbacks
        self.on_message_sent: Optional[Callable[[str, List[Any]], None]] = None
        self.on_send_error: Optional[Callable[[str, Exception], None]] = None
        
        self._connect()
    
    def _connect(self) -> bool:
        """Connect to OSC destination."""
        try:
            if self.protocol == "tcp":
                self.client = tcp_client.TcpClient(self.ip, self.port)
            else:  # UDP
                self.client = udp_client.SimpleUDPClient(self.ip, self.port)
            
            self.stats['connection_status'] = 'connected'
            self.logger.info(f"Connected to OSC {self.protocol.upper()} {self.ip}:{self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to OSC: {e}")
            self.stats['connection_status'] = 'error'
            return False
    
    def update_connection(self, ip: str, port: int, protocol: str) -> bool:
        """Update connection parameters."""
        if self.ip == ip and self.port == port and self.protocol == protocol.lower():
            return True  # No change needed
        
        self.ip = ip
        self.port = port
        self.protocol = protocol.lower()
        
        # Reconnect with new parameters
        return self._connect()
    
    def send_message(self, address: str, *args) -> None:
        """Send an OSC message (non-blocking)."""
        if not self.client:
            self.logger.warning("OSC client not connected")
            return
        
        # Submit to thread pool for non-blocking send
        future = self.executor.submit(self._send_message_sync, address, args)
        future.add_done_callback(self._handle_send_result)
    
    def _send_message_sync(self, address: str, args: tuple) -> Dict[str, Any]:
        """Send OSC message synchronously."""
        try:
            start_time = time.time()
            
            if self.client:
                self.client.send_message(address, args)
            
            send_time = time.time() - start_time
            
            # Log the message
            log_entry = {
                'timestamp': time.time(),
                'address': address,
                'args': list(args),
                'send_time': send_time,
                'status': 'success'
            }
            
            self._add_to_log(log_entry)
            self.stats['messages_sent'] += 1
            self.stats['last_send_time'] = send_time
            
            return log_entry
            
        except Exception as e:
            log_entry = {
                'timestamp': time.time(),
                'address': address,
                'args': list(args),
                'error': str(e),
                'status': 'error'
            }
            
            self._add_to_log(log_entry)
            self.stats['messages_failed'] += 1
            self.logger.error(f"Failed to send OSC message to {address}: {e}")
            
            raise e
    
    def _handle_send_result(self, future) -> None:
        """Handle the result of an async send operation."""
        try:
            result = future.result()
            if self.on_message_sent:
                self.on_message_sent(result['address'], result['args'])
        except Exception as e:
            if self.on_send_error:
                self.on_send_error("", e)
    
    def _add_to_log(self, entry: Dict[str, Any]) -> None:
        """Add entry to message log."""
        self.message_log.append(entry)
        
        # Trim log if too large
        if len(self.message_log) > self.max_log_size:
            self.message_log = self.message_log[-self.max_log_size//2:]
    
    def send_blob_data(self, blob: BlobInfo, mappings: Dict[str, str], 
                      roi_width: int, roi_height: int, normalize_coords: bool = True,
                      enabled_fields: Dict[str, bool] = None) -> None:
        """
        Send blob data using configured mappings.
        
        Args:
            blob: BlobInfo object
            mappings: Dictionary mapping field names to OSC address patterns
            roi_width: Width of ROI for normalization
            roi_height: Height of ROI for normalization
            normalize_coords: Whether to normalize coordinates (0-1)
            enabled_fields: Dictionary of which fields to send
        """
        if enabled_fields is None:
            enabled_fields = {
                'center': True,
                'position': True,
                'size': True,
                'area': True,
                'polygon': False
            }
        
        # Prepare format variables
        format_vars = {
            'id': blob.id,
            'i': blob.id,
            'time': int(time.time()),
            'cx': blob.center[0],
            'cy': blob.center[1],
            'x': blob.bbox[0],
            'y': blob.bbox[1],
            'w': blob.bbox[2],
            'h': blob.bbox[3],
            'area': int(blob.area)
        }
        
        # Send center coordinates
        if enabled_fields.get('center', False) and 'center' in mappings:
            address = mappings['center'].format(**format_vars)
            if normalize_coords:
                cx_norm, cy_norm = blob.get_center_normalized(roi_width, roi_height)
                self.send_message(address, cx_norm, cy_norm)
            else:
                self.send_message(address, blob.center[0], blob.center[1])
        
        # Send position (top-left of bounding box)
        if enabled_fields.get('position', False) and 'position' in mappings:
            address = mappings['position'].format(**format_vars)
            if normalize_coords:
                x_norm = blob.bbox[0] / roi_width
                y_norm = blob.bbox[1] / roi_height
                self.send_message(address, x_norm, y_norm)
            else:
                self.send_message(address, blob.bbox[0], blob.bbox[1])
        
        # Send size
        if enabled_fields.get('size', False) and 'size' in mappings:
            address = mappings['size'].format(**format_vars)
            if normalize_coords:
                w_norm = blob.bbox[2] / roi_width
                h_norm = blob.bbox[3] / roi_height
                self.send_message(address, w_norm, h_norm)
            else:
                self.send_message(address, blob.bbox[2], blob.bbox[3])
        
        # Send area
        if enabled_fields.get('area', False) and 'area' in mappings:
            address = mappings['area'].format(**format_vars)
            area_value = blob.area
            if normalize_coords:
                # Normalize area by ROI area
                area_value = blob.area / (roi_width * roi_height)
            self.send_message(address, area_value)
        
        # Send polygon
        if enabled_fields.get('polygon', False) and 'polygon' in mappings:
            address = mappings['polygon'].format(**format_vars)
            self.send_blob_polygon(address, blob.polygon, roi_width, roi_height, normalize_coords)
    
    def send_blob_polygon(self, address: str, polygon: List[Tuple[int, int]], 
                         roi_width: int, roi_height: int, normalize_coords: bool = True) -> None:
        """Send blob polygon data."""
        if not polygon:
            return
        
        # Option 1: Send as JSON string (most compatible)
        if normalize_coords:
            norm_polygon = [(x / roi_width, y / roi_height) for x, y in polygon]
            polygon_str = json.dumps(norm_polygon)
        else:
            polygon_str = json.dumps(polygon)
        
        self.send_message(address, polygon_str)
        
        # Option 2: Send as flat numeric array (uncomment if preferred)
        # if normalize_coords:
        #     coords = []
        #     for x, y in polygon:
        #         coords.extend([x / roi_width, y / roi_height])
        # else:
        #     coords = []
        #     for x, y in polygon:
        #         coords.extend([x, y])
        # 
        # self.send_message(address, len(polygon), *coords)
    
    def send_multiple_blobs(self, blobs: List[BlobInfo], mappings: Dict[str, str],
                           roi_width: int, roi_height: int, normalize_coords: bool = True,
                           enabled_fields: Dict[str, bool] = None) -> None:
        """Send data for multiple blobs."""
        for blob in blobs:
            self.send_blob_data(blob, mappings, roi_width, roi_height, normalize_coords, enabled_fields)
    
    def send_test_message(self, address: str = "/test") -> None:
        """Send a test message."""
        timestamp = time.time()
        self.send_message(address, "test", timestamp)
    
    def get_message_log(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent message log."""
        if limit:
            return self.message_log[-limit:]
        return self.message_log.copy()
    
    def clear_message_log(self) -> None:
        """Clear the message log."""
        self.message_log.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return self.stats.copy()
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information."""
        return {
            'ip': self.ip,
            'port': self.port,
            'protocol': self.protocol,
            'status': self.stats['connection_status']
        }
    
    def test_connection(self) -> bool:
        """Test the OSC connection."""
        try:
            self.send_test_message("/connection_test")
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def set_callbacks(self, on_message_sent: Optional[Callable[[str, List[Any]], None]] = None,
                     on_send_error: Optional[Callable[[str, Exception], None]] = None) -> None:
        """Set callback functions."""
        self.on_message_sent = on_message_sent
        self.on_send_error = on_send_error
    
    def close(self) -> None:
        """Close the OSC client."""
        if self.executor:
            self.executor.shutdown(wait=False)
        
        if hasattr(self.client, 'close'):
            try:
                self.client.close()
            except:
                pass
        
        self.client = None
        self.stats['connection_status'] = 'disconnected'
        self.logger.info("OSC client closed")
    
    def __del__(self):
        """Cleanup on destruction."""
        self.close()
