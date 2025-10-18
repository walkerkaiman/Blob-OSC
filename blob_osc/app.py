"""Main application entry point."""

import sys
import logging
import argparse
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from .utils import setup_logging
from .ui.main_window import MainWindow


def setup_application():
    """Setup the QApplication with proper configuration."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("Blob OSC")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Blob-OSC")
    
    # Set application icon if available
    # app.setWindowIcon(QIcon("icon.png"))
    
    return app


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Blob OSC: Real-time blob detection and OSC streaming"
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
        "--headless",
        action="store_true",
        help="Run in headless mode (no GUI) - for testing purposes"
    )
    
    parser.add_argument(
        "--web",
        action="store_true",
        help="Run in web mode (Flask web interface) - for Raspberry Pi"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for web mode (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port for web mode (default: 5000)"
    )
    
    parser.add_argument(
        "--target-fps",
        type=float,
        default=5.0,
        help="Target FPS for processing (default: 5.0 for Pi optimization)"
    )
    
    parser.add_argument(
        "--camera-id",
        type=int,
        default=None,
        help="Camera ID to use (default: auto-detect)"
    )
    
    parser.add_argument(
        "--osc-ip",
        type=str,
        default=None,
        help="OSC destination IP address"
    )
    
    parser.add_argument(
        "--osc-port",
        type=int,
        default=None,
        help="OSC destination port"
    )
    
    return parser.parse_args()


def main():
    """Main application entry point."""
    args = parse_arguments()
    
    # Setup logging
    logger = setup_logging()
    logger.setLevel(getattr(logging, args.log_level))
    
    logger.info("Starting Blob OSC application")
    logger.info(f"Configuration file: {args.config}")
    logger.info(f"Log level: {args.log_level}")
    
    try:
        if args.web:
            logger.info("Running in web mode")
            run_web(args)
        elif args.headless:
            logger.info("Running in headless mode")
            # TODO: Implement headless mode for testing/automation
            run_headless(args)
        else:
            run_gui(args)
            
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


def run_gui(args):
    """Run the GUI application."""
    app = setup_application()
    
    try:
        # Create main window
        window = MainWindow()
        
        # Override config path if specified
        if args.config != "config.json":
            config_path = Path(args.config)
            window.settings_manager.config_path = config_path
            window.load_settings()
        
        # Override OSC settings if specified
        if args.osc_ip:
            window.osc_ip.setText(args.osc_ip)
            window.settings_manager.update_osc_config(ip=args.osc_ip)
        
        if args.osc_port:
            window.osc_port.setValue(args.osc_port)
            window.settings_manager.update_osc_config(port=args.osc_port)
        
        # Auto-select camera if specified
        if args.camera_id is not None:
            cameras = window.camera_manager.list_cameras()
            for camera in cameras:
                if camera.id == args.camera_id:
                    window.camera_combo.setCurrentText(str(camera))
                    break
        
        # Show window
        window.show()
        
        # Run application
        exit_code = app.exec()
        
        logging.info("Application exited normally")
        sys.exit(exit_code)
        
    except Exception as e:
        logging.error(f"GUI application error: {e}", exc_info=True)
        
        # Show error dialog if possible
        try:
            QMessageBox.critical(
                None, "Application Error",
                f"An error occurred:\n\n{str(e)}\n\n"
                "Check the console for more details."
            )
        except:
            pass
        
        sys.exit(1)


def run_headless(args):
    """Run in headless mode (for testing/automation)."""
    from .cameras import CameraManager
    from .roi import ROIManager
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
    roi_manager = ROIManager()
    processor = ImageProcessor()
    
    # Setup OSC
    osc_config = settings_manager.get_osc_config()
    osc_ip = args.osc_ip or osc_config.ip
    osc_port = args.osc_port or osc_config.port
    osc_client = OSCClient(osc_ip, osc_port, osc_config.protocol)
    
    try:
        # Open camera
        cameras = camera_manager.list_cameras()
        if not cameras:
            logger.error("No cameras found")
            return
        
        camera_id = args.camera_id if args.camera_id is not None else cameras[0].id
        
        if not camera_manager.open_camera(camera_id):
            logger.error(f"Failed to open camera {camera_id}")
            return
        
        logger.info(f"Opened camera {camera_id}")
        camera_manager.start_capture()
        
        # Setup ROI
        roi_config = settings_manager.get_roi_config()
        roi_manager.set_roi(roi_config.x, roi_config.y, roi_config.w, roi_config.h, update_crop_values=False)
        
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
            roi_frame = roi_manager.apply_roi(frame)
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
                roi = roi_manager.get_roi()
                roi_width = roi.w if roi else w
                roi_height = roi.h if roi else h
                
                mappings = osc_config.mappings
                enabled_fields = {
                    'center': True,
                    'position': True,
                    'size': True,
                    'area': True,
                    'polygon': False
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
