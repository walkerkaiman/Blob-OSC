#!/usr/bin/env python3
"""Web-based run script for the Blob OSC application."""

import sys
import logging
import argparse
from pathlib import Path

from blob_osc.utils import setup_logging
from blob_osc.web_app import create_app


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Blob OSC Web: Real-time blob detection and OSC streaming"
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
        help="Host to bind to (default: 0.0.0.0 for network access)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to bind to (default: 5000)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    parser.add_argument(
        "--target-fps",
        type=float,
        default=5.0,
        help="Target FPS for processing (default: 5.0 for Pi optimization)"
    )
    
    return parser.parse_args()


def main():
    """Main application entry point."""
    args = parse_arguments()
    
    # Setup logging
    logger = setup_logging()
    logger.setLevel(getattr(logging, args.log_level))
    
    logger.info("Starting Blob OSC Web application")
    logger.info(f"Configuration file: {args.config}")
    logger.info(f"Log level: {args.log_level}")
    logger.info(f"Host: {args.host}, Port: {args.port}")
    logger.info(f"Target FPS: {args.target_fps}")
    
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
        
        logger.info(f"Web interface will be available at: http://{args.host}:{args.port}")
        logger.info("Press Ctrl+C to stop the application")
        
        # Start web server
        app.start(host=args.host, port=args.port, debug=args.debug)
            
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
