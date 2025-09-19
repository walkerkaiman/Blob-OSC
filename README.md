# Blob OSC

A real-time computer vision application that detects blobs (objects) from webcam feeds and streams their data via OSC (Open Sound Control) messages. Perfect for interactive installations, live performances, motion tracking, and creative coding projects.

## Features

- **Real-time blob detection** from webcam feeds
- **Configurable Region of Interest (ROI)** with visual cropping
- **Advanced image processing** with threshold and morphological controls
- **OSC streaming** via UDP/TCP with customizable message formats
- **Blob tracking** with persistent IDs across frames
- **Multiple color channels** (grayscale, red, green, blue)
- **Persistent settings** saved to JSON configuration
- **Rate-limited OSC** to prevent receiver overload

## Installation

### Prerequisites

- Python 3.8 or higher
- Webcam or USB camera
- OSC-compatible receiving application (TouchDesigner, Max/MSP, Pure Data, etc.)

### Setup

1. **Clone or download** this repository
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application**:
   ```bash
   python run.py
   ```

### Dependencies

- `opencv-python` - Computer vision and image processing
- `PyQt6` - GUI framework
- `python-osc` - OSC message sending
- `numpy` - Numerical operations

## Quick Start Guide

1. **Launch the application** with `python run.py`
2. **Select a camera** in the "Capture / ROI" tab
3. **Set up your region of interest** using the crop sliders
4. **Adjust detection settings** in the "Threshold & Blobs" tab
5. **Configure OSC output** in the "OSC Output" tab
6. **Connect to your OSC receiver** and start detecting!

---

## Detailed User Guide

### Tab 1: Capture / ROI

This tab handles camera setup and region of interest configuration.

#### Camera Settings

**Camera Dropdown**
- Select your webcam from the list of available cameras
- Camera names show as "Camera 0", "Camera 1", etc.
- Settings are automatically saved when changed

**Refresh Button**
- Click to rescan for available cameras
- Use this if you connect a new camera while the app is running

**Resolution Dropdown**
- Choose camera resolution: 640x480, 1280x720, or 1920x1080
- Higher resolutions provide more detail but use more processing power
- Changes apply immediately to the camera feed

#### Camera Preview

**Live Video Feed**
- Shows the raw camera feed with ROI overlay
- Red/semi-transparent rectangles show areas that will be cropped
- Yellow outline shows the final ROI boundary
- Real-time preview updates as you adjust crop settings

**Pause Button**
- Temporarily stop image processing
- Useful for adjusting settings without distraction
- Click again to resume

#### Region of Interest (ROI) Controls

The ROI system lets you focus blob detection on a specific area of the camera feed.

**Crop Sliders**
- **Left Crop**: Remove pixels from the left edge (0-1000px)
- **Top Crop**: Remove pixels from the top edge (0-1000px)  
- **Right Crop**: Remove pixels from the right edge (0-1000px)
- **Bottom Crop**: Remove pixels from the bottom edge (0-1000px)

*Tip: Start with small values and increase gradually. You'll see red overlays showing what will be cropped.*

**ROI Buttons**
- **Use ROI**: Save current ROI settings (automatic when sliders change)
- **Reset ROI**: Clear all cropping, use full camera frame
- **Lock ROI**: Disable slider changes and auto-set max blob area

**Lock ROI Feature**
- When enabled: Sliders become disabled, settings are locked
- Automatically sets "Max Area" to ROI width × height
- Saves current crop values to configuration
- Useful when you've found the perfect ROI setup

### Tab 2: Threshold & Blobs

This tab controls image processing and blob detection parameters.

#### Processing Controls

**Channel Selection**
- **Gray**: Standard grayscale processing (recommended)
- **Red**: Use only red color channel
- **Green**: Use only green color channel  
- **Blue**: Use only blue color channel

*Use color channels when detecting objects of specific colors (e.g., blue channel for blue objects).*

**Blur**
- Range: 0-15
- Applies Gaussian blur before thresholding
- Reduces noise and smooths edges
- Higher values = more blur, cleaner results
- Start with 3-5 for most situations

**Threshold Mode**
- **Global**: Single threshold value for entire image
- **Adaptive**: Different thresholds for different image regions

**Threshold Level**
- Range: 0-255 (pixel intensity)
- Pixels above this value become white, below become black
- Lower values = more white pixels
- Higher values = fewer white pixels
- Adjust while watching the "Binary Image" preview

**Noise Removal (Morphological Opening)**
- Range: 0-10
- Removes small white noise pixels
- Higher values remove larger noise spots
- Use when background has speckled noise

**Gap Filling (Morphological Closing)**  
- Range: 0-10
- Fills small black gaps inside white objects
- Makes objects more solid and complete
- Use when objects appear fragmented

**Min Area**
- Range: 1-10,000 pixels
- Minimum size for blob detection
- Smaller blobs are ignored
- Increase to filter out tiny noise objects

**Max Area**
- Range: 1,000-100,000 pixels  
- Maximum size for blob detection
- Larger blobs are ignored
- Auto-set to ROI area when "Lock ROI" is enabled

#### Preview Windows

**Binary Image**
- Shows the processed black and white image
- White areas will be detected as potential blobs
- Adjust threshold settings until objects appear solid white

**Blob Detection**
- Shows detected blobs with colored overlays
- Red rectangles: bounding boxes
- Red dots: blob centers
- Labels show: ID number and area
- Only blobs within min/max area range are shown

#### Blob Tracking

**Track IDs Checkbox**
- Enable persistent blob IDs across frames
- Blobs maintain the same ID as they move
- Useful for tracking individual objects over time

**Clear IDs Button**
- Reset all blob tracking IDs back to 0
- Use when you want to restart ID assignment

### Tab 3: OSC Output

This tab configures Open Sound Control message sending.

#### OSC Settings

**IP Address**
- Destination IP for OSC messages
- Use "127.0.0.1" for local applications
- Use network IP for remote computers

**Port**
- OSC port number (1-65535)
- Common ports: 8000, 9000, 57120
- Must match your receiving application's port

**Protocol**
- **UDP**: Faster, may drop packets under heavy load
- **TCP**: Reliable, guaranteed delivery, slightly slower

**Normalize Coordinates**
- When enabled: coordinates sent as 0.0-1.0 range
- When disabled: coordinates sent as pixel values
- Most applications expect normalized coordinates

#### OSC Field Selection

Choose which blob data to send:

**Center (cx, cy)**
- Blob center point coordinates
- Most commonly used for position tracking

**Position (x, y)**  
- Top-left corner of bounding box
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

#### OSC Address Mapping

**Mapping Table**
- Customize OSC address patterns for each data type
- Use `{id}` placeholder for blob ID number
- Examples:
  - `/blob/{id}/center` → `/blob/0/center`, `/blob/1/center`
  - `/tracker/blob{id}/pos` → `/tracker/blob0/pos`
  - `/object_{id}` → `/object_0`, `/object_1`

**Send Controls**
- **Send on Detection**: Automatically send when blobs are detected
- **Manual Send**: Send current blob data once (for testing)

#### Connection Controls

**Connect/Disconnect Button**
- Click "Connect" to establish OSC connection
- Button changes to "Disconnect" when connected
- Console shows connection status and any errors

**Test Button**
- Sends a test message to verify connection
- Useful for checking if receiver is working

---

## Typical Workflow

### 1. Initial Setup
1. Connect your camera and launch the application
2. Go to **Capture / ROI** tab
3. Select your camera from the dropdown
4. Choose appropriate resolution (1280x720 recommended)

### 2. Configure Detection Area
1. Adjust crop sliders to focus on your area of interest
2. Watch the red overlay to see what will be cropped
3. When satisfied, click **Lock ROI** to prevent accidental changes

### 3. Tune Detection Settings
1. Go to **Threshold & Blobs** tab
2. Adjust **Threshold Level** while watching the Binary Image
3. Fine-tune **Blur**, **Noise Removal**, and **Gap Filling** as needed
4. Set **Min/Max Area** to filter blob sizes (Max Area auto-set when ROI locked)

### 4. Set Up OSC Output
1. Go to **OSC Output** tab  
2. Enter your receiver's **IP Address** and **Port**
3. Choose which data fields to send (Center is most common)
4. Customize OSC addresses if needed
5. Click **Connect**

### 5. Test and Monitor
1. Check the **Blob Detection** preview for accurate tracking
2. Monitor the **Console** for OSC message activity
3. Verify your receiving application gets the data
4. Use **Manual Send** to test individual messages

---

## Configuration File

Settings are automatically saved to `config.json` in the application directory:

```json
{
  "camera": {
    "friendly_name": "Camera 0",
    "resolution": [1280, 720]
  },
  "roi": {
    "left_crop": 50,
    "top_crop": 30,
    "right_crop": 20,
    "bottom_crop": 40,
    "locked": true
  },
  "threshold": {
    "channel": "gray",
    "mode": "global", 
    "value": 127,
    "blur": 3
  },
  "blob": {
    "min_area": 200,
    "max_area": 20000
  },
  "osc": {
    "ip": "127.0.0.1",
    "port": 8000,
    "protocol": "udp",
    "send_center": true,
    "send_position": false
  }
}
```

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
- **Receiver crashes**: Check OSC address format compatibility

### Performance Issues
- **Low FPS**: Reduce camera resolution, simplify ROI
- **High CPU usage**: Increase blur, reduce processing complexity
- **Memory usage**: Restart application periodically for long sessions

## Advanced Usage

### Custom OSC Mappings
Edit the mapping table to create custom address patterns:
- Use `{id}` for blob ID
- Use descriptive paths like `/performer/{id}/position`
- Test with Manual Send before enabling auto-send

### Multi-Object Tracking
- Enable "Track IDs" for persistent object identification
- Use center coordinates for smooth position tracking
- Clear IDs when objects leave and re-enter the scene

### Color-Specific Detection
- Use Red/Green/Blue channels for colored object detection
- Combine with appropriate lighting for best results
- Adjust threshold per color channel as needed

### Integration Examples

**TouchDesigner**: Use CHOPs to receive OSC data
**Max/MSP**: Use `udpreceive` object  
**Pure Data**: Use `netreceive` object
**Processing/p5.js**: Use OSC libraries like oscP5
**Unity**: Use OSC plugins for game integration

---

## Technical Details

### System Requirements
- **OS**: Windows 10/11, macOS 10.14+, Linux (Ubuntu 18.04+)
- **Python**: 3.8 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **CPU**: Dual-core 2GHz minimum for HD processing

### Performance Notes
- **Camera Resolution**: Higher = more detail, lower = better performance
- **ROI Size**: Smaller ROI = faster processing
- **Blur Amount**: Higher blur = slower but cleaner processing
- **OSC Rate**: Fixed at 30 FPS to prevent receiver overload

### File Structure
```
Blob-OSC/
├── blob_osc/           # Main application code
│   ├── app.py         # Application entry point
│   ├── cameras.py     # Camera management
│   ├── processor.py   # Image processing and blob detection
│   ├── osc_client.py  # OSC message sending
│   ├── simple_roi.py  # ROI management
│   ├── settings_manager.py  # Configuration persistence
│   └── ui/            # User interface
│       ├── main_window.py   # Main application window
│       └── widgets.py       # Custom UI widgets
├── config.json        # Settings file (auto-generated)
├── requirements.txt   # Python dependencies
├── run.py            # Application launcher
└── README.md         # This file
```

## Support

For issues, feature requests, or questions:
1. Check the troubleshooting section above
2. Review console messages for error details
3. Verify your OSC receiver configuration
4. Test with minimal settings (default values)

---

## License

This project is open source. See individual file headers for specific licensing information.
