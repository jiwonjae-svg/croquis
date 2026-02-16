"""
Qt Resource Loader Module
Load images and CSV from compiled .qrc resources with improved error handling
"""

from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import QFile, QIODevice
import logging
import sys
from pathlib import Path
import csv
from io import StringIO

logger = logging.getLogger('Croquis')

# Add assets directory to sys.path for resources_rc import
assets_dir = Path(__file__).parent.parent / "assets"
if str(assets_dir) not in sys.path:
    sys.path.insert(0, str(assets_dir))

# Try to import compiled resources
try:
    import resources_rc  # type: ignore[import-not-found]
    RESOURCES_AVAILABLE = True
    # Get the _RESOURCES dictionary
    if hasattr(resources_rc, '_RESOURCES'):
        _RESOURCES_DICT = resources_rc._RESOURCES
    else:
        _RESOURCES_DICT = {}
    logger.info("Qt resources_rc module loaded successfully")
except ImportError as e:
    RESOURCES_AVAILABLE = False
    _RESOURCES_DICT = {}
    logger.warning(f"resources_rc.py not found: {e}. Run 'python scripts/compile_resources.py' first.")


class QtResourceLoader:
    """Qt Resource Loader with fallback support"""
    
    def __init__(self):
        self.resources_available = RESOURCES_AVAILABLE
        if not self.resources_available:
            logger.warning("Qt resources not available. Some features may not work.")
    
    def resource_exists(self, resource_path: str) -> bool:
        """Check if a resource exists"""
        if not self.resources_available:
            return False
        
        qfile = QFile(resource_path)
        return qfile.exists()
    
    def get_pixmap(self, resource_path: str) -> QPixmap:
        """
        Load QPixmap from Qt resource
        
        Args:
            resource_path: Qt resource path (e.g., "/buttons/정지.png")
        
        Returns:
            QPixmap object (empty if failed)
        """
        if not self.resources_available:
            logger.warning(f"Resources not available for: {resource_path}")
            return QPixmap()
        
        try:
            import base64
            # Strip : prefix to match dictionary keys
            dict_key = resource_path[1:] if resource_path.startswith(":") else resource_path
            
            if dict_key in _RESOURCES_DICT:
                encoded_data = _RESOURCES_DICT[dict_key]
                raw_data = base64.b64decode(encoded_data.encode('ascii'))
                pixmap = QPixmap()
                pixmap.loadFromData(raw_data)
                if pixmap.isNull():
                    logger.warning(f"Failed to decode pixmap data: {resource_path}")
                    return QPixmap()
                return pixmap
            
            # Fallback: try loading from filesystem
            pixmap = self._load_pixmap_fallback(resource_path)
            if not pixmap.isNull():
                return pixmap
            
            logger.warning(f"Failed to load pixmap: {resource_path}")
            return QPixmap()
            
        except Exception as e:
            logger.error(f"Error loading pixmap {resource_path}: {e}")
            return QPixmap()
    
    def _load_pixmap_fallback(self, resource_path: str) -> QPixmap:
        """
        Fallback method to load pixmap from filesystem
        """
        try:
            if resource_path.startswith(":/"):
                rel_path = resource_path[2:]
            elif resource_path.startswith("/"):
                rel_path = resource_path[1:]
            else:
                rel_path = resource_path
            
            possible_paths = [
                Path(__file__).parent.parent / "assets" / rel_path,
                Path(__file__).parent.parent.parent / rel_path,
                Path(rel_path)
            ]
            
            for file_path in possible_paths:
                if file_path.exists():
                    pixmap = QPixmap(str(file_path))
                    if not pixmap.isNull():
                        logger.info(f"Loaded pixmap from fallback: {file_path}")
                        return pixmap
            
            return QPixmap()
        except Exception as e:
            logger.error(f"Fallback pixmap load failed for {resource_path}: {e}")
            return QPixmap()
    
    def get_icon(self, resource_path: str) -> QIcon:
        """
        Load QIcon from Qt resource
        
        Args:
            resource_path: Qt resource path (e.g., ":/buttons/정지.png")
        
        Returns:
            QIcon object
        """
        pixmap = self.get_pixmap(resource_path)
        return QIcon(pixmap)
    
    def read_text_file(self, resource_path: str, encoding: str = 'utf-8') -> str:
        """
        Read text file from Qt resource
        
        Args:
            resource_path: Qt resource path (e.g., ":/data/translations.csv")
            encoding: Text encoding (default: utf-8)
        
        Returns:
            File content as string
        """
        if not self.resources_available:
            logger.warning(f"Resources not available for: {resource_path}")
            # Fallback: try to load from actual file
            return self._read_file_fallback(resource_path, encoding)
        
        try:
            # First try: Load from _RESOURCES_DICT directly
            # Strip : prefix to match dictionary keys (keep the leading /)
            dict_key = resource_path[1:] if resource_path.startswith(":") else resource_path
            
            if dict_key in _RESOURCES_DICT:
                import base64
                encoded_data = _RESOURCES_DICT[dict_key]
                data = base64.b64decode(encoded_data.encode('ascii'))
                return data.decode(encoding)
            
            # Second try: QFile (for compatibility)
            qfile = QFile(resource_path)
            if not qfile.exists():
                logger.warning(f"Resource not found: {resource_path}")
                return self._read_file_fallback(resource_path, encoding)
            
            if not qfile.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
                logger.error(f"Failed to open resource: {resource_path}")
                return self._read_file_fallback(resource_path, encoding)
            
            # Read bytes and decode
            data = qfile.readAll().data()
            qfile.close()
            
            return data.decode(encoding)
            
        except Exception as e:
            logger.error(f"Error reading text file {resource_path}: {e}")
            return self._read_file_fallback(resource_path, encoding)
    
    def _read_file_fallback(self, resource_path: str, encoding: str = 'utf-8') -> str:
        """
        Fallback method to read file from filesystem
        Converts resource path (:/data/file.csv) to actual file path
        """
        try:
            # Remove :/ prefix and construct actual path
            if resource_path.startswith(":/"):
                rel_path = resource_path[2:]
            else:
                rel_path = resource_path
            
            # Try multiple possible locations
            possible_paths = [
                Path(__file__).parent.parent / "assets" / rel_path,
                Path(__file__).parent.parent.parent / rel_path,
                Path(rel_path)
            ]
            
            for file_path in possible_paths:
                if file_path.exists():
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    logger.info(f"Loaded file from fallback: {file_path}")
                    return content
            
            logger.error(f"Could not find file in any fallback location: {resource_path}")
            return ""
            
        except Exception as e:
            logger.error(f"Fallback read failed for {resource_path}: {e}")
            return ""
    
    def read_csv_as_dict(self, resource_path: str, encoding: str = 'utf-8') -> dict:
        """
        Read CSV file from Qt resource and convert to dictionary
        
        Args:
            resource_path: Qt resource path to CSV file
            encoding: Text encoding
        
        Returns:
            Dictionary with first column as keys
        """
        try:
            content = self.read_text_file(resource_path, encoding)
            if not content:
                logger.error(f"Empty content for CSV: {resource_path}")
                return {}
            
            # Parse CSV
            csv_reader = csv.DictReader(StringIO(content))
            result = {}
            
            for row in csv_reader:
                if not row:
                    continue
                # First column value becomes the key
                key = list(row.values())[0] if row else None
                if key:
                    result[key] = row
            
            logger.info(f"Successfully parsed CSV with {len(result)} rows")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing CSV {resource_path}: {e}")
            return {}


# Global resource loader instance
_qt_resource_loader = None

def get_qt_resource_loader() -> QtResourceLoader:
    """Get Qt resource loader singleton instance"""
    global _qt_resource_loader
    if _qt_resource_loader is None:
        _qt_resource_loader = QtResourceLoader()
    return _qt_resource_loader

# Convenience functions
def load_pixmap(resource_path: str) -> QPixmap:
    """Load QPixmap from Qt resource"""
    return get_qt_resource_loader().get_pixmap(resource_path)

def load_icon(resource_path: str) -> QIcon:
    """Load QIcon from Qt resource"""
    return get_qt_resource_loader().get_icon(resource_path)

def load_text(resource_path: str, encoding: str = 'utf-8') -> str:
    """Load text file from Qt resource"""
    return get_qt_resource_loader().read_text_file(resource_path, encoding)
