# Blob OSC

A professional real-time computer vision application that detects and tracks objects (blobs) from webcam feeds and streams their data via OSC (Open Sound Control) messages. Features advanced ByteTrack multi-object tracking for robust performance in complex scenarios. Perfect for interactive installations, live performances, motion tracking, and creative coding projects.

## Features

- **Real-time blob detection** from webcam feeds with advanced OpenCV processing
- **Professional tracking** with ByteTrack algorithm - handles occlusions, crossovers, and noise
- **Intelligent camera detection** with descriptive names (resolution, type, model)
- **Configurable Region of Interest (ROI)** with visual cropping and auto-lock features
- **Advanced image processing** with channel selection, threshold modes, and morphological operations
- **Flexible OSC streaming** via UDP/TCP with customizable message formats and field selection
- **Smart rate limiting** (30 FPS) to prevent receiver overload
- **Comprehensive settings persistence** - all configurations saved to JSON
- **Cross-platform support** (Windows, macOS, Linux) with platform-specific optimizations
- **Professional UI** with tabbed interface and real-time previews

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
- `lap`, `cython-bbox`, `scipy`, `filterpy` - ByteTrack dependencies for advanced tracking

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

This tab handles camera setup and region of interest configuration. All capture-related controls are consolidated here for an efficient workflow.

#### Camera Settings

**Camera Dropdown**
- Select your webcam from intelligently named options
- Shows descriptive names like "HD Webcam (720p) #0", "Built-in Webcam", "USB Webcam #1"
- Automatically detects camera capabilities and types
- Settings are automatically saved when changed

**Refresh Button**
- Click to rescan for available cameras
- Use this if you connect a new camera while the app is running
- Updates camera names with latest detection

**Resolution Dropdown**
- Choose camera resolution: 640x480, 1280x720, or 1920x1080
- Higher resolutions provide more detail but use more processing power
- Changes apply immediately to the camera feed
- Optimal resolution depends on your tracking needs vs performance

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
- Automatically sets "Max Area" to ROI width × height (optimal for the selected region)
- Saves current crop values to configuration file
- Prevents accidental changes to a perfected ROI setup
- Essential workflow: adjust ROI → lock when perfect → focus on detection tuning

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

**Min Area (Slider)**
- Range: 1-10,000 pixels
- Minimum size for blob detection
- Smaller blobs are ignored
- Increase to filter out tiny noise objects
- Real-time adjustment with immediate visual feedback

**Max Area (Slider)**
- Range: 1,000-100,000 pixels  
- Maximum size for blob detection
- Larger blobs are ignored
- **Auto-set to ROI area when "Lock ROI" is enabled** - this is the recommended workflow
- Prevents detecting objects larger than your region of interest

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

**Use ByteTrack Checkbox**
- Enable advanced ByteTrack algorithm for robust tracking
- Better handles occlusions, crossovers, and noisy detections
- Recommended for complex scenes with multiple moving objects
- Falls back to simple tracking if ByteTrack fails to initialize

**ByteTrack Parameters**
- **Track Threshold**: Confidence threshold for starting new tracks (0.1-1.0)
- **Track Buffer**: Number of frames to keep lost tracks before deletion (1-100)
- Higher buffer values maintain tracks longer during temporary occlusions

**Clear IDs Button**
- Reset all blob tracking IDs back to 0
- Works with both simple tracking and ByteTrack
- Use when you want to restart ID assignment

### Tab 3: OSC Output

This tab configures Open Sound Control message sending with comprehensive field selection and mapping options.

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
- Blob center point coordinates (centroid of the actual shape)
- Most commonly used for smooth motion tracking
- Better for following object movement and cursor control

**Position (x, y)**  
- Top-left corner of bounding box rectangle
- Useful for precise object positioning and UI element placement
- More predictable for rectangular layouts and anchoring

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
1. Connect your camera and launch the application with `python run.py`
2. Go to **Capture / ROI** tab (all camera and ROI controls are here)
3. Select your camera from the intelligently-named dropdown
4. Choose appropriate resolution (1280x720 recommended for balance of quality/performance)

### 2. Configure Detection Area
1. Adjust crop sliders to focus on your area of interest
2. Watch the red overlay rectangles to see what will be cropped out
3. Yellow outline shows your final detection region
4. **Important**: Click **Lock ROI** when satisfied - this auto-sets optimal Max Area

### 3. Tune Detection Settings
1. Go to **Threshold & Blobs** tab
2. Adjust **Threshold Level** while watching the Binary Image preview
3. Fine-tune **Blur**, **Noise Removal**, and **Gap Filling** as needed
4. **Min/Max Area sliders** are now in the Processing Controls for easy access
5. Enable **ByteTrack** for robust tracking (recommended for complex scenes)

### 4. Set Up OSC Output
1. Go to **OSC Output** tab  
2. Enter your receiver's **IP Address** and **Port**
3. Choose which data fields to send:
   - **Center**: Most common, smooth motion tracking
   - **Position**: Top-left corner, good for UI positioning
   - **Size/Area**: For scale-responsive interactions
4. Customize OSC addresses in the mapping table if needed
5. Click **Connect** to establish connection

### 5. Test and Monitor
1. Check the **Blob Detection** preview for accurate tracking with persistent IDs
2. Monitor the **Console** for OSC message activity and connection status
3. Verify your receiving application gets the data
4. Use **Manual Send** to test individual messages
5. **Clear IDs** to restart tracking when needed

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
    "max_area": 20000,
    "track_ids": true,
    "use_bytetrack": true
  },
  "bytetrack": {
    "track_thresh": 0.5,
    "track_buffer": 30,
    "match_thresh": 0.8,
    "min_box_area": 10
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
- **Low FPS**: Reduce camera resolution, simplify ROI, disable ByteTrack temporarily
- **High CPU usage**: Increase blur, reduce processing complexity, use smaller ROI
- **Memory usage**: Restart application periodically for long sessions
- **ByteTrack slow**: Increase track threshold, reduce track buffer, use simple tracking

## Advanced Usage

### Custom OSC Mappings
Edit the mapping table to create custom address patterns:
- Use `{id}` for blob ID
- Use descriptive paths like `/performer/{id}/position`
- Test with Manual Send before enabling auto-send

### Multi-Object Tracking

**ByteTrack (Recommended)**
- Enable "Use ByteTrack" for advanced tracking algorithm
- Handles occlusions: objects maintain IDs when temporarily hidden
- Manages crossovers: objects keep correct IDs when paths cross
- Robust to noise: filters out false detections automatically
- Based on [ByteTrack research](https://github.com/FoundationVision/ByteTrack) from ECCV 2022

**Simple Tracking (Fallback)**
- Basic centroid-based tracking
- Faster but less robust than ByteTrack
- Automatically used if ByteTrack fails to initialize

**Best Practices**
- Use ByteTrack for complex scenes with multiple objects
- Adjust Track Threshold (0.3-0.7) based on detection quality
- Increase Track Buffer (30-60) for scenes with frequent occlusions
- Clear IDs when starting a new tracking session

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
- **RAM**: 4GB minimum, 8GB recommended for ByteTrack
- **CPU**: Dual-core 2GHz minimum for HD processing, Quad-core recommended for ByteTrack

### Performance Notes
- **Camera Resolution**: Higher = more detail, lower = better performance
- **ROI Size**: Smaller ROI = significantly faster processing
- **ByteTrack**: More CPU intensive but much better tracking quality
- **Tracking Mode**: Simple tracking for performance, ByteTrack for quality
- **OSC Rate**: Fixed at 30 FPS to prevent receiver overload
- **Memory**: ByteTrack uses more memory for track history management

### File Structure
```
Blob-OSC/
├── blob_osc/           # Main application code
│   ├── app.py         # Application entry point
│   ├── cameras.py     # Camera management with intelligent naming
│   ├── processor.py   # Image processing and blob detection
│   ├── bytetrack.py   # ByteTrack multi-object tracking implementation
│   ├── osc_client.py  # OSC message sending with rate limiting
│   ├── simple_roi.py  # ROI management
│   ├── settings_manager.py  # Configuration persistence
│   └── ui/            # User interface
│       ├── main_window.py   # Main application window with tabbed interface
│       └── widgets.py       # Custom UI widgets
├── config.json        # Settings file (auto-generated with all tab settings)
├── requirements.txt   # Python dependencies including ByteTrack
├── run.py            # Application launcher
└── README.md         # This comprehensive documentation
```