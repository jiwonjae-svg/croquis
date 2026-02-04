"""
Common utility functions for Croquis application
"""

import sys
from pathlib import Path
from PyQt6.QtGui import QIcon
from utils.language_manager import TRANSLATIONS


def get_data_path():
    """Get base path for data files (dat, logs, croquis_pairs etc.).
    Returns the project root directory."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - use executable's directory
        return Path(sys.executable).parent
    else:
        # Running as script - use project root (parent of src directory)
        return Path(__file__).parent.parent.parent


def tr(key: str, lang: str = "ko") -> str:
    """Translation helper"""
    return TRANSLATIONS.get(lang, TRANSLATIONS["ko"]).get(key, key)


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
        # Running as script - icon is in src/assets
        icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
    
    if icon_path and icon_path.exists():
        return QIcon(str(icon_path))
    
    return QIcon()
