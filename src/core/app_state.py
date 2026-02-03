"""
Application State Management
Centralized state management for Croquis application using signals
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from core.models import CroquisSettings


class AppState(QObject):
    """
    Central application state manager.
    All UI components should reference this singleton for shared state.
    """
    
    # Signals for state changes
    settings_changed = pyqtSignal()
    deck_changed = pyqtSignal(str)  # deck_path
    images_loaded = pyqtSignal(list)  # image_files
    tag_filter_changed = pyqtSignal(set)  # enabled_tags
    croquis_completed = pyqtSignal()
    croquis_saved = pyqtSignal(object, object, int, str, dict)  # original, screenshot, time, filename, metadata
    language_changed = pyqtSignal(str)  # lang
    heatmap_updated = pyqtSignal()
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        
        # Core state
        self.settings = CroquisSettings()
        self.image_files: List[str] = []
        self.enabled_tags: Set[str] = set()
        self.current_deck_path: str = ""
        
        # Heatmap data
        self.heatmap_data: Dict[str, int] = {}
        self.total_croquis_count: int = 0
    
    def update_settings(self, settings: CroquisSettings):
        """Update application settings"""
        self.settings = settings
        self.settings_changed.emit()
    
    def load_deck(self, deck_path: str, image_files: List[str]):
        """Load a new deck"""
        self.current_deck_path = deck_path
        self.image_files = image_files
        self.deck_changed.emit(deck_path)
        self.images_loaded.emit(image_files)
    
    def set_tag_filter(self, enabled_tags: Set[str]):
        """Update tag filter"""
        self.enabled_tags = enabled_tags
        self.tag_filter_changed.emit(enabled_tags)
    
    def set_language(self, lang: str):
        """Update application language"""
        self.settings.language = lang
        self.language_changed.emit(lang)
        self.settings_changed.emit()
    
    def increment_croquis_count(self, count: int = 1):
        """Increment daily croquis count"""
        from datetime import date
        today = date.today().isoformat()
        self.heatmap_data[today] = self.heatmap_data.get(today, 0) + count
        self.total_croquis_count += count
        self.heatmap_updated.emit()
    
    def get_lang(self) -> str:
        """Get current language"""
        return self.settings.language


# Global singleton instance
def get_app_state() -> AppState:
    """Get global AppState singleton"""
    return AppState()
