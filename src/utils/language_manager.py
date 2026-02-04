"""
Language Manager Module
Loads translations from CSV file and provides them as a dictionary.
Priority: translations.csv file -> Qt resources -> minimal fallback
"""

import sys
import csv
from pathlib import Path
from io import StringIO

def get_base_path():
    """Get base path for resources. Handles PyInstaller bundled executables."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - use executable directory
        return Path(sys.executable).parent
    else:
        # Running as script - go up to project root (2 levels up from src/utils/)
        return Path(__file__).parent.parent.parent

def load_translations_from_csv(csv_path: str = None) -> dict:
    """Load translations from CSV file into a nested dictionary."""
    if csv_path is None:
        csv_path = get_base_path() / "translations.csv"
    else:
        csv_path = Path(csv_path)
    
    translations = {}
    
    # 1. Try loading from file first (for development/editing)
    if csv_path.exists():
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                # Get language columns (all columns except 'key')
                languages = [col for col in reader.fieldnames if col != 'key']
                
                # Initialize language dictionaries
                for lang in languages:
                    translations[lang] = {}
                
                # Read each row and populate translations
                for row in reader:
                    key = row['key']
                    for lang in languages:
                        translations[lang][key] = row[lang]
            
            # Successfully loaded from file
            return translations
            
        except Exception as e:
            # Error loading from file, will try Qt resources
            pass
    
    # 2. Try loading from Qt resources (compiled from .qrc)
    try:
        from qt_resource_loader import load_text
        csv_content = load_text(":/data/translations.csv")
        
        if csv_content:
            reader = csv.DictReader(StringIO(csv_content))
            languages = [col for col in reader.fieldnames if col != 'key']
            
            # Initialize language dictionaries
            for lang in languages:
                translations[lang] = {}
            
            # Read each row and populate translations
            for row in reader:
                key = row['key']
                for lang in languages:
                    translations[lang][key] = row[lang]
            
            # Successfully loaded from Qt resources
            return translations
    
    except Exception as e:
        # Error loading Qt resources
        pass
    
    # 3. Return minimal translations as last resort
    return {
        "ko": {"error": "번역 파일을 찾을 수 없습니다."},
        "en": {"error": "Translation file not found."},
        "ja": {"error": "翻訳ファイルが見つかりません。"}
    }

# Load translations on module import
TRANSLATIONS = load_translations_from_csv()
