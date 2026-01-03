"""
Croquis Practice App
PyQt6-based croquis practice application
"""

import sys
import os
import json
import random
import hashlib
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
import base64
from log_manager import LOG_MESSAGES
from language_manager import TRANSLATIONS
from qt_resource_loader import QtResourceLoader

# ============== Path helpers ==============
def get_data_path():
    """Get base path for data files (dat, logs, croquis_pairs etc.).
    Always uses the directory where the executable/script is located."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - use executable's directory
        return Path(sys.executable).parent
    else:
        # Running as script - use script's directory
        return Path(__file__).parent

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox,
    QSpinBox, QGroupBox, QFileDialog, QDialog, QDialogButtonBox,
    QScrollArea, QFrame, QSplitter, QMenuBar, QMenu, QToolBar,
    QListWidget, QListWidgetItem, QMessageBox, QSizePolicy, QStackedWidget,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QRubberBand,
    QTimeEdit, QDateEdit, QCalendarWidget, QSystemTrayIcon, QAbstractItemView
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QRect, QPoint, pyqtSignal, QMimeData, QUrl,
    QPropertyAnimation, QEasingCurve, QSettings, QTime, QDate, QDateTime
)
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QPen, QBrush, QFont, QIcon,
    QIntValidator, QScreen, QGuiApplication, QDragEnterEvent, QDropEvent,
    QMouseEvent, QPaintEvent, QKeyEvent, QAction, QDrag
)

# ============== Alarm Check Functions ==============
def get_icon_path():
    """Get the icon file path for toast notifications.
    For compiled executables, icon.ico is bundled into _MEIPASS."""
    if getattr(sys, 'frozen', False):
        # Compiled executable: icon is in _MEIPASS
        if hasattr(sys, '_MEIPASS'):
            icon_path = Path(sys._MEIPASS) / "icon.ico"
        else:
            icon_path = Path(sys.executable).parent / "icon.ico"
    else:
        # Script mode: icon is in script directory
        icon_path = Path(__file__).parent / "icon.ico"
    
    return str(icon_path) if icon_path.exists() else None

def show_toast_notification(title: str, message: str, icon_path: str = None):
    """Display Windows toast notification"""
    # Set icon path
    if icon_path is None:
        icon_path = get_icon_path()
    
    icon_exists = icon_path and os.path.exists(icon_path)
    logger.info(LOG_MESSAGES["toast_notification_requested"].format(title, message, icon_path))
    logger.info(f"Icon exists: {icon_exists}")
    
    # Priority 1: win11toast (Windows 10/11 native notifications)
    try:
        from win11toast import toast_async
        import asyncio
        
        async def show_toast():
            # 5 second timeout
            try:
                await asyncio.wait_for(
                    toast_async(
                        title,
                        message,
                        icon=icon_path if icon_exists else None,
                        app_id="Croquis Practice"
                    ),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning(LOG_MESSAGES["toast_notification_timeout"])
        
        asyncio.run(show_toast())
        logger.info(LOG_MESSAGES["toast_notification_success"].format("win11toast"))
        return
    except Exception as e:
        logger.error(LOG_MESSAGES["toast_notification_failed"].format("win11toast", e))
    
    # Priority 2: plyer (cross-platform)
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Croquis Practice",
            app_icon=icon_path if icon_exists else None,
            timeout=10
        )
        logger.info(LOG_MESSAGES["toast_notification_success"].format("plyer"))
        return
    except Exception as e:
        logger.error(LOG_MESSAGES["toast_notification_failed"].format("plyer", e))
    
    # Last resort: console output
    fallback_msg = f"[ALARM] {title}: {message}"
    print(fallback_msg)
    logger.info(LOG_MESSAGES["toast_notification_fallback"].format(fallback_msg))

def check_and_trigger_alarms():
    """Check and trigger alarms (prevent duplicates)"""
    dat_dir = get_data_path() / "dat"
    alarms_file = dat_dir / "alarms.dat"
    
    if not alarms_file.exists():
        return
    
    try:
        with open(alarms_file, "rb") as f:
            encrypted = f.read()
        data = decrypt_data(encrypted)
        alarms = data.get("alarms", [])
        
        if not alarms:
            return
        
        logger.info(LOG_MESSAGES["alarm_checking"].format(len(alarms)))
        
        # Current time
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%Y-%m-%d")
        current_weekday = now.weekday()
        icon_path = get_icon_path()
        
        # Check alarms
        for i, alarm in enumerate(alarms):
            if not alarm.get("enabled", False):
                continue
            
            alarm_time = alarm.get("time", "")
            alarm_type = alarm.get("type", "")
            
            # Check time match
            if alarm_time != current_time:
                continue
            
            # Check by type
            should_trigger = False
            
            if alarm_type == "weekday":
                weekdays = alarm.get("weekdays", [])
                if current_weekday in weekdays:
                    should_trigger = True
            elif alarm_type == "date":
                alarm_date = alarm.get("date", "")
                if alarm_date == current_date:
                    should_trigger = True
            
            if should_trigger:
                title = alarm.get("title", "Croquis Alarm")
                message = alarm.get("message", "Time to practice croquis!")
                logger.info(LOG_MESSAGES["alarm_triggered"].format(title, current_time))
                show_toast_notification(title, message, icon_path)
                
    except Exception as e:
        logger.error(LOG_MESSAGES["alarm_check_failed"].format(e))

# ============== Size constants ==============
# Deck editor list item sizes
DECK_ICON_WIDTH = 100
DECK_ICON_HEIGHT = 120
DECK_GRID_WIDTH = 120
DECK_GRID_HEIGHT = 160
DECK_SPACING = 3

# History window list item sizes
HISTORY_ICON_WIDTH = 300
HISTORY_ICON_HEIGHT = 150
HISTORY_GRID_WIDTH = 320
HISTORY_GRID_HEIGHT = 185
HISTORY_SPACING = 5

# ============== Logging setup ==============
def setup_logging():
    """Initialize logging system"""
    # Use execution path for logs directory (not script path)
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - use executable's directory
        base_dir = Path(sys.executable).parent
    else:
        # Running as script - use script's directory
        base_dir = Path(__file__).parent
    
    log_dir = base_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"croquis_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('Croquis')

# --check-alarm 모드에서는 로깅 초기화하지 않음
if not (len(sys.argv) > 1 and sys.argv[1] == "--check-alarm"):
    logger = setup_logging()
    logger.info(LOG_MESSAGES["program_started"])
else:
    # 알람 체크 모드: 최소한의 로거만 생성 (파일 로깅 없음)
    logger = logging.getLogger('Croquis')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())


# ============== Translation setup ==============
def tr(key: str, lang: str = "ko") -> str:
    """Translation helper"""
    return TRANSLATIONS.get(lang, TRANSLATIONS["ko"]).get(key, key)

# ============== Icon setup ==============
def get_app_icon() -> QIcon:
    """Load application icon from file (optimized for PyInstaller)"""
    icon_path = None
    
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        # PyInstaller extracts files to sys._MEIPASS (temp directory)
        bundled_icon = Path(sys._MEIPASS) / "icon.ico"
        if bundled_icon.exists():
            icon_path = bundled_icon
        else:
            # Fallback: check executable directory
            icon_path = get_data_path() / "icon.ico"
    else:
        # Running as script
        icon_path = Path(__file__).parent / "icon.ico"
    
    if icon_path and icon_path.exists():
        return QIcon(str(icon_path))
    
    return QIcon()

# ============== Encryption utilities ==============
def encrypt_data(data: dict) -> bytes:
    """Compress and encrypt data"""
    import zlib
    key = base64.urlsafe_b64encode(hashlib.sha256(b"croquis_secret_key").digest())
    fernet = Fernet(key)
    json_str = json.dumps(data, ensure_ascii=False)
    # Compress with zlib (level 9 = max compression)
    compressed = zlib.compress(json_str.encode(), level=9)
    encrypted = fernet.encrypt(compressed)
    return encrypted

def decrypt_data(encrypted: bytes) -> dict:
    """Decrypt and decompress data"""
    import zlib
    key = base64.urlsafe_b64encode(hashlib.sha256(b"croquis_secret_key").digest())
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted)
    # Decompress
    decompressed = zlib.decompress(decrypted)
    data = json.loads(decompressed.decode())
    return data

# ============== Data classes ==============
@dataclass
class CroquisSettings:
    """Croquis settings data class"""
    image_folder: str = ""
    image_width: int = 400
    image_height: int = 700
    grayscale: bool = False
    flip_horizontal: bool = False
    timer_position: str = "bottom_right"
    timer_font_size: str = "large"
    time_seconds: int = 5
    language: str = "ko"
    dark_mode: bool = False
    study_mode: bool = False
    today_croquis_count_position: str = "top_right"
    today_croquis_count_font_size: str = "medium"


@dataclass
class CroquisRecord:
    """Croquis record data class"""
    date: str
    count: int

# ============== Heatmap widget ==============
class HeatmapWidget(QWidget):
    """GitHub-style croquis heatmap widget"""
    
    def __init__(self, parent=None, lang: str = "ko"):
        super().__init__(parent)
        self.lang = lang
        self.data: Dict[str, int] = {}
        self.cell_size = 8
        self.cell_gap = 1
        self.weeks = 53
        self.days = 7
        self.total_count = 0
        self.load_data()
        self.setMinimumHeight(120)
        self.setMaximumHeight(120)
        self.setMouseTracking(True)
        self.hover_date = None
        self.hover_pos = None
        
    def load_data(self):
        """Load history data"""
        dat_dir = get_data_path() / "dat"
        dat_dir.mkdir(exist_ok=True)
        data_path = dat_dir / "croquis_history.dat"
        if data_path.exists():
            try:
                with open(data_path, "rb") as f:
                    encrypted = f.read()
                decrypted = decrypt_data(encrypted)
                self.data = decrypted
                self.total_count = sum(self.data.values())
            except Exception:
                self.data = {}
                self.total_count = 0
        else:
            self.data = {}
            self.total_count = 0
    
    def save_data(self):
        """Save history data"""
        dat_dir = get_data_path() / "dat"
        dat_dir.mkdir(exist_ok=True)
        data_path = dat_dir / "croquis_history.dat"
        encrypted = encrypt_data(self.data)
        with open(data_path, "wb") as f:
            f.write(encrypted)
    
    def add_croquis(self, count: int = 1):
        """Increment daily croquis count"""
        today = date.today().isoformat()
        self.data[today] = self.data.get(today, 0) + count
        self.total_count += count
        self.save_data()
        self.update()
    
    def get_color(self, count: int) -> QColor:
        """Return color based on count"""
        if count == 0:
            return QColor(235, 237, 240)
        elif count <= 2:
            return QColor(155, 233, 168)
        elif count <= 5:
            return QColor(64, 196, 99)
        elif count <= 10:
            return QColor(48, 161, 78)
        else:
            return QColor(33, 110, 57)
    
    def paintEvent(self, event: QPaintEvent):
        """Draw the heatmap"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Month labels
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        today = date.today()
        start_date = today - timedelta(days=365)
        
        # Draw month labels
        painter.setFont(QFont("Arial", 9))
        painter.setPen(QColor(100, 100, 100))
        
        x_offset = 60
        y_offset = 20
        
        # Compute start position per month and draw labels
        current_month = 0
        for week in range(self.weeks):
            check_date = start_date + timedelta(weeks=week)
            if check_date.month != current_month:
                current_month = check_date.month
                x = x_offset + week * (self.cell_size + self.cell_gap)
                painter.drawText(x, y_offset - 8, months[current_month - 1])
        
        # Draw heatmap cells
        for week in range(self.weeks):
            for day in range(self.days):
                cell_date = start_date + timedelta(weeks=week, days=day)
                if cell_date > today:
                    continue
                
                date_str = cell_date.isoformat()
                count = self.data.get(date_str, 0)
                color = self.get_color(count)
                
                x = x_offset + week * (self.cell_size + self.cell_gap)
                y = y_offset + day * (self.cell_size + self.cell_gap)
                
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(x, y, self.cell_size, self.cell_size, 2, 2)
        
        # Draw legend
        legend_x = x_offset
        legend_y = y_offset + self.days * (self.cell_size + self.cell_gap) + 10
        
        painter.setPen(QColor(100, 100, 100))
        painter.drawText(legend_x, legend_y + 10, tr("less", self.lang))
        
        legend_colors = [0, 1, 3, 6, 11]
        for i, c in enumerate(legend_colors):
            color = self.get_color(c)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            lx = legend_x + 35 + i * (self.cell_size + 2)
            painter.drawRoundedRect(lx, legend_y, self.cell_size, self.cell_size, 2, 2)
        
        painter.setPen(QColor(100, 100, 100))
        painter.drawText(legend_x + 35 + 5 * (self.cell_size + 2) + 5, legend_y + 10, tr("more", self.lang))
        
        # Show hover tooltip
        if self.hover_date and self.hover_pos:
            count = self.data.get(self.hover_date, 0)
            tooltip_text = f"{self.hover_date}: {count} {(tr('croquis_times', self.lang))}"
            
            painter.setFont(QFont("Arial", 10))
            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance(tooltip_text)
            text_height = fm.height()
            
            # Tooltip background with bounds adjustment
            padding = 5
            tooltip_width = text_width + padding * 2
            tooltip_height = text_height + padding * 2
            
            tooltip_x = self.hover_pos.x() + 10
            tooltip_y = self.hover_pos.y() - 25
            
            # If it would overflow to the right, place on the left
            if tooltip_x + tooltip_width > self.width():
                tooltip_x = self.hover_pos.x() - tooltip_width - 10
            
            # If it would overflow above, place below
            if tooltip_y < 0:
                tooltip_y = self.hover_pos.y() + 10
            
            painter.setBrush(QBrush(QColor(50, 50, 50, 230)))
            painter.setPen(QPen(QColor(200, 200, 200)))
            painter.drawRoundedRect(
                tooltip_x, tooltip_y,
                tooltip_width, tooltip_height,
                3, 3
            )
            
            # Tooltip text
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                tooltip_x + padding,
                tooltip_y + padding + fm.ascent(),
                tooltip_text
            )
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Track mouse movement over the heatmap"""
        today = date.today()
        start_date = today - timedelta(days=365)
        x_offset = 60
        y_offset = 20  # Start below month labels
        
        mx = event.pos().x()
        my = event.pos().y()
        
        found = False
        for week in range(self.weeks):
            for day in range(self.days):
                cell_date = start_date + timedelta(weeks=week, days=day)
                if cell_date > today:
                    continue
                
                x = x_offset + week * (self.cell_size + self.cell_gap)
                y = y_offset + day * (self.cell_size + self.cell_gap)
                
                if x <= mx <= x + self.cell_size and y <= my <= y + self.cell_size:
                    self.hover_date = cell_date.isoformat()
                    self.hover_pos = event.pos()
                    found = True
                    self.update()
                    break
            if found:
                break
        
        if not found:
            if self.hover_date is not None:
                self.hover_date = None
                self.hover_pos = None
                self.update()
    
    def leaveEvent(self, event):
        """Reset hover state when the cursor leaves"""
        self.hover_date = None
        self.hover_pos = None
        self.update()


# ============== Screenshot mode widget ==============
class ScreenshotOverlay(QWidget):
    """Screenshot mode overlay"""
    
    screenshot_taken = pyqtSignal(QPixmap)
    cancelled = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        self.start_pos = None
        self.end_pos = None
        self.selecting = False
        self.screenshot = None
        
    def start_capture(self):
        """Begin screenshot capture"""
        # Reset selection area
        self.start_pos = None
        self.end_pos = None
        self.selecting = False
        
        screen = QGuiApplication.primaryScreen()
        self.screenshot = screen.grabWindow(0)
        self.setGeometry(screen.geometry())
        self.showFullScreen()
        self.activateWindow()
        
    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        
        if self.screenshot:
            painter.drawPixmap(0, 0, self.screenshot)
        
        # Semi-transparent dark overlay
        overlay = QColor(0, 0, 0, 128)
        painter.fillRect(self.rect(), overlay)
        
        # Draw selection rectangle
        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            
            # Show the original image within the selection (1:1)
            if self.screenshot:
                # Account for devicePixelRatio when mapping to source
                ratio = self.screenshot.devicePixelRatio()
                source_rect = QRect(
                    int(rect.x() * ratio),
                    int(rect.y() * ratio),
                    int(rect.width() * ratio),
                    int(rect.height() * ratio)
                )
                # Draw using the original pixels
                painter.drawPixmap(rect, self.screenshot, source_rect)
            
            # White border
            pen = QPen(QColor(255, 255, 255), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.selecting = True
            self.update()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.selecting:
            self.end_pos = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.selecting:
            self.selecting = False
            self.end_pos = event.pos()
            
            if self.start_pos and self.end_pos:
                rect = QRect(self.start_pos, self.end_pos).normalized()
                if rect.width() > 10 and rect.height() > 10:
                    # Adjust for devicePixelRatio to crop accurate region
                    ratio = self.screenshot.devicePixelRatio()
                    scaled_rect = QRect(
                        int(rect.x() * ratio),
                        int(rect.y() * ratio),
                        int(rect.width() * ratio),
                        int(rect.height() * ratio)
                    )
                    cropped = self.screenshot.copy(scaled_rect)
                    self.hide()
                    self.screenshot_taken.emit(cropped)
                    return
            
            self.update()
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()


# ============== Image viewer window ==============
class ImageViewerWindow(QWidget):
    """Croquis image viewer window"""
    
    croquis_completed = pyqtSignal()
    croquis_saved = pyqtSignal(QPixmap, QPixmap, int, str, dict)  # original, screenshot, duration, filename, metadata
    
    def __init__(self, settings: CroquisSettings, images: List[Any], lang: str = "ko", parent=None):
        super().__init__(parent)
        self.setWindowIcon(get_app_icon())  # Set window icon
        self.settings = settings
        self.images = images  # List of str (file path) or dict (image data)
        self.lang = lang
        self.current_index = 0
        self.paused = False
        self.remaining_time = settings.time_seconds if not settings.study_mode else 0
        self.elapsed_time = 0  # Elapsed time for study mode
        self.random_seed = None
        
        # Set window icon
        self.setWindowIcon(get_app_icon())
        
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
        
        # Compute weights (higher difficulty appears more often)
        weights = []
        for img in images:
            if isinstance(img, dict):
                difficulty = img.get("difficulty", 1)
                # Weight as difficulty^2 (1→1, 2→4, 3→9, 4→16, 5→25)
                weight = difficulty * difficulty
                weights.append(weight)
            else:
                weights.append(1)
        
        # Weighted random selection
        total_weight = sum(weights)
        if total_weight == 0:
            return images
        
        result = []
        remaining = images.copy()
        remaining_weights = weights.copy()
        
        while remaining:
            # Build cumulative probability
            cumulative = []
            cumsum = 0
            for w in remaining_weights:
                cumsum += w
                cumulative.append(cumsum)
            
            # Pick by random threshold
            rand_val = random.random() * cumsum
            for i, cum in enumerate(cumulative):
                if rand_val <= cum:
                    result.append(remaining[i])
                    remaining.pop(i)
                    remaining_weights.pop(i)
                    break
        
        return result
        
    def setup_ui(self):
        # Configure window without title bar
        self.setWindowFlags(
            Qt.WindowType.Window | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint  # Keep above other apps
        )
        self.setFixedSize(self.settings.image_width, self.settings.image_height + 50)  # Fixed size
        
        # Center on screen
        screen = QGuiApplication.primaryScreen().geometry()
        x = (screen.width() - self.settings.image_width) // 2
        y = (screen.height() - (self.settings.image_height + 50)) // 2
        self.move(x, y)
        
        # Track mouse drag position for moving
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
        
        # Timer label over the image
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
        
        # Today's croquis count label over the image
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
        
        # Control button area
        control_widget = QWidget()
        control_widget.setStyleSheet("background-color: #333;")
        control_layout = QHBoxLayout(control_widget)
        control_layout.setContentsMargins(10, 5, 10, 5)
        
        # Load resource loader
        resource_loader = QtResourceLoader()
        
        # Icon buttons
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
        """Update today's croquis count display"""
        count = self.load_today_croquis_count()
        self.today_count_label.setText(f"{count} {tr('croquis_times', self.lang)}")
        self.today_count_label.adjustSize()
    
    def update_today_count_font(self):
        """Update today's croquis count font size"""
        sizes = {"large": 20, "medium": 15, "small": 10}
        size = sizes.get(self.settings.today_croquis_count_font_size, 15)
        font = QFont("Arial", size, QFont.Weight.Bold)
        self.today_count_label.setFont(font)
    
    def update_today_count_position(self):
        """Update today's croquis count position, avoiding overlap with timer"""
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
            # If positions match, adjust based on vertical position
            if "top" in pos:
                # Move today count below timer
                timer_h = self.timer_label.height()
                y = margin + timer_h + 5
            else:  # "bottom" in pos
                # Move today count above timer
                timer_h = self.timer_label.height()
                y = ch - h - margin - timer_h - 5
        
        self.today_count_label.move(x, y)
        
    def load_current_image(self):
        if 0 <= self.current_index < len(self.images):
            image_item = self.images[self.current_index]
            
            # Load image (dict or str)
            if isinstance(image_item, dict):
                # New format: decode image_data from dict
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
                # Legacy format: load directly from file path
                pixmap = QPixmap(image_item)
                self.current_filename = os.path.basename(image_item)
            
            if self.settings.grayscale:
                image = pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
                pixmap = QPixmap.fromImage(image)
            
            if self.settings.flip_horizontal:
                from PyQt6.QtGui import QTransform
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
                # Study mode: count up
                self.elapsed_time += 1
                self.update_timer_display()
            else:
                # Regular mode: count down
                if self.remaining_time > 0:
                    self.remaining_time -= 1
                    self.update_timer_display()
                    
                    if self.remaining_time == 0:
                        self.timer.stop()
                        # 화면이 00:00으로 업데이트될 시간을 준 후 스크린샷 캡처
                        QTimer.singleShot(150, self.start_screenshot_mode)
                
    def start_screenshot_mode(self):
        logger.info(LOG_MESSAGES["screenshot_mode_enabled"])
        self.screenshot_overlay.start_capture()
        
    def on_screenshot_taken(self, screenshot: QPixmap):
        # Build custom confirmation dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("save_croquis", self.lang))
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        # Show large preview image
        image_label = QLabel()
        preview = screenshot.scaled(500, 500, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        image_label.setPixmap(preview)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(image_label)
        
        # Question prompt
        question_label = QLabel(tr("save_question", self.lang))
        question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        question_label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(question_label)
        
        # Button area
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
        # Calculate croquis duration
        if self.settings.study_mode:
            croquis_time = self.elapsed_time
        else:
            croquis_time = self.settings.time_seconds
        
        # Extract current image info
        current_image = self.images[self.current_index]
        
        if isinstance(current_image, dict):
            # New format: use metadata from dict
            image_filename = os.path.splitext(current_image.get("filename", "unknown"))[0]
            image_metadata = {
                "filename": current_image.get("filename", "unknown"),
                "path": current_image.get("original_path", ""),
                "width": current_image.get("width", self.current_pixmap.width()),
                "height": current_image.get("height", self.current_pixmap.height()),
                "size": current_image.get("size", 0)
            }
        else:
            # Legacy format: extract metadata from file path
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
            # Study mode: switch to screenshot capture
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
            # Loop back to the first image
            self.current_index = 0
        self.load_current_image()
        self.update_today_count_display()  # Update count display
        self.timer.start(1000)
            
    def next_image_no_screenshot(self):
        if self.settings.study_mode:
            # Study mode: switch to screenshot capture
            self.timer.stop()
            self.start_screenshot_mode()
        else:
            self.next_image()
        
    def toggle_pause(self):
        self.paused = not self.paused
        logger.info(LOG_MESSAGES["croquis_paused" if self.paused else "croquis_playing"])
        
        # Swap play/pause icon
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



# ============== Difficulty widget ==============
class DifficultyWidget(QWidget):
    """Difficulty display widget (number plus colored star)"""
    
    def __init__(self, difficulty: int, parent=None):
        super().__init__(parent)
        self.difficulty = difficulty
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(3)
        
        # Background style
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 150);
                border-radius: 8px;
            }
        """)
        
        # Layer 1: difficulty number (white)
        number_label = QLabel(str(self.difficulty))
        number_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 11px;
                font-weight: bold;
                background-color: transparent;
            }
        """)
        layout.addWidget(number_label)
        
        # Layer 2: star widget (transparent background, colored star)
        star_label = QLabel("★")
        colors = ["#FFD700", "#FFA500", "#FF8C00", "#FF4500", "#FF0000"]
        color = colors[self.difficulty - 1] if 1 <= self.difficulty <= 5 else "#FFD700"
        star_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 11px;
                font-weight: bold;
                background-color: transparent;
            }}
        """)
        layout.addWidget(star_label)
        
        self.setFixedHeight(20)


# ============== Deck item widget ==============
class DeckItemWidget(QWidget):
    """Deck editor item widget (image with clickable difficulty)"""
    
    def __init__(self, pixmap: QPixmap, img_data: dict, parent_window, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.img_data = img_data
        self.parent_window = parent_window
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Image container
        container = QWidget()
        container.setFixedSize(DECK_ICON_WIDTH, DECK_ICON_HEIGHT)
        
        # Image label
        image_label = QLabel(container)
        image_label.setPixmap(self.pixmap)
        image_label.setFixedSize(DECK_ICON_WIDTH, DECK_ICON_HEIGHT)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Difficulty button (clickable)
        difficulty = self.img_data.get("difficulty", 1)
        self.difficulty_btn = QPushButton(container)
        self.difficulty_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_difficulty_display()
        self.difficulty_btn.clicked.connect(self.cycle_difficulty)
        
        layout.addWidget(container)
        
        # Filename
        filename_label = QLabel(f"{self.img_data['filename']}")
        filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        filename_label.setWordWrap(True)
        filename_label.setStyleSheet("font-size: 9px;")
        layout.addWidget(filename_label)
        
        self.filename_label = filename_label
    
    def update_difficulty_display(self):
        """Update difficulty display"""
        difficulty = self.img_data.get("difficulty", 1)
        
        # Choose star color
        colors = ["#FFD700", "#FFA500", "#FF8C00", "#FF4500", "#FF0000"]
        color = colors[difficulty - 1] if 1 <= difficulty <= 5 else "#FFD700"
        
        # Build difficulty widget
        diff_widget = DifficultyWidget(difficulty)
        diff_widget.resize(diff_widget.sizeHint())
        
        # Render difficulty widget to pixmap
        diff_pixmap = QPixmap(diff_widget.size())
        diff_pixmap.fill(Qt.GlobalColor.transparent)
        diff_widget.render(diff_pixmap)
        
        # Apply as button icon
        self.difficulty_btn.setIcon(QIcon(diff_pixmap))
        self.difficulty_btn.setIconSize(diff_pixmap.size())
        self.difficulty_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
        """)
        
        # Position button at bottom-right
        btn_size = diff_pixmap.size()
        self.difficulty_btn.setFixedSize(btn_size)
        self.difficulty_btn.move(90 - btn_size.width(), 110 - btn_size.height())
    
    def cycle_difficulty(self):
        """Cycle difficulty (1→2→3→4→5→1)"""
        current = self.img_data.get("difficulty", 1)
        new_difficulty = (current % 5) + 1
        
        self.img_data["difficulty"] = new_difficulty
        logger.info(LOG_MESSAGES["difficulty_changed"].format(self.img_data['filename'], new_difficulty))
        
        # Update parent window deck_images
        filename = self.img_data["filename"]
        for i, deck_img in enumerate(self.parent_window.deck_images):
            if deck_img.get("filename") == filename:
                self.parent_window.deck_images[i]["difficulty"] = new_difficulty
                break
        
        # Refresh UI
        self.update_difficulty_display()
        
        # Refresh filename label
        self.filename_label.setText(f"{self.img_data['filename']}")
        
        self.parent_window.save_temp_file()
        self.parent_window.mark_modified()


# ============== Image property dialogs ==============
class ImageRenameDialog(QDialog):
    """Dialog to rename an image file"""
    
    def __init__(self, current_name: str, lang: str, parent=None):
        super().__init__(parent)
        self.setWindowIcon(get_app_icon())
        self.lang = lang
        self.setWindowTitle(tr("rename_title", self.lang))
        self.resize(380, 160)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Split extension from filename
        import os
        name_without_ext, ext = os.path.splitext(current_name)
        self.extension = ext
        
        # Current name display
        current_layout = QHBoxLayout()
        current_layout.addWidget(QLabel(tr("current_label", self.lang)))
        current_label = QLabel(current_name)
        current_label.setStyleSheet("color: #666; padding: 3px;")
        current_layout.addWidget(current_label, 1)
        layout.addLayout(current_layout)
        
        # New name input
        new_layout = QHBoxLayout()
        new_layout.addWidget(QLabel(tr("new_name_label", self.lang)))
        self.name_edit = QLineEdit()
        self.name_edit.setText(name_without_ext)
        self.name_edit.selectAll()
        self.name_edit.setPlaceholderText(tr("name_placeholder", self.lang))
        new_layout.addWidget(self.name_edit, 1)
        layout.addLayout(new_layout)
        
        # Disallowed character hint
        invalid_chars_label = QLabel(tr("invalid_chars", self.lang))
        invalid_chars_label.setStyleSheet("color: #999; font-size: 10px; padding: 3px;")
        layout.addWidget(invalid_chars_label)
        
        layout.addStretch()
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_new_name(self) -> str:
        """Return new filename including extension"""
        new_name = self.name_edit.text().strip()
        
        # Remove disallowed characters
        invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '.']
        for char in invalid_chars:
            new_name = new_name.replace(char, '')
        
        return new_name + self.extension if new_name else None


class ImageTagDialog(QDialog):
    """Dialog to configure image tags"""
    
    def __init__(self, current_tags: List[str], lang: str, parent=None):
        super().__init__(parent)
        self.setWindowIcon(get_app_icon())
        self.lang = lang
        self.setWindowTitle(tr("tag_title", self.lang))
        self.resize(420, 170)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Info label
        info_label = QLabel(tr("tag_info", self.lang))
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(info_label)
        
        # Example label
        example_label = QLabel(tr("tag_example", self.lang))
        example_label.setStyleSheet("color: #666; font-size: 11px; padding-left: 5px;")
        layout.addWidget(example_label)
        
        # Tag input
        self.tag_edit = QLineEdit()
        self.tag_edit.setPlaceholderText(tr("tag_placeholder", self.lang))
        if current_tags:
            self.tag_edit.setText('#' + '#'.join(current_tags))
        self.tag_edit.setStyleSheet("padding: 8px; font-size: 12px;")
        layout.addWidget(self.tag_edit)
        
        layout.addStretch()
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_tags(self) -> List[str]:
        """Return tag list"""
        text = self.tag_edit.text().strip()
        if not text:
            return []
        
        # If not starting with '#', trim everything before the first '#'
        if not text.startswith('#'):
            hash_pos = text.find('#')
            if hash_pos > 0:
                text = text[hash_pos:]
            elif hash_pos == -1:
                # No '#', return empty list
                return []
        
        # Split by '#'
        tags = [tag.strip() for tag in text.split('#') if tag.strip()]
        
        # Limit each tag to 24 characters
        tags = [tag[:24] for tag in tags]
        
        return tags


class ImagePropertiesDialog(QDialog):
    """Dialog to display image properties"""
    
    def __init__(self, img_data: dict, lang: str, parent=None):
        super().__init__(parent)
        self.setWindowIcon(get_app_icon())
        self.lang = lang
        self.setWindowTitle(tr("properties_title", self.lang))
        self.resize(450, 320)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel(tr("properties_heading", self.lang))
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding-bottom: 5px;")
        layout.addWidget(title)
        
        # Image info display
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(8)
        
        properties = [
            (tr("prop_filename", self.lang), img_data.get('filename', tr("unknown", self.lang))),
            (tr("prop_size", self.lang), self.format_size(img_data.get('size', 0))),
            (tr("prop_dimensions", self.lang), f"{img_data.get('width', 0)} × {img_data.get('height', 0)} px"),
            (tr("prop_difficulty", self.lang), f"{img_data.get('difficulty', 1)} {'★' * img_data.get('difficulty', 1)}"),
            (tr("prop_tags", self.lang), ', '.join(img_data.get('tags', [])) if img_data.get('tags') else tr("none", self.lang)),
            (tr("prop_source_path", self.lang), img_data.get('original_path', tr("unknown", self.lang)))
        ]
        
        for label_text, value_text in properties:
            prop_layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: bold; min-width: 90px;")
            value = QLabel(str(value_text))
            value.setWordWrap(True)
            value.setStyleSheet("color: #555;")
            prop_layout.addWidget(label)
            prop_layout.addWidget(value, 1)
            info_layout.addLayout(prop_layout)
        
        layout.addWidget(info_widget)
        layout.addStretch()
        
        # Close button
        close_btn = QPushButton(tr("close", self.lang))
        close_btn.setFixedHeight(32)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def format_size(self, size_bytes: int) -> str:
        """Format bytes into a human-readable size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"


# ============== Custom deck list widget ==============
class DeckListWidget(QListWidget):
    """Custom list widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcut (Ctrl+V paste)"""
        if event.key() == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Call parent window paste_image_from_clipboard
            parent_window = self.parent()
            while parent_window and not isinstance(parent_window, DeckEditorWindow):
                parent_window = parent_window.parent()
            if parent_window:
                parent_window.paste_image_from_clipboard()
        else:
            super().keyPressEvent(event)


# ============== Croquis deck editor ==============
class DeckEditorWindow(QMainWindow):
    """Croquis deck editor window"""
    
    def __init__(self, lang: str = "ko", dark_mode: bool = False, parent=None):
        super().__init__(parent)
        self.lang = lang
        self.dark_mode = dark_mode
        self.deck_images: List[Dict[str, Any]] = []  # List of image info dicts
        self.current_deck_path = None
        self.temp_file_path = None  # Temp file path
        self.is_modified = False  # Tracks unsaved changes
        
        # Sort settings
        self.sort_by = "name"  # name, size, difficulty, date
        self.sort_order = "asc"  # asc, desc
        
        # Icon scale
        self.icon_scale = 100  # Default 100%
        
        # Lazy loading settings
        self.lazy_load_batch_size = 50  # Load 50 items at a time
        self.lazy_load_current_index = 0
        self.lazy_load_timer = QTimer(self)
        self.lazy_load_timer.timeout.connect(self._load_next_batch)
        
        # Recent files (max 5)
        self.recent_files = self.load_recent_files()
        
        self.setup_temp_file()
        self.setup_ui()
        self.apply_dark_mode()
        self.update_title()
    
    def setup_temp_file(self):
        """Initialize temporary file"""
        temp_dir = get_data_path() / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        # Generate unique temp filename
        import uuid
        temp_id = str(uuid.uuid4())[:8]
        self.temp_file_path = temp_dir / f"deck_{temp_id}.temp"
        
        # Create empty temp file
        self.save_temp_file()
    
    def save_temp_file(self):
        """Save current deck state to temp file (async)"""
        if not self.temp_file_path:
            return
        
        # Use QTimer for async save
        QTimer.singleShot(0, self._save_temp_file_async)
    
    def _save_temp_file_async(self):
        """Async temp file save"""
        try:
            data = {
                "images": self.deck_images,
                "current_path": self.current_deck_path
            }
            
            encrypted = encrypt_data(data)
            
            with open(self.temp_file_path, "wb") as f:
                f.write(encrypted)
        except Exception as e:
            print(tr("temp_file_save_failed", self.lang).format(e))
    
    def load_temp_file(self, source_path: str = None):
        """Load temp file (copy from deck file or start new)"""
        try:
            if source_path and os.path.exists(source_path):
                # Copy from existing deck
                with open(source_path, "rb") as f:
                    encrypted = f.read()
                data = decrypt_data(encrypted)
                self.deck_images = data.get("images", [])
            else:
                # Start fresh
                self.deck_images = []
            
            self.save_temp_file()
            self.update_image_list()
        except Exception as e:
            print(tr("temp_file_load_failed", self.lang).format(e))
            self.deck_images = []
    
    def cleanup_temp_file(self):
        """Remove temp file"""
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            try:
                os.unlink(self.temp_file_path)
            except Exception as e:
                print(tr("temp_file_delete_failed", self.lang).format(e))
        
    def setup_ui(self):
        self.setWindowTitle(tr("edit_deck", self.lang))
        self.resize(1000, 600)
        
        # Set window icon
        self.setWindowIcon(get_app_icon())
        
        # Menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu(tr("file", self.lang))
        
        new_action = QAction(tr("new", self.lang), self)
        new_action.triggered.connect(self.new_deck)
        file_menu.addAction(new_action)
        
        open_action = QAction(tr("open", self.lang), self)
        open_action.triggered.connect(self.open_deck)
        file_menu.addAction(open_action)
        
        # Open Recent submenu
        self.recent_menu = file_menu.addMenu(tr("open_recent", self.lang))
        self.update_recent_menu()
        
        save_action = QAction(tr("save", self.lang), self)
        save_action.triggered.connect(self.save_deck)
        file_menu.addAction(save_action)
        
        self.save_as_action = QAction(tr("save_as", self.lang), self)
        self.save_as_action.triggered.connect(self.save_deck_as)
        file_menu.addAction(self.save_as_action)
        
        # View menu
        view_menu = menubar.addMenu(tr("view", self.lang))
        
        # Sort submenu
        sort_menu = view_menu.addMenu(tr("sort", self.lang))
        
        # Sort criteria
        self.sort_name_action = QAction(tr("sort_name", self.lang), self)
        self.sort_name_action.triggered.connect(lambda: self.set_sort_by("name"))
        sort_menu.addAction(self.sort_name_action)
        
        self.sort_size_action = QAction(tr("sort_size", self.lang), self)
        self.sort_size_action.triggered.connect(lambda: self.set_sort_by("size"))
        sort_menu.addAction(self.sort_size_action)
        
        self.sort_difficulty_action = QAction(tr("sort_difficulty", self.lang), self)
        self.sort_difficulty_action.triggered.connect(lambda: self.set_sort_by("difficulty"))
        sort_menu.addAction(self.sort_difficulty_action)
        
        self.sort_date_action = QAction(tr("sort_date", self.lang), self)
        self.sort_date_action.triggered.connect(lambda: self.set_sort_by("date"))
        sort_menu.addAction(self.sort_date_action)
        
        sort_menu.addSeparator()
        
        # Sort order
        self.sort_asc_action = QAction(tr("sort_asc", self.lang), self)
        self.sort_asc_action.triggered.connect(lambda: self.set_sort_order("asc"))
        sort_menu.addAction(self.sort_asc_action)
        
        self.sort_desc_action = QAction(tr("sort_desc", self.lang), self)
        self.sort_desc_action.triggered.connect(lambda: self.set_sort_order("desc"))
        sort_menu.addAction(self.sort_desc_action)
        
        # Default sort (name asc); kept non-checkable
        # self.sort_name_action.setChecked(True)
        # self.sort_asc_action.setChecked(True)
        
        # Icon size submenu
        icon_size_menu = view_menu.addMenu(tr("icon_size", self.lang))
        
        self.icon_50_action = QAction("50%", self)
        self.icon_50_action.triggered.connect(lambda: self.set_icon_scale(50))
        icon_size_menu.addAction(self.icon_50_action)
        
        self.icon_75_action = QAction("75%", self)
        self.icon_75_action.triggered.connect(lambda: self.set_icon_scale(75))
        icon_size_menu.addAction(self.icon_75_action)
        
        self.icon_100_action = QAction("100%", self)
        self.icon_100_action.triggered.connect(lambda: self.set_icon_scale(100))
        icon_size_menu.addAction(self.icon_100_action)
        
        self.icon_125_action = QAction("125%", self)
        self.icon_125_action.triggered.connect(lambda: self.set_icon_scale(125))
        icon_size_menu.addAction(self.icon_125_action)
        
        self.icon_150_action = QAction("150%", self)
        self.icon_150_action.triggered.connect(lambda: self.set_icon_scale(150))
        icon_size_menu.addAction(self.icon_150_action)
        
        self.icon_200_action = QAction("200%", self)
        self.icon_200_action.triggered.connect(lambda: self.set_icon_scale(200))
        icon_size_menu.addAction(self.icon_200_action)
        
        self.icon_custom_action = QAction(tr("custom", self.lang), self)
        self.icon_custom_action.triggered.connect(self.set_custom_icon_scale)
        icon_size_menu.addAction(self.icon_custom_action)
        
        # Default icon scale (100%); kept non-checkable
        # self.icon_100_action.setChecked(True)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        
        # Left: deck image area
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Top buttons
        button_layout = QHBoxLayout()
        import_btn = QPushButton(tr("import_images", self.lang))
        import_btn.clicked.connect(self.import_images)
        button_layout.addWidget(import_btn)
        
        delete_btn = QPushButton(tr("delete_selected", self.lang))
        delete_btn.clicked.connect(self.delete_selected_images)
        button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        
        left_layout.addLayout(button_layout)
        
        self.image_list = DeckListWidget()
        self.image_list.setIconSize(QSize(DECK_ICON_WIDTH, DECK_ICON_HEIGHT))
        self.image_list.setGridSize(QSize(DECK_GRID_WIDTH, DECK_GRID_HEIGHT))
        self.image_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.image_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.image_list.setMovement(QListWidget.Movement.Static)  # Keep static movement
        self.image_list.setFlow(QListWidget.Flow.LeftToRight)
        self.image_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)  # Allow multi-select via drag
        self.image_list.setSpacing(DECK_SPACING)
        self.image_list.setWordWrap(True)
        self.image_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.image_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)  # Ellipsize long filenames in the middle
        self.image_list.setUniformItemSizes(True)  # Enable uniform item sizes for performance
        self.image_list.verticalScrollBar().valueChanged.connect(self._on_image_list_scroll)
        self.image_list.setStyleSheet("""
            QListWidget::item {
                text-align: center;
                padding: 3px;
            }
            QListWidget::item:selected {
                background-color: rgba(0, 120, 212, 0.2);
            }
            QListWidget::item:hover {
                background-color: rgba(0, 120, 212, 0.1);
            }
            QListWidget {
                outline: none;
            }
        """)
        # Click event (show croquis list)
        self.image_list.itemClicked.connect(self.on_deck_item_clicked)
        # Double-click event (change difficulty)
        self.image_list.itemDoubleClicked.connect(self.on_deck_item_double_clicked)
        # Context menu (change difficulty)
        self.image_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.image_list.customContextMenuRequested.connect(self.show_image_context_menu)
        left_layout.addWidget(self.image_list)
        
        layout.addWidget(left_widget, 2)
        
        # Right: croquis list
        right_widget = QGroupBox(tr("croquis_list", self.lang))
        right_layout = QVBoxLayout(right_widget)
        
        # Croquis list widget
        self.croquis_list = QListWidget()
        self.croquis_list = QListWidget()
        self.croquis_list.setIconSize(QSize(DECK_ICON_WIDTH, DECK_ICON_HEIGHT))
        self.croquis_list.setGridSize(QSize(DECK_GRID_WIDTH, DECK_GRID_HEIGHT))
        self.croquis_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.croquis_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.croquis_list.setMovement(QListWidget.Movement.Static)  # Keep static movement
        self.croquis_list.setFlow(QListWidget.Flow.LeftToRight)
        self.croquis_list.setSpacing(DECK_SPACING)
        self.croquis_list.setWordWrap(True)  # Allow text wrapping
        self.croquis_list.setUniformItemSizes(True)  # Enable uniform item sizes for performance
        self.croquis_list.setStyleSheet("""
            QListWidget::item {
                text-align: center;
                padding: 3px;
            }
            QListWidget::item:selected {
                background-color: rgba(0, 120, 212, 0.2);
            }
        """)
        self.croquis_list.itemClicked.connect(self.show_croquis_large_view)
        self.croquis_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.croquis_list.customContextMenuRequested.connect(self.show_croquis_context_menu)
        self.croquis_list.hide()  # Hidden by default
        right_layout.addWidget(self.croquis_list)
        
        layout.addWidget(right_widget, 1)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasText() or event.mimeData().hasHtml():
            event.acceptProposedAction()
            
    def dropEvent(self, event: QDropEvent):
        # Handle URL drops
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path and path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                    self.add_image_to_deck(path)
                elif not path:  # URL drop that is not a local file
                    url_str = url.toString()
                    if url_str.startswith('http://') or url_str.startswith('https://'):
                        self.download_image_from_url(url_str)
        
        # Handle text/URL drops (e.g., Pinterest links)
        elif event.mimeData().hasText():
            text = event.mimeData().text().strip()
            # Detect URL pattern
            if text.startswith('http://') or text.startswith('https://'):
                self.download_image_from_url(text)
        
        # Handle HTML drops (Pinterest may provide HTML)
        elif event.mimeData().hasHtml():
            html = event.mimeData().html()
            # Extract URLs from HTML
            import re
            # Find img src patterns
            img_patterns = [
                r'<img[^>]+src=["\']([^"\']+)["\']',
                r'https?://[^\s<>"\']+(\.(jpg|jpeg|png|gif|bmp|webp))',
            ]
            for pattern in img_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    for match in matches:
                        url = match if isinstance(match, str) else match[0]
                        if url.startswith('http://') or url.startswith('https://'):
                            self.download_image_from_url(url)
                            break
                    break
    
    def download_image_from_url(self, url: str):
        """Download image from URL"""
        try:
            import urllib.request
            import tempfile
            import re
            from urllib.parse import urlparse, unquote
            
            # If Pinterest URL, try to extract the image URL
            if 'pinterest.com' in url:
                # Attempt to extract image URL from Pinterest page
                try:
                    import ssl
                    import json
                    
                    # Create SSL context
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    
                    # Add User-Agent header
                    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                    req = urllib.request.Request(url, headers=headers)
                    
                    with urllib.request.urlopen(req, context=context, timeout=10) as response:
                        html = response.read().decode('utf-8')
                        
                        # Find image URL patterns (Pinterest originals)
                        patterns = [
                            r'"url":"(https://i\.pinimg\.com/originals/[^"]+)"',
                            r'"url":"(https://i\.pinimg\.com/[0-9]+x/[^"]+)"',
                            r'<meta property="og:image" content="([^"]+)"'
                        ]
                        
                        for pattern in patterns:
                            matches = re.findall(pattern, html)
                            if matches:
                                # Use the first (largest) image URL
                                image_url = matches[0].replace('\\/', '/')
                                logger.info(LOG_MESSAGES["pinterest_image_extracted"].format(image_url))
                                # Recurse with the extracted URL
                                self.download_image_from_url(image_url)
                                return
                except Exception as e:
                    logger.error(LOG_MESSAGES["pinterest_extraction_failed"].format(e))
                    print(tr("pinterest_extract_failed_msg", self.lang).format(e))
                    QMessageBox.warning(self, tr("warning", self.lang), tr("pinterest_extract_failed", self.lang))
                    return
            
            # Download image
            logger.info(LOG_MESSAGES["downloading_image"].format(url))
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                image_data = response.read()
                
                # Build filename
                parsed_url = urlparse(url)
                filename = os.path.basename(unquote(parsed_url.path))
                
                # If missing name or extension, fall back
                if not filename or '.' not in filename:
                    filename = f"downloaded_{hash(url) % 100000}.jpg"
                
                # Handle directly in memory
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)
                
                if pixmap.isNull():
                    QMessageBox.warning(self, tr("warning", self.lang), tr("invalid_image", self.lang))
                    return
                
                # Convert image to bytes
                from PyQt6.QtCore import QBuffer, QIODevice
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                pixmap.save(buffer, "PNG")
                image_bytes = buffer.data().data()
                
                # Build image info dictionary
                image_data_dict = {
                    "filename": filename,
                    "original_path": url,  # Store URL as original path
                    "width": pixmap.width(),
                    "height": pixmap.height(),
                    "size": len(image_bytes),
                    "image_data": base64.b64encode(image_bytes).decode(),
                    "difficulty": 1,
                    "tags": []
                }
                
                # Add to deck
                self.deck_images.append(image_data_dict)
                logger.info(LOG_MESSAGES["image_added_to_deck"].format(filename))
                self.save_temp_file()
                self.update_image_list()
                self.mark_modified()
                
        except Exception as e:
            logger.error(LOG_MESSAGES["url_download_failed"].format(e))
            QMessageBox.warning(self, "오류", f"이미지를 다운로드하는 중 오류가 발생했습니다:\n{str(e)}")
                
    def add_image_to_deck(self, path: str, difficulty: int = 1):
        """Add image to deck and store metadata"""
        # Check for duplicates by filename
        filename = os.path.basename(path)
        logger.info(f"Added image to deck: {filename}")
        for img_data in self.deck_images:
            if img_data.get("filename") == filename:
                return  # Already added
        
        try:
            # Validate image and extract info
            pixmap = QPixmap(path)
            if pixmap.isNull():
                QMessageBox.warning(self, tr("warning", self.lang), f"{tr('invalid_image', self.lang)}: {filename}")
                return
            
            # Convert image to bytes (QBuffer)
            from PyQt6.QtCore import QBuffer, QIODevice
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            pixmap.save(buffer, "PNG")
            image_bytes = buffer.data().data()
            
            # Build image info dictionary
            image_data = {
                "filename": filename,
                "original_path": path,
                "width": pixmap.width(),
                "height": pixmap.height(),
                "size": len(image_bytes),
                "image_data": base64.b64encode(image_bytes).decode(),
                "difficulty": difficulty,
                "tags": []  # Add tag field
            }
            
            self.deck_images.append(image_data)
            self.save_temp_file()  # Update temp file
            self.update_image_list()  # Refresh UI
            self.mark_modified()
            
        except Exception as e:
            QMessageBox.warning(self, "오류", f"이미지 추가 실패: {str(e)}")
    
    def create_thumbnail_with_difficulty(self, img_data: dict) -> QPixmap:
        """Create thumbnail with difficulty overlay"""
        # Build pixmap from image data
        image_bytes = base64.b64decode(img_data["image_data"])
        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes)
        
        # Compute sizes
        icon_width = int(DECK_ICON_WIDTH * self.icon_scale / 100)
        icon_height = int(DECK_ICON_HEIGHT * self.icon_scale / 100)
        
        # Generate thumbnail (KeepAspectRatio)
        scaled_thumb = pixmap.scaled(
            icon_width, 
            icon_height, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Center on canvas
        thumbnail = QPixmap(icon_width, icon_height)
        thumbnail.fill(Qt.GlobalColor.transparent)
        thumb_painter = QPainter(thumbnail)
        thumb_x = (icon_width - scaled_thumb.width()) // 2
        thumb_y = (icon_height - scaled_thumb.height()) // 2
        thumb_painter.drawPixmap(thumb_x, thumb_y, scaled_thumb)
        
        # Add difficulty overlay (bottom-right) scaled by icon size
        difficulty = img_data.get("difficulty", 1)
        colors = ["#FFD700", "#FFA500", "#FF8C00", "#FF4500", "#FF0000"]
        star_color = colors[difficulty - 1] if 1 <= difficulty <= 5 else "#FFD700"
        
        # Scale overlay size
        overlay_width = int(32 * self.icon_scale / 100)
        overlay_height = int(18 * self.icon_scale / 100)
        overlay_offset_x = int(35 * self.icon_scale / 100)
        overlay_offset_y = int(20 * self.icon_scale / 100)
        font_size = max(8, int(10 * self.icon_scale / 100))
        
        # Semi-transparent dark background
        bg_rect = QRect(icon_width - overlay_offset_x, icon_height - overlay_offset_y, overlay_width, overlay_height)
        thumb_painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
        thumb_painter.setPen(Qt.PenStyle.NoPen)
        thumb_painter.drawRoundedRect(bg_rect, 8, 8)
        
        # Difficulty number (white)
        thumb_painter.setPen(QColor(255, 255, 255))
        thumb_painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
        thumb_painter.drawText(icon_width - int(32 * self.icon_scale / 100), icon_height - int(6 * self.icon_scale / 100), str(difficulty))
        
        # Star indicator (colored)
        thumb_painter.setPen(QColor(star_color))
        thumb_painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
        thumb_painter.drawText(icon_width - int(20 * self.icon_scale / 100), icon_height - int(6 * self.icon_scale / 100), "★")
        
        thumb_painter.end()
        return thumbnail
    
    def update_image_list(self):
        """Update image list UI with lazy loading"""
        self.image_list.clear()
        self.lazy_load_current_index = 0
        self.lazy_load_timer.stop()
        
        # Start lazy loading
        if self.deck_images:
            self._load_next_batch()
    
    def _load_next_batch(self):
        """Load next batch of images"""
        start_idx = self.lazy_load_current_index
        end_idx = min(start_idx + self.lazy_load_batch_size, len(self.deck_images))
        
        if start_idx >= len(self.deck_images):
            return
        
        for idx in range(start_idx, end_idx):
            try:
                img_data = self.deck_images[idx]
                
                # Compute sizes
                icon_width = int(DECK_ICON_WIDTH * self.icon_scale / 100)
                icon_height = int(DECK_ICON_HEIGHT * self.icon_scale / 100)
                grid_width = int(DECK_GRID_WIDTH * self.icon_scale / 100)
                grid_height = int(DECK_GRID_HEIGHT * self.icon_scale / 100)
                
                # Build pixmap from image data
                image_bytes = base64.b64decode(img_data["image_data"])
                pixmap = QPixmap()
                pixmap.loadFromData(image_bytes)
                
                # Generate thumbnail (KeepAspectRatio)
                scaled_thumb = pixmap.scaled(
                    icon_width, 
                    icon_height, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Center on canvas
                thumbnail = QPixmap(icon_width, icon_height)
                thumbnail.fill(Qt.GlobalColor.transparent)
                thumb_painter = QPainter(thumbnail)
                thumb_x = (icon_width - scaled_thumb.width()) // 2
                thumb_y = (icon_height - scaled_thumb.height()) // 2
                thumb_painter.drawPixmap(thumb_x, thumb_y, scaled_thumb)
                
                # Add difficulty overlay (bottom-right) scaled by icon size
                difficulty = img_data.get("difficulty", 1)
                colors = ["#FFD700", "#FFA500", "#FF8C00", "#FF4500", "#FF0000"]
                star_color = colors[difficulty - 1] if 1 <= difficulty <= 5 else "#FFD700"
                
                # Scale overlay size
                overlay_width = int(32 * self.icon_scale / 100)
                overlay_height = int(18 * self.icon_scale / 100)
                overlay_offset_x = int(35 * self.icon_scale / 100)
                overlay_offset_y = int(20 * self.icon_scale / 100)
                font_size = max(8, int(10 * self.icon_scale / 100))
                
                # Semi-transparent dark background
                bg_rect = QRect(icon_width - overlay_offset_x, icon_height - overlay_offset_y, overlay_width, overlay_height)
                thumb_painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
                thumb_painter.setPen(Qt.PenStyle.NoPen)
                thumb_painter.drawRoundedRect(bg_rect, 8, 8)
                
                # Difficulty number (white)
                thumb_painter.setPen(QColor(255, 255, 255))
                thumb_painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
                thumb_painter.drawText(icon_width - int(32 * self.icon_scale / 100), icon_height - int(6 * self.icon_scale / 100), str(difficulty))
                
                # Star indicator (colored)
                thumb_painter.setPen(QColor(star_color))
                thumb_painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
                thumb_painter.drawText(icon_width - int(20 * self.icon_scale / 100), icon_height - int(6 * self.icon_scale / 100), "★")
                
                thumb_painter.end()
                
                # Create list item
                item = QListWidgetItem()
                item.setIcon(QIcon(thumbnail))
                item.setSizeHint(QSize(grid_width, grid_height))
                
                # Filename label
                filename = img_data.get("filename", "")
                item.setText(f"{filename}")
                
                # Tooltip with difficulty and tags
                tooltip = f"난이도: {difficulty} {'★' * difficulty}"
                tags = img_data.get("tags", [])
                if tags:
                    tooltip += f"\n태그: {', '.join(tags)}"
                item.setToolTip(tooltip)
                
                # Store image data in UserRole
                item.setData(Qt.ItemDataRole.UserRole, img_data)
                
                self.image_list.addItem(item)
                
            except Exception as e:
                print(tr("image_load_failed", self.lang).format(e))
        
        self.lazy_load_current_index = end_idx
        
        # Continue loading if there are more items
        if self.lazy_load_current_index < len(self.deck_images):
            self.lazy_load_timer.start(100)  # Load next batch after 100ms
    
    def _on_image_list_scroll(self, value):
        """Trigger loading when scrolling near the bottom"""
        scrollbar = self.image_list.verticalScrollBar()
        if scrollbar.maximum() > 0:
            # Load more when scrolled to 80% of the way
            if value >= scrollbar.maximum() * 0.8:
                if self.lazy_load_current_index < len(self.deck_images) and not self.lazy_load_timer.isActive():
                    self._load_next_batch()
            
    def import_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            tr("import_images", self.lang),
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        for f in files:
            self.add_image_to_deck(f)
        
        # Refresh Save As menu state
        if files:
            self.update_title()
            
    def on_image_selected(self, item: QListWidgetItem):
        """Show croquis list for the selected image"""
        img_data = item.data(Qt.ItemDataRole.UserRole)
        if not img_data:
            return
        
        # Show croquis list
        self.croquis_list.show()
        
        # Load croquis list asynchronously by filename
        filename = img_data.get("filename", "")
        if filename:
            self.load_croquis_for_image(filename)
            
    def new_deck(self):
        """Create a new deck"""
        logger.info(LOG_MESSAGES["deck_created"])
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                "저장 확인",
                "현재 파일이 수정되었습니다. 저장하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_deck()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        # Remove old temp file
        self.cleanup_temp_file()
        
        # Create new temp file
        self.setup_temp_file()
        
        self.deck_images.clear()
        self.current_deck_path = None
        self.is_modified = False
        
        # Reset UI
        self.update_image_list()
        self.croquis_list.clear()
        self.croquis_list.hide()
        
        self.update_title()
        
    def open_deck(self):
        """Open an existing deck"""
        logger.info(LOG_MESSAGES["deck_loaded"])
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                tr("save_confirm_title", self.lang),
                tr("save_confirm_body", self.lang),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_deck()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("open", self.lang),
            "",
            "Croquis Deck Files (*.crdk)"
        )
        if path:
            try:
                # Remove old temp file
                self.cleanup_temp_file()
                
                # Copy deck file into temp file
                self.load_temp_file(path)
                
                self.current_deck_path = path
                self.is_modified = False
                
                # Add to recent files
                self.add_recent_file(path)
                
                self.update_title()
            except Exception as e:
                QMessageBox.warning(self, tr("error", self.lang), f"{tr('load_error', self.lang)}: {str(e)}")
                
    def save_deck(self):
        """Save deck by copying temp file"""
        logger.info(LOG_MESSAGES["deck_saved"])
        if self.current_deck_path:
            self._save_to_path(self.current_deck_path)
        else:
            self.save_deck_as()
            
    def save_deck_as(self):
        """Save deck as..."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("save_as", self.lang),
            "",
            "Croquis Deck Files (*.crdk)"
        )
        if path:
            if not path.endswith('.crdk'):
                path += '.crdk'
            self._save_to_path(path)
            
    def _save_to_path(self, path: str):
        """Persist to file by copying temp to target path"""
        try:
            # Ensure temp file exists
            if not self.temp_file_path or not os.path.exists(self.temp_file_path):
                QMessageBox.warning(self, "저장 오류", "임시 파일을 찾을 수 없습니다.")
                return
            
            # Copy temp file to target path
            import shutil
            shutil.copy2(self.temp_file_path, path)
            
            self.current_deck_path = path
            self.is_modified = False
            self.update_title()
            
        except Exception as e:
            QMessageBox.critical(self, "저장 오류", f"파일 저장 중 오류가 발생했습니다:\n{str(e)}")
    
    def load_recent_files(self) -> List[str]:
        """Load recent files from encrypted dat file"""
        dat_dir = get_data_path() / "dat"
        recent_path = dat_dir / "recent.dat"
        
        if not recent_path.exists():
            return []
        
        try:
            with open(recent_path, "rb") as f:
                encrypted = f.read()
            data = decrypt_data(encrypted)
            recent_files = data.get("recent_files", [])
            
            # Filter out non-existent files
            return [f for f in recent_files if os.path.exists(f)][:5]
        except Exception:
            return []
    
    def save_recent_files(self):
        """Save recent files to encrypted dat file"""
        dat_dir = get_data_path() / "dat"
        dat_dir.mkdir(exist_ok=True)
        recent_path = dat_dir / "recent.dat"
        
        try:
            data = {"recent_files": self.recent_files}
            encrypted = encrypt_data(data)
            
            with open(recent_path, "wb") as f:
                f.write(encrypted)
        except Exception as e:
            logger.error(f"Failed to save recent files: {e}")
    
    def add_recent_file(self, file_path: str):
        """Add file to recent files list"""
        # Remove if already exists
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        
        # Add to front
        self.recent_files.insert(0, file_path)
        
        # Keep only 5 recent files
        self.recent_files = self.recent_files[:5]
        
        # Save and update menu
        self.save_recent_files()
        self.update_recent_menu()
    
    def update_recent_menu(self):
        """Update recent files menu"""
        self.recent_menu.clear()
        
        if not self.recent_files:
            empty_action = QAction(tr("open_recent_empty", self.lang), self)
            empty_action.setEnabled(False)
            self.recent_menu.addAction(empty_action)
        else:
            for file_path in self.recent_files:
                action = QAction(os.path.basename(file_path), self)
                action.triggered.connect(lambda checked, p=file_path: self.open_recent_file(p))
                self.recent_menu.addAction(action)
            
            self.recent_menu.addSeparator()
            
            clear_action = QAction(tr("open_recent_clear", self.lang), self)
            clear_action.triggered.connect(self.clear_recent_files)
            self.recent_menu.addAction(clear_action)
    
    def open_recent_file(self, file_path: str):
        """Open a recent file"""
        if not os.path.exists(file_path):
            QMessageBox.warning(self, tr("error", self.lang), f"파일을 찾을 수 없습니다:\n{file_path}")
            # Remove from recent files
            self.recent_files.remove(file_path)
            self.save_recent_files()
            self.update_recent_menu()
            return
        
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                tr("save_confirm_title", self.lang),
                tr("save_confirm_body", self.lang),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_deck()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        try:
            # Remove old temp file
            self.cleanup_temp_file()
            
            # Copy deck file into temp file
            self.load_temp_file(file_path)
            
            self.current_deck_path = file_path
            self.is_modified = False
            
            # Move to front of recent files
            self.add_recent_file(file_path)
            
            self.update_title()
            
            logger.info(LOG_MESSAGES["deck_loaded"])
        except Exception as e:
            QMessageBox.critical(self, "오류", f"덱 불러오기 실패:\n{e}")
            logger.error(f"Failed to open recent file: {e}")
    
    def clear_recent_files(self):
        """Clear recent files list"""
        self.recent_files = []
        self.save_recent_files()
        self.update_recent_menu()
    
    def delete_selected_images(self):
        """Delete selected images"""
        selected_items = self.image_list.selectedItems()
        if not selected_items:
            return
        
        logger.info(LOG_MESSAGES["images_deleted"].format(len(selected_items)))
        
        # Collect filenames of selected items
        filenames_to_delete = []
        for item in selected_items:
            img_data = item.data(Qt.ItemDataRole.UserRole)
            if img_data and isinstance(img_data, dict):
                filenames_to_delete.append(img_data["filename"])
        
        # Remove from deck_images
        self.deck_images = [img for img in self.deck_images if img["filename"] not in filenames_to_delete]
        
        # Refresh UI
        self.update_image_list()
        
        # Reset croquis list
        self.croquis_list.clear()
        self.croquis_list.hide()
        
        # Save temp file
        self.save_temp_file()
        self.mark_modified()
    
    def on_deck_item_clicked(self, item: QListWidgetItem):
        """Show croquis list when a deck item is clicked"""
        img_data = item.data(Qt.ItemDataRole.UserRole)
        if not img_data:
            return
        
        # Show croquis list
        self.croquis_list.show()
        
        # Load croquis list
        filename = img_data.get("filename", "")
        if filename:
            self.load_croquis_for_image(filename)
    
    def on_deck_item_double_clicked(self, item: QListWidgetItem):
        """Show large image preview on double-click"""
        self.show_image_preview(item)
    
    def show_image_context_menu(self, position):
        """Context menu for the image list"""
        item = self.image_list.itemAt(position)
        
        menu = QMenu(self)
        
        # Paste image (always shown)
        paste_action = menu.addAction(tr("paste_image", self.lang))
        paste_action.triggered.connect(self.paste_image_from_clipboard)
        
        # Remaining menu only when an item is selected
        if item:
            # Export image
            export_action = menu.addAction(tr("export_image", self.lang))
            export_action.triggered.connect(lambda: self.export_image(item))
            
            menu.addSeparator()
            
            # Rename
            rename_action = menu.addAction(tr("rename_image", self.lang))
            rename_action.triggered.connect(lambda: self.rename_image(item))
            
            # Difficulty submenu
            difficulty_menu = menu.addMenu(tr("set_difficulty", self.lang))
            for i in range(1, 6):
                action = difficulty_menu.addAction(f"★{i}")
                action.triggered.connect(lambda checked, d=i, it=item: self.set_item_difficulty(it, d))
            
            # Set tags
            tag_action = menu.addAction(tr("set_tags", self.lang))
            tag_action.triggered.connect(lambda: self.set_image_tags(item))
            
            # Properties
            props_action = menu.addAction(tr("properties", self.lang))
            props_action.triggered.connect(lambda: self.show_image_properties(item))
        
        menu.exec(self.image_list.mapToGlobal(position))
    
    def paste_image_from_clipboard(self):
        """Paste image from clipboard"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        
        # Check for URL text
        text = clipboard.text()
        if text and (text.startswith('http://') or text.startswith('https://')):
            # Handle Pinterest pin URL
            if 'pinterest.com/pin/' in text:
                logger.info(LOG_MESSAGES["pinterest_url_detected"].format(text))
                self.download_image_from_url(text)
            elif any(ext in text.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']):
                # Generic image URL
                self.download_image_from_url(text)
            else:
                QMessageBox.information(self, "안내", "이미지 URL을 복사해주세요.\n핀터레스트 핀 URL도 지원합니다.")
            return
        
        # Check for image data
        mime_data = clipboard.mimeData()
        if mime_data.hasImage():
            from PyQt6.QtGui import QImage
            image = clipboard.image()
            if not image.isNull():
                # Process image in memory
                pixmap = QPixmap.fromImage(image)
                
                # Build filename
                import time
                filename = f"clipboard_{int(time.time())}.png"
                
                # Convert image to bytes
                from PyQt6.QtCore import QBuffer, QIODevice
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                pixmap.save(buffer, "PNG")
                image_bytes = buffer.data().data()
                
                # Build image info dictionary
                image_data_dict = {
                    "filename": filename,
                    "original_path": "클립보드",
                    "width": pixmap.width(),
                    "height": pixmap.height(),
                    "size": len(image_bytes),
                    "image_data": base64.b64encode(image_bytes).decode(),
                    "difficulty": 1,
                    "tags": []
                }
                
                # Add to deck
                self.deck_images.append(image_data_dict)
                logger.info(f"Image added to deck: {filename}")
                self.save_temp_file()
                self.update_image_list()
                self.mark_modified()
            return
        
        QMessageBox.information(self, tr("info", self.lang), tr("clipboard_no_image_or_url", self.lang))
    
    def export_image(self, item: QListWidgetItem):
        """Export image at original size"""
        img_data = item.data(Qt.ItemDataRole.UserRole)
        if not img_data:
            return
        
        filename = img_data.get("filename", "image.png")
        
        # Choose save path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("export_image", self.lang),
            filename,
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Load image bytes
            image_bytes = base64.b64decode(img_data["image_data"])
            
            # Write to file
            with open(file_path, 'wb') as f:
                f.write(image_bytes)
            
            logger.info(f"Image exported: {filename} -> {file_path}")
            QMessageBox.information(self, tr("success", self.lang), f"{tr("export_success", self.lang)}:\n{file_path}")
        except Exception as e:
            logger.error(f"Image export failed: {e}")
            QMessageBox.warning(self, tr("error", self.lang), f"{tr("export_failed", self.lang)}:\n{str(e)}")
    
    def cycle_item_difficulty(self, item: QListWidgetItem):
        """Cycle item difficulty (1→2→3→4→5→1)"""
        img_data = item.data(Qt.ItemDataRole.UserRole)
        if not img_data:
            return
        
        current = img_data.get("difficulty", 1)
        new_difficulty = (current % 5) + 1
        self.set_item_difficulty(item, new_difficulty)
    
    def set_item_difficulty(self, item: QListWidgetItem, difficulty: int):
        """Set item difficulty"""
        img_data = item.data(Qt.ItemDataRole.UserRole)
        if not img_data:
            return
        
        img_data["difficulty"] = difficulty
        logger.info(f"Difficulty changed: {img_data['filename']} -> {difficulty}")
        
        # Update deck_images
        filename = img_data["filename"]
        for i, deck_img in enumerate(self.deck_images):
            if deck_img.get("filename") == filename:
                self.deck_images[i]["difficulty"] = difficulty
                break
        
        # Rebuild thumbnail (with overlay)
        thumbnail = self.create_thumbnail_with_difficulty(img_data)
        item.setIcon(QIcon(thumbnail))
        
        # Update tooltip
        item.setToolTip(f"{tr('difficulty', self.lang)}: {difficulty} {'★' * difficulty}")
        item.setData(Qt.ItemDataRole.UserRole, img_data)
        
        self.save_temp_file()
        self.mark_modified()
    
    def rename_image(self, item: QListWidgetItem):
        """Rename an image"""
        img_data = item.data(Qt.ItemDataRole.UserRole)
        if not img_data:
            return
        
        current_name = img_data.get("filename", "")
        
        dialog = ImageRenameDialog(current_name, self.lang, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.get_new_name()
            if new_name and new_name != current_name:
                # Rename
                img_data["filename"] = new_name
                logger.info(f"Filename changed: {current_name} -> {new_name}")
                
                # Update deck_images
                for i, deck_img in enumerate(self.deck_images):
                    if deck_img.get("filename") == current_name:
                        self.deck_images[i]["filename"] = new_name
                        break
                
                # Update item label
                item.setText(new_name)
                item.setData(Qt.ItemDataRole.UserRole, img_data)
                
                self.save_temp_file()
                self.mark_modified()
    
    def set_image_tags(self, item: QListWidgetItem):
        """Set tags for an image"""
        img_data = item.data(Qt.ItemDataRole.UserRole)
        if not img_data:
            return
        
        current_tags = img_data.get("tags", [])
        
        dialog = ImageTagDialog(current_tags, self.lang, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_tags = dialog.get_tags()
            
            # Update tags
            img_data["tags"] = new_tags
            logger.info(f"{tr('set_tags', self.lang)}: {img_data['filename']} -> {new_tags}")
            
            # Update deck_images
            filename = img_data["filename"]
            for i, deck_img in enumerate(self.deck_images):
                if deck_img.get("filename") == filename:
                    self.deck_images[i]["tags"] = new_tags
                    break
            
            # Update tooltip
            tooltip = f"{tr('difficulty', self.lang)}: {img_data.get('difficulty', 1)} {'★' * img_data.get('difficulty', 1)}"
            if new_tags:
                tooltip += f"\n{tr('tag', self.lang)}: {', '.join(new_tags)}"
            item.setToolTip(tooltip)
            item.setData(Qt.ItemDataRole.UserRole, img_data)
            
            self.save_temp_file()
            self.mark_modified()
    
    def show_image_preview(self, item: QListWidgetItem):
        """Show large image preview dialog"""
        img_data = item.data(Qt.ItemDataRole.UserRole)
        if not img_data:
            return
        
        # Load pixmap from image_data
        image_data = img_data.get("image_data")
        if not image_data:
            return
        
        try:
            image_bytes = base64.b64decode(image_data)
            pixmap = QPixmap()
            pixmap.loadFromData(image_bytes)
            if pixmap.isNull():
                return
        except Exception as e:
            print(f"{tr('failed_to_load_image_preview', self.lang)}: {e}")
            return
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(img_data.get("filename", tr("no_title", self.lang)))
        dialog.setModal(True)
        
        # Get screen size
        screen = self.screen()
        screen_rect = screen.availableGeometry()
        max_width = int(screen_rect.width() * 0.9)
        max_height = int(screen_rect.height() * 0.9)
        
        # Create label for image
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Scale image if larger than screen
        scaled_pixmap = pixmap
        if pixmap.width() > max_width or pixmap.height() > max_height:
            scaled_pixmap = pixmap.scaled(
                max_width, max_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        
        label.setPixmap(scaled_pixmap)
        
        # Close on click
        def close_dialog(event):
            dialog.close()
        label.mousePressEvent = close_dialog
        
        # Set layout
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.setContentsMargins(0, 0, 0, 0)
        dialog.setLayout(layout)
        
        # Set dialog size to image size
        dialog.resize(scaled_pixmap.size())
        
        # Show dialog
        dialog.exec()
    
    def show_image_properties(self, item: QListWidgetItem):
        """Show image properties"""
        img_data = item.data(Qt.ItemDataRole.UserRole)
        if not img_data:
            return
        
        dialog = ImagePropertiesDialog(img_data, self.lang, self)
        dialog.exec()
    
    def update_title(self):
        """Update window title"""
        title = tr("edit_deck", self.lang)
        
        if self.current_deck_path:
            filename = os.path.basename(self.current_deck_path)
            title += f" - {filename}"
        else:
            title += f" - {tr("no_title", self.lang)}"
        
        if self.is_modified:
            title += " *"
        
        self.setWindowTitle(title)
        
        # Manage Save As enabled state
        # Allow Save As when images exist even without a file path
        self.save_as_action.setEnabled(len(self.deck_images) > 0)
    
    def set_sort_by(self, sort_by: str):
        """Change sort field"""
        self.sort_by = sort_by
        
        # Update menu labels
        self.sort_name_action.setText(f"{tr('sort_name', self.lang)} ✔" if sort_by == "name" else tr('sort_name', self.lang))
        self.sort_size_action.setText(f"{tr('sort_size', self.lang)} ✔" if sort_by == "size" else tr('sort_size', self.lang))
        self.sort_difficulty_action.setText(f"{tr('sort_difficulty', self.lang)} ✔" if sort_by == "difficulty" else tr('sort_difficulty', self.lang))
        self.sort_date_action.setText(f"{tr('sort_date', self.lang)} ✔" if sort_by == "date" else tr('sort_date', self.lang))
        
        # Apply sorting
        self.apply_sort()
    
    def set_sort_order(self, order: str):
        """Change sort order"""
        self.sort_order = order
        
        # Update menu labels
        self.sort_asc_action.setText(f"{tr('sort_asc', self.lang)} ✔" if order == "asc" else tr('sort_asc', self.lang))
        self.sort_desc_action.setText(f"{tr('sort_desc', self.lang)} ✔" if order == "desc" else tr('sort_desc', self.lang))
        
        # Apply sorting
        self.apply_sort()
    
    def apply_sort(self):
        """Apply sorting"""
        if not self.deck_images:
            return
        
        # Select sort key
        if self.sort_by == "name":
            key_func = lambda x: x.get("filename", "").lower()
        elif self.sort_by == "size":
            key_func = lambda x: x.get("size", 0)
        elif self.sort_by == "difficulty":
            key_func = lambda x: x.get("difficulty", 1)
        elif self.sort_by == "date":
            # Sort by original path mtime, fallback to 0 if missing
            def get_mtime(img_data):
                path = img_data.get("original_path", "")
                if path and os.path.exists(path):
                    return os.path.getmtime(path)
                return 0
            key_func = get_mtime
        else:
            key_func = lambda x: x.get("filename", "").lower()
        
        # Sort
        reverse = (self.sort_order == "desc")
        self.deck_images.sort(key=key_func, reverse=reverse)
        
        # Refresh UI
        self.update_image_list()
        self.save_temp_file()
    
    def set_icon_scale(self, scale: int):
        """Change icon scale"""
        self.icon_scale = scale
        
        # Update menu labels
        self.icon_50_action.setText("50% ✔" if scale == 50 else "50%")
        self.icon_75_action.setText("75% ✔" if scale == 75 else "75%")
        self.icon_100_action.setText("100% ✔" if scale == 100 else "100%")
        self.icon_125_action.setText("125% ✔" if scale == 125 else "125%")
        self.icon_150_action.setText("150% ✔" if scale == 150 else "150%")
        self.icon_200_action.setText("200% ✔" if scale == 200 else "200%")
        # Reset custom menu label
        self.icon_custom_action.setText(self.tr("custom"))
        
        # Apply icon size
        self.apply_icon_scale()
    
    def set_custom_icon_scale(self):
        """Set a custom icon scale"""
        from PyQt6.QtWidgets import QInputDialog
        
        scale, ok = QInputDialog.getInt(
            self,
            self.tr("custom_size_title"),
            self.tr("custom_size_prompt"),
            self.icon_scale,
            50,
            200,
            1
        )
        
        if ok:
            self.icon_scale = scale
            # Clear checkmarks on preset sizes
            self.icon_50_action.setText("50%")
            self.icon_75_action.setText("75%")
            self.icon_100_action.setText("100%")
            self.icon_125_action.setText("125%")
            self.icon_150_action.setText("150%")
            self.icon_200_action.setText("200%")
            # Add checkmark to custom menu
            self.icon_custom_action.setText(f"{self.tr('custom_with_value').format(scale=scale)} ✔")
            
            # Apply icon size
            self.apply_icon_scale()
    
    def apply_icon_scale(self):
        """Apply icon size to the list"""
        # Compute sizes
        icon_width = int(DECK_ICON_WIDTH * self.icon_scale / 100)
        icon_height = int(DECK_ICON_HEIGHT * self.icon_scale / 100)
        grid_width = int(DECK_GRID_WIDTH * self.icon_scale / 100)
        grid_height = int(DECK_GRID_HEIGHT * self.icon_scale / 100)
        
        # Apply to image_list
        self.image_list.setIconSize(QSize(icon_width, icon_height))
        self.image_list.setGridSize(QSize(grid_width, grid_height))
        
        # Refresh UI (regenerate thumbnails)
        self.update_image_list()
    
    def mark_modified(self):
        """Mark deck as modified"""
        if not self.is_modified:
            self.is_modified = True
            self.update_title()
    
    def load_croquis_for_image(self, image_path: str):
        """Load croquis list drawn from the selected image"""
        self.croquis_list.clear()
        
        # Show loading message
        loading_item = QListWidgetItem(tr("loading", self.lang))
        self.croquis_list.addItem(loading_item)
        
        # Use QTimer to process asynchronously
        QTimer.singleShot(0, lambda: self._load_croquis_async(image_path))
    
    def _load_croquis_async(self, image_path: str):
        """Internal async loader for croquis list"""
        self.croquis_list.clear()
        
        pairs_dir = get_data_path() / "croquis_pairs"
        # if not pairs_dir.exists():
        #     no_data_item = QListWidgetItem(tr("croquis_not_found", self.lang))
        #     self.croquis_list.addItem(no_data_item)
        #     return
        
        image_filename = os.path.basename(image_path)
        found_count = 0
        
        try:
            # Iterate .croq files
            for file in sorted(pairs_dir.glob("*.croq"), reverse=True):
                try:
                    with open(file, "rb") as f:
                        encrypted = f.read()
                    
                    key = base64.urlsafe_b64encode(hashlib.sha256(b"croquis_secret_key").digest())
                    fernet = Fernet(key)
                    decrypted = fernet.decrypt(encrypted)
                    data = json.loads(decrypted.decode())
                    
                    # Validate metadata
                    metadata = data.get("image_metadata", {})
                    file_metadata_name = metadata.get("filename", "")
                    
                    # Skip old files without metadata
                    if not file_metadata_name:
                        continue
                    
                    # Match filename
                    if file_metadata_name == image_filename:
                        found_count += 1
                        
                        # Load croquis image
                        screenshot_bytes = base64.b64decode(data["screenshot"])
                        screenshot_pixmap = QPixmap()
                        screenshot_pixmap.loadFromData(screenshot_bytes)
                        
                        # Create thumbnail (fixed 100x120)
                        scaled_thumb = screenshot_pixmap.scaled(100, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        
                        # Center on 100x120 canvas
                        thumbnail = QPixmap(100, 120)
                        thumbnail.fill(Qt.GlobalColor.transparent)
                        thumb_painter = QPainter(thumbnail)
                        thumb_x = (100 - scaled_thumb.width()) // 2
                        thumb_y = (120 - scaled_thumb.height()) // 2
                        thumb_painter.drawPixmap(thumb_x, thumb_y, scaled_thumb)
                        
                        # Add time overlay (bottom-right)
                        croquis_time = data.get("croquis_time", 0)
                        time_str = f"{croquis_time // 60}:{croquis_time % 60:02d}"
                        
                        # Semi-transparent dark background
                        time_width = 38
                        time_height = 18
                        bg_rect = QRect(100 - time_width - 5, 120 - time_height - 5, time_width, time_height)
                        thumb_painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
                        thumb_painter.setPen(Qt.PenStyle.NoPen)
                        thumb_painter.drawRoundedRect(bg_rect, 8, 8)
                        
                        # Time text (white)
                        thumb_painter.setPen(QColor(255, 255, 255))
                        thumb_painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                        thumb_painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, time_str)
                        
                        thumb_painter.end()
                        
                        # Create list item
                        list_item = QListWidgetItem()
                        list_item.setIcon(QIcon(thumbnail))
                        list_item.setSizeHint(QSize(DECK_GRID_WIDTH, DECK_GRID_HEIGHT))
                        
                        # Timestamp and duration
                        timestamp = data.get("timestamp", "")
                        croquis_time = data.get("croquis_time", 0)
                        
                        # Format date (YYYY-MM-DD)
                        if len(timestamp) >= 8:
                            year = timestamp[:4]
                            month = timestamp[4:6]
                            day = timestamp[6:8]
                            date_str = f"{year}-{month}-{day}"
                        else:
                            date_str = timestamp
                        
                        list_item.setText(date_str)
                        
                        # Load original image
                        original_bytes = base64.b64decode(data["original"])
                        original_pixmap = QPixmap()
                        original_pixmap.loadFromData(original_bytes)
                        
                        # Store data on item
                        croquis_item_data = {
                            "original": original_pixmap,
                            "screenshot": screenshot_pixmap,
                            "timestamp": timestamp,
                            "time": croquis_time,
                            "date": f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}",
                            "file_path": str(file)  # Persist file path
                        }
                        list_item.setData(Qt.ItemDataRole.UserRole, croquis_item_data)
                        
                        # Show memo in tooltip when present
                        memo_text = CroquisMemoDialog.get_memo(str(file))
                        if memo_text:
                            list_item.setToolTip(f"📝 {memo_text}")
                        
                        self.croquis_list.addItem(list_item)
                        
                except Exception as e:
                    continue  # Ignore individual file errors
            
            # if found_count == 0:
            #     no_data_item = QListWidgetItem(tr("croquis_not_found", self.lang))
            #     self.croquis_list.addItem(no_data_item)
                
        except Exception as e:
            error_item = QListWidgetItem(f"{tr('error', self.lang)}: {str(e)}")
            self.croquis_list.addItem(error_item)
    
    def show_croquis_large_view(self, item: QListWidgetItem):
        """Open selected croquis in large view"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        logger.info(LOG_MESSAGES["croquis_large_view_selected"])
        croquis_file_path = data.get("file_path")
        dialog = CroquisLargeViewDialog(data, self.lang, croquis_file_path, self)
        dialog.exec()
    
    def show_croquis_context_menu(self, position):
        """Context menu for croquis list"""
        item = self.croquis_list.itemAt(position)
        if not item:
            return
        
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        croquis_file_path = data.get("file_path")
        if not croquis_file_path:
            return
        
        menu = QMenu(self)
        memo_action = QAction(tr("add_memo", self.lang), self)
        memo_action.triggered.connect(lambda: self.open_croquis_memo(croquis_file_path))
        menu.addAction(memo_action)
        
        menu.exec(self.croquis_list.mapToGlobal(position))
    
    def open_croquis_memo(self, croquis_file_path: str):
        """Open croquis memo dialog"""
        dialog = CroquisMemoDialog(croquis_file_path, self.lang, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # After saving memo, refresh croquis list (tooltip update)
            current_item = self.croquis_list.currentItem()
            if current_item:
                self.on_image_selected(current_item)
    
    def closeEvent(self, event):
        """Handle close event; prompt to save if modified"""
        logger.info(LOG_MESSAGES["deck_editor_closed"])
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                tr("save_confirm_title", self.lang),
                tr("save_confirm_body", self.lang),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_deck()
                self.cleanup_temp_file()
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                self.cleanup_temp_file()
                event.accept()
            else:  # Cancel
                event.ignore()
        else:
            self.cleanup_temp_file()
            event.accept()
    
    def apply_dark_mode(self):
        """Apply dark mode stylesheet"""
        if self.dark_mode:
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QGroupBox {
                    border: 1px solid #555;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QPushButton {
                    background-color: #3a3a3a;
                    border: 1px solid #555;
                    border-radius: 5px;
                    padding: 8px;
                    color: #ffffff;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QListWidget {
                    background-color: #3a3a3a;
                    border: 1px solid #555;
                    color: #ffffff;
                }
                QListWidget::item {
                    color: #ffffff;
                }
                QListWidget::item:selected {
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                }
                QCheckBox {
                    color: #ffffff;
                }
                QMenuBar {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QMenuBar::item:selected {
                    background-color: #3a3a3a;
                }
                QMenu {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #555;
                }
                QMenu::item:selected {
                    background-color: #3a3a3a;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #ffffff;
                    color: #000000;
                }
                QGroupBox {
                    border: 1px solid #cccccc;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #cccccc;
                    border-radius: 5px;
                    padding: 8px;
                    color: #000000;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
                QListWidget {
                    background-color: #ffffff;
                    border: 1px solid #cccccc;
                    color: #000000;
                }
                QListWidget::item {
                    color: #000000;
                }
                QListWidget::item:selected {
                    color: #000000;
                }
                QLabel {
                    color: #000000;
                }
                QCheckBox {
                    color: #000000;
                }
                QMenuBar {
                    background-color: #f0f0f0;
                    color: #000000;
                }
                QMenuBar::item:selected {
                    background-color: #e0e0e0;
                }
                QMenu {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #cccccc;
                }
                QMenu::item:selected {
                    background-color: #e0e0e0;
                }
            """)


# ============== Alarm Background Service (BAT File with ANSI) ==============
def setup_alarm_background_service():
    """BAT 파일을 ANSI 인코딩으로 생성하고 Windows 시작프로그램에 등록"""
    try:
        # 컴파일된 실행 파일만 등록
        if not getattr(sys, 'frozen', False):
            logger.info("Development mode - skipping background service setup")
            return True
        
        exe_path = Path(sys.executable).resolve()
        exe_dir = exe_path.parent
        
        # BAT 파일 생성 (1분마다 알람 체크) - ANSI(CP949) 인코딩
        bat_content = f"""@echo off
title Croquis Alarm Service
cd /d "{exe_dir}"
:loop
start /b /wait "" "{exe_path}" --check-alarm
timeout /t 60 /nobreak >nul
goto loop
"""
        
        bat_path = exe_dir / "croquis_alarm_service.bat"
        with open(bat_path, "w", encoding="cp949") as f:
            f.write(bat_content)
        
        # VBS 파일 생성 (BAT를 보이지 않게 실행) - 절대 경로 사용
        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """{bat_path}""", 0, False
Set WshShell = Nothing
'''
        
        vbs_path = exe_dir / "croquis_alarm_service.vbs"
        with open(vbs_path, "w", encoding="cp949") as f:
            f.write(vbs_content)
        
        # Windows 시작프로그램 폴더 경로
        startup_folder = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup_link = startup_folder / "Croquis_Alarm.vbs"
        
        # 기존 링크 삭제
        if startup_link.exists():
            startup_link.unlink()
        
        # Copy VBS file to startup folder
        import shutil
        shutil.copy2(vbs_path, startup_link)
        
        logger.info(LOG_MESSAGES["alarm_service_installed"])
        return True
        
    except Exception as e:
        logger.warning(f"Failed to setup alarm background service: {e}")
        return False

def remove_alarm_background_service():
    """Remove BAT file and startup registration"""
    try:
        exe_dir = get_data_path()
        
        # Delete BAT, VBS, Python files
        bat_path = exe_dir / "croquis_alarm_service.bat"
        vbs_path = exe_dir / "croquis_alarm_service.vbs"
        py_path = exe_dir / "croquis_alarm_background.py"
        
        if bat_path.exists():
            bat_path.unlink()
        if vbs_path.exists():
            vbs_path.unlink()
        if py_path.exists():
            py_path.unlink()
        
        # Remove from startup folder
        startup_folder = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup_link = startup_folder / "Croquis_Alarm.vbs"
        
        if startup_link.exists():
            startup_link.unlink()
        
        logger.info(LOG_MESSAGES["alarm_service_removed"])
        return True
        
    except Exception as e:
        logger.warning(f"Failed to remove alarm background service: {e}")
        return False


# ============== History Window ==============
class HistoryWindow(QDialog):
    """Dialog showing saved croquis history."""
    
    def __init__(self, lang: str = "ko", parent=None, dark_mode: bool = False):
        super().__init__(parent)
        self.setWindowIcon(get_app_icon())  # Set window icon
        self.lang = lang
        self.dark_mode = dark_mode
        
        # Lazy loading settings
        self.lazy_load_batch_size = 30  # Load 30 items at a time
        self.lazy_load_current_index = 0
        self.lazy_load_timer = QTimer(self)
        self.lazy_load_timer.timeout.connect(self._load_next_history_batch)
        self.filtered_history = []  # Stores filtered history data
        
        self.setup_ui()
        self.load_history()
        
    def setup_ui(self):
        self.setWindowTitle(tr("croquis_history", self.lang))
        self.resize(1000, 600)
        
        # Set window icon
        self.setWindowIcon(get_app_icon())
        
        layout = QVBoxLayout(self)
        
        # Date filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel(tr("filter_by_date", self.lang)))
        
        self.date_filter = QComboBox()
        self.date_filter.addItem(tr("all", self.lang), None)
        self.date_filter.currentIndexChanged.connect(self.filter_by_date)
        filter_layout.addWidget(self.date_filter)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # History list (matches deck editor style)
        self.history_list = QListWidget()
        self.history_list.setIconSize(QSize(HISTORY_ICON_WIDTH, HISTORY_ICON_HEIGHT))
        self.history_list.setGridSize(QSize(HISTORY_GRID_WIDTH, HISTORY_GRID_HEIGHT))
        self.history_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.history_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.history_list.setMovement(QListWidget.Movement.Static)  # Static으로 일관성 유지
        self.history_list.setFlow(QListWidget.Flow.LeftToRight)
        self.history_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.history_list.setWordWrap(True)
        self.history_list.setSpacing(HISTORY_SPACING)
        self.history_list.setUniformItemSizes(True)  # Enable uniform item sizes for performance
        self.history_list.verticalScrollBar().valueChanged.connect(self._on_history_list_scroll)
        
        # Adjust text color for dark/light mode
        text_color = "#ffffff" if self.dark_mode else "#000000"
        self.history_list.setStyleSheet(f"""
            QListWidget::item {{
                text-align: center;
                padding: 3px;
                color: {text_color};
            }}
            QListWidget::item:selected {{
                background-color: rgba(0, 120, 212, 0.2);
                color: {text_color};
            }}
            QListWidget::item:hover {{
                background-color: rgba(0, 120, 212, 0.1);
            }}
            QListWidget {{
                outline: none;
            }}
        """)
        self.history_list.itemClicked.connect(self.show_large_view)
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_history_context_menu)
        
        layout.addWidget(self.history_list)
        
    def load_history(self):
        """Load saved croquis pairs."""
        history_dir = get_data_path() / "croquis_pairs"
        if not history_dir.exists():
            return
        
        self.history_data = []
        dates_set = set()
        
        # Load and decrypt files
        for file in sorted(history_dir.glob("*.croq"), reverse=True):
            try:
                with open(file, "rb") as f:
                    encrypted = f.read()
                
                key = base64.urlsafe_b64encode(hashlib.sha256(b"croquis_secret_key").digest())
                fernet = Fernet(key)
                decrypted = fernet.decrypt(encrypted)
                data = json.loads(decrypted.decode())
                
                # Extract date
                timestamp = data.get("timestamp", file.stem)
                date_str = timestamp[:8]  # YYYYMMDD
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                dates_set.add(formatted_date)
                
                # Build original and screenshot pixmaps
                original_bytes = base64.b64decode(data["original"])
                original_pixmap = QPixmap()
                original_pixmap.loadFromData(original_bytes)
                
                screenshot_bytes = base64.b64decode(data["screenshot"])
                screenshot_pixmap = QPixmap()
                screenshot_pixmap.loadFromData(screenshot_bytes)
                
                # Croquis timer value
                croquis_time = data.get("croquis_time", 0)
                
                # Image metadata (newer files only)
                image_metadata = data.get("image_metadata", {})
                
                self.history_data.append({
                    "date": formatted_date,
                    "timestamp": timestamp,
                    "original": original_pixmap,
                    "screenshot": screenshot_pixmap,
                    "time": croquis_time,
                    "file": file,
                    "image_metadata": image_metadata
                })
            except Exception as e:
                print(tr("error_loading_file", self.lang).format(file, e))
        
        # Fill date filter combo box
        for date_str in sorted(dates_set, reverse=True):
            self.date_filter.addItem(date_str, date_str)
        
        self.display_history()
    
    def filter_by_date(self, index):
        """Apply date filter selection."""
        self.display_history()
    
    def display_history(self):
        """Render history list with lazy loading."""
        # Remove existing items
        self.history_list.clear()
        self.lazy_load_current_index = 0
        self.lazy_load_timer.stop()
        
        # Selected date filter
        selected_date = self.date_filter.currentData()
        
        # Filter history data
        self.filtered_history = []
        for item in self.history_data:
            if selected_date and item["date"] != selected_date:
                continue
            self.filtered_history.append(item)
        
        # Start lazy loading
        if self.filtered_history:
            self._load_next_history_batch()
    
    def _load_next_history_batch(self):
        """Load next batch of history items"""
        start_idx = self.lazy_load_current_index
        end_idx = min(start_idx + self.lazy_load_batch_size, len(self.filtered_history))
        
        if start_idx >= len(self.filtered_history):
            return
        
        for idx in range(start_idx, end_idx):
            item = self.filtered_history[idx]
            
            # Build combined thumbnail (left: croquis, right: original)
            combined_width = 300
            combined_height = 150
            combined_pixmap = QPixmap(combined_width, combined_height)
            combined_pixmap.fill(Qt.GlobalColor.white)
            
            painter = QPainter(combined_pixmap)
            
            # Original image (left)
            original_scaled = item["original"].scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            original_x = (150 - original_scaled.width()) // 2
            original_y = (150 - original_scaled.height()) // 2
            painter.drawPixmap(original_x, original_y, original_scaled)
            
            # Croquis image (right)
            screenshot_scaled = item["screenshot"].scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            screenshot_x = 150 + (150 - screenshot_scaled.width()) // 2
            screenshot_y = (150 - screenshot_scaled.height()) // 2
            painter.drawPixmap(screenshot_x, screenshot_y, screenshot_scaled)
            
            # Time overlay in bottom-right of croquis image
            time_str = f"{item['time'] // 60}:{item['time'] % 60:02d}" if item['time'] > 0 else "N/A"
            
            # Semi-transparent black background
            time_width = 48
            time_height = 22
            bg_rect = QRect(300 - time_width - 8, 150 - time_height - 8, time_width, time_height)
            painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bg_rect, 8, 8)
            
            # Time text (white)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, time_str)
            
            painter.end()
            
            # Create QListWidgetItem
            list_item = QListWidgetItem()
            list_item.setIcon(QIcon(combined_pixmap))
            
            # Info text (time omitted)
            text = f"{item['date']} {item['timestamp'][9:11]}:{item['timestamp'][11:13]}"
            list_item.setText(text)
            
            # Store data (including file_path)
            item_data_with_path = item.copy()
            item_data_with_path["file_path"] = str(item["file"])
            list_item.setData(Qt.ItemDataRole.UserRole, item_data_with_path)
            
            # Show memo in tooltip if present
            memo_text = CroquisMemoDialog.get_memo(str(item["file"]))
            if memo_text:
                list_item.setToolTip(f"📝 {memo_text}")
            
            self.history_list.addItem(list_item)
        
        self.lazy_load_current_index = end_idx
        
        # Continue loading if there are more items
        if self.lazy_load_current_index < len(self.filtered_history):
            self.lazy_load_timer.start(100)  # Load next batch after 100ms
    
    def _on_history_list_scroll(self, value):
        """Trigger loading when scrolling near the bottom"""
        scrollbar = self.history_list.verticalScrollBar()
        if scrollbar.maximum() > 0:
            # Load more when scrolled to 80% of the way
            if value >= scrollbar.maximum() * 0.8:
                if self.lazy_load_current_index < len(self.filtered_history) and not self.lazy_load_timer.isActive():
                    self._load_next_history_batch()
    
    def show_large_view(self, item: QListWidgetItem):
        """Open large view dialog for croquis."""
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        # Retrieve file path
        croquis_file_path = data.get("file_path")
        dialog = CroquisLargeViewDialog(data, self.lang, croquis_file_path, self)
        dialog.exec()
    
    def show_history_context_menu(self, position):
        """Context menu for history list."""
        item = self.history_list.itemAt(position)
        if not item:
            return
        
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        croquis_file_path = data.get("file_path")
        if not croquis_file_path:
            return
        
        menu = QMenu(self)
        memo_action = QAction(tr("add_memo", self.lang), self)
        memo_action.triggered.connect(lambda: self.open_history_memo(croquis_file_path))
        menu.addAction(memo_action)
        
        menu.exec(self.history_list.mapToGlobal(position))
    
    def open_history_memo(self, croquis_file_path: str):
        """Open memo dialog from history list."""
        dialog = CroquisMemoDialog(croquis_file_path, self.lang, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Refresh list after memo save
            self.display_history()
    
    def show_croquis_detail(self, item: QListWidgetItem):
        """Show croquis details in large view."""
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        # Get croquis file path for memo functionality
        croquis_file_path = data.get("file_path")
        
        # Show in large view dialog
        dialog = CroquisLargeViewDialog(data, self.lang, croquis_file_path, self)
        dialog.exec()


# ============== Croquis Large View Dialog ==============
class CroquisLargeViewDialog(QDialog):
    """Dialog to view a croquis in large format."""
    
    def __init__(self, croquis_data: dict, lang: str = "ko", croquis_file_path: str = None, parent=None):
        super().__init__(parent)
        self.setWindowIcon(get_app_icon())
        self.croquis_data = croquis_data
        self.lang = lang
        self.croquis_file_path = croquis_file_path
        self.setup_ui()
        logger.info(LOG_MESSAGES["croquis_large_view_opened"])
    
    def setup_ui(self):
        self.setWindowTitle(tr("croquis_large_view", self.lang))
        self.resize(950, 550)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # Info display (top)
        info_text = f"📅 {self.croquis_data['date']} {self.croquis_data['timestamp'][9:11]}:{self.croquis_data['timestamp'][11:13]}"
        time_str = f"{self.croquis_data['time'] // 60}:{self.croquis_data['time'] % 60:02d}" if self.croquis_data['time'] > 0 else "N/A"
        info_text += f"  ⏱️ {time_str}"
        
        info_label = QLabel(info_text)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("font-size: 13px; font-weight: bold; padding: 8px; background-color: rgba(0, 120, 212, 0.1); border-radius: 5px;")
        main_layout.addWidget(info_label)
        
        # Image layout
        images_layout = QHBoxLayout()
        images_layout.setSpacing(15)
        
        # Original image (left)
        left_container = QVBoxLayout()
        left_container.setSpacing(5)
        
        orig_label = QLabel(tr("original_image", self.lang))
        orig_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        orig_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #0078d4;")
        left_container.addWidget(orig_label)
        
        # Fixed-size container (440x440)
        orig_img_container = QLabel()
        orig_img_container.setFixedSize(440, 440)
        orig_img_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        orig_img_container.setStyleSheet("border: 2px solid #e0e0e0; border-radius: 5px; background-color: white;")
        
        # Scale image within 440x440 while preserving aspect ratio
        orig_pixmap = self.croquis_data["original"].scaled(440, 440, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        orig_img_container.setPixmap(orig_pixmap)
        left_container.addWidget(orig_img_container)
        
        images_layout.addLayout(left_container)
        
        # Croquis image (right)
        right_container = QVBoxLayout()
        right_container.setSpacing(5)
        
        shot_label = QLabel(tr("croquis_image", self.lang))
        shot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shot_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #0078d4;")
        right_container.addWidget(shot_label)
        
        # Fixed-size container (440x440)
        shot_img_container = QLabel()
        shot_img_container.setFixedSize(440, 440)
        shot_img_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shot_img_container.setStyleSheet("border: 2px solid #e0e0e0; border-radius: 5px; background-color: white;")
        
        # Scale image within 440x440 while preserving aspect ratio
        shot_pixmap = self.croquis_data["screenshot"].scaled(440, 440, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        shot_img_container.setPixmap(shot_pixmap)
        right_container.addWidget(shot_img_container)
        
        images_layout.addLayout(right_container)
        
        main_layout.addLayout(images_layout)
        
        # Add memo button if croquis path is available
        if self.croquis_file_path:
            memo_btn = QPushButton(tr("add_memo", self.lang))
            memo_btn.clicked.connect(self.open_memo_dialog)
            main_layout.addWidget(memo_btn)
    
    def open_memo_dialog(self):
        """Open memo dialog from large view."""
        if self.croquis_file_path:
            dialog = CroquisMemoDialog(self.croquis_file_path, self.lang, self)
            dialog.exec()


# ============== Croquis Memo Dialog ==============
class CroquisMemoDialog(QDialog):
    """Dialog for viewing and editing croquis memos."""
    
    def __init__(self, croquis_file_path: str, lang: str = "ko", parent=None):
        super().__init__(parent)
        self.setWindowIcon(get_app_icon())
        self.croquis_file_path = croquis_file_path
        self.lang = lang
        self.setup_ui()
        self.load_memo()
        logger.info(LOG_MESSAGES["memo_dialog_opened"].format(os.path.basename(croquis_file_path)))
    
    def setup_ui(self):
        self.setWindowTitle(tr("memo", self.lang))
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Memo input area
        from PyQt6.QtWidgets import QTextEdit
        self.memo_edit = QTextEdit()
        self.memo_edit.setPlaceholderText(tr("memo_placeholder", self.lang))
        layout.addWidget(self.memo_edit)
        
        # Close button
        close_btn = QPushButton(tr("close", self.lang))
        close_btn.clicked.connect(self.save_and_close)
        layout.addWidget(close_btn)
    
    def load_memo(self):
        """Load memo from encrypted croquis file."""
        if os.path.exists(self.croquis_file_path):
            try:
                with open(self.croquis_file_path, "rb") as f:
                    encrypted = f.read()
                
                key = base64.urlsafe_b64encode(hashlib.sha256(b"croquis_secret_key").digest())
                fernet = Fernet(key)
                decrypted = fernet.decrypt(encrypted)
                data = json.loads(decrypted.decode())
                
                memo_text = data.get("memo", "")
                self.memo_edit.setPlainText(memo_text)
            except Exception as e:
                logger.error(LOG_MESSAGES["memo_loading_failed"].format(e))
    
    def save_and_close(self):
        """Persist memo and close dialog."""
        try:
            memo_text = self.memo_edit.toPlainText()
            
            # Read existing croq file
            with open(self.croquis_file_path, "rb") as f:
                encrypted = f.read()
            
            key = base64.urlsafe_b64encode(hashlib.sha256(b"croquis_secret_key").digest())
            fernet = Fernet(key)
            decrypted = fernet.decrypt(encrypted)
            data = json.loads(decrypted.decode())
            
            # Update memo content
            data["memo"] = memo_text
            
            # Re-encrypt and save
            encrypted_new = fernet.encrypt(json.dumps(data).encode())
            with open(self.croquis_file_path, "wb") as f:
                f.write(encrypted_new)
            
            logger.info(LOG_MESSAGES["memo_saved"].format(os.path.basename(self.croquis_file_path)))
            self.accept()
        except Exception as e:
            logger.error(LOG_MESSAGES["memo_saving_failed"].format(e))
            QMessageBox.warning(self, tr("error", self.lang), tr("memo_save_failed", self.lang).format(str(e)))
    
    @staticmethod
    def get_memo(croquis_file_path: str) -> str:
        """Retrieve memo text (for tooltip display)."""
        if os.path.exists(croquis_file_path):
            try:
                with open(croquis_file_path, "rb") as f:
                    encrypted = f.read()
                
                key = base64.urlsafe_b64encode(hashlib.sha256(b"croquis_secret_key").digest())
                fernet = Fernet(key)
                decrypted = fernet.decrypt(encrypted)
                data = json.loads(decrypted.decode())
                
                return data.get("memo", "").strip()
            except:
                return ""
        return ""


# ============== Alarm Window ==============
class AlarmWindow(QDialog):
    """Dialog managing croquis alarms."""
    
    def __init__(self, lang: str = "ko", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.alarms = []
        self.load_alarms()
        self.setup_ui()
        # 백그라운드 알람은 Windows 작업 스케줄러에서 처리됨
        
    def setup_ui(self):
        self.setWindowTitle(tr("croquis_alarm", self.lang))
        self.resize(690, 500)
        
        # Set window icon
        self.setWindowIcon(get_app_icon())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 15, 15, 15)
        
        # Alarm list        cd dist        .\Croquis.exe
        list_label = QLabel(tr("alarm_list_label", self.lang))
        layout.addWidget(list_label)
        
        self.alarm_list = QListWidget()
        self.alarm_list.itemDoubleClicked.connect(self.edit_alarm)
        layout.addWidget(self.alarm_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton(tr("add_alarm", self.lang))
        add_btn.clicked.connect(self.add_alarm)
        button_layout.addWidget(add_btn)
        
        edit_btn = QPushButton(tr("edit_alarm", self.lang))
        edit_btn.clicked.connect(self.edit_alarm)
        button_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton(tr("delete_alarm", self.lang))
        delete_btn.clicked.connect(self.delete_alarm)
        button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.refresh_alarm_list()
        
    def add_alarm(self):
        """Add a new alarm."""
        dialog = AlarmEditDialog(self.lang, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            alarm_data = dialog.get_alarm_data()
            self.alarms.append(alarm_data)
            self.save_alarms()
            self.refresh_alarm_list()
            
    def edit_alarm(self):
        """Edit the selected alarm."""
        current_item = self.alarm_list.currentItem()
        if not current_item:
            return
        
        index = self.alarm_list.row(current_item)
        alarm_data = self.alarms[index]
        
        dialog = AlarmEditDialog(self.lang, self, alarm_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.alarms[index] = dialog.get_alarm_data()
            self.save_alarms()
            self.refresh_alarm_list()
            
    def delete_alarm(self):
        """Delete the selected alarm."""
        current_item = self.alarm_list.currentItem()
        if not current_item:
            return
        
        index = self.alarm_list.row(current_item)
        del self.alarms[index]
        self.save_alarms()
        self.refresh_alarm_list()
        
    def refresh_alarm_list(self):
        """Refresh the alarm list UI."""
        self.alarm_list.clear()
        for alarm in self.alarms:
            if alarm.get("type") == "weekday":
                days = ", ".join([["월", "화", "수", "목", "금", "토", "일"][d] for d in alarm["weekdays"]])
                text = f"{alarm['title']} - 매주 {days} {alarm['time']}"
            else:
                text = f"{alarm['title']} - {alarm['date']} {alarm['time']}"
            
            item = QListWidgetItem(text)
            self.alarm_list.addItem(item)
    
    def save_alarms(self):
        """Persist alarms to disk."""
        dat_dir = get_data_path() / "dat"
        dat_dir.mkdir(exist_ok=True)
        alarms_path = dat_dir / "alarms.dat"
        encrypted = encrypt_data({"alarms": self.alarms})
        with open(alarms_path, "wb") as f:
            f.write(encrypted)
        
        # BAT 파일 기반 백그라운드 서비스 자동 관리
        if self.alarms:
            setup_alarm_background_service()
        else:
            # 알람이 없으면 백그라운드 서비스 제거
            remove_alarm_background_service()
    
    def load_alarms(self):
        """Load alarms from disk."""
        dat_dir = get_data_path() / "dat"
        alarms_path = dat_dir / "alarms.dat"
        if alarms_path.exists():
            try:
                with open(alarms_path, "rb") as f:
                    encrypted = f.read()
                decrypted = decrypt_data(encrypted)
                self.alarms = decrypted.get("alarms", [])
            except Exception:
                self.alarms = []
        else:
            self.alarms = []


class AlarmEditDialog(QDialog):
    """Dialog to create or edit an alarm."""
    
    def __init__(self, lang: str, parent=None, alarm_data=None):
        super().__init__(parent)
        self.setWindowIcon(get_app_icon())
        self.lang = lang
        self.alarm_data = alarm_data or {}
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle(tr("edit_alarm", self.lang) if self.alarm_data else tr("add_alarm", self.lang))
        self.resize(490, 400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 15, 15, 15)
        
        # Title
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel(tr("alarm_title", self.lang) + ":"))
        self.title_input = QLineEdit()
        self.title_input.setText(self.alarm_data.get("title", ""))
        title_layout.addWidget(self.title_input)
        layout.addLayout(title_layout)
        
        # Message
        layout.addWidget(QLabel(tr("alarm_message", self.lang) + ":"))
        from PyQt6.QtWidgets import QTextEdit
        self.message_input = QTextEdit()
        self.message_input.setPlainText(self.alarm_data.get("message", ""))
        self.message_input.setMinimumHeight(150)
        # Position cursor at top
        cursor = self.message_input.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.message_input.setTextCursor(cursor)
        layout.addWidget(self.message_input)
        
        # Time
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel(tr("alarm_time", self.lang) + ":"))
        self.time_edit = QTimeEdit()
        if self.alarm_data.get("time"):
            self.time_edit.setTime(QTime.fromString(self.alarm_data["time"], "HH:mm"))
        else:
            self.time_edit.setTime(QTime.currentTime())
        time_layout.addWidget(self.time_edit)
        layout.addLayout(time_layout)
        
        # Type selection
        self.type_combo = QComboBox()
        self.type_combo.addItem(tr("weekday_repeat", self.lang), "weekday")
        self.type_combo.addItem(tr("specific_date", self.lang), "date")
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        layout.addWidget(self.type_combo)
        
        # Weekday selection
        self.weekday_group = QGroupBox(tr("weekday_repeat_select", self.lang))
        self.weekday_group.setMaximumHeight(80)
        weekday_layout = QHBoxLayout(self.weekday_group)
        weekday_layout.setContentsMargins(10, 5, 10, 5)
        self.weekday_checks = []
        for day in [tr("mon", self.lang), tr("tue", self.lang), tr("wed", self.lang), tr("thu", self.lang), tr("fri", self.lang), tr("sat", self.lang), tr("sun", self.lang)]:
            check = QCheckBox(day)
            self.weekday_checks.append(check)
            weekday_layout.addWidget(check)
        layout.addWidget(self.weekday_group)
        
        # Date selection
        self.date_group = QGroupBox(tr("specific_date_select", self.lang))
        self.date_group.setMaximumHeight(80)
        date_layout = QVBoxLayout(self.date_group)
        date_layout.setContentsMargins(10, 5, 10, 5)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        if self.alarm_data.get("date"):
            self.date_edit.setDate(QDate.fromString(self.alarm_data["date"], "yyyy-MM-dd"))
        else:
            self.date_edit.setDate(QDate.currentDate())
        date_layout.addWidget(self.date_edit)
        layout.addWidget(self.date_group)
        
        # Load existing data
        if self.alarm_data.get("type") == "weekday":
            self.type_combo.setCurrentIndex(0)
            for i, checked in enumerate(self.alarm_data.get("weekdays", [])):
                if i < len(self.weekday_checks):
                    self.weekday_checks[checked].setChecked(True)
        else:
            self.type_combo.setCurrentIndex(1)
        
        self.on_type_changed()
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def on_type_changed(self):
        """Handle alarm type change."""
        alarm_type = self.type_combo.currentData()
        self.weekday_group.setVisible(alarm_type == "weekday")
        self.date_group.setVisible(alarm_type == "date")
    
    def get_alarm_data(self):
        """Return alarm data payload."""
        alarm_type = self.type_combo.currentData()
        data = {
            "title": self.title_input.text(),
            "message": self.message_input.toPlainText(),  # QTextEdit 사용
            "time": self.time_edit.time().toString("HH:mm"),
            "type": alarm_type,
            "enabled": True  # 새 알람은 기본적으로 활성화
        }
        
        if alarm_type == "weekday":
            data["weekdays"] = [i for i, check in enumerate(self.weekday_checks) if check.isChecked()]
        else:
            data["date"] = self.date_edit.date().toString("yyyy-MM-dd")
        
        return data


# ============== Tag Filtering Dialog ==============
class TagFilterDialog(QDialog):
    """Dialog for filtering deck images by tags."""
    
    def __init__(self, deck_path: str, lang: str = "ko", parent=None):
        super().__init__(parent)
        self.setWindowIcon(get_app_icon())
        self.deck_path = deck_path
        self.lang = lang
        self.all_tags: List[str] = []
        self.tag_checkboxes: Dict[str, QCheckBox] = {}
        self.deck_images: List[Dict[str, Any]] = []
        self.enabled_tags: set = set()  # 활성화된 태그
        
        self.setWindowTitle(tr("tag_title", self.lang))
        self.resize(400, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 15, 20)
        layout.setSpacing(12)
        
        # Info label
        info_label = QLabel(tr("tag_info", self.lang))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Loading indicator
        self.loading_label = QLabel(tr("tag_loading", self.lang))
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.loading_label)
        
        # Scroll area for tag list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.tags_layout = QVBoxLayout(scroll_widget)
        self.tags_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tags_layout.setContentsMargins(10, 10, 10, 10)  # 스크롤 내부 마진 증가
        scroll.setWidget(scroll_widget)
        scroll.hide()  # 처음에는 숨김
        self.scroll_area = scroll
        layout.addWidget(scroll, 1)
        
        # Selected image count display
        self.count_label = QLabel()
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_label.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(self.count_label)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Load tags asynchronously
        QTimer.singleShot(0, self.load_tags_async)
    
    def load_tags_async(self):
        """Load tags asynchronously from deck file."""
        try:
            # Load deck file
            if not self.deck_path or not os.path.exists(self.deck_path):
                self.loading_label.setText("덱 파일을 찾을 수 없습니다.")
                return
            
            with open(self.deck_path, "rb") as f:
                encrypted = f.read()
            
            data = decrypt_data(encrypted)
            self.deck_images = data.get("images", [])
            
            # Gather all tags (deduplicated)
            tags_set = set()
            for img in self.deck_images:
                tags = img.get("tags", [])
                if tags:
                    tags_set.update(tags)
            
            # Sort tags alphabetically
            self.all_tags = sorted(list(tags_set))
            
            # Initialize with all tags enabled
            self.enabled_tags = set(self.all_tags)
            
            # Update UI after loading tags
            self.update_tags_ui()
            
        except Exception as e:
            self.loading_label.setText(f"태그 로드 실패: {str(e)}")
            logger.error(LOG_MESSAGES["tag_loading_failed"].format(e))
    
    def update_tags_ui(self):
        """Refresh tag selection UI."""
        # Hide loading label and show scroll area
        self.loading_label.hide()
        self.scroll_area.show()
        
        # Remove existing checkboxes
        for i in reversed(range(self.tags_layout.count())):
            self.tags_layout.itemAt(i).widget().setParent(None)
        
        self.tag_checkboxes.clear()
        
        if not self.all_tags:
            no_tags_label = QLabel("이 덱에는 태그가 없습니다.")
            no_tags_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_tags_label.setStyleSheet("color: gray; padding: 20px;")
            self.tags_layout.addWidget(no_tags_label)
        else:
            # Create checkboxes per tag
            for tag in self.all_tags:
                cb = QCheckBox(tag)
                cb.setChecked(tag in self.enabled_tags)
                cb.stateChanged.connect(self.on_tag_changed)
                self.tag_checkboxes[tag] = cb
                self.tags_layout.addWidget(cb)
        
        # Update image count display
        self.update_count()
    
    def on_tag_changed(self):
        """Handle tag checkbox toggle."""
        # Update enabled tag set
        self.enabled_tags.clear()
        for tag, cb in self.tag_checkboxes.items():
            if cb.isChecked():
                self.enabled_tags.add(tag)
        
        # Refresh count
        self.update_count()
    
    def update_count(self):
        """Update label with filtered image count."""
        count = self.get_filtered_count()
        total = len(self.deck_images)
        self.count_label.setText(f"선택된 그림: {count} / {total}")
    
    def get_filtered_count(self) -> int:
        """Return number of images matching tag filter."""
        count = 0
        for img in self.deck_images:
            tags = img.get("tags", [])
            
            # Always include images with no tags
            if not tags:
                count += 1
                continue
            
            # Include when any enabled tag matches
            if any(tag in self.enabled_tags for tag in tags):
                count += 1
        
        return count
    
    def get_enabled_tags(self) -> set:
        """Return set of enabled tags."""
        return self.enabled_tags.copy()


# ============== Main Window ==============
class MainWindow(QMainWindow):
    """Main window for the croquis practice app."""
    
    def __init__(self):
        super().__init__()
        self.setWindowIcon(get_app_icon())  # Set main window icon
        self.settings = CroquisSettings()
        self.load_settings()
        self.lang = self.settings.language  # Add lang attribute
        self.image_files: List[str] = []
        self.enabled_tags: set = set()  # 활성화된 태그
        self.setup_ui()
        self.apply_language()
        self.apply_dark_mode()
        
    def setup_ui(self):
        self.setWindowTitle(tr("app_title", self.lang))
        self.setFixedSize(750, 750)
        
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 20, 10, 10)
        
        # Heatmap section
        heatmap_group = QGroupBox()
        heatmap_group.setMinimumHeight(150)  # Keep tooltips from clipping
        self.heatmap_group = heatmap_group
        heatmap_layout = QVBoxLayout(heatmap_group)
        heatmap_layout.setContentsMargins(10, 20, 10, 5)  # Minimize vertical padding
        heatmap_layout.setSpacing(0)
        
        # Align heatmap to the right
        heatmap_container = QHBoxLayout()
        heatmap_container.setContentsMargins(0, 0, 0, 0)
        heatmap_container.setSpacing(0)
        heatmap_container.addStretch(1)
        self.heatmap_widget = HeatmapWidget(lang=self.lang)
        self.heatmap_widget.setMinimumSize(600, 120)
        self.heatmap_widget.setContentsMargins(0, 0, 0, 0)
        heatmap_container.addWidget(self.heatmap_widget)
        heatmap_container.addStretch(1)
        heatmap_layout.addLayout(heatmap_container)
        
        main_layout.addWidget(heatmap_group)
        
        # Settings area (two-column layout)
        settings_layout = QHBoxLayout()
        
        # Left column
        left_column = QVBoxLayout()
        
        # Basic settings
        basic_group = QGroupBox()
        self.basic_group = basic_group
        basic_layout = QVBoxLayout(basic_group)
        
        folder_layout = QHBoxLayout()
        self.deck_label = QLabel()
        self.folder_value = QLineEdit()
        self.folder_value.setReadOnly(True)
        self.folder_value.setPlaceholderText(tr("deck_not_selected", self.lang))
        folder_layout.addWidget(self.deck_label)
        folder_layout.addWidget(self.folder_value, 1)
        basic_layout.addLayout(folder_layout)
        
        self.select_deck_btn = QPushButton()
        self.select_deck_btn.setMinimumHeight(32)
        self.select_deck_btn.clicked.connect(self.select_folder)
        basic_layout.addWidget(self.select_deck_btn)
        
        self.tag_filter_btn = QPushButton(tr("set_tags_filter", self.lang))
        self.tag_filter_btn.setMinimumHeight(32)
        self.tag_filter_btn.clicked.connect(self.show_tag_filter_dialog)
        self.tag_filter_btn.setEnabled(False)  # Disabled until a deck is selected
        basic_layout.addWidget(self.tag_filter_btn)
        
        left_column.addWidget(basic_group)
        
        # Image settings
        image_group = QGroupBox()
        self.image_group = image_group
        image_layout = QVBoxLayout(image_group)
        image_layout.setSpacing(8)  # Increase spacing
        
        width_layout = QHBoxLayout()
        self.width_label = QLabel()
        self.width_input = QSpinBox()
        self.width_input.setRange(100, 3000)
        self.width_input.setValue(self.settings.image_width)
        self.width_input.setMinimumWidth(80)
        self.width_input.setMinimumHeight(28)
        self.width_input.valueChanged.connect(self.on_width_changed)
        width_layout.addWidget(self.width_label)
        width_layout.addWidget(self.width_input)
        image_layout.addLayout(width_layout)
        
        height_layout = QHBoxLayout()
        self.height_label = QLabel()
        self.height_input = QSpinBox()
        self.height_input.setRange(100, 3000)
        self.height_input.setValue(self.settings.image_height)
        self.height_input.setMinimumWidth(80)
        self.height_input.setMinimumHeight(28)
        self.height_input.valueChanged.connect(self.on_height_changed)
        height_layout.addWidget(self.height_label)
        height_layout.addWidget(self.height_input)
        image_layout.addLayout(height_layout)
        
        self.grayscale_check = QCheckBox()
        self.grayscale_check.setChecked(self.settings.grayscale)
        self.grayscale_check.setMinimumHeight(25)
        self.grayscale_check.stateChanged.connect(self.on_grayscale_changed)
        image_layout.addWidget(self.grayscale_check)
        
        self.flip_check = QCheckBox()
        self.flip_check.setChecked(self.settings.flip_horizontal)
        self.flip_check.setMinimumHeight(25)
        self.flip_check.stateChanged.connect(self.on_flip_changed)
        image_layout.addWidget(self.flip_check)
        
        left_column.addWidget(image_group)
        left_column.addStretch()
        
        settings_layout.addLayout(left_column)
        
        # Right column
        right_column = QVBoxLayout()
        
        # Timer settings
        timer_group = QGroupBox()
        self.timer_group = timer_group
        timer_layout = QVBoxLayout(timer_group)
        
        pos_layout = QHBoxLayout()
        self.timer_pos_label = QLabel()
        self.timer_pos_combo = QComboBox()
        self.timer_pos_combo.addItems([
            tr("bottom_right", self.lang), tr("bottom_center", self.lang), tr("bottom_left", self.lang),
            tr("top_right", self.lang), tr("top_center", self.lang), tr("top_left", self.lang)
        ])
        # Map internal position to translated text
        pos_map_init = {
            "bottom_right": tr("bottom_right", self.lang),
            "bottom_center": tr("bottom_center", self.lang),
            "bottom_left": tr("bottom_left", self.lang),
            "top_right": tr("top_right", self.lang),
            "top_center": tr("top_center", self.lang),
            "top_left": tr("top_left", self.lang)
        }
        # Block signals during initialization to prevent logging
        self.timer_pos_combo.blockSignals(True)
        self.timer_pos_combo.setCurrentText(pos_map_init.get(self.settings.timer_position, tr("bottom_right", self.lang)))
        self.timer_pos_combo.blockSignals(False)
        # Connect signal after setting initial value
        self.timer_pos_combo.currentTextChanged.connect(self.on_timer_pos_changed)
        pos_layout.addWidget(self.timer_pos_label)
        pos_layout.addWidget(self.timer_pos_combo, 1)
        timer_layout.addLayout(pos_layout)
        
        font_layout = QHBoxLayout()
        self.timer_font_label = QLabel()
        self.timer_font_combo = QComboBox()
        self.timer_font_combo.currentTextChanged.connect(self.on_timer_font_changed)
        font_layout.addWidget(self.timer_font_label)
        font_layout.addWidget(self.timer_font_combo, 1)
        timer_layout.addLayout(font_layout)
        
        time_layout = QHBoxLayout()
        self.time_label = QLabel()
        self.time_input = QSpinBox()
        self.time_input.setRange(1, 3600)
        self.time_input.setValue(self.settings.time_seconds)
        self.time_input.setMinimumWidth(80)
        self.time_input.setMinimumHeight(28)
        self.time_input.valueChanged.connect(self.on_time_changed)
        time_layout.addWidget(self.time_label)
        time_layout.addWidget(self.time_input)
        timer_layout.addLayout(time_layout)
        
        # Study mode
        self.study_mode_check = QCheckBox()
        self.study_mode_check.setChecked(self.settings.study_mode)
        self.study_mode_check.setMinimumHeight(25)
        self.study_mode_check.stateChanged.connect(self.on_study_mode_changed)
        timer_layout.addWidget(self.study_mode_check)
        
        right_column.addWidget(timer_group)
        
        # Other settings
        other_group = QGroupBox()
        self.other_group = other_group
        other_layout = QVBoxLayout(other_group)
        
        lang_layout = QHBoxLayout()
        self.lang_label = QLabel()
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["한국어", "English", "日本語"])
        if self.lang == "ko":
            self.lang_combo.setCurrentText("한국어")
        elif self.lang == "ja":
            self.lang_combo.setCurrentText("日本語")
        else:
            self.lang_combo.setCurrentText("English")
        self.lang_combo.currentTextChanged.connect(self.on_language_changed)
        lang_layout.addWidget(self.lang_label)
        lang_layout.addWidget(self.lang_combo, 1)
        other_layout.addLayout(lang_layout)
        
        self.dark_mode_check = QCheckBox()
        self.dark_mode_check.setChecked(self.settings.dark_mode)
        self.dark_mode_check.setMinimumHeight(25)
        self.dark_mode_check.stateChanged.connect(self.on_dark_mode_changed)
        other_layout.addWidget(self.dark_mode_check)
        
        # Today's croquis count position
        today_pos_layout = QHBoxLayout()
        self.today_pos_label = QLabel()
        self.today_pos_combo = QComboBox()
        # Block signals during initialization to prevent logging
        self.today_pos_combo.blockSignals(True)
        self.today_pos_combo.addItems([
            tr("bottom_right", self.lang), tr("bottom_center", self.lang), tr("bottom_left", self.lang),
            tr("top_right", self.lang), tr("top_center", self.lang), tr("top_left", self.lang)
        ])
        # Set current value using internal settings
        today_pos_map_init = {
            "bottom_right": tr("bottom_right", self.lang),
            "bottom_center": tr("bottom_center", self.lang),
            "bottom_left": tr("bottom_left", self.lang),
            "top_right": tr("top_right", self.lang),
            "top_center": tr("top_center", self.lang),
            "top_left": tr("top_left", self.lang)
        }
        self.today_pos_combo.setCurrentText(today_pos_map_init.get(self.settings.today_croquis_count_position, tr("top_right", self.lang)))
        self.today_pos_combo.blockSignals(False)
        # Connect signal after setting initial value
        self.today_pos_combo.currentTextChanged.connect(self.on_today_pos_changed)
        today_pos_layout.addWidget(self.today_pos_label)
        today_pos_layout.addWidget(self.today_pos_combo, 1)
        other_layout.addLayout(today_pos_layout)
        
        # Today's croquis count font size
        today_font_layout = QHBoxLayout()
        self.today_font_label = QLabel()
        self.today_font_combo = QComboBox()
        self.today_font_combo.addItems([
            tr("font_large_20", self.lang),
            tr("font_medium_15", self.lang),
            tr("font_small_10", self.lang)
        ])
        # Set current value
        font_map = {"large": tr("font_large_20", self.lang), "medium": tr("font_medium_15", self.lang), "small": tr("font_small_10", self.lang)}
        self.today_font_combo.setCurrentText(font_map.get(self.settings.today_croquis_count_font_size, tr("font_medium_15", self.lang)))
        self.today_font_combo.currentTextChanged.connect(self.on_today_font_changed)
        today_font_layout.addWidget(self.today_font_label)
        today_font_layout.addWidget(self.today_font_combo, 1)
        other_layout.addLayout(today_font_layout)
        
        right_column.addWidget(other_group)
        right_column.addStretch()
        
        settings_layout.addLayout(right_column)
        main_layout.addLayout(settings_layout)
        
        # Button area
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        
        self.start_btn = QPushButton()
        self.start_btn.setEnabled(False)
        self.start_btn.setMinimumHeight(32)
        self.start_btn.clicked.connect(self.start_croquis)
        button_layout.addWidget(self.start_btn)
        
        self.edit_deck_btn = QPushButton()
        self.edit_deck_btn.setMinimumHeight(32)
        self.edit_deck_btn.clicked.connect(self.open_deck_editor)
        button_layout.addWidget(self.edit_deck_btn)
        
        self.history_btn = QPushButton()
        self.history_btn.setMinimumHeight(32)
        self.history_btn.clicked.connect(self.open_history)
        button_layout.addWidget(self.history_btn)
        
        self.alarm_btn = QPushButton()
        self.alarm_btn.setMinimumHeight(32)
        self.alarm_btn.clicked.connect(self.open_alarm)
        button_layout.addWidget(self.alarm_btn)
        
        main_layout.addLayout(button_layout)
        
        # Enable/disable time input based on study mode
        self.time_input.setEnabled(not self.settings.study_mode)
        
    def apply_language(self):
        """Apply translated UI text for current language."""
        self.lang = self.settings.language
        
        self.setWindowTitle(tr("app_title", self.lang))
        
        # Heatmap
        count = self.heatmap_widget.total_count
        self.heatmap_group.setTitle(f"{tr('heatmap_title', self.lang)} - {tr('croquis_count', self.lang)}: {count} {tr('croquis_times', self.lang)}")
        self.heatmap_widget.lang = self.lang
        
        # Basic settings
        self.basic_group.setTitle(tr("basic_settings", self.lang))
        self.deck_label.setText(tr("croquis_deck", self.lang))
        self.select_deck_btn.setText(tr("select_deck", self.lang))
        self.tag_filter_btn.setText(tr("set_tags_filter", self.lang))
        self.folder_value.setPlaceholderText(tr("deck_not_selected", self.lang))
        
        # Image settings
        self.image_group.setTitle(tr("image_settings", self.lang))
        self.width_label.setText(tr("image_width", self.lang))
        self.height_label.setText(tr("image_height", self.lang))
        self.grayscale_check.setText(tr("grayscale", self.lang))
        self.flip_check.setText(tr("flip_horizontal", self.lang))
        
        # Timer settings
        self.timer_group.setTitle(tr("timer_settings", self.lang))
        self.timer_pos_label.setText(tr("timer_position", self.lang))
        self.timer_font_label.setText(tr("timer_font_size", self.lang))
        self.time_label.setText(tr("time_setting", self.lang))
        self.study_mode_check.setText(tr("study_mode", self.lang))
        
        # Refresh timer position combo box
        # Store current internal position from settings
        current_internal_pos = self.settings.timer_position
        # Block signals during entire refresh process
        self.timer_pos_combo.blockSignals(True)
        self.timer_pos_combo.clear()
        self.timer_pos_combo.addItems([
            tr("bottom_right", self.lang), tr("bottom_center", self.lang), tr("bottom_left", self.lang),
            tr("top_right", self.lang), tr("top_center", self.lang), tr("top_left", self.lang)
        ])
        # Restore the selected position using internal settings value
        self.timer_pos_combo.setCurrentText(tr(current_internal_pos, self.lang))
        self.timer_pos_combo.blockSignals(False)
        
        # Refresh timer font combo box
        self.timer_font_combo.clear()
        self.timer_font_combo.addItems([
            tr("large", self.lang),
            tr("medium", self.lang),
            tr("small", self.lang)
        ])
        font_map = {"large": 0, "medium": 1, "small": 2}
        self.timer_font_combo.setCurrentIndex(font_map.get(self.settings.timer_font_size, 0))
        
        # Other settings
        self.other_group.setTitle(tr("other_settings", self.lang))
        self.lang_label.setText(tr("language", self.lang))
        self.dark_mode_check.setText(tr("dark_mode", self.lang))
        
        # Today's croquis count position
        self.today_pos_label.setText(tr("today_croquis_count_position", self.lang))
        current_today_pos = self.settings.today_croquis_count_position
        self.today_pos_combo.blockSignals(True)
        self.today_pos_combo.clear()
        self.today_pos_combo.addItems([
            tr("bottom_right", self.lang), tr("bottom_center", self.lang), tr("bottom_left", self.lang),
            tr("top_right", self.lang), tr("top_center", self.lang), tr("top_left", self.lang)
        ])
        self.today_pos_combo.setCurrentText(tr(current_today_pos, self.lang))
        self.today_pos_combo.blockSignals(False)
        
        # Today's croquis count font size
        self.today_font_label.setText(tr("today_croquis_count_font_size", self.lang))
        self.today_font_combo.clear()
        self.today_font_combo.addItems([
            tr("font_large_20", self.lang),
            tr("font_medium_15", self.lang),
            tr("font_small_10", self.lang)
        ])
        today_font_map = {"large": 0, "medium": 1, "small": 2}
        self.today_font_combo.setCurrentIndex(today_font_map.get(self.settings.today_croquis_count_font_size, 1))
        
        # Buttons
        self.start_btn.setText(tr("start_croquis", self.lang))
        self.edit_deck_btn.setText(tr("edit_deck", self.lang))
        self.history_btn.setText(tr("croquis_history", self.lang))
        self.alarm_btn.setText(tr("croquis_alarm", self.lang))
        
    def apply_dark_mode(self):
        """Apply dark mode palette and styles."""
        if self.settings.dark_mode:
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QGroupBox {
                    border: 1px solid #555;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QPushButton {
                    background-color: #3a3a3a;
                    border: 1px solid #555;
                    border-radius: 5px;
                    padding: 8px;
                    color: #ffffff;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:disabled {
                    background-color: #2a2a2a;
                    color: #666;
                }
                QLineEdit, QSpinBox, QComboBox {
                    background-color: #3a3a3a;
                    border: 1px solid #555;
                    border-radius: 4px;
                    padding: 5px;
                    color: #ffffff;
                }
                QCheckBox {
                    color: #ffffff;
                }
                QCheckBox::indicator {
                    background-color: #252525;
                }
                QCheckBox::indicator:checked {
                    background-color: #0078d4;
                    border-color: #0078d4;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #ffffff;
                    color: #000000;
                }
                QGroupBox {
                    border: 1px solid #555;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QPushButton {
                    background-color: #eeeeee;
                    border: 1px solid #555;
                    border-radius: 5px;
                    padding: 8px;
                    color: #000000;
                }
                QPushButton:hover {
                    background-color: #eeeeee;
                }
                QPushButton:disabled {
                    background-color: #dddddd;
                    color: #666;
                }
                QLineEdit, QSpinBox, QComboBox {
                    background-color: #dddddd;
                    border: 1px solid #555;
                    border-radius: 4px;
                    padding: 5px;
                    color: #000000;
                }
                QCheckBox {
                    color: #000000;
                }
                QCheckBox::indicator {
                    background-color: #dddddd;
                }
                QCheckBox::indicator:checked {
                    background-color: #0078d4;
                    border-color: #0078d4;
                }
            """)
            
    def select_folder(self):
        """Open file dialog to pick a croquis deck."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("select_deck_file", self.lang),
            "",
            f"{tr('croquis_deck_file', self.lang)} (*.crdk)"
        )
        if file_path:
            logger.info(LOG_MESSAGES["deck_selected"].format(os.path.basename(file_path)))
            self.load_deck_file(file_path)
            
    def load_deck_file(self, file_path: str):
        """Load images from croquis deck file."""
        try:
            with open(file_path, "rb") as f:
                encrypted = f.read()
            
            data = decrypt_data(encrypted)
            self.image_files = []
            
            images_data = data.get("images", [])
            
            # Handle new format (dict) or legacy format (str)
            for img in images_data:
                if isinstance(img, dict):
                    # Apply tag filtering
                    img_tags = img.get("tags", [])
                    
                    # Always include images without tags
                    if not img_tags:
                        pass
                    # When enabled tags exist and none match, skip image
                    elif self.enabled_tags and not any(tag in self.enabled_tags for tag in img_tags):
                        continue
                    
                    # New format: extract image_data field
                    try:
                        image_data_b64 = img.get("image_data", "")
                        if image_data_b64:
                            # Base64 decode to in-memory image
                            image_bytes = base64.b64decode(image_data_b64)
                            # Temporarily store dict (handled in ImageViewerWindow)
                            self.image_files.append(img)
                    except Exception as e:
                        print(f"{tr('invalid_image', self.lang)}: {e}")
                        continue
                elif isinstance(img, str):
                    # Legacy format: file path
                    if os.path.exists(img):
                        self.image_files.append(img)
            
            if self.image_files:
                self.settings.image_folder = file_path
                self.folder_value.setText(f"{os.path.basename(file_path)} ({len(self.image_files)} {tr("images_count", self.lang)})")
                self.start_btn.setEnabled(True)
                self.tag_filter_btn.setEnabled(True)  # Enable tag filter button
                self.save_settings()
            else:
                QMessageBox.warning(self, tr("warning", self.lang), tr("deck_no_valid_images", self.lang))
        except Exception as e:
            QMessageBox.warning(self, tr("error", self.lang), f"{tr("deck_file_load_error", self.lang)}: {str(e)}")
    
    def load_images_from_deck(self, deck_path: str):
        """Reload images from deck applying tag filters."""
        self.load_deck_file(deck_path)
            
    def load_images_from_folder(self, folder: str):
        """Load images from a folder (legacy compatibility)."""
        if folder.endswith('.crdk'):
            self.load_deck_file(folder)
            return
            
        self.image_files.clear()
        extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
        
        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(extensions):
                    self.image_files.append(os.path.join(root, file))
        
        self.start_btn.setEnabled(len(self.image_files) > 0)
        
    def on_width_changed(self, value: int):
        self.settings.image_width = value
        logger.info(LOG_MESSAGES["image_width_changed"].format(value))
        self.save_settings()
        
    def on_height_changed(self, value: int):
        self.settings.image_height = value
        logger.info(LOG_MESSAGES["image_height_changed"].format(value))
        self.save_settings()
        
    def on_grayscale_changed(self, state: int):
        self.settings.grayscale = state == Qt.CheckState.Checked.value
        logger.info(LOG_MESSAGES["grayscale_mode"].format(self.settings.grayscale))
        self.save_settings()
        
    def on_flip_changed(self, state: int):
        self.settings.flip_horizontal = state == Qt.CheckState.Checked.value
        logger.info(LOG_MESSAGES["flip_horizontal"].format(self.settings.flip_horizontal))
        self.save_settings()
        
    def on_timer_pos_changed(self, text: str):
        # Map translated text to internal position value
        pos_map = {
            tr("bottom_right", self.lang): "bottom_right",
            tr("bottom_center", self.lang): "bottom_center",
            tr("bottom_left", self.lang): "bottom_left",
            tr("top_right", self.lang): "top_right",
            tr("top_center", self.lang): "top_center",
            tr("top_left", self.lang): "top_left"
        }
        internal_value = pos_map.get(text, "bottom_right")
        self.settings.timer_position = internal_value
        logger.info(LOG_MESSAGES["timer_position_changed"].format(internal_value))
        self.save_settings()
        
    def on_timer_font_changed(self, text: str):
        font_map = {
            tr("large", self.lang): "large",
            tr("medium", self.lang): "medium",
            tr("small", self.lang): "small",
            # "크게": "large", "보통": "medium", "작게": "small",
            # "Large": "large", "Medium": "medium", "Small": "small"
        }
        old_size = self.settings.timer_font_size
        self.settings.timer_font_size = font_map.get(text, "large")
        # Only log when value actually changes
        if old_size != self.settings.timer_font_size:
            logger.info(LOG_MESSAGES["timer_font_size_changed"].format(self.settings.timer_font_size))
        self.save_settings()
    
    def on_today_pos_changed(self, text: str):
        # Map translated text to internal position value
        pos_map = {
            tr("bottom_right", self.lang): "bottom_right",
            tr("bottom_center", self.lang): "bottom_center",
            tr("bottom_left", self.lang): "bottom_left",
            tr("top_right", self.lang): "top_right",
            tr("top_center", self.lang): "top_center",
            tr("top_left", self.lang): "top_left"
        }
        internal_value = pos_map.get(text, "top_right")
        self.settings.today_croquis_count_position = internal_value
        self.save_settings()
    
    def on_today_font_changed(self, text: str):
        # Map translated text to internal font size value
        font_map = {
            tr("font_large_20", self.lang): "large",
            tr("font_medium_15", self.lang): "medium",
            tr("font_small_10", self.lang): "small"
        }
        self.settings.today_croquis_count_font_size = font_map.get(text, "medium")
        self.save_settings()
        
    def on_time_changed(self, value: int):
        self.settings.time_seconds = value
        logger.info(LOG_MESSAGES["timer_time_changed"].format(value))
        self.save_settings()
        
    def on_language_changed(self, text: str):
        if text == "한국어":
            self.settings.language = "ko"
        elif text == "日本語":
            self.settings.language = "ja"
        else:
            self.settings.language = "en"
        self.lang = self.settings.language  # Update lang attribute
        logger.info(LOG_MESSAGES["language_changed"].format(self.lang))
        self.apply_language()
        self.save_settings()
        
    def on_dark_mode_changed(self, state: int):
        self.settings.dark_mode = state == Qt.CheckState.Checked.value
        logger.info(LOG_MESSAGES["dark_mode"].format(self.settings.dark_mode))
        self.apply_dark_mode()
        self.save_settings()
        
    def on_study_mode_changed(self, state: int):
        """Toggle study mode state."""
        self.settings.study_mode = state == Qt.CheckState.Checked.value
        self.time_input.setEnabled(not self.settings.study_mode)
        self.save_settings()
    
    def show_tag_filter_dialog(self):
        """Display tag filtering dialog."""
        # Validate deck path
        deck_path = self.settings.image_folder
        if not deck_path or not os.path.exists(deck_path):
            QMessageBox.warning(self, tr("warning", self.lang), tr("select_deck_first", self.lang))
            return
        
        # Show dialog
        dialog = TagFilterDialog(deck_path, self.lang, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.enabled_tags = dialog.get_enabled_tags()
            logger.info(LOG_MESSAGES["tags_enabled"].format(self.enabled_tags))
            
            # Reload images with tag filters applied
            self.load_images_from_deck(deck_path)
    
    def start_croquis(self):
        """Start croquis session."""
        if not self.image_files:
            return
        
        logger.info(LOG_MESSAGES["croquis_started"].format(len(self.image_files)))
        self.viewer = ImageViewerWindow(
            self.settings,
            self.image_files.copy(),
            self.lang
        )
        self.viewer.croquis_completed.connect(self.on_croquis_completed)
        self.viewer.croquis_saved.connect(self.on_croquis_saved)
        self.viewer.show()
        
    def on_croquis_completed(self):
        """Handle croquis completion event."""
        # Don't add count here - it's added in on_croquis_saved
        count = self.heatmap_widget.total_count
        self.heatmap_group.setTitle(
            f"{tr('heatmap_title', self.lang)} - "
            f"{tr('croquis_count', self.lang)}: {count} {tr('croquis_times', self.lang)}"
        )
        
    def on_croquis_saved(self, original: QPixmap, screenshot: QPixmap, croquis_time: int, image_filename: str, image_metadata: dict):
        """Persist croquis pair when saved."""
        # Save as encrypted file
        pairs_dir = get_data_path() / "croquis_pairs"
        pairs_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Convert QPixmap to bytes via temporary files
        import tempfile
        import time
        
        # Create temporary files for export
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_orig:
            orig_path = tmp_orig.name
        
        original.save(orig_path, "PNG")
        time.sleep(0.1)  # Wait for filesystem sync
        with open(orig_path, "rb") as f:
            orig_bytes = f.read()
        time.sleep(0.1)
        try:
            os.unlink(orig_path)
        except PermissionError:
            pass  # Ignore occasional Windows file lock
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_shot:
            shot_path = tmp_shot.name
        
        screenshot.save(shot_path, "PNG")
        time.sleep(0.1)
        with open(shot_path, "rb") as f:
            shot_bytes = f.read()
        time.sleep(0.1)
        try:
            os.unlink(shot_path)
        except PermissionError:
            pass
        
        # Simple encryption (Fernet)
        key = base64.urlsafe_b64encode(hashlib.sha256(b"croquis_secret_key").digest())
        fernet = Fernet(key)
        
        data = {
            "original": base64.b64encode(orig_bytes).decode(),
            "screenshot": base64.b64encode(shot_bytes).decode(),
            "timestamp": timestamp,
            "croquis_time": croquis_time,
            "image_metadata": image_metadata,
            "memo": ""  # Blank memo field
        }
        
        encrypted = fernet.encrypt(json.dumps(data).encode())
        
        # Include original image name in filename
        filename = f"{timestamp}_{image_filename}.croq"
        croq_path = pairs_dir / filename
        with open(croq_path, "wb") as f:
            f.write(encrypted)
            
        self.heatmap_widget.add_croquis(1)
        
    def open_deck_editor(self):
        """Open deck editor window."""
        logger.info(LOG_MESSAGES["deck_editor_opened"])
        self.deck_editor = DeckEditorWindow(self.lang, self.settings.dark_mode)
        self.deck_editor.show()
        
    def open_history(self):
        """Open croquis history dialog."""
        logger.info(LOG_MESSAGES["history_opened"])
        dialog = HistoryWindow(self.lang, self, self.settings.dark_mode)
        dialog.exec()
        logger.info(LOG_MESSAGES["history_closed"])
        
    def open_alarm(self):
        """Open alarm settings dialog."""
        logger.info(LOG_MESSAGES["alarm_settings_opened"])
        dialog = AlarmWindow(self.lang, self)
        dialog.exec()
        logger.info(LOG_MESSAGES["alarm_settings_closed"])
        
    def load_settings(self):
        """Load settings from disk."""
        dat_dir = get_data_path() / "dat"
        dat_dir.mkdir(exist_ok=True)
        settings_path = dat_dir / "settings.dat"
        if settings_path.exists():
            try:
                with open(settings_path, "rb") as f:
                    encrypted = f.read()
                decrypted = decrypt_data(encrypted)
                self.settings = CroquisSettings(**decrypted)
            except Exception:
                self.settings = CroquisSettings()
                self.save_settings()  # Save default settings on error
        else:
            # Create default settings when file is missing
            self.settings = CroquisSettings()
            self.save_settings()
                
    def save_settings(self):
        """Persist settings to disk."""
        dat_dir = get_data_path() / "dat"
        dat_dir.mkdir(exist_ok=True)
        settings_path = dat_dir / "settings.dat"
        encrypted = encrypt_data(asdict(self.settings))
        with open(settings_path, "wb") as f:
            f.write(encrypted)
            
    def closeEvent(self, event):
        logger.info(LOG_MESSAGES["program_closed"])
        self.save_settings()
        super().closeEvent(event)


def main():
    # --check-alarm 인수로 실행된 경우 알람만 확인하고 종료
    if len(sys.argv) > 1 and sys.argv[1] == "--check-alarm":
        check_and_trigger_alarms()
        sys.exit(0)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
