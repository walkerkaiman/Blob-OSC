"""Settings manager for JSON configuration persistence."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from .utils import get_config_path, backup_config


@dataclass
class CameraConfig:
    friendly_name: str = ""
    backend_id: str = ""
    resolution: list[int] = None
    
    def __post_init__(self):
        if self.resolution is None:
            self.resolution = [1280, 720]


@dataclass
class ROIConfig:
    x: int = 0
    y: int = 0
    w: int = 640
    h: int = 480
    locked: bool = False
    # Crop slider values (pixels from each edge)
    left_crop: int = 0
    top_crop: int = 0
    right_crop: int = 0
    bottom_crop: int = 0


@dataclass
class ThresholdConfig:
    mode: str = "global"  # "global" or "adaptive"
    channel: str = "gray"  # "gray", "red", "green", "blue"
    value: int = 127
    blur: int = 3
    adaptive: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.adaptive is None:
            self.adaptive = {
                "method": "gaussian",
                "blocksize": 11,
                "C": 2
            }


@dataclass
class MorphConfig:
    open: int = 0
    close: int = 0


@dataclass
class BlobConfig:
    min_area: int = 200
    max_area: int = 20000
    track_ids: bool = True


@dataclass
class OSCConfig:
    ip: str = "127.0.0.1"
    port: int = 8000
    protocol: str = "udp"
    mappings: Dict[str, str] = None
    send_on_detect: bool = True
    normalize_coords: bool = True
    max_fps: float = 30.0  # Maximum OSC message rate (FPS)
    rate_limit_enabled: bool = True
    
    def __post_init__(self):
        if self.mappings is None:
            self.mappings = {
                "center": "/blob/{id}/center",
                "position": "/blob/{id}/pos",
                "size": "/blob/{id}/size",
                "polygon": "/blob/{id}/poly",
                "area": "/blob/{id}/area"
            }


@dataclass
class AppConfig:
    camera: CameraConfig = None
    roi: ROIConfig = None
    threshold: ThresholdConfig = None
    morph: MorphConfig = None
    blob: BlobConfig = None
    osc: OSCConfig = None
    
    def __post_init__(self):
        if self.camera is None:
            self.camera = CameraConfig()
        if self.roi is None:
            self.roi = ROIConfig()
        if self.threshold is None:
            self.threshold = ThresholdConfig()
        if self.morph is None:
            self.morph = MorphConfig()
        if self.blob is None:
            self.blob = BlobConfig()
        if self.osc is None:
            self.osc = OSCConfig()


class SettingsManager:
    """Manages application settings with JSON persistence."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or get_config_path()
        self.config = AppConfig()
        self.logger = logging.getLogger(__name__)
        self._auto_save_enabled = True
        
    def load_config(self) -> None:
        """Load configuration from JSON file."""
        if not self.config_path.exists():
            self.logger.info(f"Config file {self.config_path} not found, using defaults")
            self.save_config()
            return
            
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            self._load_from_dict(data)
            self.logger.info(f"Loaded config from {self.config_path}")
        except (json.JSONDecodeError, Exception) as e:
            self.logger.error(f"Failed to load config: {e}")
            backup_config(self.config_path)
            self.logger.info("Created backup and using default config")
            self.save_config()
    
    def save_config(self) -> None:
        """Save configuration to JSON file."""
        if not self._auto_save_enabled:
            return
            
        try:
            data = self._to_dict()
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
            self.logger.debug(f"Saved config to {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
    
    def _load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load configuration from dictionary."""
        # Camera config
        if 'camera' in data:
            cam_data = data['camera']
            self.config.camera = CameraConfig(
                friendly_name=cam_data.get('friendly_name', ''),
                backend_id=cam_data.get('backend_id', ''),
                resolution=cam_data.get('resolution', [1280, 720])
            )
        
        # ROI config
        if 'roi' in data:
            roi_data = data['roi']
            self.config.roi = ROIConfig(
                x=roi_data.get('x', 0),
                y=roi_data.get('y', 0),
                w=roi_data.get('w', 640),
                h=roi_data.get('h', 480),
                locked=roi_data.get('locked', False),
                left_crop=roi_data.get('left_crop', 0),
                top_crop=roi_data.get('top_crop', 0),
                right_crop=roi_data.get('right_crop', 0),
                bottom_crop=roi_data.get('bottom_crop', 0)
            )
        
        # Threshold config
        if 'threshold' in data:
            thresh_data = data['threshold']
            self.config.threshold = ThresholdConfig(
                mode=thresh_data.get('mode', 'global'),
                channel=thresh_data.get('channel', 'gray'),
                value=thresh_data.get('value', 127),
                blur=thresh_data.get('blur', 3),
                adaptive=thresh_data.get('adaptive', {
                    "method": "gaussian",
                    "blocksize": 11,
                    "C": 2
                })
            )
        
        # Morph config
        if 'morph' in data:
            morph_data = data['morph']
            self.config.morph = MorphConfig(
                open=morph_data.get('open', 0),
                close=morph_data.get('close', 0)
            )
        
        # Blob config
        if 'blob' in data:
            blob_data = data['blob']
            self.config.blob = BlobConfig(
                min_area=blob_data.get('min_area', 200),
                max_area=blob_data.get('max_area', 20000),
                track_ids=blob_data.get('track_ids', True)
            )
        
        # OSC config
        if 'osc' in data:
            osc_data = data['osc']
            self.config.osc = OSCConfig(
                ip=osc_data.get('ip', '127.0.0.1'),
                port=osc_data.get('port', 8000),
                protocol=osc_data.get('protocol', 'udp'),
                mappings=osc_data.get('mappings', {
                    "center": "/blob/{id}/center",
                    "position": "/blob/{id}/pos",
                    "size": "/blob/{id}/size",
                    "polygon": "/blob/{id}/poly",
                    "area": "/blob/{id}/area"
                }),
                send_on_detect=osc_data.get('send_on_detect', True),
                normalize_coords=osc_data.get('normalize_coords', True),
                max_fps=osc_data.get('max_fps', 30.0),
                rate_limit_enabled=osc_data.get('rate_limit_enabled', True)
            )
    
    def _to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'camera': asdict(self.config.camera),
            'roi': asdict(self.config.roi),
            'threshold': asdict(self.config.threshold),
            'morph': asdict(self.config.morph),
            'blob': asdict(self.config.blob),
            'osc': asdict(self.config.osc)
        }
    
    def get_camera_config(self) -> CameraConfig:
        """Get camera configuration."""
        return self.config.camera
    
    def get_roi_config(self) -> ROIConfig:
        """Get ROI configuration."""
        return self.config.roi
    
    def get_threshold_config(self) -> ThresholdConfig:
        """Get threshold configuration."""
        return self.config.threshold
    
    def get_morph_config(self) -> MorphConfig:
        """Get morphological operations configuration."""
        return self.config.morph
    
    def get_blob_config(self) -> BlobConfig:
        """Get blob detection configuration."""
        return self.config.blob
    
    def get_osc_config(self) -> OSCConfig:
        """Get OSC configuration."""
        return self.config.osc
    
    def update_camera_config(self, **kwargs) -> None:
        """Update camera configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config.camera, key):
                setattr(self.config.camera, key, value)
        self.save_config()
    
    def update_roi_config(self, **kwargs) -> None:
        """Update ROI configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config.roi, key):
                setattr(self.config.roi, key, value)
        self.save_config()
    
    def update_threshold_config(self, **kwargs) -> None:
        """Update threshold configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config.threshold, key):
                setattr(self.config.threshold, key, value)
        self.save_config()
    
    def update_morph_config(self, **kwargs) -> None:
        """Update morphological operations configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config.morph, key):
                setattr(self.config.morph, key, value)
        self.save_config()
    
    def update_blob_config(self, **kwargs) -> None:
        """Update blob detection configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config.blob, key):
                setattr(self.config.blob, key, value)
        self.save_config()
    
    def update_osc_config(self, **kwargs) -> None:
        """Update OSC configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config.osc, key):
                setattr(self.config.osc, key, value)
        self.save_config()
    
    def disable_auto_save(self) -> None:
        """Disable automatic saving."""
        self._auto_save_enabled = False
    
    def enable_auto_save(self) -> None:
        """Enable automatic saving."""
        self._auto_save_enabled = True
