"""
Data models and settings for Croquis application
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List


# Default shortcut key bindings
DEFAULT_SHORTCUTS = {
    "next_image": "Space",
    "previous_image": "Left",
    "toggle_pause": "P",
    "stop_croquis": "Escape",
}


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
    shortcuts: dict = field(default_factory=lambda: DEFAULT_SHORTCUTS.copy())


@dataclass
class CroquisRecord:
    """Croquis record data class"""
    date: str
    count: int


# Size constants for UI elements
class UIConstants:
    """UI size and layout constants"""
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
