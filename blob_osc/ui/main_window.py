"""Main application window with tabbed interface."""

import logging
import time
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QTabWidget, QComboBox, QPushButton, QLabel, QSlider,
                            QSpinBox, QCheckBox, QLineEdit, QTextEdit, QGroupBox,
                            QGridLayout, QFormLayout, QSplitter, QFrame, QButtonGroup,
                            QRadioButton, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
                            QHeaderView, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QAction, QFont, QIcon

from ..cameras import CameraManager, CameraInfo
from ..simple_roi import SimpleROI
from ..processor import ImageProcessor, BlobInfo
from ..osc_client import OSCClient
from ..settings_manager import SettingsManager
from .widgets import VideoPreview, ConsoleWidget, StatusBar, CollapsibleSection


class ProcessingThread(QThread):
    """Thread for image processing to keep UI responsive."""
    
    frame_processed = pyqtSignal(object, object, object, list)  # original_frame, roi_frame, binary_frame, blobs
    stats_updated = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.camera_manager: Optional[CameraManager] = None
        self.roi_manager: Optional[SimpleROI] = None
        self.processor: Optional[ImageProcessor] = None
        self.settings_manager: Optional[SettingsManager] = None
        self.running = False
        self.processing_enabled = True
        
    def setup(self, camera_manager: CameraManager, roi_manager: SimpleROI,
              processor: ImageProcessor, settings_manager: SettingsManager):
        """Setup the processing thread with required components."""
        self.camera_manager = camera_manager
        self.roi_manager = roi_manager
        self.processor = processor
        self.settings_manager = settings_manager
    
    def run(self):
        """Main processing loop."""
        self.running = True
        
        while self.running:
            if not self.processing_enabled or not self.camera_manager:
                self.msleep(50)
                continue
            
            # Get frame from camera
            frame = self.camera_manager.get_frame()
            if frame is None:
                self.msleep(16)  # ~60 FPS
                continue
            
            try:
                # Apply ROI
                roi_frame = self.roi_manager.apply_crop(frame) if self.roi_manager else frame
                if roi_frame is None:
                    self.msleep(16)
                    continue
                
                # Process image
                threshold_config = self.settings_manager.get_threshold_config()
                morph_config = self.settings_manager.get_morph_config()
                blob_config = self.settings_manager.get_blob_config()
                
                binary_frame, blobs = self.processor.process_image(
                    roi_frame,
                    threshold_config.__dict__,
                    morph_config.__dict__,
                    blob_config.__dict__
                )
                
                # Emit results - pass both original frame and cropped frame
                self.frame_processed.emit(frame, roi_frame, binary_frame, blobs)
                
                # Emit stats
                camera_stats = self.camera_manager.get_stats()
                processor_stats = self.processor.get_tracker_stats()
                stats = {**camera_stats, **processor_stats}
                self.stats_updated.emit(stats)
                
            except Exception as e:
                logging.error(f"Processing error: {e}")
            
            self.msleep(16)  # ~60 FPS
    
    def stop(self):
        """Stop the processing thread."""
        self.running = False
        self.wait()
    
    def set_processing_enabled(self, enabled: bool):
        """Enable or disable processing."""
        self.processing_enabled = enabled


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Core components
        self.camera_manager = CameraManager()
        self.roi_manager = SimpleROI()
        self.processor = ImageProcessor()
        self.osc_client: Optional[OSCClient] = None
        self.settings_manager = SettingsManager()
        
        # Processing thread
        self.processing_thread = ProcessingThread()
        self.processing_thread.setup(
            self.camera_manager, self.roi_manager, 
            self.processor, self.settings_manager
        )
        
        # UI state
        self.current_frame = None
        self.current_roi_frame = None
        self.current_binary = None
        self.current_blobs: List[BlobInfo] = []
        self.cameras: List[CameraInfo] = []
        self._loading_settings = False
        
        # OSC rate limiting
        self.last_osc_send_time = 0.0
        self.osc_send_interval = 1.0 / 30.0  # Default 30 FPS
        
        
        # Setup UI first
        self.setup_ui()
        self.setup_connections()

        # Set overlay callback for ROI preview
        self.roi_preview.set_overlay_callback(
            lambda img: self.roi_manager.draw_crop_overlay(img)
        )

        # Initialize lock state (default unlocked)
        self._apply_roi_lock_state(False)

        # Load settings after UI and connections are set up
        self.load_settings()
        self.refresh_cameras()

        # Initialize ByteTrack if available
        bytetrack_config = self.settings_manager.get_bytetrack_config()
        blob_config = self.settings_manager.get_blob_config()
        
        if blob_config.use_bytetrack:
            success = self.processor.initialize_bytetrack(
                track_thresh=bytetrack_config.track_thresh,
                track_buffer=bytetrack_config.track_buffer,
                match_thresh=bytetrack_config.match_thresh,
                min_box_area=bytetrack_config.min_box_area
            )
            if success:
                self.processor.set_tracking_mode(True)
                self.console.append_message("ByteTrack initialized", "success")
            else:
                self.console.append_message("ByteTrack failed to initialize, using simple tracking", "warning")

        # Auto-connect to OSC if enabled
        osc_config = self.settings_manager.get_osc_config()
        if osc_config.auto_connect:
            # Use QTimer to delay auto-connect until UI is fully loaded
            QTimer.singleShot(1000, self.auto_connect_osc)

        # Start processing
        self.processing_thread.start()
    
    def setup_ui(self):
        """Setup the main UI."""
        self.setWindowTitle("Blob OSC")
        self.setMinimumSize(1200, 800)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Central widget with tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Main tabs
        self.tab_widget = QTabWidget()
        
        # Tab 1: Capture/ROI
        self.roi_tab = self.create_roi_tab()
        self.tab_widget.addTab(self.roi_tab, "1. Capture / ROI")
        
        # Tab 2: Threshold & Blob Detection
        self.threshold_tab = self.create_threshold_tab()
        self.tab_widget.addTab(self.threshold_tab, "2. Threshold & Blobs")
        
        # Tab 3: OSC Output
        self.osc_tab = self.create_osc_tab()
        self.tab_widget.addTab(self.osc_tab, "3. OSC Output")
        
        layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_bar = StatusBar()
        layout.addWidget(self.status_bar)
    
    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        save_action = QAction("Save Settings", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_settings)
        file_menu.addAction(save_action)
        
        load_action = QAction("Load Settings", self)
        load_action.triggered.connect(self.load_settings_dialog)
        file_menu.addAction(load_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_roi_tab(self):
        """Create the ROI selection tab."""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Left side: Video preview
        preview_group = QGroupBox("Camera Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.roi_preview = VideoPreview()
        self.roi_preview.setMinimumSize(640, 480)
        preview_layout.addWidget(self.roi_preview)
        
        # Preview controls
        preview_controls = QHBoxLayout()
        self.pause_button = QPushButton("Pause")
        self.pause_button.setCheckable(True)
        preview_controls.addWidget(self.pause_button)
        
        preview_controls.addStretch()
        preview_layout.addLayout(preview_controls)
        
        layout.addWidget(preview_group, 2)
        
        # Right side: Camera and ROI controls
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        
        # Camera settings group
        camera_group = QGroupBox("Camera Settings")
        camera_layout = QGridLayout(camera_group)
        
        camera_layout.addWidget(QLabel("Camera:"), 0, 0)
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(200)
        camera_layout.addWidget(self.camera_combo, 0, 1)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_cameras)
        camera_layout.addWidget(self.refresh_button, 0, 2)
        
        camera_layout.addWidget(QLabel("Resolution:"), 1, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["640x480", "1280x720", "1920x1080"])
        self.resolution_combo.setCurrentText("1280x720")
        camera_layout.addWidget(self.resolution_combo, 1, 1, 1, 2)
        
        controls_layout.addWidget(camera_group)
        
        # ROI controls group
        roi_group = QGroupBox("Region of Interest")
        roi_layout = QVBoxLayout(roi_group)
        
        # ROI info
        self.roi_info = QLabel("ROI: Not set")
        roi_layout.addWidget(self.roi_info)
        
        # ROI controls with sliders (pixel-based cropping)
        roi_controls = QGridLayout()
        
        # Left crop slider
        roi_controls.addWidget(QLabel("Left Crop px:"), 0, 0)
        self.left_slider = QSlider(Qt.Orientation.Horizontal)
        self.left_slider.setRange(0, 1000)
        self.left_slider.setValue(0)
        self.left_slider.setTracking(True)  # Keep tracking for real-time preview
        roi_controls.addWidget(self.left_slider, 0, 1)
        self.left_label = QLabel("0px")
        self.left_label.setMinimumWidth(60)
        roi_controls.addWidget(self.left_label, 0, 2)
        
        # Top crop slider
        roi_controls.addWidget(QLabel("Top Crop px:"), 1, 0)
        self.top_slider = QSlider(Qt.Orientation.Horizontal)
        self.top_slider.setRange(0, 1000)
        self.top_slider.setValue(0)
        self.top_slider.setTracking(True)  # Keep tracking for real-time preview
        roi_controls.addWidget(self.top_slider, 1, 1)
        self.top_label = QLabel("0px")
        self.top_label.setMinimumWidth(60)
        roi_controls.addWidget(self.top_label, 1, 2)
        
        # Right crop slider
        roi_controls.addWidget(QLabel("Right Crop px:"), 2, 0)
        self.right_slider = QSlider(Qt.Orientation.Horizontal)
        self.right_slider.setRange(0, 1000)
        self.right_slider.setValue(0)
        self.right_slider.setTracking(True)  # Keep tracking for real-time preview
        roi_controls.addWidget(self.right_slider, 2, 1)
        self.right_label = QLabel("0px")
        self.right_label.setMinimumWidth(60)
        roi_controls.addWidget(self.right_label, 2, 2)
        
        # Bottom crop slider
        roi_controls.addWidget(QLabel("Bottom Crop px:"), 3, 0)
        self.bottom_slider = QSlider(Qt.Orientation.Horizontal)
        self.bottom_slider.setRange(0, 1000)
        self.bottom_slider.setValue(0)
        self.bottom_slider.setTracking(True)  # Keep tracking for real-time preview
        roi_controls.addWidget(self.bottom_slider, 3, 1)
        self.bottom_label = QLabel("0px")
        self.bottom_label.setMinimumWidth(60)
        roi_controls.addWidget(self.bottom_label, 3, 2)
        
        roi_layout.addLayout(roi_controls)
        
        # ROI buttons
        roi_buttons = QVBoxLayout()
        
        self.use_roi_button = QPushButton("Use ROI")
        roi_buttons.addWidget(self.use_roi_button)
        
        self.reset_roi_button = QPushButton("Reset ROI")
        roi_buttons.addWidget(self.reset_roi_button)
        
        self.lock_roi_checkbox = QCheckBox("Lock ROI")
        roi_buttons.addWidget(self.lock_roi_checkbox)
        
        roi_buttons.addStretch()
        roi_layout.addLayout(roi_buttons)
        
        controls_layout.addWidget(roi_group)
        controls_layout.addStretch()  # Push controls to top
        
        layout.addWidget(controls_widget, 1)
        
        return tab
    
    def create_threshold_tab(self):
        """Create the threshold and blob detection tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Top: Controls
        controls_group = QGroupBox("Processing Controls")
        controls_layout = QGridLayout(controls_group)
        
        # Channel selection
        controls_layout.addWidget(QLabel("Channel:"), 0, 0)
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["Gray", "Red", "Green", "Blue"])
        self.channel_combo.setToolTip("Select which color channel to use for processing")
        controls_layout.addWidget(self.channel_combo, 0, 1)
        
        # Blur
        controls_layout.addWidget(QLabel("Blur:"), 0, 2)
        self.blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.blur_slider.setRange(0, 15)
        self.blur_slider.setValue(3)
        self.blur_slider.setToolTip("Apply Gaussian blur to reduce noise before thresholding")
        controls_layout.addWidget(self.blur_slider, 0, 3)
        
        self.blur_label = QLabel("3")
        controls_layout.addWidget(self.blur_label, 0, 4)
        
        # Threshold type
        threshold_group = QButtonGroup()
        self.global_radio = QRadioButton("Global")
        self.global_radio.setChecked(True)
        self.global_radio.setToolTip("Use a single threshold value for the entire image")
        self.adaptive_radio = QRadioButton("Adaptive")
        self.adaptive_radio.setToolTip("Use different threshold values for different parts of the image")
        threshold_group.addButton(self.global_radio)
        threshold_group.addButton(self.adaptive_radio)
        
        controls_layout.addWidget(QLabel("Threshold:"), 1, 0)
        controls_layout.addWidget(self.global_radio, 1, 1)
        controls_layout.addWidget(self.adaptive_radio, 1, 2)
        
        # Invert toggle
        self.invert_threshold_checkbox = QCheckBox("Invert")
        self.invert_threshold_checkbox.setToolTip("Invert the threshold image (swap black and white)")
        controls_layout.addWidget(self.invert_threshold_checkbox, 1, 3)
        
        # Threshold value
        controls_layout.addWidget(QLabel("Threshold Level:"), 2, 0)
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 255)
        self.threshold_slider.setValue(127)
        self.threshold_slider.setToolTip("Pixel intensity threshold (0-255). Pixels above this value become white, below become black")
        controls_layout.addWidget(self.threshold_slider, 2, 1, 1, 3)
        
        self.threshold_label = QLabel("127")
        controls_layout.addWidget(self.threshold_label, 2, 4)
        
        # Morphological operations
        controls_layout.addWidget(QLabel("Noise Removal:"), 3, 0)
        self.morph_open_slider = QSlider(Qt.Orientation.Horizontal)
        self.morph_open_slider.setRange(0, 10)
        self.morph_open_slider.setToolTip("Remove small noise pixels (morphological opening)")
        controls_layout.addWidget(self.morph_open_slider, 3, 1, 1, 3)
        
        self.morph_open_label = QLabel("0")
        controls_layout.addWidget(self.morph_open_label, 3, 4)
        
        controls_layout.addWidget(QLabel("Gap Filling:"), 4, 0)
        self.morph_close_slider = QSlider(Qt.Orientation.Horizontal)
        self.morph_close_slider.setRange(0, 10)
        self.morph_close_slider.setToolTip("Fill small gaps in objects (morphological closing)")
        controls_layout.addWidget(self.morph_close_slider, 4, 1, 1, 3)
        
        self.morph_close_label = QLabel("0")
        controls_layout.addWidget(self.morph_close_label, 4, 4)
        
        # Blob area filtering
        controls_layout.addWidget(QLabel("Min Area:"), 5, 0)
        self.min_area_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_area_slider.setRange(0, 100000)  # 0-100000 for 0.0-1.0 normalized values (0.00001 steps)
        self.min_area_slider.setValue(2000)  # Default to 0.02 (2% of ROI area)
        self.min_area_slider.setToolTip("Minimum blob area as fraction of ROI area (0.0-1.0)")
        controls_layout.addWidget(self.min_area_slider, 5, 1, 1, 3)
        
        self.min_area_label = QLabel("0.02000")
        controls_layout.addWidget(self.min_area_label, 5, 4)
        
        controls_layout.addWidget(QLabel("Max Area:"), 6, 0)
        self.max_area_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_area_slider.setRange(0, 100000)  # 0-100000 for 0.0-1.0 normalized values (0.00001 steps)
        self.max_area_slider.setValue(100000)  # Default to 1.0 (100% of ROI area)
        self.max_area_slider.setToolTip("Maximum blob area as fraction of ROI area (0.0-1.0)")
        controls_layout.addWidget(self.max_area_slider, 6, 1, 1, 3)
        
        self.max_area_label = QLabel("1.00000")
        controls_layout.addWidget(self.max_area_label, 6, 4)
        
        layout.addWidget(controls_group, 0)  # No stretch - keep compact
        
        # Middle: Preview images with proper scaling - give this the most space
        preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        preview_splitter.setChildrenCollapsible(False)
        
        # Binary preview
        binary_group = QGroupBox("Binary Image")
        binary_layout = QVBoxLayout(binary_group)
        binary_layout.setContentsMargins(5, 5, 5, 5)
        
        self.binary_preview = VideoPreview()
        self.binary_preview.setMinimumSize(320, 240)
        # Remove maximum size constraint to allow proper scaling
        binary_layout.addWidget(self.binary_preview)
        
        preview_splitter.addWidget(binary_group)
        
        # Overlay preview
        overlay_group = QGroupBox("Blob Detection")
        overlay_layout = QVBoxLayout(overlay_group)
        overlay_layout.setContentsMargins(5, 5, 5, 5)
        
        self.overlay_preview = VideoPreview()
        self.overlay_preview.setMinimumSize(320, 240)
        # Remove maximum size constraint to allow proper scaling
        overlay_layout.addWidget(self.overlay_preview)
        
        preview_splitter.addWidget(overlay_group)
        
        # Set equal sizes for both preview panes
        preview_splitter.setSizes([1, 1])
        
        # Give the preview area the most space in the layout
        layout.addWidget(preview_splitter, 1)  # stretch factor of 1
        
        # Bottom: Bounding box controls
        blob_group = QGroupBox("Bounding Boxes")
        blob_layout = QVBoxLayout(blob_group)
        
        # First row: basic tracking controls
        basic_tracking_layout = QHBoxLayout()
        
        self.track_ids_checkbox = QCheckBox("Track IDs")
        self.track_ids_checkbox.setChecked(True)
        self.track_ids_checkbox.setToolTip("Enable blob ID tracking across frames")
        basic_tracking_layout.addWidget(self.track_ids_checkbox)
        
        self.use_bytetrack_checkbox = QCheckBox("Use ByteTrack")
        self.use_bytetrack_checkbox.setChecked(True)
        self.use_bytetrack_checkbox.setToolTip("Use advanced ByteTrack algorithm for better tracking across occlusions")
        basic_tracking_layout.addWidget(self.use_bytetrack_checkbox)
        
        self.clear_ids_button = QPushButton("Clear IDs")
        self.clear_ids_button.setToolTip("Reset all blob tracking IDs")
        basic_tracking_layout.addWidget(self.clear_ids_button)
        
        basic_tracking_layout.addStretch()  # Push controls to the left
        blob_layout.addLayout(basic_tracking_layout)
        
        # Second row: ByteTrack parameters (collapsible)
        bytetrack_layout = QHBoxLayout()
        
        bytetrack_layout.addWidget(QLabel("Track Threshold:"))
        self.track_thresh_spin = QDoubleSpinBox()
        self.track_thresh_spin.setRange(0.1, 1.0)
        self.track_thresh_spin.setSingleStep(0.1)
        self.track_thresh_spin.setValue(0.5)
        self.track_thresh_spin.setToolTip("Confidence threshold for starting new tracks")
        bytetrack_layout.addWidget(self.track_thresh_spin)
        
        bytetrack_layout.addWidget(QLabel("Track Buffer:"))
        self.track_buffer_spin = QSpinBox()
        self.track_buffer_spin.setRange(1, 100)
        self.track_buffer_spin.setValue(30)
        self.track_buffer_spin.setToolTip("Frames to keep lost tracks before deletion")
        bytetrack_layout.addWidget(self.track_buffer_spin)
        
        bytetrack_layout.addStretch()
        blob_layout.addLayout(bytetrack_layout)
        
        layout.addWidget(blob_group, 0)  # No stretch - keep compact
        
        return tab
    
    def create_osc_tab(self):
        """Create the OSC output tab."""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Left side: OSC settings
        settings_group = QGroupBox("OSC Settings")
        settings_layout = QFormLayout(settings_group)
        
        self.osc_ip = QLineEdit("127.0.0.1")
        settings_layout.addRow("IP Address:", self.osc_ip)
        
        self.osc_port = QSpinBox()
        self.osc_port.setRange(1, 65535)
        self.osc_port.setValue(8000)
        settings_layout.addRow("Port:", self.osc_port)
        
        self.osc_protocol = QComboBox()
        self.osc_protocol.addItems(["UDP", "TCP"])
        settings_layout.addRow("Protocol:", self.osc_protocol)
        
        self.normalize_coords = QCheckBox("Normalize Coordinates")
        self.normalize_coords.setChecked(True)
        settings_layout.addRow(self.normalize_coords)
        
        self.auto_connect_checkbox = QCheckBox("Auto-Connect on Startup")
        self.auto_connect_checkbox.setChecked(False)
        self.auto_connect_checkbox.setToolTip("Automatically connect to OSC destination when application starts")
        settings_layout.addRow(self.auto_connect_checkbox)
        
        # Connection controls
        conn_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.test_button = QPushButton("Test")
        conn_layout.addWidget(self.connect_button)
        conn_layout.addWidget(self.test_button)
        settings_layout.addRow(conn_layout)
        
        layout.addWidget(settings_group)
        
        # Middle: Field selection and mapping
        mapping_group = QGroupBox("OSC Mapping")
        mapping_layout = QVBoxLayout(mapping_group)
        
        # Field checkboxes
        fields_layout = QGridLayout()
        
        self.send_center = QCheckBox("Center (cx, cy)")
        self.send_center.setChecked(True)
        fields_layout.addWidget(self.send_center, 0, 0)
        
        self.send_position = QCheckBox("Position (x, y)")
        fields_layout.addWidget(self.send_position, 0, 1)
        
        self.send_size = QCheckBox("Size (w, h)")
        fields_layout.addWidget(self.send_size, 1, 0)
        
        self.send_area = QCheckBox("Area")
        fields_layout.addWidget(self.send_area, 1, 1)
        
        self.send_polygon = QCheckBox("Polygon")
        fields_layout.addWidget(self.send_polygon, 2, 0)
        
        mapping_layout.addLayout(fields_layout)
        
        # Mapping table
        self.mapping_table = QTableWidget(5, 2)
        self.mapping_table.setHorizontalHeaderLabels(["Field", "OSC Address"])
        self.mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Default mappings
        mappings = [
            ("Center", "/blob/{id}/center"),
            ("Position", "/blob/{id}/pos"),
            ("Size", "/blob/{id}/size"),
            ("Area", "/blob/{id}/area"),
            ("Polygon", "/blob/{id}/poly")
        ]
        
        for i, (field, address) in enumerate(mappings):
            self.mapping_table.setItem(i, 0, QTableWidgetItem(field))
            self.mapping_table.setItem(i, 1, QTableWidgetItem(address))
        
        mapping_layout.addWidget(self.mapping_table)
        
        # Send controls
        send_layout = QHBoxLayout()
        
        self.send_on_detect = QCheckBox("Send on Detection")
        self.send_on_detect.setChecked(True)
        send_layout.addWidget(self.send_on_detect)
        
        self.manual_send_button = QPushButton("Manual Send")
        send_layout.addWidget(self.manual_send_button)
        
        mapping_layout.addLayout(send_layout)
        
        layout.addWidget(mapping_group)
        
        # Right side: Console
        console_group = QGroupBox("Console")
        console_layout = QVBoxLayout(console_group)
        
        self.console = ConsoleWidget()
        console_layout.addWidget(self.console)
        
        console_controls = QHBoxLayout()
        self.clear_console_button = QPushButton("Clear")
        self.clear_console_button.clicked.connect(self.console.clear_console)
        console_controls.addWidget(self.clear_console_button)
        console_controls.addStretch()
        
        console_layout.addLayout(console_controls)
        
        layout.addWidget(console_group)
        
        return tab
    
    def setup_connections(self):
        """Setup signal connections."""
        # Camera selection
        self.camera_combo.currentTextChanged.connect(self.on_camera_changed)
        self.resolution_combo.currentTextChanged.connect(self.on_resolution_changed)
        
        # ROI controls
        self.use_roi_button.clicked.connect(self.on_use_roi)
        self.reset_roi_button.clicked.connect(self.on_reset_roi)
        self.lock_roi_checkbox.toggled.connect(self.on_roi_lock_changed)
        
        # ROI sliders - only update on release to prevent accumulation
        self.left_slider.sliderReleased.connect(self.on_roi_slider_released)
        self.top_slider.sliderReleased.connect(self.on_roi_slider_released)
        self.right_slider.sliderReleased.connect(self.on_roi_slider_released)
        self.bottom_slider.sliderReleased.connect(self.on_roi_slider_released)

        # For real-time visual feedback, connect valueChanged to preview update only
        self.left_slider.valueChanged.connect(self.on_roi_slider_preview)
        self.top_slider.valueChanged.connect(self.on_roi_slider_preview)
        self.right_slider.valueChanged.connect(self.on_roi_slider_preview)
        self.bottom_slider.valueChanged.connect(self.on_roi_slider_preview)
        
        # Processing controls
        self.pause_button.toggled.connect(self.on_pause_toggled)
        self.channel_combo.currentTextChanged.connect(self.on_processing_changed)
        self.blur_slider.valueChanged.connect(self.on_blur_changed)
        self.global_radio.toggled.connect(self.on_processing_changed)
        self.adaptive_radio.toggled.connect(self.on_processing_changed)
        self.invert_threshold_checkbox.toggled.connect(self.on_invert_changed)
        self.threshold_slider.valueChanged.connect(self.on_threshold_changed)
        self.morph_open_slider.valueChanged.connect(self.on_morph_open_changed)
        self.morph_close_slider.valueChanged.connect(self.on_morph_close_changed)
        self.min_area_slider.valueChanged.connect(self.on_min_area_changed)
        self.max_area_slider.valueChanged.connect(self.on_max_area_changed)
        
        # Blob controls
        self.track_ids_checkbox.toggled.connect(self.on_blob_config_changed)
        self.use_bytetrack_checkbox.toggled.connect(self.on_blob_config_changed)
        self.clear_ids_button.clicked.connect(self.on_clear_ids)
        
        # ByteTrack parameters
        self.track_thresh_spin.valueChanged.connect(self.on_bytetrack_config_changed)
        self.track_buffer_spin.valueChanged.connect(self.on_bytetrack_config_changed)
        
        # OSC controls
        self.connect_button.clicked.connect(self.on_osc_connect)
        self.test_button.clicked.connect(self.on_osc_test)
        self.manual_send_button.clicked.connect(self.on_manual_send)
        self.osc_ip.textChanged.connect(self.on_osc_config_changed)
        self.osc_port.valueChanged.connect(self.on_osc_config_changed)
        self.osc_protocol.currentTextChanged.connect(self.on_osc_config_changed)
        
        # OSC field selection checkboxes
        self.send_center.toggled.connect(self.on_osc_config_changed)
        self.send_position.toggled.connect(self.on_osc_config_changed)
        self.send_size.toggled.connect(self.on_osc_config_changed)
        self.send_area.toggled.connect(self.on_osc_config_changed)
        self.send_polygon.toggled.connect(self.on_osc_config_changed)
        self.send_on_detect.toggled.connect(self.on_osc_config_changed)
        self.normalize_coords.toggled.connect(self.on_osc_config_changed)
        self.auto_connect_checkbox.toggled.connect(self.on_osc_config_changed)
        
        # OSC mapping table changes
        self.mapping_table.itemChanged.connect(self.on_mapping_table_changed)
        
        # Processing thread
        self.processing_thread.frame_processed.connect(self.on_frame_processed)
        self.processing_thread.stats_updated.connect(self.on_stats_updated)
    
    @pyqtSlot()
    def refresh_cameras(self):
        """Refresh the camera list."""
        self.cameras = self.camera_manager.list_cameras()
        self.camera_combo.clear()
        
        for camera in self.cameras:
            self.camera_combo.addItem(str(camera))
        
        if self.cameras:
            self.console.append_message(f"Found {len(self.cameras)} cameras", "info")
        else:
            self.console.append_message("No cameras found", "warning")
    
    @pyqtSlot(str)
    def on_camera_changed(self, camera_name: str):
        """Handle camera selection change."""
        if not self.cameras:
            return
        
        # Find camera by name
        selected_camera = None
        for camera in self.cameras:
            if str(camera) == camera_name:
                selected_camera = camera
                break
        
        if selected_camera:
            if self.camera_manager.open_camera(selected_camera.id):
                self.console.append_message(f"Opened camera: {camera_name}", "success")
                self.camera_manager.start_capture()
                
                # Update settings
                self.settings_manager.update_camera_config(
                    friendly_name=selected_camera.friendly_name,
                    backend_id=selected_camera.backend_id
                )
            else:
                self.console.append_message(f"Failed to open camera: {camera_name}", "error")
    
    @pyqtSlot(str)
    def on_resolution_changed(self, resolution: str):
        """Handle resolution change."""
        if "x" in resolution:
            try:
                width, height = map(int, resolution.split("x"))
                if self.camera_manager.set_resolution(width, height):
                    self.console.append_message(f"Set resolution to {resolution}", "info")
                    self.settings_manager.update_camera_config(resolution=[width, height])
            except ValueError:
                pass
    
    # ROI event handlers
    @pyqtSlot()
    def on_roi_slider_preview(self):
        """Handle ROI slider preview - real-time visual feedback only."""
        # Get current slider values for preview
        left = self.left_slider.value()
        top = self.top_slider.value()
        right = self.right_slider.value()
        bottom = self.bottom_slider.value()

        # Update labels in real-time
        self.left_label.setText(f"{left}px")
        self.top_label.setText(f"{top}px")
        self.right_label.setText(f"{right}px")
        self.bottom_label.setText(f"{bottom}px")

        # Update ROI manager for visual preview only
        self.roi_manager.set_crop_values(left, top, right, bottom)

    @pyqtSlot()
    def on_roi_slider_released(self):
        """Handle ROI slider release - commit changes and save config."""
        # Get final slider values
        left = self.left_slider.value()
        top = self.top_slider.value()
        right = self.right_slider.value()
        bottom = self.bottom_slider.value()

        # Update ROI manager (this persists the changes)
        self.roi_manager.set_crop_values(left, top, right, bottom)

        # Save to config - include crop values
        x, y, w, h = self.roi_manager.get_roi_bounds()
        self.settings_manager.update_roi_config(
            x=x, y=y, w=w, h=h, 
            locked=self.lock_roi_checkbox.isChecked(),
            left_crop=left, top_crop=top, 
            right_crop=right, bottom_crop=bottom
        )
    
    @pyqtSlot()
    def on_use_roi(self):
        """Use current ROI settings."""
        x, y, w, h = self.roi_manager.get_roi_bounds()
        self.settings_manager.update_roi_config(x=x, y=y, w=w, h=h)
        self.console.append_message("ROI settings saved", "success")
    
    @pyqtSlot()
    def on_reset_roi(self):
        """Reset ROI to full frame."""
        self.roi_manager.reset()

        # Reset sliders (block signals to prevent feedback)
        self.left_slider.blockSignals(True)
        self.top_slider.blockSignals(True)
        self.right_slider.blockSignals(True)
        self.bottom_slider.blockSignals(True)

        self.left_slider.setValue(0)
        self.top_slider.setValue(0)
        self.right_slider.setValue(0)
        self.bottom_slider.setValue(0)

        self.left_slider.blockSignals(False)
        self.top_slider.blockSignals(False)
        self.right_slider.blockSignals(False)
        self.bottom_slider.blockSignals(False)

        # Update labels
        self.left_label.setText("0px")
        self.top_label.setText("0px")
        self.right_label.setText("0px")
        self.bottom_label.setText("0px")

        # Save to config - include reset crop values (all zeros)
        x, y, w, h = self.roi_manager.get_roi_bounds()
        self.settings_manager.update_roi_config(
            x=x, y=y, w=w, h=h, 
            locked=self.lock_roi_checkbox.isChecked(),
            left_crop=0, top_crop=0, right_crop=0, bottom_crop=0
        )
        
        self.update_roi_info()
    
    def _apply_roi_lock_state(self, locked: bool):
        """Apply ROI lock state to UI without saving."""
        # Enable/disable ROI sliders based on lock state
        self.left_slider.setEnabled(not locked)
        self.top_slider.setEnabled(not locked)
        self.right_slider.setEnabled(not locked)
        self.bottom_slider.setEnabled(not locked)
        
        # Also disable the ROI control buttons when locked
        self.use_roi_button.setEnabled(not locked)
        self.reset_roi_button.setEnabled(not locked)

    @pyqtSlot(bool)
    def on_roi_lock_changed(self, locked: bool):
        """Handle ROI lock change from user interaction."""
        # Apply the UI state
        self._apply_roi_lock_state(locked)
        
        # When locking, save current slider values to config
        if locked:
            left_crop = self.left_slider.value()
            top_crop = self.top_slider.value()
            right_crop = self.right_slider.value()
            bottom_crop = self.bottom_slider.value()
            
            # Get ROI bounds for x, y, w, h values
            x, y, w, h = self.roi_manager.get_roi_bounds()
            
            # Calculate ROI area for normalization
            roi_area = w * h
            if roi_area > 0:
                # Keep current normalized values when ROI changes
                # The pixel values will be recalculated based on new ROI area
                current_min_normalized = self.min_area_slider.value() / 100000.0
                current_max_normalized = self.max_area_slider.value() / 100000.0
                
                # Update labels with current normalized values
                self.min_area_label.setText(f"{current_min_normalized:.5f}")
                self.max_area_label.setText(f"{current_max_normalized:.5f}")
                
                # Update the settings with converted pixel values
                self.settings_manager.update_blob_config(
                    min_area=self._normalized_to_pixel_area(current_min_normalized, roi_area),
                    max_area=self._normalized_to_pixel_area(current_max_normalized, roi_area),
                    track_ids=self.track_ids_checkbox.isChecked()
                )
            
            # Save all ROI settings including crop values
            self.settings_manager.update_roi_config(
                locked=locked,
                left_crop=left_crop,
                top_crop=top_crop,
                right_crop=right_crop,
                bottom_crop=bottom_crop,
                x=x, y=y, w=w, h=h
            )
        else:
            # Just save the lock state when unlocking
            self.settings_manager.update_roi_config(locked=locked)
    
    def update_roi_info(self):
        """Update ROI information display."""
        x, y, w, h = self.roi_manager.get_roi_bounds()
        left, top, right, bottom = self.roi_manager.get_crop_values()
        self.roi_info.setText(f"ROI: ({x}, {y}) {w}x{h} - Crop: L:{left}px T:{top}px R:{right}px B:{bottom}px")
    
    
    # Processing event handlers
    @pyqtSlot(bool)
    def on_pause_toggled(self, paused: bool):
        """Handle pause toggle."""
        self.processing_thread.set_processing_enabled(not paused)
        self.pause_button.setText("Resume" if paused else "Pause")
    
    @pyqtSlot()
    def on_processing_changed(self):
        """Handle processing parameter changes."""
        channel = self.channel_combo.currentText().lower()
        mode = "global" if self.global_radio.isChecked() else "adaptive"
        
        self.settings_manager.update_threshold_config(
            channel=channel,
            mode=mode
        )
    
    @pyqtSlot(bool)
    def on_invert_changed(self, checked: bool):
        """Handle invert threshold toggle."""
        self.settings_manager.update_threshold_config(invert=checked)
    
    @pyqtSlot(int)
    def on_blur_changed(self, value: int):
        """Handle blur change."""
        self.blur_label.setText(str(value))
        self.settings_manager.update_threshold_config(blur=value)
    
    @pyqtSlot(int)
    def on_threshold_changed(self, value: int):
        """Handle threshold change."""
        self.threshold_label.setText(str(value))
        self.settings_manager.update_threshold_config(value=value)
    
    @pyqtSlot(int)
    def on_morph_open_changed(self, value: int):
        """Handle morphological open change."""
        self.morph_open_label.setText(str(value))
        self.settings_manager.update_morph_config(open=value)
    
    @pyqtSlot(int)
    def on_morph_close_changed(self, value: int):
        """Handle morphological close change."""
        self.morph_close_label.setText(str(value))
        self.settings_manager.update_morph_config(close=value)
    
    def _normalized_to_pixel_area(self, normalized_value: float, roi_area: int) -> int:
        """Convert normalized area value (0.0-1.0) to pixel area."""
        return int(normalized_value * roi_area)
    
    def _pixel_to_normalized_area(self, pixel_value: int, roi_area: int) -> float:
        """Convert pixel area to normalized value (0.0-1.0)."""
        if roi_area <= 0:
            return 0.0
        return pixel_value / roi_area

    @pyqtSlot(int)
    def on_min_area_changed(self, value: int):
        """Handle min area change."""
        normalized_value = value / 100000.0  # Convert 0-100000 to 0.0-1.0
        self.min_area_label.setText(f"{normalized_value:.5f}")
        
        # Get current ROI area for conversion
        roi_bounds = self.roi_manager.get_roi_bounds()
        roi_area = roi_bounds[2] * roi_bounds[3]  # w * h
        
        # Convert to pixel value for settings
        pixel_min_area = self._normalized_to_pixel_area(normalized_value, roi_area)
        
        self.settings_manager.update_blob_config(
            min_area=pixel_min_area,
            max_area=self._normalized_to_pixel_area(self.max_area_slider.value() / 100000.0, roi_area),
            track_ids=self.track_ids_checkbox.isChecked()
        )
    
    @pyqtSlot(int)
    def on_max_area_changed(self, value: int):
        """Handle max area change."""
        normalized_value = value / 100000.0  # Convert 0-100000 to 0.0-1.0
        self.max_area_label.setText(f"{normalized_value:.5f}")
        
        # Get current ROI area for conversion
        roi_bounds = self.roi_manager.get_roi_bounds()
        roi_area = roi_bounds[2] * roi_bounds[3]  # w * h
        
        # Convert to pixel value for settings
        pixel_max_area = self._normalized_to_pixel_area(normalized_value, roi_area)
        
        self.settings_manager.update_blob_config(
            min_area=self._normalized_to_pixel_area(self.min_area_slider.value() / 100000.0, roi_area),
            max_area=pixel_max_area,
            track_ids=self.track_ids_checkbox.isChecked()
        )
    
    @pyqtSlot()
    def on_blob_config_changed(self):
        """Handle blob configuration changes."""
        # Get current ROI area for conversion
        roi_bounds = self.roi_manager.get_roi_bounds()
        roi_area = roi_bounds[2] * roi_bounds[3]  # w * h
        
        self.settings_manager.update_blob_config(
            min_area=self._normalized_to_pixel_area(self.min_area_slider.value() / 100000.0, roi_area),
            max_area=self._normalized_to_pixel_area(self.max_area_slider.value() / 100000.0, roi_area),
            track_ids=self.track_ids_checkbox.isChecked(),
            use_bytetrack=self.use_bytetrack_checkbox.isChecked()
        )
        
        # Update processor tracking mode
        self.processor.set_tracking_mode(self.use_bytetrack_checkbox.isChecked())
    
    @pyqtSlot()
    def on_bytetrack_config_changed(self):
        """Handle ByteTrack configuration changes."""
        self.settings_manager.update_bytetrack_config(
            track_thresh=self.track_thresh_spin.value(),
            track_buffer=self.track_buffer_spin.value()
        )
        
        # Reinitialize ByteTrack with new parameters
        if self.use_bytetrack_checkbox.isChecked():
            bytetrack_config = self.settings_manager.get_bytetrack_config()
            # Reset existing tracker before reinitializing
            self.processor.bytetrack_tracker = None
            self.processor.initialize_bytetrack(
                track_thresh=bytetrack_config.track_thresh,
                track_buffer=bytetrack_config.track_buffer,
                match_thresh=bytetrack_config.match_thresh,
                min_box_area=bytetrack_config.min_box_area
            )
    
    @pyqtSlot()
    def on_clear_ids(self):
        """Clear blob tracking IDs."""
        self.processor.reset_tracker()
        self.console.append_message("Blob tracking IDs cleared", "info")
    
    # OSC event handlers
    @pyqtSlot()
    def on_osc_connect(self):
        """Connect or disconnect OSC destination."""
        if self.connect_button.text() == "Connect":
            # Connect
            ip = self.osc_ip.text()
            port = self.osc_port.value()
            protocol = self.osc_protocol.currentText().lower()
            
            if self.osc_client:
                self.osc_client.close()
            
            self.osc_client = OSCClient(ip, port, protocol, async_mode=False)  # Use sync mode to avoid threading issues
            self.osc_client.set_callbacks(
                on_message_sent=self.on_osc_message_sent,
                on_send_error=self.on_osc_error
            )
            
            if self.osc_client.test_connection():
                self.console.append_message(f"Connected to OSC {protocol.upper()} {ip}:{port}", "success")
                self.status_bar.update_connection_status("Connected")
                self.connect_button.setText("Disconnect")
            else:
                self.console.append_message("Failed to connect to OSC", "error")
                self.status_bar.update_connection_status("Error")
        else:
            # Disconnect
            if self.osc_client:
                # Clear callbacks before closing to prevent lingering messages
                self.osc_client.set_callbacks(None, None)
                self.osc_client.close()
                self.osc_client = None
            
            self.console.append_message("Disconnected from OSC", "info")
            self.status_bar.update_connection_status("Disconnected")
            self.connect_button.setText("Connect")
    
    def auto_connect_osc(self):
        """Auto-connect to OSC on startup."""
        try:
            # Only auto-connect if not already connected
            if not self.osc_client and self.connect_button.text() == "Connect":
                self.console.append_message("Auto-connecting to OSC...", "info")
                self.on_osc_connect()
        except Exception as e:
            self.console.append_message(f"Auto-connect failed: {e}", "error")
    
    @pyqtSlot()
    def on_osc_test(self):
        """Send test OSC message."""
        if self.osc_client:
            self.osc_client.send_test_message()
        else:
            self.console.append_message("OSC not connected", "warning")
    
    @pyqtSlot()
    def on_manual_send(self):
        """Manually send blob data."""
        if self.osc_client and self.current_blobs:
            self.send_blob_data()
        else:
            self.console.append_message("No OSC connection or no blobs detected", "warning")
    
    @pyqtSlot()
    def on_osc_config_changed(self):
        """Handle OSC configuration changes."""
        # Don't save during settings loading
        if self._loading_settings:
            return
            
        self.settings_manager.update_osc_config(
            ip=self.osc_ip.text(),
            port=self.osc_port.value(),
            protocol=self.osc_protocol.currentText().lower(),
            normalize_coords=self.normalize_coords.isChecked(),
            send_on_detect=self.send_on_detect.isChecked(),
            auto_connect=self.auto_connect_checkbox.isChecked(),
            rate_limit_enabled=True,  # Always enabled
            max_fps=30.0,  # Fixed at 30 FPS
            send_center=self.send_center.isChecked(),
            send_position=self.send_position.isChecked(),
            send_size=self.send_size.isChecked(),
            send_area=self.send_area.isChecked(),
            send_polygon=self.send_polygon.isChecked()
        )
    
    @pyqtSlot()
    def on_mapping_table_changed(self):
        """Handle changes to the OSC mapping table."""
        # Get current mappings from table
        mappings = {}
        for i in range(self.mapping_table.rowCount()):
            field_item = self.mapping_table.item(i, 0)
            address_item = self.mapping_table.item(i, 1)
            if field_item and address_item:
                field = field_item.text().lower()
                address = address_item.text()
                mappings[field] = address
        
        # Update config with new mappings
        self.settings_manager.update_osc_config(mappings=mappings)
    
    def on_osc_message_sent(self, address: str, args: List[Any]):
        """Handle OSC message sent callback."""
        # Only log if we still have an active OSC client
        if self.osc_client:
            self.console.append_osc_message(address, args)
    
    def on_osc_error(self, address: str, error: Exception):
        """Handle OSC send error callback."""
        # Only log if we still have an active OSC client
        if self.osc_client:
            self.console.append_error(f"OSC send failed: {error}")
    
    # Processing thread handlers
    @pyqtSlot(object, object, object, list)
    def on_frame_processed(self, original_frame, roi_frame, binary_frame, blobs: List[BlobInfo]):
        """Handle processed frame from processing thread."""
        self.current_frame = original_frame  # Store original uncropped frame
        self.current_roi_frame = roi_frame   # Store already-cropped frame
        self.current_binary = binary_frame
        self.current_blobs = blobs
        
        # Update video previews
        if self.current_frame is not None:
            # Set image size only if it changed to avoid constant updates
            h, w = self.current_frame.shape[:2]
            if (self.roi_manager.image_width != w or self.roi_manager.image_height != h):
                self.roi_manager.set_image_size(w, h)
            
            # Update ROI preview with overlay (shows full image with crop rectangles)
            self.roi_preview.set_image(self.current_frame)  # Full uncropped image
        
        # Update binary preview
        if self.current_binary is not None:
            self.binary_preview.set_image(self.current_binary)
        
        # Update overlay preview with blob detection - use already-cropped frame
        if self.current_roi_frame is not None:
            if self.current_blobs:
                overlay_image = self.processor.draw_blob_overlay(self.current_roi_frame, self.current_blobs)
                self.overlay_preview.set_image(overlay_image)
            else:
                # Show the frame even if no blobs detected
                self.overlay_preview.set_image(self.current_roi_frame)
        
        # Send OSC data if enabled (with rate limiting)
        if (self.send_on_detect.isChecked() and self.osc_client and 
            self.current_blobs and self.current_frame is not None):
            self._send_blob_data_rate_limited()
    
    @pyqtSlot(dict)
    def on_stats_updated(self, stats: Dict[str, Any]):
        """Handle stats update from processing thread."""
        self.status_bar.update_fps(stats.get('fps', 0))
        self.status_bar.update_dropped_frames(stats.get('dropped_frames', 0))
    
    def _send_blob_data_rate_limited(self):
        """Send blob data with rate limiting (always enabled at 30 FPS)."""
        current_time = time.time()
        
        # Fixed rate limiting at 30 FPS
        self.osc_send_interval = 1.0 / 30.0
        
        # Check if enough time has passed since last send
        if current_time - self.last_osc_send_time >= self.osc_send_interval:
            self.send_blob_data()
            self.last_osc_send_time = current_time
    
    def send_blob_data(self):
        """Send blob data via OSC with error handling."""
        if not self.osc_client or not self.current_blobs:
            return
        
        try:
            # Get ROI dimensions for normalization
            x, y, roi_width, roi_height = self.roi_manager.get_roi_bounds()
            
            # Get current mappings from table
            mappings = {}
            for i in range(self.mapping_table.rowCount()):
                field_item = self.mapping_table.item(i, 0)
                address_item = self.mapping_table.item(i, 1)
                if field_item and address_item:
                    field = field_item.text().lower()
                    address = address_item.text()
                    mappings[field] = address
            
            # Get enabled fields
            enabled_fields = {
                'center': self.send_center.isChecked(),
                'position': self.send_position.isChecked(),
                'size': self.send_size.isChecked(),
                'area': self.send_area.isChecked(),
                'polygon': self.send_polygon.isChecked()
            }
            
            # Send data for all blobs
            self.osc_client.send_multiple_blobs(
                self.current_blobs,
                mappings,
                roi_width,
                roi_height,
                self.normalize_coords.isChecked(),
                enabled_fields
            )
            
        except Exception as e:
            # Log error but don't crash the application
            logging.error(f"OSC send error: {e}")
            self.console.append_message(f"OSC send error: {e}", "error")
    
    def load_settings(self):
        """Load settings from file."""
        try:
            self._loading_settings = True
            self.settings_manager.load_config()
            
            # Apply loaded settings to UI
            camera_config = self.settings_manager.get_camera_config()
            roi_config = self.settings_manager.get_roi_config()
            threshold_config = self.settings_manager.get_threshold_config()
            morph_config = self.settings_manager.get_morph_config()
            blob_config = self.settings_manager.get_blob_config()
            bytetrack_config = self.settings_manager.get_bytetrack_config()
            osc_config = self.settings_manager.get_osc_config()
            
            # Update UI controls
            self.channel_combo.setCurrentText(threshold_config.channel.capitalize())
            self.global_radio.setChecked(threshold_config.mode == "global")
            self.adaptive_radio.setChecked(threshold_config.mode == "adaptive")
            self.invert_threshold_checkbox.setChecked(threshold_config.invert)
            self.blur_slider.setValue(threshold_config.blur)
            self.threshold_slider.setValue(threshold_config.value)
            self.morph_open_slider.setValue(morph_config.open)
            self.morph_close_slider.setValue(morph_config.close)
            # Convert pixel values to normalized values for sliders
            roi_bounds = self.roi_manager.get_roi_bounds()
            roi_area = roi_bounds[2] * roi_bounds[3]  # w * h
            
            if roi_area > 0:
                min_normalized = int(self._pixel_to_normalized_area(blob_config.min_area, roi_area) * 100000)
                max_normalized = int(self._pixel_to_normalized_area(blob_config.max_area, roi_area) * 100000)
                
                # Clamp to valid range
                min_normalized = max(0, min(100000, min_normalized))
                max_normalized = max(0, min(100000, max_normalized))
                
                self.min_area_slider.setValue(min_normalized)
                self.max_area_slider.setValue(max_normalized)
                
                # Update labels
                self.min_area_label.setText(f"{min_normalized / 100000.0:.5f}")
                self.max_area_label.setText(f"{max_normalized / 100000.0:.5f}")
            else:
                # Fallback to default values if ROI area is 0
                self.min_area_slider.setValue(2000)  # 0.02
                self.max_area_slider.setValue(100000)  # 1.0
                self.min_area_label.setText("0.02000")
                self.max_area_label.setText("1.00000")
            self.track_ids_checkbox.setChecked(blob_config.track_ids)
            self.use_bytetrack_checkbox.setChecked(blob_config.use_bytetrack)
            
            # Load ByteTrack settings
            self.track_thresh_spin.setValue(bytetrack_config.track_thresh)
            self.track_buffer_spin.setValue(bytetrack_config.track_buffer)
            
            self.osc_ip.setText(osc_config.ip)
            self.osc_port.setValue(osc_config.port)
            self.osc_protocol.setCurrentText(osc_config.protocol.upper())
            self.normalize_coords.setChecked(osc_config.normalize_coords)
            self.send_on_detect.setChecked(osc_config.send_on_detect)
            self.auto_connect_checkbox.setChecked(osc_config.auto_connect)
            
            # Load field selection states
            self.send_center.setChecked(osc_config.send_center)
            self.send_position.setChecked(osc_config.send_position)
            self.send_size.setChecked(osc_config.send_size)
            self.send_area.setChecked(osc_config.send_area)
            self.send_polygon.setChecked(osc_config.send_polygon)
            
            # Load custom mappings into table
            if osc_config.mappings:
                mapping_order = ["center", "position", "size", "area", "polygon"]
                for i, field_key in enumerate(mapping_order):
                    if i < self.mapping_table.rowCount() and field_key in osc_config.mappings:
                        address = osc_config.mappings[field_key]
                        self.mapping_table.setItem(i, 1, QTableWidgetItem(address))
            
            # Update ROI crop values from config - use saved crop values directly
            left_crop = roi_config.left_crop
            top_crop = roi_config.top_crop
            right_crop = roi_config.right_crop
            bottom_crop = roi_config.bottom_crop

            # Set crop values on ROI manager
            self.roi_manager.set_crop_values(left_crop, top_crop, right_crop, bottom_crop)

            # Update slider positions (block signals to prevent feedback)
            self.left_slider.blockSignals(True)
            self.top_slider.blockSignals(True)
            self.right_slider.blockSignals(True)
            self.bottom_slider.blockSignals(True)

            self.left_slider.setValue(left_crop)
            self.top_slider.setValue(top_crop)
            self.right_slider.setValue(right_crop)
            self.bottom_slider.setValue(bottom_crop)

            self.left_slider.blockSignals(False)
            self.top_slider.blockSignals(False)
            self.right_slider.blockSignals(False)
            self.bottom_slider.blockSignals(False)

            # Update labels to match loaded values
            self.left_label.setText(f"{left_crop}px")
            self.top_label.setText(f"{top_crop}px")
            self.right_label.setText(f"{right_crop}px")
            self.bottom_label.setText(f"{bottom_crop}px")

            self.lock_roi_checkbox.setChecked(roi_config.locked)
            # Apply the lock state to sliders without saving
            self._apply_roi_lock_state(roi_config.locked)
            
            self._loading_settings = False
            self.console.append_message("Settings loaded", "success")
            self.status_bar.update_config_status("Loaded")
            
        except Exception as e:
            self.console.append_message(f"Failed to load settings: {e}", "error")
            self.status_bar.update_config_status("Error")
            self._loading_settings = False
    
    def save_settings(self):
        """Save current settings to file."""
        try:
            self.settings_manager.save_config()
            self.console.append_message("Settings saved", "success")
            self.status_bar.update_config_status("Saved")
        except Exception as e:
            self.console.append_message(f"Failed to save settings: {e}", "error")
            self.status_bar.update_config_status("Error")
    
    def load_settings_dialog(self):
        """Show load settings dialog."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Settings", "", "JSON files (*.json)"
        )
        if filename:
            try:
                self.settings_manager.config_path = filename
                self.load_settings()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load settings: {e}")
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self, "About Blob OSC",
            "Blob OSC v1.0\n\n"
            "A real-time blob detection and OSC streaming application.\n"
            "Captures webcam feed, detects blobs, and sends data via OSC."
        )
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop processing thread
        self.processing_thread.stop()
        
        # Close camera
        self.camera_manager.close_camera()
        
        # Close OSC client
        if self.osc_client:
            self.osc_client.close()
        
        # Save settings
        self.save_settings()
        
        event.accept()
