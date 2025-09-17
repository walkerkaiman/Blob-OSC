# Webcam-to-OSC

A real-time Python application that captures webcam feeds, performs blob detection through image processing, and streams the results over OSC (Open Sound Control). Perfect for interactive installations, motion tracking, and creative coding projects.

## Features

- **Real-time webcam capture** with camera enumeration by friendly names
- **Interactive ROI (Region of Interest) selection** with click-and-drag interface
- **Advanced image processing pipeline**:
  - Grayscale conversion with channel selection
  - Gaussian blur
  - Global and adaptive thresholding
  - Morphological operations (opening/closing)
- **Blob detection and tracking**:
  - Area-based filtering
  - Persistent ID tracking across frames
  - Bounding box and centroid calculation
  - Polygon simplification
- **OSC streaming**:
  - Configurable OSC address patterns
  - Multiple data formats (center, position, size, area, polygon)
  - Normalized or pixel coordinates
  - UDP/TCP support
- **Persistent configuration** with JSON settings
- **Professional GUI** with tabbed interface
- **Real-time console logging** and statistics
- **Cross-platform support** (Windows, macOS, Linux)

## Installation

### Prerequisites

- Python 3.10 or higher
- Webcam/camera device

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Dependencies

- `opencv-python>=4.8.0` - Computer vision and camera capture
- `PyQt6>=6.5.0` - GUI framework
- `python-osc>=1.8.0` - OSC protocol support
- `numpy>=1.24.0` - Numerical operations
- `tqdm>=4.65.0` - Progress bars (for testing)
- `pytest>=7.4.0` - Testing framework

## Quick Start

### Basic Usage

```bash
# Run the application
python -m webcam_osc.app

# Or with specific config
python -m webcam_osc.app --config my_config.json

# Run with custom OSC settings
python -m webcam_osc.app --osc-ip 192.168.1.100 --osc-port 9000
```

### Headless Mode (for automation)

```bash
# Run without GUI
python -m webcam_osc.app --headless --camera-id 0 --osc-ip 127.0.0.1
```

## User Interface Guide

### Tab 1: Capture / ROI

1. **Select Camera**: Choose from detected cameras in the dropdown
2. **Set Resolution**: Choose capture resolution (640x480, 1280x720, 1920x1080)
3. **Define ROI**: 
   - Click and drag on the preview to draw a region of interest
   - Use handles to resize the ROI
   - Double-click to reset to full frame
   - Lock ROI to prevent accidental changes

### Tab 2: Threshold & Blob Detection

1. **Image Processing**:
   - Choose color channel (Gray, Red, Green, Blue)
   - Adjust blur kernel size
   - Select threshold type (Global/Adaptive)
   - Fine-tune threshold value
   - Apply morphological operations

2. **Blob Detection**:
   - Set minimum and maximum blob area (in pixels)
   - Enable/disable ID tracking
   - View binary and overlay previews

### Tab 3: OSC Output

1. **Connection Settings**:
   - Set destination IP address
   - Configure port number
   - Choose protocol (UDP/TCP)
   - Enable coordinate normalization

2. **Data Mapping**:
   - Select which data fields to send
   - Customize OSC address patterns
   - Use format variables: `{id}`, `{i}`, `{time}`, `{cx}`, `{cy}`, `{x}`, `{y}`, `{w}`, `{h}`, `{area}`

3. **Sending Options**:
   - Auto-send on detection
   - Manual send button
   - Test connection

## Configuration

Settings are automatically saved to `config.json`. Example configuration:

```json
{
  "camera": {
    "friendly_name": "Logitech C920",
    "backend_id": "camera://0",
    "resolution": [1280, 720]
  },
  "roi": {
    "x": 100,
    "y": 50,
    "w": 800,
    "h": 400,
    "locked": false
  },
  "threshold": {
    "mode": "global",
    "value": 127,
    "blur": 3,
    "adaptive": {
      "method": "gaussian",
      "blocksize": 11,
      "C": 2
    }
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
    "protocol": "udp",
    "mappings": {
      "center": "/blob/{id}/center",
      "position": "/blob/{id}/pos",
      "size": "/blob/{id}/size",
      "polygon": "/blob/{id}/poly",
      "area": "/blob/{id}/area"
    },
    "send_on_detect": true,
    "normalize_coords": true
  }
}
```

## OSC Message Format

### Default Address Patterns

- **Center**: `/blob/{id}/center` → `[cx_normalized, cy_normalized]`
- **Position**: `/blob/{id}/pos` → `[x_normalized, y_normalized]` (top-left)
- **Size**: `/blob/{id}/size` → `[w_normalized, h_normalized]`
- **Area**: `/blob/{id}/area` → `[area_normalized]`
- **Polygon**: `/blob/{id}/poly` → `['[[x1,y1],[x2,y2],...]']` (JSON string)

### Coordinate Systems

- **Normalized**: Values from 0.0 to 1.0 relative to ROI
- **Pixel**: Raw pixel coordinates relative to ROI

## Integration Examples

### TouchDesigner

```python
# In TouchDesigner, use OSC In DAT to receive messages
# Address: /blob/*/center
# Parse the two float values as X, Y coordinates
```

### Max/MSP

```max
# Use [udpreceive] object
[udpreceive 8000]
|
[oscparse]
|
[route /blob]
|
[route center position size area]
```

### Unity

```csharp
// Use OscCore or similar OSC library
// Listen for messages on port 8000
void OnBlobCenter(int blobId, float x, float y) {
    // Handle blob center data
}
```

## Performance Tips

- **Resolution**: Lower camera resolution = higher FPS
- **ROI**: Smaller regions of interest process faster
- **Blob Count**: Limit max blob area to reduce processing
- **Threading**: Processing runs in separate threads to keep UI responsive
- **Queue Size**: Frame queue is limited to prevent memory buildup

## Troubleshooting

### Camera Issues
- **No cameras found**: Check camera connections and permissions
- **Camera won't open**: Try different camera indices or restart application
- **Low FPS**: Reduce resolution or ROI size

### OSC Issues
- **Connection failed**: Check IP address and port availability
- **No data received**: Verify OSC address patterns and enable "Send on Detection"
- **Firewall**: Ensure firewall allows OSC traffic on specified port

### Performance Issues
- **High CPU usage**: Reduce camera resolution or increase processing intervals
- **Memory leaks**: Restart application periodically for long-running sessions
- **UI freezing**: Check that processing thread is running properly

## Development

### Running Tests

```bash
# Run all tests
python -m pytest webcam_osc/tests/

# Run specific test
python -m pytest webcam_osc/tests/test_processor.py -v

# Run with coverage
python -m pytest --cov=webcam_osc
```

### Project Structure

```
webcam_osc/
├── app.py                    # Application entry point
├── cameras.py                # Camera management
├── roi.py                    # ROI selection and management
├── processor.py              # Image processing and blob detection
├── osc_client.py             # OSC client wrapper
├── settings_manager.py       # Configuration management
├── utils.py                  # Utility functions
├── ui/
│   ├── main_window.py        # Main application window
│   └── widgets.py            # Custom UI widgets
└── tests/
    └── test_processor.py     # Unit tests
```

## License

This project is open source. Feel free to modify and distribute according to your needs.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

For issues, feature requests, or questions:
- Check the troubleshooting section
- Review existing issues
- Create a new issue with detailed information

---

**Webcam-to-OSC** - Real-time computer vision meets creative coding!
