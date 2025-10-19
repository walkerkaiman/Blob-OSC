# Blob OSC

A professional real-time computer vision application that detects and tracks objects (blobs) from camera feeds and streams their data via OSC (Open Sound Control) messages. Features a modern web-based interface optimized for Raspberry Pi and cross-platform deployment. Perfect for interactive installations, live performances, motion tracking, and creative coding projects.

## Features

- **🌐 Modern Web Interface** - Accessible from any device on your network
- **🎯 Real-time blob detection** with advanced OpenCV processing
- **📱 Mobile-friendly** responsive design for remote control
- **🔧 Simple OpenCV tracking** optimized for Raspberry Pi performance
- **📷 Intelligent camera detection** with support for Pi Camera Module and USB cameras
- **⚙️ Configurable Region of Interest (ROI)** with visual cropping and lock features
- **🎨 Advanced image processing** with channel selection, threshold modes, and morphological operations
- **📡 Flexible OSC streaming** via UDP with customizable message formats
- **💾 Comprehensive settings persistence** - all configurations saved to JSON
- **🚀 Optimized for Raspberry Pi** with configurable FPS and performance settings
- **🔄 X/Y axis flipping** for camera orientation adjustment
- **📊 Real-time blob data display** with normalized coordinates (0-1 range)

## Installation

### Prerequisites

- Python 3.8 or higher
- Camera (USB webcam or Raspberry Pi Camera Module)
- OSC-compatible receiving application (TouchDesigner, Max/MSP, Pure Data, etc.)

### Setup

1. **Clone or download** this repository
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the web application**:
   ```bash
   python run_web.py
   ```
4. **Open your browser** and navigate to `http://localhost:5000` (or your device's IP address)

### Dependencies

- `opencv-python` - Computer vision and image processing
- `flask`, `flask-socketio`, `eventlet` - Web framework and real-time communication
- `pillow` - Image processing and streaming
- `picamera2` - Raspberry Pi Camera Module support (Linux only)
- `python-osc` - OSC message sending
- `numpy` - Numerical operations

## Quick Start Guide

1. **Launch the application** with `python run_web.py`
2. **Open your browser** to `http://localhost:5000`
3. **Select a camera** in the "Capture / ROI" tab
4. **Set up your region of interest** using the crop sliders
5. **Adjust detection settings** in the "Threshold & Blobs" tab
6. **Configure OSC output** in the "OSC Output" tab
7. **Connect to your OSC receiver** and start detecting!

---

## Detailed User Guide

### Tab 1: Capture / ROI

This tab handles camera setup, performance settings, and region of interest configuration.

#### Camera Settings

**Camera Selection**
- Select your camera from the dropdown (USB cameras or Raspberry Pi Camera Module)
- Automatically detects available cameras
- Settings are automatically saved when changed

**Resolution Selection**
- Choose camera resolution: 640x480, 1280x720, or 1920x1080
- Higher resolutions provide more detail but use more processing power
- Changes apply immediately to the camera feed

**Image Transform**
- **Flip X (Horizontal)**: Mirror the camera feed horizontally
- **Flip Y (Vertical)**: Flip the camera feed vertically
- Useful for adjusting camera orientation without physical rotation

#### Performance Settings

**Target FPS**
- Adjustable from 1-60 FPS
- Default: 30 FPS for optimal performance
- Lower FPS for better performance on resource-constrained devices
- Setting is saved and persists between sessions

#### Region of Interest (ROI) Controls

**Crop Sliders**
- **Left Crop**: Remove pixels from the left edge (0-1000px)
- **Top Crop**: Remove pixels from the top edge (0-1000px)  
- **Right Crop**: Remove pixels from the right edge (0-1000px)
- **Bottom Crop**: Remove pixels from the bottom edge (0-1000px)

*Tip: Start with small values and increase gradually. You'll see overlays showing what will be cropped.*

**ROI Controls**
- **Reset ROI**: Clear all cropping, use full camera frame
- **Lock ROI**: Disable slider changes to prevent accidental modifications

### Tab 2: Threshold & Blobs

This tab controls image processing and blob detection parameters.

#### Processing Controls

**Channel Selection**
- **Gray**: Standard grayscale processing (recommended)
- **Red**: Use only red color channel
- **Green**: Use only green color channel  
- **Blue**: Use only blue color channel

**Blur**
- Range: 0-15
- Applies Gaussian blur before thresholding
- Reduces noise and smooths edges

**Threshold Mode**
- **Global**: Single threshold value for entire image
- **Adaptive**: Different thresholds for different image regions

**Threshold Level**
- Range: 0-255 (pixel intensity)
- Pixels above this value become white, below become black
- Adjust while watching the binary image preview

**Invert Threshold**
- Invert the binary image (black becomes white, white becomes black)
- Useful for detecting dark objects on light backgrounds

**Noise Removal (Morphological Opening)**
- Range: 0-10
- Removes small white noise pixels
- Higher values remove larger noise spots

**Gap Filling (Morphological Closing)**  
- Range: 0-10
- Fills small black gaps inside white objects
- Makes objects more solid and complete

**Min Area (Slider)**
- Range: 1-100,000 pixels
- Minimum size for blob detection
- Smaller blobs are ignored

**Max Area (Slider)**
- Range: 1,000-100,000 pixels  
- Maximum size for blob detection
- Larger blobs are ignored

#### Blob Tracking

**Track IDs Checkbox**
- Enable persistent blob IDs across frames
- Blobs maintain the same ID as they move
- Useful for tracking individual objects over time

**Clear IDs Button**
- Reset all blob tracking IDs back to 0
- Use when you want to restart ID assignment

#### Detected Blobs Display

Shows real-time information about detected blobs:
- **Blob ID**: Unique identifier for each tracked blob
- **Center**: Normalized center coordinates (0-1 range)
- **Area**: Normalized area as fraction of ROI (0-1) + raw pixels
- **BBox**: Normalized bounding box coordinates (position and size)

### Tab 3: OSC Output

This tab configures Open Sound Control message sending with comprehensive field selection.

#### OSC Settings

**IP Address**
- Destination IP for OSC messages
- Use "127.0.0.1" for local applications
- Use network IP for remote computers

**Port**
- OSC port number (1-65535)
- Common ports: 8000, 9000, 57120
- Must match your receiving application's port

**Normalize Coordinates**
- When enabled: coordinates sent as 0.0-1.0 range (recommended)
- When disabled: coordinates sent as pixel values
- Most applications expect normalized coordinates

**Connect on Start**
- Automatically connect to OSC when the application starts
- Eliminates need for manual connection each time

#### Field Selection

Choose which blob data to send:

**Center (cx, cy)**
- Blob center point coordinates (centroid of the actual shape)
- Most commonly used for smooth motion tracking

**Position (x, y)**  
- Top-left corner of bounding box rectangle
- Useful for precise object positioning

**Size (w, h)**
- Width and height of bounding box
- Useful for scale-responsive interactions

**Area**
- Total blob area in pixels (or normalized)
- Useful for size-based triggers

**Polygon**
- Simplified contour points as JSON array
- Advanced use for precise shape tracking

**Send Controls**
- **Send on Detection**: Automatically send when blobs are detected
- **Connect/Disconnect**: Establish or close OSC connection

---

## Configuration File

Settings are automatically saved to `config.json` in the application directory:

```json
{
  "camera": {
    "friendly_name": "Camera 0",
    "resolution": [1280, 720],
    "flip_x": false,
    "flip_y": false
  },
  "roi": {
    "x": 0,
    "y": 0,
    "w": 640,
    "h": 480,
    "locked": false,
    "left_crop": 0,
    "top_crop": 0,
    "right_crop": 0,
    "bottom_crop": 0
  },
  "threshold": {
    "mode": "global",
    "channel": "gray",
    "value": 127,
    "blur": 3,
    "invert": false
  },
  "morph": {
    "open": 0,
    "close": 0
  },
  "blob": {
    "min_area": 200,
    "max_area": 20000,
    "track_ids": true
  },
  "osc": {
    "ip": "127.0.0.1",
    "port": 8000,
    "mappings": {
      "center": "/blob/{id}/center",
      "position": "/blob/{id}/pos",
      "size": "/blob/{id}/size",
      "polygon": "/blob/{id}/poly",
      "area": "/blob/{id}/area"
    },
    "send_on_detect": true,
    "normalize_coords": true,
    "max_fps": 30.0,
    "rate_limit_enabled": true,
    "connect_on_start": false,
    "send_center": true,
    "send_position": false,
    "send_size": false,
    "send_area": false,
    "send_polygon": false
  },
  "performance": {
    "target_fps": 30.0,
    "max_camera_fps": 30.0,
    "processing_enabled": true,
    "camera_module_enabled": true
  }
}
```

## Raspberry Pi Optimization

This application is optimized for Raspberry Pi deployment:

### Performance Features
- **Configurable FPS**: Adjust target FPS from 1-60 based on your Pi's capabilities
- **Pi Camera Module Support**: Native support for Raspberry Pi Camera Module
- **Lightweight Processing**: Simple OpenCV tracking optimized for Pi performance
- **Memory Efficient**: Streamlined codebase without heavy dependencies

### Recommended Settings for Pi
- **Target FPS**: 15-30 FPS depending on your Pi model
- **Camera Resolution**: 640x480 or 1280x720 for best performance
- **ROI**: Use smaller regions of interest to reduce processing load
- **OSC Rate**: Default 30 FPS is automatically rate-limited

## Troubleshooting

### Camera Issues
- **No cameras found**: Check camera connections, try clicking Refresh
- **Camera won't open**: Close other applications using the camera
- **Poor image quality**: Try different resolutions or lighting

### Detection Issues  
- **No blobs detected**: Lower threshold value, check lighting
- **Too many false detections**: Raise threshold, increase min area
- **Blobs are fragmented**: Increase gap filling (morph close)
- **Noisy detection**: Increase blur and noise removal

### OSC Issues
- **Connection failed**: Check IP address and port number
- **No messages received**: Verify receiver is listening on correct port
- **Too many messages**: Rate limiting is automatic (30 FPS max)

### Web Interface Issues
- **Can't access web interface**: Check firewall settings, ensure port 5000 is open
- **Interface not loading**: Try hard refresh (Ctrl+F5) or clear browser cache
- **Slow performance**: Reduce target FPS or camera resolution

## Advanced Usage

### Network Access
- **Local Access**: `http://localhost:5000` or `http://127.0.0.1:5000`
- **Network Access**: `http://[device-ip]:5000` (e.g., `http://192.168.1.100:5000`)
- **Mobile Control**: Access the interface from any device on your network

### Custom OSC Mappings
The application uses default OSC address patterns:
- `/blob/{id}/center` - Blob center coordinates
- `/blob/{id}/pos` - Blob position (top-left)
- `/blob/{id}/size` - Blob size (width, height)
- `/blob/{id}/area` - Blob area
- `/blob/{id}/poly` - Blob polygon points

### Integration Examples

**TouchDesigner**: Use CHOPs to receive OSC data
**Max/MSP**: Use `udpreceive` object  
**Pure Data**: Use `netreceive` object
**Processing/p5.js**: Use OSC libraries like oscP5
**Unity**: Use OSC plugins for game integration

---

## Technical Details

### System Requirements
- **OS**: Windows 10/11, macOS 10.14+, Linux (Ubuntu 18.04+), Raspberry Pi OS
- **Python**: 3.8 or higher
- **RAM**: 2GB minimum, 4GB recommended for Raspberry Pi
- **CPU**: Any modern processor, optimized for ARM (Raspberry Pi)

### Performance Notes
- **Camera Resolution**: Higher = more detail, lower = better performance
- **ROI Size**: Smaller ROI = significantly faster processing
- **Target FPS**: Adjustable based on hardware capabilities
- **OSC Rate**: Fixed at 30 FPS to prevent receiver overload
- **Web Interface**: Responsive design works on desktop and mobile

### File Structure
```
Blob-OSC/
├── blob_osc/           # Main application code
│   ├── app.py         # Application entry point
│   ├── web_app.py     # Flask web application
│   ├── cameras.py     # Camera management with Pi Camera support
│   ├── processor.py   # Image processing and blob detection
│   ├── osc_client.py  # OSC message sending with rate limiting
│   ├── simple_roi.py  # ROI management
│   ├── settings_manager.py  # Configuration persistence
│   └── templates/     # Web interface templates
│       └── index.html # Main web interface
├── config.json        # Settings file (auto-generated)
├── requirements.txt   # Python dependencies
├── run_web.py        # Web application launcher
└── README.md         # This documentation
```