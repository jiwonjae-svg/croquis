# 📝 Croquis Release Notes

## Version 1.0.2 (February 5, 2026)

### ✨ New Features
- **Shortcut Key Configuration System**
  - Customizable keyboard shortcuts for all croquis actions
  - New settings dialog accessible from main window (`단축키 설정` button)
  - Configurable actions: Next Image, Previous Image, Toggle Pause, Stop Croquis
  - Default keys: Space (next), Left Arrow (previous), P (pause), Escape (stop)
  - Real-time key capture with visual feedback
  - Duplicate key detection with warning messages
  - Reset to defaults functionality
  - Full multi-language support (Korean, English, Japanese)
  - Settings persist across sessions via encrypted storage

### 🐛 Bug Fixes
- **Pixmap Loading Fix**
  - Fixed 4 pixmap loading warnings (`이전.png`, `일시 정지.png`, `다음.png`, `정지.png`)
  - Root cause: `QPixmap()` constructor cannot resolve custom `:` prefix paths without `QResource.registerResource()`
  - Solution: Decode base64 data directly from compiled resource dictionary using `QPixmap.loadFromData()`
  - Added filesystem fallback for development convenience

- **QSS Stylesheet Warning Fix**
  - Fixed stylesheet file path resolution (now correctly points to `src/assets/style.qss`)
  - Downgraded missing stylesheet log from WARNING to DEBUG (app uses inline styles)

- **Build Script Fix**
  - Fixed executable path detection in `scripts/build.py` for PyInstaller onefile mode
  - Now checks `dist/Croquis.exe` (onefile) before `dist/Croquis/Croquis.exe` (onedir)

### 🔧 Technical Improvements
- Added `_KEY_NAME_TO_QT` mapping for string-to-Qt.Key conversion
- Added `_build_shortcut_map()` for dynamic shortcut resolution
- Added `keyPressEvent()` handler to `ImageViewerWindow`
- New `ShortcutKeyEdit` widget with key capture support
- New `ShortcutConfigDialog` with per-action key binding
- Extended `CroquisSettings` with `shortcuts` field (backward compatible)
- Added 8 new translation keys to `translations.csv`
- Recompiled `resources_rc.py` with updated translations
- Window height increased from 750px to 800px to accommodate new button

### 📦 Distribution
- Single-file executable: 46.87 MB
- All existing user data fully compatible (no migration needed)

### Upgrade Notes
- **Data Compatibility**: Settings from 1.0.1 are fully compatible; shortcuts will auto-initialize to defaults
- **No Breaking Changes**: All existing features preserved

---

## Version 1.0.1 (February 4, 2026)

### 🎨 Visual Improvements
- **New Application Icon**: Refreshed icon design for better visual appeal
  - Applied to executable, window dialogs, and taskbar
  - Modern and professional appearance

- **Heatmap Widget Enhancements**
  - Fixed visibility issues with proper sizing (10px cells, 1px gap)
  - Improved center alignment within container
  - Enhanced color scheme for better contrast (darker gray for empty cells)
  - Added visible borders to cells for better definition
  - Optimized dimensions: 600x120px widget, 155px container height
  - Legend now properly visible at bottom

### 📚 Documentation
- **Comprehensive README Rewrite**
  - Modern documentation style with badges and emoji sections
  - Clear navigation with quick links
  - Detailed feature descriptions and usage guides
  - Architecture diagrams and component explanations
  - Enhanced troubleshooting section
  - Added roadmap and contribution guidelines
  - Multi-language support documentation

### 🔧 Technical Improvements
- **Code Cleanup**
  - Removed duplicate imports
  - Added type hints for better IDE support (`# type: ignore[import-not-found]`)
  - Improved method organization (`_update_heatmap_title()`)
  - Better separation of concerns

- **Build System**
  - Added automated build script (`scripts/build.py`)
  - Icon verification before build
  - Clean build directory management

### 🐛 Bug Fixes
- Fixed heatmap not displaying after main.py refactoring
- Resolved heatmap title update issues
- Fixed cell rendering with proper paintEvent implementation
- Corrected language change handling for heatmap labels

### 📦 Distribution
- PyInstaller executable with embedded icon
- Optimized executable size with exclusions
- Single-file deployment (48.6MB)

---

## Version 1.0.0 (January 2026)

### 🎯 Major Refactoring
- **Modular Architecture**
  - Split monolithic 5,144-line `main.py` into organized modules
  - Created `src/core/`, `src/gui/`, `src/utils/` structure
  - Reduced main file to 3,880 lines (~1,264 lines removed)

- **New Modules**
  - `core/models.py`: Data models (CroquisSettings, UIConstants)
  - `core/alarm_service.py`: Alarm notification system (173 lines)
  - `gui/widgets.py`: Reusable widgets - HeatmapWidget, ScreenshotOverlay (333 lines)
  - `gui/image_viewer_window.py`: Image viewer window (542 lines)
  - `utils/helpers.py`: Helper functions (45 lines)

### 🔒 Security Enhancements
- **Production-Grade Encryption**
  - Machine ID-based key derivation (SHA-256)
  - Cross-platform hardware UUID extraction
  - Fernet (AES-128) encryption for all user data
  - User isolation with OS username integration

### ✨ New Features
- **Heatmap Visualization**
  - GitHub-style contribution graph
  - 365-day practice tracking
  - Color-coded intensity (0 to 10+ sessions)
  - Hover tooltips with date and count
  - Persistent encrypted storage

- **Screenshot Capture**
  - Save drawings alongside reference images
  - Keyboard shortcut: S or Enter
  - Organized storage in `croquis_pairs/`

- **Multi-language Support**
  - Korean, English, and Japanese
  - CSV-based translation system (176+ keys)
  - Runtime language switching

- **Alarm System**
  - Windows 10/11 native notifications
  - Schedule reminders for practice sessions
  - Configurable days and times

### 🎨 UI/UX Improvements
- Consistent icon usage across all windows
- Dark mode support
- Customizable timer position and font size
- Study mode for unlimited viewing time
- Weighted shuffle algorithm

### 🛠️ Technical Stack
- **Framework**: PyQt6 (upgraded from PyQt5)
- **Encryption**: cryptography (Fernet)
- **Notifications**: win11toast, plyer
- **Build**: PyInstaller with optimized configuration

### 📁 Project Structure
```
Croquis/
├── main.py (entry point)
├── src/
│   ├── core/ (business logic)
│   ├── gui/ (UI components)
│   ├── utils/ (utilities)
│   └── assets/ (resources)
├── scripts/ (build tools)
├── deck/ (user decks)
├── dat/ (encrypted data)
└── logs/ (application logs)
```

### 🐛 Bug Fixes
- Fixed translation loading path issues
- Resolved 49 Pylance errors (missing imports)
- Corrected f-string syntax errors
- Fixed nested quote issues in translations

---

## System Requirements

- **Operating System**: Windows 10/11
- **Python**: 3.10 or higher (for source)
- **RAM**: 512MB minimum
- **Disk Space**: 200MB (including dependencies)

## Installation

### Executable (Recommended)
1. Download `Croquis.exe` from [Releases](https://github.com/jiwonjae-svg/Croquis/releases)
2. Run the executable - no installation needed!

### From Source
```bash
git clone https://github.com/jiwonjae-svg/Croquis.git
cd Croquis
pip install -r requirements.txt
python main.py
```

## Upgrade Notes

### Upgrading from 1.0.0 to 1.0.1
- **Data Compatibility**: All user data (decks, settings, history) is fully compatible
- **Configuration**: No migration needed
- **Recommended**: Backup `dat/` and `deck/` folders before upgrading

### Breaking Changes
- None. All features from 1.0.0 are preserved.

## Known Issues

- System tray icon may take 5-10 seconds to appear on Windows 11
- Heatmap tooltip may be clipped if window is too small (minimum 800x600 recommended)
- Alarm notifications require administrator rights for startup service registration

## Support

- **Issues**: [GitHub Issues](https://github.com/jiwonjae-svg/Croquis/issues)
- **Discussions**: [GitHub Discussions](https://github.com/jiwonjae-svg/Croquis/discussions)
- **Documentation**: [README.md](README.md)

---

**Thank you for using Croquis!** 🎨

We hope this application helps you improve your figure drawing skills through consistent practice.
