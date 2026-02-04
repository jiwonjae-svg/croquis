"""
Reusable GUI widgets for Croquis application
"""

from datetime import date, timedelta
from typing import Dict, Optional
from pathlib import Path

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QPixmap,
    QPaintEvent, QMouseEvent, QKeyEvent, QGuiApplication
)

from core.key_manager import encrypt_data, decrypt_data
from utils.language_manager import TRANSLATIONS


def tr(key: str, lang: str = "ko") -> str:
    """Translation helper"""
    return TRANSLATIONS.get(lang, TRANSLATIONS["ko"]).get(key, key)


def get_data_path():
    """Get base path for data files (dat, logs, croquis_pairs etc.).
    Returns the project root directory."""
    import sys
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - use executable's directory
        return Path(sys.executable).parent
    else:
        # Running as script - use project root (parent of src directory)
        return Path(__file__).parent.parent.parent


class HeatmapWidget(QWidget):
    """GitHub-style croquis heatmap widget"""
    
    def __init__(self, parent=None, lang: str = "ko"):
        super().__init__(parent)
        self.lang = lang
        self.data: Dict[str, int] = {}
        self.cell_size = 10
        self.cell_gap = 1
        self.weeks = 53
        self.days = 7
        self.total_count = 0
        self.load_data()
        self.setMinimumHeight(120)
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
            return QColor(200, 200, 200)  # Darker gray for empty cells
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
        
        x_offset = 10
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
                painter.setPen(QPen(QColor(150, 150, 150), 1))  # Add light border
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
