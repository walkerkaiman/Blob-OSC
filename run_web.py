#!/usr/bin/env python3
"""Web-based run script for the Blob OSC application."""

import sys
import logging
import argparse
import os
import tempfile
import atexit
from pathlib import Path

from blob_osc.utils import setup_logging
from blob_osc.web_app import create_app


def check_singleton():
    """Check if another instance is already running using lock file."""
    lock_path = Path(tempfile.gettempdir()) / "blob_osc.lock"
    
    try:
        if lock_path.exists():
            # Read the PID from the lock file
            with open(lock_path, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if the process is still running
            try:
                os.kill(pid, 0)  # This will raise an exception if process doesn't exist
                print("ERROR: Another instance of Blob OSC is already running!")
                print(f"Please close the existing instance (PID: {pid}) before starting a new one.")
                print("To force close, you can:")
                print(f"  - Kill the process: taskkill /PID {pid} /F (Windows) or kill {pid} (Linux/Mac)")
                print(f"  - Or delete the lock file: {lock_path}")
                return False
            except OSError:
                # Process doesn't exist, remove stale lock file
                lock_path.unlink()
                print(f"Removed stale lock file from previous session (PID: {pid})")
        
        # Create lock file with current PID
        with open(lock_path, 'w') as f:
            f.write(str(os.getpid()))
        
        print(f"Blob OSC instance started (PID: {os.getpid()})")
        return True
        
    except Exception as e:
        print(f"Error checking for existing instances: {e}")
        return True  # Continue anyway to avoid blocking the user


def cleanup_lock():
    """Clean up lock file on exit."""
    try:
        lock_path = Path(tempfile.gettempdir()) / "blob_osc.lock"
        if lock_path.exists():
            # Verify this is our lock file by checking PID
            with open(lock_path, 'r') as f:
                stored_pid = int(f.read().strip())
            
            if stored_pid == os.getpid():
                lock_path.unlink()
                print(f"Cleaned up lock file (PID: {os.getpid()})")
    except Exception as e:
        print(f"Error cleaning up lock file: {e}")


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
    # Check for existing instance first
    if not check_singleton():
        sys.exit(1)
    
    # Register cleanup function
    atexit.register(cleanup_lock)
    
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
