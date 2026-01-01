"""
Qt 리소스 로더 모듈
.qrc로 컴파일된 리소스에서 이미지와 CSV 로드
"""

from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import QByteArray
import logging

# 리소스 모듈 import (compile_resources.py 실행 후 생성됨)
try:
    import resources_rc
    RESOURCES_AVAILABLE = True
except ImportError:
    RESOURCES_AVAILABLE = False
    print("Warning: resources_rc.py not found. Run 'python compile_resources.py' first.")

logger = logging.getLogger('Croquis')

class QtResourceLoader:
    """Qt 리소스 로더 클래스"""
    
    def __init__(self):
        if not RESOURCES_AVAILABLE:
            logger.warning("Qt resources not available. Please compile resources.qrc")
    
    def get_pixmap(self, resource_path: str) -> QPixmap:
        """
        Qt 리소스에서 QPixmap 가져오기
        
        Args:
            resource_path: Qt 리소스 경로 (예: ":/buttons/정지.png")
        
        Returns:
            QPixmap 객체
        """
        if not RESOURCES_AVAILABLE:
            logger.warning(f"Resources not available for: {resource_path}")
            return QPixmap()
        
        try:
            # resources_rc에서 데이터 가져오기
            data = resources_rc.get_resource_data(resource_path)
            if not data:
                logger.warning(f"Resource not found: {resource_path}")
                return QPixmap()
            
            # QByteArray를 통해 QPixmap 생성
            pixmap = QPixmap()
            pixmap.loadFromData(QByteArray(data))
            
            if pixmap.isNull():
                logger.warning(f"Failed to load pixmap: {resource_path}")
            
            return pixmap
            
        except Exception as e:
            logger.error(f"Error loading pixmap {resource_path}: {e}")
            return QPixmap()
    
    def get_icon(self, resource_path: str) -> QIcon:
        """
        Qt 리소스에서 QIcon 가져오기
        
        Args:
            resource_path: Qt 리소스 경로 (예: ":/buttons/정지.png")
        
        Returns:
            QIcon 객체
        """
        pixmap = self.get_pixmap(resource_path)
        return QIcon(pixmap)
    
    def read_text_file(self, resource_path: str, encoding: str = 'utf-8') -> str:
        """
        Qt 리소스에서 텍스트 파일 읽기
        
        Args:
            resource_path: Qt 리소스 경로 (예: ":/data/translations.csv")
            encoding: 텍스트 인코딩 (기본값: utf-8)
        
        Returns:
            파일 내용 문자열
        """
        if not RESOURCES_AVAILABLE:
            logger.warning(f"Resources not available for: {resource_path}")
            return ""
        
        try:
            # resources_rc에서 데이터 가져오기
            data = resources_rc.get_resource_data(resource_path)
            if not data:
                logger.error(f"Resource not found: {resource_path}")
                return ""
            
            return data.decode(encoding)
            
        except Exception as e:
            logger.error(f"Failed to read resource file {resource_path}: {e}")
            return ""
    
    def resource_exists(self, resource_path: str) -> bool:
        """
        Qt 리소스 존재 여부 확인
        
        Args:
            resource_path: Qt 리소스 경로
        
        Returns:
            존재 여부 (True/False)
        """
        if not RESOURCES_AVAILABLE:
            return False
        
        try:
            return resources_rc.resource_exists(resource_path)
        except:
            return False

# 전역 리소스 로더 인스턴스
_qt_resource_loader = None

def get_qt_resource_loader() -> QtResourceLoader:
    """Qt 리소스 로더 싱글톤 인스턴스 가져오기"""
    global _qt_resource_loader
    if _qt_resource_loader is None:
        _qt_resource_loader = QtResourceLoader()
    return _qt_resource_loader

# 편의 함수들
def load_pixmap(resource_path: str) -> QPixmap:
    """Qt 리소스에서 QPixmap 로드"""
    return get_qt_resource_loader().get_pixmap(resource_path)

def load_icon(resource_path: str) -> QIcon:
    """Qt 리소스에서 QIcon 로드"""
    return get_qt_resource_loader().get_icon(resource_path)

def load_text(resource_path: str, encoding: str = 'utf-8') -> str:
    """Qt 리소스에서 텍스트 파일 로드"""
    return get_qt_resource_loader().read_text_file(resource_path, encoding)
