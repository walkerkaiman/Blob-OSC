"""Utility functions and constants."""

import json
import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path


def get_config_path() -> Path:
    """Get the path to the config file."""
    return Path("config.json")


def backup_config(config_path: Path) -> None:
    """Create a backup of the config file."""
    backup_path = config_path.with_suffix('.json.bak')
    if config_path.exists():
        backup_path.write_text(config_path.read_text())


def setup_logging() -> logging.Logger:
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('blob_osc')


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(value, max_val))


def normalize_coords(x: int, y: int, width: int, height: int) -> tuple[float, float]:
    """Normalize pixel coordinates to 0-1 range."""
    return x / width, y / height


def denormalize_coords(x_norm: float, y_norm: float, width: int, height: int) -> tuple[int, int]:
    """Convert normalized coordinates back to pixels."""
    return int(x_norm * width), int(y_norm * height)
