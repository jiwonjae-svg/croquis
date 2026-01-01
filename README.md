# Croquis Practice App

A PyQt6 desktop app for timed croquis practice. Manage image decks, run timed drawing sessions, review history with overlays, and keep memos. Resources are bundled and encrypted for portability.

## Features
- Deck management: add/import images, rename, tag, delete, and edit decks.
- Timed croquis sessions: play/pause/next/previous with configurable timer position and font size.
- History viewer: side-by-side original and croquis thumbnails with duration overlays and memo support.
- Deck editor overlays: thumbnails show drawing duration, date labels, and memo tooltips.
- Memos: per-croquis memo dialog for notes.
- Localization: Korean, English, Japanese (extensible via translations dictionary).
- **Qt Resource System**: embedded button images and translations using Qt's `.qrc` format.
- Logging: centralized English log messages with rotation per day.

## Qt Resource System

This application uses Qt Resource System (.qrc) for managing button images and translation files.

### Compiling Resources

When you modify resources (button images or translations), recompile them:

```bash
python compile_resources.py
```

This reads `resources.qrc` and generates `resources_rc.py` module.

### Resource Usage

```python
from qt_resource_loader import QtResourceLoader

loader = QtResourceLoader()

# Load images
pixmap = loader.get_pixmap(":/buttons/정지.png")
icon = loader.get_icon(":/buttons/재생.png")

# Read CSV file
csv_data = loader.read_text_file(":/data/translations.csv")

# Check resource existence
if loader.resource_exists(":/buttons/정지.png"):
    print("Resource exists!")
```

### Resource Structure

- `:/buttons/` - Button images (Stop, Play, Pause, Previous, Next)
- `:/data/` - Translation CSV file (translations.csv)

## Installation
1. Python 3.11+ recommended.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\\Scripts\\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   (If `requirements.txt` is missing, install PyQt6 and cryptography: `pip install PyQt6 cryptography`.)

## Running
```bash
python main.py
```

## Decks and Data
- Croquis pairs are stored under `croquis_pairs/` with encrypted `.croq` files.
- Deck files use the `.crdk` extension and live alongside your images.
- Logs are written to `logs/croquis_YYYYMMDD.log`.

## History and Overlays
- History thumbnails show original (left) and croquis (right) with duration overlays.
- Deck editor thumbnails display per-croquis duration at bottom right plus date labels.

## Localization
Strings are served via the `TRANSLATIONS` dictionary in `main.py`. Add new keys there for additional locales. Logging strings are centralized in `LOG_MESSAGES`.

## Notes on Alarm Guide
`ALARM_SERVICE_GUIDE.md` is a design note. Alarm functions are not fully implemented in `main.py`; implement `load_alarms` and `decrypt_data` there before using the guide.

## Troubleshooting
- If durations do not show on thumbnails, ensure the croquis data include `croquis_time` and reload the deck.
- For UI language issues, confirm the `TRANSLATIONS` entries cover all keys used in `tr()` calls.
- If button icons do not appear, run `python compile_resources.py` to rebuild Qt resources.

## PyInstaller Deployment

When building with PyInstaller, the following files are NOT needed in the distribution:
- `resources.qrc` (source definition file)
- `compile_resources.py` (build tool)
- Button image files in `btn/` folder (embedded in `resources_rc.py`)
- `translations.csv` (embedded in `resources_rc.py`)

The `resources_rc.py` module contains all embedded resources and will be included automatically by PyInstaller.

## License
Internal use only. Add your license details here if you plan to distribute.
