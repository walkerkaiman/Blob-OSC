"""Main application entry point for Blob OSC Web Application."""

import sys
import logging
import argparse
from pathlib import Path

from .utils import setup_logging


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Blob OSC: Real-time blob detection and OSC streaming via web interface"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="config.json",
        help="Configuration file path (default: config.json)"
    )
    
    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for web interface (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port for web interface (default: 5000)"
    )
    
    parser.add_argument(
        "--target-fps",
        type=float,
        default=30.0,
        help="Target FPS for processing (default: 30.0)"
    )
    
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (no web interface) - for testing purposes"
    )
    
    return parser.parse_args()


def main():
    """Main application entry point."""
    args = parse_arguments()
    
    # Setup logging
    logger = setup_logging()
    logger.setLevel(getattr(logging, args.log_level))
    
    logger.info("Starting Blob OSC Web Application")
    logger.info(f"Configuration file: {args.config}")
    logger.info(f"Log level: {args.log_level}")
    
    try:
        if args.headless:
            logger.info("Running in headless mode")
            run_headless(args)
        else:
            logger.info("Running in web mode")
            run_web(args)
            
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


def run_headless(args):
    """Run in headless mode (for testing/automation)."""
    from .cameras import CameraManager
    from .simple_roi import SimpleROI
    from .processor import ImageProcessor
    from .osc_client import OSCClient
    from .settings_manager import SettingsManager
    import time
    import cv2
    
    logger = logging.getLogger(__name__)
    logger.info("Starting headless mode")
    
    # Setup components
    settings_manager = SettingsManager(Path(args.config))
    settings_manager.load_config()
    
    camera_manager = CameraManager()
    roi_manager = SimpleROI()
    processor = ImageProcessor()
    
    # Setup OSC
    osc_config = settings_manager.get_osc_config()
    osc_client = OSCClient(osc_config.ip, osc_config.port, osc_config.protocol)
    
    try:
        # Open camera
        cameras = camera_manager.list_cameras()
        if not cameras:
            logger.error("No cameras found")
            return
        
        camera_id = cameras[0].id
        
        if not camera_manager.open_camera(camera_id):
            logger.error(f"Failed to open camera {camera_id}")
            return
        
        logger.info(f"Opened camera {camera_id}")
        camera_manager.start_capture()
        
        # Main processing loop
        logger.info("Starting processing loop (Ctrl+C to stop)")
        frame_count = 0
        
        while True:
            frame = camera_manager.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            
            # Set image size for ROI manager
            h, w = frame.shape[:2]
            roi_manager.set_image_size(w, h)
            
            # Apply ROI
            roi_frame = roi_manager.apply_crop(frame)
            if roi_frame is None:
                continue
            
            # Process image
            threshold_config = settings_manager.get_threshold_config()
            morph_config = settings_manager.get_morph_config()
            blob_config = settings_manager.get_blob_config()
            
            binary_frame, blobs = processor.process_image(
                roi_frame,
                threshold_config.__dict__,
                morph_config.__dict__,
                blob_config.__dict__
            )
            
            # Send OSC data
            if blobs and osc_config.send_on_detect:
                roi_bounds = roi_manager.get_roi_bounds()
                roi_width = roi_bounds[2] if roi_bounds else w
                roi_height = roi_bounds[3] if roi_bounds else h
                
                mappings = osc_config.mappings
                enabled_fields = {
                    'center': osc_config.send_center,
                    'position': osc_config.send_position,
                    'size': osc_config.send_size,
                    'area': osc_config.send_area,
                    'polygon': osc_config.send_polygon
                }
                
                osc_client.send_multiple_blobs(
                    blobs, mappings, roi_width, roi_height,
                    osc_config.normalize_coords, enabled_fields
                )
            
            frame_count += 1
            
            # Log stats periodically
            if frame_count % 300 == 0:  # Every ~5 seconds at 60fps
                stats = camera_manager.get_stats()
                logger.info(f"Frame {frame_count}, FPS: {stats['fps']:.1f}, "
                           f"Blobs: {len(blobs)}, Dropped: {stats['dropped_frames']}")
            
            time.sleep(0.01)  # Small delay
    
    except KeyboardInterrupt:
        logger.info("Headless mode interrupted")
    except Exception as e:
        logger.error(f"Headless mode error: {e}", exc_info=True)
    finally:
        # Cleanup
        camera_manager.close_camera()
        osc_client.close()
        logger.info("Headless mode finished")


def run_web(args):
    """Run the web application."""
    from .web_app import create_app
    
    try:
        # Create web application
        app = create_app(args.config)
        
        # Set target FPS from command line
        app.target_fps = args.target_fps
        app.frame_interval = 1.0 / args.target_fps
        
        # Update performance config
        app.settings_manager.update_performance_config(
            target_fps=args.target_fps
        )
        
        logger = logging.getLogger(__name__)
        logger.info(f"Web interface available at: http://{args.host}:{args.port}")
        logger.info("Press Ctrl+C to stop the application")
        
        # Start web server
        app.start(host=args.host, port=args.port, debug=False)
        
    except Exception as e:
        logger.error(f"Web application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()