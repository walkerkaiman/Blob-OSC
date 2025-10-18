# Blob OSC - Raspberry Pi Edition

A lightweight, web-based version of Blob OSC optimized for Raspberry Pi with support for the Pi Camera Module.

## Features

- **Web-based GUI** - Access from any device on your network
- **Raspberry Pi Camera Module support** - Native Pi Camera integration
- **Performance optimized** - Default 5 FPS processing for Pi efficiency
- **All original features** - Complete blob detection and OSC streaming
- **Lightweight design** - Optimized for Pi's limited resources

## Quick Start

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Blob-OSC
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Enable Pi Camera Module** (if using):
   ```bash
   sudo raspi-config
   # Navigate to Interface Options > Camera > Enable
   sudo reboot
   ```

### Running the Application

**Web Interface (Recommended)**:
```bash
python run_web.py
```

**Or using the main script**:
```bash
python -m blob_osc.app --web --host 0.0.0.0 --port 5000 --target-fps 5
```

**Access the web interface**:
- Open your browser and go to: `http://<pi-ip-address>:5000`
- Example: `http://192.168.1.100:5000`

## Configuration

### Performance Settings

The application is optimized for Raspberry Pi with these default settings:

- **Target FPS**: 5 FPS (configurable)
- **Camera Module**: Enabled by default
- **Processing**: Optimized for Pi's CPU

You can adjust the target FPS via command line:
```bash
python run_web.py --target-fps 10  # Increase to 10 FPS
```

### Camera Setup

**Pi Camera Module**:
- Automatically detected when available
- Supports resolutions: 640x480, 1280x720, 1920x1080
- Optimized for blob detection

**USB Camera**:
- Also supported as fallback
- Standard USB webcam compatibility

## Web Interface

The web interface provides the same functionality as the desktop version:

### Tab 1: Capture / ROI
- Camera selection and preview
- Region of Interest (ROI) configuration
- Real-time video feed

### Tab 2: Threshold & Blobs
- Image processing controls
- Blob detection parameters
- Live preview of binary and overlay images

### Tab 3: OSC Output
- OSC connection settings
- Field selection and mapping
- Real-time console output

## Network Access

The web interface is designed for network access:

- **Default host**: `0.0.0.0` (accessible from network)
- **Default port**: `5000`
- **Access from any device** on the same network

### Finding Your Pi's IP Address

```bash
hostname -I
```

## Performance Optimization

### For Raspberry Pi 4 (Recommended)
- **Target FPS**: 5-10 FPS
- **Resolution**: 1280x720
- **ByteTrack**: Enabled for better tracking

### For Raspberry Pi 3
- **Target FPS**: 3-5 FPS
- **Resolution**: 640x480
- **ByteTrack**: May need to be disabled for performance

### For Older Pi Models
- **Target FPS**: 2-3 FPS
- **Resolution**: 640x480
- **ByteTrack**: Disabled
- **Processing**: Simplified mode

## Troubleshooting

### Camera Issues

**Pi Camera Module not detected**:
```bash
# Check if camera is enabled
sudo raspi-config
# Interface Options > Camera > Enable

# Test camera manually
libcamera-hello --timeout 5000
```

**USB Camera issues**:
```bash
# List USB devices
lsusb

# Check video devices
ls /dev/video*
```

### Performance Issues

**Low FPS**:
- Reduce target FPS: `--target-fps 3`
- Lower camera resolution
- Disable ByteTrack in settings

**High CPU usage**:
- Enable ROI to crop processing area
- Increase blur and noise removal
- Use simpler tracking mode

### Network Access Issues

**Cannot access from other devices**:
- Check firewall settings
- Ensure Pi is on same network
- Try accessing via IP address directly

**Connection refused**:
- Check if port 5000 is available
- Try different port: `--port 8080`

## Command Line Options

```bash
python run_web.py --help
```

Key options:
- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to bind to (default: 5000)
- `--target-fps`: Target processing FPS (default: 5.0)
- `--config`: Configuration file path
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Configuration File

Settings are automatically saved to `config.json`. Key Pi-specific settings:

```json
{
  "performance": {
    "target_fps": 5.0,
    "camera_module_enabled": true,
    "processing_enabled": true
  },
  "camera": {
    "friendly_name": "Raspberry Pi Camera Module",
    "resolution": [1280, 720]
  }
}
```

## Integration Examples

### TouchDesigner
- Set OSC IP to your Pi's address
- Use default port 5000
- Receive blob data on `/blob/{id}/center`

### Max/MSP
- Use `udpreceive` object
- Configure for Pi's IP and port 5000

### Processing/p5.js
- Use OSC libraries like oscP5
- Connect to Pi's IP address

## System Requirements

### Raspberry Pi 4 (Recommended)
- 4GB RAM minimum
- Pi Camera Module v2 or v3
- MicroSD card (32GB+)
- Ethernet or WiFi connection

### Raspberry Pi 3
- 1GB RAM minimum
- Pi Camera Module v1 or v2
- MicroSD card (16GB+)
- Ethernet connection recommended

### Software Requirements
- Raspberry Pi OS (Bullseye or newer)
- Python 3.8+
- OpenCV with Pi optimizations
- Picamera2 library

## Development

### Running in Development Mode

```bash
python run_web.py --debug --log-level DEBUG
```

### Customizing the Web Interface

The web interface is built with:
- Flask for the backend
- Socket.IO for real-time communication
- Vanilla JavaScript for the frontend
- CSS for responsive design

Files to modify:
- `blob_osc/web_app.py` - Backend API
- `blob_osc/templates/index.html` - Frontend interface

## Support

For issues specific to the Raspberry Pi edition:
1. Check the troubleshooting section above
2. Verify Pi Camera Module is properly enabled
3. Ensure adequate cooling for sustained operation
4. Monitor CPU temperature during operation

## License

Same as the main Blob OSC project.
