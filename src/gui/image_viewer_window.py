"""
Image viewer window for croquis practice
"""

import os
import random
import base64
import logging
from datetime import date
from typing import List, Any
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import (
    QPixmap, QImage, QFont, QMouseEvent, QTransform, QGuiApplication,
    QKeyEvent
)

from core.models import CroquisSettings, DEFAULT_SHORTCUTS
from core.key_manager import decrypt_data
from utils.helpers import get_app_icon, get_data_path, tr
from utils.qt_resource_loader import QtResourceLoader
from utils.log_manager import LOG_MESSAGES
from gui.widgets import ScreenshotOverlay

logger = logging.getLogger('Croquis')


class ImageViewerWindow(QWidget):
    """Croquis image viewer window"""
    
    croquis_completed = pyqtSignal()
    croquis_saved = pyqtSignal(QPixmap, QPixmap, int, str, dict)  # original, screenshot, duration, filename, metadata
    
    def __init__(self, settings: CroquisSettings, images: List[Any], lang: str = "ko", parent=None):
        super().__init__(parent)
        self.setWindowIcon(get_app_icon())
        self.settings = settings
        self.images = images
        self.lang = lang
        self.current_index = 0
        self.paused = False
        self.remaining_time = settings.time_seconds if not settings.study_mode else 0
        self.elapsed_time = 0
        self.random_seed = None
        
        # Always shuffle using difficulty-weighted random order
        self.random_seed = random.randint(0, 1000000)
        random.seed(self.random_seed)
        self.images = self.weighted_shuffle(self.images)
        
        self.setup_ui()
        self.setup_timer()
        self.load_current_image()
    
    def weighted_shuffle(self, images: List[Any]) -> List[Any]:
        """Randomize images weighted by difficulty"""
        if not images:
            return images
        
        weights = []
        for img in images:
            if isinstance(img, dict):
                difficulty = img.get("difficulty", 1)
                weight = difficulty * difficulty
                weights.append(weight)
            else:
                weights.append(1)
        
        total_weight = sum(weights)
        if total_weight == 0:
            return images
        
        result = []
        remaining = images.copy()
        remaining_weights = weights.copy()
        
        while remaining:
            cumulative = []
            cumsum = 0
            for w in remaining_weights:
                cumsum += w
                cumulative.append(cumsum)
            
            rand_val = random.random() * cumsum
            for i, cum in enumerate(cumulative):
                if rand_val <= cum:
                    result.append(remaining[i])
                    remaining.pop(i)
                    remaining_weights.pop(i)
                    break
        
        return result
        
    def setup_ui(self):
        self.setWindowFlags(
            Qt.WindowType.Window | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(self.settings.image_width, self.settings.image_height + 50)
        
        # Center on screen
        screen = QGuiApplication.primaryScreen().geometry()
        x = (screen.width() - self.settings.image_width) // 2
        y = (screen.height() - (self.settings.image_height + 50)) // 2
        self.move(x, y)
        
        self.drag_position = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Image display area
        self.image_container = QWidget()
        self.image_container.setMinimumSize(self.settings.image_width, self.settings.image_height)
        image_layout = QVBoxLayout(self.image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #2a2a2a;")
        image_layout.addWidget(self.image_label)
        
        # Timer label
        self.timer_label = QLabel(self.image_container)
        self.timer_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 150);
                padding: 5px 10px;
                border-radius: 5px;
            }
        """)
        self.update_timer_position()
        self.update_timer_font()
        
        # Today's count label
        self.today_count_label = QLabel(self.image_container)
        self.today_count_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 150);
                padding: 5px 10px;
                border-radius: 5px;
            }
        """)
        self.update_today_count_display()
        self.update_today_count_font()
        self.update_today_count_position()
        
        layout.addWidget(self.image_container, 1)
        
        # Control buttons
        control_widget = QWidget()
        control_widget.setStyleSheet("background-color: #333;")
        control_layout = QHBoxLayout(control_widget)
        control_layout.setContentsMargins(10, 5, 10, 5)
        
        resource_loader = QtResourceLoader()
        
        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(resource_loader.get_icon("/buttons/이전.png"))
        self.prev_btn.setIconSize(QSize(24, 24))
        self.prev_btn.setToolTip(tr("previous", self.lang))
        self.prev_btn.clicked.connect(self.previous_image)
        
        self.pause_btn = QPushButton()
        self.pause_btn.setIcon(resource_loader.get_icon("/buttons/일시 정지.png"))
        self.pause_btn.setIconSize(QSize(24, 24))
        self.pause_btn.setToolTip(tr("pause", self.lang))
        self.pause_btn.clicked.connect(self.toggle_pause)
        
        self.next_btn = QPushButton()
        self.next_btn.setIcon(resource_loader.get_icon("/buttons/다음.png"))
        self.next_btn.setIconSize(QSize(24, 24))
        self.next_btn.setToolTip(tr("next", self.lang))
        self.next_btn.clicked.connect(self.next_image_no_screenshot)
        
        self.stop_btn = QPushButton()
        self.stop_btn.setIcon(resource_loader.get_icon("/buttons/정지.png"))
        self.stop_btn.setIconSize(QSize(24, 24))
        self.stop_btn.setToolTip(tr("stop", self.lang))
        self.stop_btn.clicked.connect(self.stop_croquis)
        
        for btn in [self.prev_btn, self.pause_btn, self.next_btn, self.stop_btn]:
            btn.setFixedSize(40, 40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(85, 85, 85, 180);
                    border: none;
                    border-radius: 20px;
                }
                QPushButton:hover {
                    background-color: rgba(102, 102, 102, 200);
                }
                QPushButton:pressed {
                    background-color: rgba(68, 68, 68, 220);
                }
            """)
        
        control_layout.addStretch()
        control_layout.addWidget(self.prev_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.next_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addStretch()
        
        layout.addWidget(control_widget)
        
        # Screenshot overlay
        self.screenshot_overlay = ScreenshotOverlay()
        self.screenshot_overlay.screenshot_taken.connect(self.on_screenshot_taken)
        self.screenshot_overlay.cancelled.connect(self.on_screenshot_cancelled)
        
    def setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer_tick)
        self.timer.start(1000)
        
    def update_timer_position(self):
        pos = self.settings.timer_position
        margin = 10
        
        self.timer_label.adjustSize()
        w = self.timer_label.width()
        h = self.timer_label.height()
        cw = self.image_container.width()
        ch = self.image_container.height()
        
        positions = {
            "bottom_right": (cw - w - margin, ch - h - margin),
            "bottom_center": ((cw - w) // 2, ch - h - margin),
            "bottom_left": (margin, ch - h - margin),
            "top_right": (cw - w - margin, margin),
            "top_center": ((cw - w) // 2, margin),
            "top_left": (margin, margin),
        }
        
        x, y = positions.get(pos, positions["bottom_right"])
        self.timer_label.move(x, y)
        
    def update_timer_font(self):
        sizes = {"large": 24, "medium": 18, "small": 12}
        size = sizes.get(self.settings.timer_font_size, 24)
        font = QFont("Arial", size, QFont.Weight.Bold)
        self.timer_label.setFont(font)
    
    def load_today_croquis_count(self):
        """Load today's croquis count from history data"""
        dat_dir = get_data_path() / "dat"
        data_path = dat_dir / "croquis_history.dat"
        if data_path.exists():
            try:
                with open(data_path, "rb") as f:
                    encrypted = f.read()
                decrypted = decrypt_data(encrypted)
                today = date.today().isoformat()
                return decrypted.get(today, 0)
            except Exception:
                return 0
        return 0
    
    def update_today_count_display(self):
        count = self.load_today_croquis_count()
        self.today_count_label.setText(f"{count} {tr('croquis_times', self.lang)}")
        self.today_count_label.adjustSize()
    
    def update_today_count_font(self):
        sizes = {"large": 20, "medium": 15, "small": 10}
        size = sizes.get(self.settings.today_croquis_count_font_size, 15)
        font = QFont("Arial", size, QFont.Weight.Bold)
        self.today_count_label.setFont(font)
    
    def update_today_count_position(self):
        pos = self.settings.today_croquis_count_position
        timer_pos = self.settings.timer_position
        margin = 10
        
        self.today_count_label.adjustSize()
        w = self.today_count_label.width()
        h = self.today_count_label.height()
        cw = self.image_container.width()
        ch = self.image_container.height()
        
        positions = {
            "bottom_right": (cw - w - margin, ch - h - margin),
            "bottom_center": ((cw - w) // 2, ch - h - margin),
            "bottom_left": (margin, ch - h - margin),
            "top_right": (cw - w - margin, margin),
            "top_center": ((cw - w) // 2, margin),
            "top_left": (margin, margin),
        }
        
        x, y = positions.get(pos, positions["top_right"])
        
        # Check for overlap with timer
        if pos == timer_pos:
            if "top" in pos:
                timer_h = self.timer_label.height()
                y = margin + timer_h + 5
            else:
                timer_h = self.timer_label.height()
                y = ch - h - margin - timer_h - 5
        
        self.today_count_label.move(x, y)
        
    def load_current_image(self):
        if 0 <= self.current_index < len(self.images):
            image_item = self.images[self.current_index]
            
            if isinstance(image_item, dict):
                try:
                    image_data_b64 = image_item.get("image_data", "")
                    image_bytes = base64.b64decode(image_data_b64)
                    pixmap = QPixmap()
                    pixmap.loadFromData(image_bytes)
                    self.current_filename = image_item.get("filename", "unknown")
                except Exception as e:
                    print(tr("image_load_failed", self.lang).format(e))
                    return
            else:
                pixmap = QPixmap(image_item)
                self.current_filename = os.path.basename(image_item)
            
            if self.settings.grayscale:
                image = pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
                pixmap = QPixmap.fromImage(image)
            
            if self.settings.flip_horizontal:
                transform = QTransform().scale(-1, 1)
                pixmap = pixmap.transformed(transform)
            
            scaled = pixmap.scaled(
                self.settings.image_width, 
                self.settings.image_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
            self.current_pixmap = pixmap
            
            if self.settings.study_mode:
                self.elapsed_time = 0
            else:
                self.remaining_time = self.settings.time_seconds
            self.update_timer_display()
            
    def update_timer_display(self):
        if self.settings.study_mode:
            minutes = self.elapsed_time // 60
            seconds = self.elapsed_time % 60
        else:
            minutes = self.remaining_time // 60
            seconds = self.remaining_time % 60
        self.timer_label.setText(f"{minutes:02d}:{seconds:02d}")
        self.timer_label.adjustSize()
        self.update_timer_position()
        
    def on_timer_tick(self):
        if not self.paused and hasattr(self, 'timer') and self.timer:
            if self.settings.study_mode:
                self.elapsed_time += 1
                self.update_timer_display()
            else:
                if self.remaining_time > 0:
                    self.remaining_time -= 1
                    self.update_timer_display()
                    
                    if self.remaining_time == 0:
                        self.timer.stop()
                        QTimer.singleShot(150, self.start_screenshot_mode)
                
    def start_screenshot_mode(self):
        logger.info(LOG_MESSAGES["screenshot_mode_enabled"])
        self.screenshot_overlay.start_capture()
        
    def on_screenshot_taken(self, screenshot: QPixmap):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("save_croquis", self.lang))
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        image_label = QLabel()
        preview = screenshot.scaled(500, 500, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        image_label.setPixmap(preview)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(image_label)
        
        question_label = QLabel(tr("save_question", self.lang))
        question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        question_label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(question_label)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        yes_btn = QPushButton(tr("yes", self.lang))
        yes_btn.setMinimumWidth(100)
        yes_btn.setMinimumHeight(35)
        yes_btn.clicked.connect(dialog.accept)
        
        no_btn = QPushButton(tr("no", self.lang))
        no_btn.setMinimumWidth(100)
        no_btn.setMinimumHeight(35)
        no_btn.clicked.connect(dialog.reject)
        
        button_layout.addWidget(yes_btn)
        button_layout.addWidget(no_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            self.save_croquis_pair(screenshot)
            self.next_image()
        else:
            self.start_screenshot_mode()
            
    def on_screenshot_cancelled(self):
        logger.info(LOG_MESSAGES["screenshot_mode_cancelled"])
        self.start_screenshot_mode()
        
    def save_croquis_pair(self, screenshot: QPixmap):
        """Save the croquis image pair with encryption"""
        logger.info(LOG_MESSAGES["croquis_pair_saved"])
        if self.settings.study_mode:
            croquis_time = self.elapsed_time
        else:
            croquis_time = self.settings.time_seconds
        
        current_image = self.images[self.current_index]
        
        if isinstance(current_image, dict):
            image_filename = os.path.splitext(current_image.get("filename", "unknown"))[0]
            image_metadata = {
                "filename": current_image.get("filename", "unknown"),
                "path": current_image.get("original_path", ""),
                "width": current_image.get("width", self.current_pixmap.width()),
                "height": current_image.get("height", self.current_pixmap.height()),
                "size": current_image.get("size", 0)
            }
        else:
            current_image_path = current_image
            image_filename = os.path.splitext(os.path.basename(current_image_path))[0]
            image_metadata = {
                "filename": os.path.basename(current_image_path),
                "path": current_image_path,
                "width": self.current_pixmap.width(),
                "height": self.current_pixmap.height(),
                "size": os.path.getsize(current_image_path) if os.path.exists(current_image_path) else 0
            }
        
        self.croquis_saved.emit(self.current_pixmap, screenshot, croquis_time, image_filename, image_metadata)
        
    def previous_image(self):
        logger.info(LOG_MESSAGES["croquis_previous"])
        if self.settings.study_mode:
            self.timer.stop()
            self.start_screenshot_mode()
        elif self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()
            self.timer.start(1000)
            
    def next_image(self):
        logger.info(LOG_MESSAGES["croquis_next"])
        if self.current_index < len(self.images) - 1:
            self.current_index += 1
        else:
            self.current_index = 0
        self.load_current_image()
        self.update_today_count_display()
        self.timer.start(1000)
            
    def next_image_no_screenshot(self):
        if self.settings.study_mode:
            self.timer.stop()
            self.start_screenshot_mode()
        else:
            self.next_image()
        
    def toggle_pause(self):
        self.paused = not self.paused
        logger.info(LOG_MESSAGES["croquis_paused" if self.paused else "croquis_playing"])
        
        resource_loader = QtResourceLoader()
        if self.paused:
            self.pause_btn.setIcon(resource_loader.get_icon("/buttons/재생.png"))
            self.pause_btn.setToolTip(tr("play", self.lang))
        else:
            self.pause_btn.setIcon(resource_loader.get_icon("/buttons/일시 정지.png"))
            self.pause_btn.setToolTip(tr("pause", self.lang))
            if self.remaining_time == 0:
                self.next_image()
                
    def stop_croquis(self):
        logger.info(LOG_MESSAGES["croquis_stopped"])
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None
        if hasattr(self, 'screenshot_overlay'):
            self.screenshot_overlay.hide()
            self.screenshot_overlay.close()
            self.screenshot_overlay = None
        self.croquis_completed.emit()
        self.close()
    
    def closeEvent(self, event):
        """Handle window close event"""
        logger.info(LOG_MESSAGES["croquis_window_closed"])
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None
        if hasattr(self, 'screenshot_overlay') and self.screenshot_overlay:
            self.screenshot_overlay.hide()
            self.screenshot_overlay.close()
            self.screenshot_overlay = None
        self.croquis_completed.emit()
        event.accept()
    
    def mousePressEvent(self, event: QMouseEvent):
        """Start drag on mouse press"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Move window while dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_timer_position()
        self.update_today_count_position()

    # --- Shortcut key mapping ---
    _KEY_NAME_TO_QT = {
        "Space": Qt.Key.Key_Space,
        "Escape": Qt.Key.Key_Escape,
        "Enter": Qt.Key.Key_Return,
        "Return": Qt.Key.Key_Return,
        "Left": Qt.Key.Key_Left,
        "Right": Qt.Key.Key_Right,
        "Up": Qt.Key.Key_Up,
        "Down": Qt.Key.Key_Down,
        "Tab": Qt.Key.Key_Tab,
        "Backspace": Qt.Key.Key_Backspace,
        "Delete": Qt.Key.Key_Delete,
        "A": Qt.Key.Key_A, "B": Qt.Key.Key_B, "C": Qt.Key.Key_C,
        "D": Qt.Key.Key_D, "E": Qt.Key.Key_E, "F": Qt.Key.Key_F,
        "G": Qt.Key.Key_G, "H": Qt.Key.Key_H, "I": Qt.Key.Key_I,
        "J": Qt.Key.Key_J, "K": Qt.Key.Key_K, "L": Qt.Key.Key_L,
        "M": Qt.Key.Key_M, "N": Qt.Key.Key_N, "O": Qt.Key.Key_O,
        "P": Qt.Key.Key_P, "Q": Qt.Key.Key_Q, "R": Qt.Key.Key_R,
        "S": Qt.Key.Key_S, "T": Qt.Key.Key_T, "U": Qt.Key.Key_U,
        "V": Qt.Key.Key_V, "W": Qt.Key.Key_W, "X": Qt.Key.Key_X,
        "Y": Qt.Key.Key_Y, "Z": Qt.Key.Key_Z,
        "0": Qt.Key.Key_0, "1": Qt.Key.Key_1, "2": Qt.Key.Key_2,
        "3": Qt.Key.Key_3, "4": Qt.Key.Key_4, "5": Qt.Key.Key_5,
        "6": Qt.Key.Key_6, "7": Qt.Key.Key_7, "8": Qt.Key.Key_8,
        "9": Qt.Key.Key_9,
        "F1": Qt.Key.Key_F1, "F2": Qt.Key.Key_F2, "F3": Qt.Key.Key_F3,
        "F4": Qt.Key.Key_F4, "F5": Qt.Key.Key_F5, "F6": Qt.Key.Key_F6,
        "F7": Qt.Key.Key_F7, "F8": Qt.Key.Key_F8, "F9": Qt.Key.Key_F9,
        "F10": Qt.Key.Key_F10, "F11": Qt.Key.Key_F11, "F12": Qt.Key.Key_F12,
    }

    def _build_shortcut_map(self) -> dict:
        """Build a mapping from Qt key codes to action names based on settings."""
        shortcuts = getattr(self.settings, 'shortcuts', DEFAULT_SHORTCUTS)
        key_map = {}
        for action, key_name in shortcuts.items():
            if key_name and key_name in self._KEY_NAME_TO_QT:
                qt_key = self._KEY_NAME_TO_QT[key_name]
                key_map[qt_key] = action
        return key_map

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts for the croquis viewer."""
        key_map = self._build_shortcut_map()
        pressed_key = event.key()

        action = key_map.get(pressed_key)
        if action is None:
            super().keyPressEvent(event)
            return

        if action == "next_image":
            self.next_image_no_screenshot()
        elif action == "previous_image":
            self.previous_image()
        elif action == "toggle_pause":
            self.toggle_pause()
        elif action == "stop_croquis":
            self.stop_croquis()
        else:
            super().keyPressEvent(event)
            return

        event.accept()
