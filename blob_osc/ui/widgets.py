"""Custom widgets for the Blob OSC application."""

import cv2
import numpy as np
from typing import Optional, Callable, List, Dict, Any
from PyQt6.QtWidgets import (QLabel, QTextEdit, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QRect
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QBrush, QColor, QFont


class VideoPreview(QLabel):
    """Video preview widget with overlay support."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(640, 480)
        self.setScaledContents(False)  # We'll handle scaling manually
        self.setStyleSheet("border: 1px solid gray;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Image data
        self.current_image: Optional[np.ndarray] = None
        self.display_image: Optional[QImage] = None
        self.scale_factor = 1.0
        
        # Overlay callbacks
        self.draw_overlay_callback: Optional[Callable[[np.ndarray], np.ndarray]] = None
    
    def set_image(self, image: np.ndarray) -> None:
        """Set the image to display."""
        if image is None:
            return
        
        self.current_image = image.copy()
        self._update_display()
    
    def set_overlay_callback(self, callback: Optional[Callable[[np.ndarray], np.ndarray]]) -> None:
        """Set callback function for drawing overlays."""
        self.draw_overlay_callback = callback
        if self.current_image is not None:
            self._update_display()
    
    def _update_display(self) -> None:
        """Update the displayed image."""
        if self.current_image is None:
            return
        
        # Apply overlay if callback is set
        display_image = self.current_image.copy()
        if self.draw_overlay_callback:
            display_image = self.draw_overlay_callback(display_image)
        
        # Convert to QImage
        height, width = display_image.shape[:2]
        
        if len(display_image.shape) == 3:
            # Color image
            rgb_image = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
            q_image = QImage(rgb_image.data, width, height, width * 3, QImage.Format.Format_RGB888)
        else:
            # Grayscale image
            q_image = QImage(display_image.data, width, height, width, QImage.Format.Format_Grayscale8)
        
        self.display_image = q_image
        
        # Scale to fit widget while maintaining aspect ratio
        pixmap = QPixmap.fromImage(q_image)
        
        # Get widget size
        widget_size = self.size()
        widget_width = widget_size.width()
        widget_height = widget_size.height()
        
        # Calculate scaling to fit within widget while maintaining aspect ratio
        if pixmap.width() > 0 and pixmap.height() > 0:
            scale_x = widget_width / pixmap.width()
            scale_y = widget_height / pixmap.height()
            scale_factor = min(scale_x, scale_y)
            
            # Calculate new size maintaining aspect ratio
            new_width = int(pixmap.width() * scale_factor)
            new_height = int(pixmap.height() * scale_factor)
            
            scaled_pixmap = pixmap.scaled(new_width, new_height, 
                                        Qt.AspectRatioMode.KeepAspectRatio, 
                                        Qt.TransformationMode.SmoothTransformation)
            
            self.scale_factor = scale_factor
        else:
            scaled_pixmap = pixmap
            self.scale_factor = 1.0
        
        self.setPixmap(scaled_pixmap)
    
    
    def get_image_size(self) -> tuple[int, int]:
        """Get the size of the current image."""
        if self.current_image is not None:
            return (self.current_image.shape[1], self.current_image.shape[0])
        return (0, 0)
    
    def refresh(self) -> None:
        """Refresh the display."""
        if self.current_image is not None:
            self._update_display()


class ConsoleWidget(QTextEdit):
    """Console widget for displaying log messages."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        # Note: setMaximumBlockCount is not available in PyQt6
        # We'll manage line count manually
        self.max_lines = 1000
        self.setFont(QFont("Courier", 9))
        
        # Styling
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #555;
            }
        """)
    
    def append_message(self, message: str, level: str = "info") -> None:
        """Append a message with optional color coding."""
        import time
        timestamp = time.strftime("%H:%M:%S")
        
        # Color coding based on level
        colors = {
            "error": "#ff6b6b",
            "warning": "#feca57",
            "success": "#48ca48",
            "info": "#74b9ff",
            "debug": "#a29bfe"
        }
        
        color = colors.get(level.lower(), "#ffffff")
        formatted_message = f'<span style="color: #888;">[{timestamp}]</span> <span style="color: {color};">{message}</span>'
        
        self.append(formatted_message)
        
        # Manage line count manually
        self._limit_lines()
        
        # Auto-scroll to bottom
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _limit_lines(self) -> None:
        """Limit the number of lines in the console."""
        from PyQt6.QtGui import QTextCursor
        
        document = self.document()
        if document.blockCount() > self.max_lines:
            # Remove excess lines from the beginning
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            
            # Calculate how many lines to remove
            lines_to_remove = document.blockCount() - self.max_lines + 100  # Remove extra to avoid frequent trimming
            
            # Select and delete the excess lines
            for _ in range(lines_to_remove):
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
    
    def append_osc_message(self, address: str, args: List[Any]) -> None:
        """Append an OSC message to the console."""
        args_str = ", ".join(str(arg) for arg in args)
        message = f"OSC → {address} [{args_str}]"
        self.append_message(message, "success")
    
    def append_error(self, error: str) -> None:
        """Append an error message."""
        self.append_message(f"ERROR: {error}", "error")
    
    def clear_console(self) -> None:
        """Clear the console."""
        self.clear()


class StatusBar(QWidget):
    """Custom status bar widget."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
        # Status values
        self.fps = 0.0
        self.dropped_frames = 0
        self.connection_status = "Disconnected"
        self.config_status = "Saved"
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # Update every second
    
    def setup_ui(self) -> None:
        """Setup the status bar UI."""
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        
        # FPS label
        self.fps_label = QLabel("FPS: 0.0")
        self.fps_label.setMinimumWidth(80)
        
        # Dropped frames label
        self.dropped_label = QLabel("Dropped: 0")
        self.dropped_label.setMinimumWidth(100)
        
        # Connection status label
        self.connection_label = QLabel("OSC: Disconnected")
        self.connection_label.setMinimumWidth(150)
        
        # Config status label
        self.config_label = QLabel("Config: Saved")
        self.config_label.setMinimumWidth(100)
        
        # Add separators
        def create_separator():
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFrameShadow(QFrame.Shadow.Sunken)
            return sep
        
        layout.addWidget(self.fps_label)
        layout.addWidget(create_separator())
        layout.addWidget(self.dropped_label)
        layout.addWidget(create_separator())
        layout.addWidget(self.connection_label)
        layout.addWidget(create_separator())
        layout.addWidget(self.config_label)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Styling
        self.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                border-top: 1px solid #ccc;
            }
            QLabel {
                padding: 2px 5px;
            }
        """)
    
    def update_fps(self, fps: float) -> None:
        """Update FPS value."""
        self.fps = fps
    
    def update_dropped_frames(self, count: int) -> None:
        """Update dropped frames count."""
        self.dropped_frames = count
    
    def update_connection_status(self, status: str) -> None:
        """Update OSC connection status."""
        self.connection_status = status
    
    def update_config_status(self, status: str) -> None:
        """Update configuration status."""
        self.config_status = status
    
    def update_display(self) -> None:
        """Update the status display."""
        self.fps_label.setText(f"FPS: {self.fps:.1f}")
        self.dropped_label.setText(f"Dropped: {self.dropped_frames}")
        
        # Color code connection status
        status_colors = {
            "Connected": "#48ca48",
            "Disconnected": "#ff6b6b",
            "Error": "#ff6b6b"
        }
        color = status_colors.get(self.connection_status, "#333")
        self.connection_label.setText(f"OSC: {self.connection_status}")
        self.connection_label.setStyleSheet(f"color: {color};")
        
        # Color code config status
        config_colors = {
            "Saved": "#48ca48",
            "Modified": "#feca57",
            "Error": "#ff6b6b"
        }
        color = config_colors.get(self.config_status, "#333")
        self.config_label.setText(f"Config: {self.config_status}")
        self.config_label.setStyleSheet(f"color: {color};")


class CollapsibleSection(QWidget):
    """A collapsible section widget."""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.content_widget = QWidget()
        self.is_expanded = True
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Setup the collapsible section UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header button
        self.header_button = QPushButton(f"▼ {self.title}")
        self.header_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px;
                border: none;
                background-color: #e0e0e0;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)
        self.header_button.clicked.connect(self.toggle_expansion)
        
        # Content area
        self.content_area = QScrollArea()
        self.content_area.setWidget(self.content_widget)
        self.content_area.setWidgetResizable(True)
        self.content_area.setFrameShape(QFrame.Shape.NoFrame)
        
        layout.addWidget(self.header_button)
        layout.addWidget(self.content_area)
        
        self.setLayout(layout)
    
    def toggle_expansion(self) -> None:
        """Toggle the expansion state."""
        self.is_expanded = not self.is_expanded
        self.content_area.setVisible(self.is_expanded)
        
        arrow = "▼" if self.is_expanded else "▶"
        self.header_button.setText(f"{arrow} {self.title}")
    
    def set_content_layout(self, layout) -> None:
        """Set the content layout."""
        self.content_widget.setLayout(layout)
    
    def add_content_widget(self, widget: QWidget) -> None:
        """Add a widget to the content area."""
        if not self.content_widget.layout():
            self.content_widget.setLayout(QVBoxLayout())
        self.content_widget.layout().addWidget(widget)
