# Croquis - Figure Drawing Practice Application

**Version 1.0.1**

A desktop application for systematic figure drawing practice with timer functionality, deck management, and practice tracking.

## Features

- **Deck Management**: Organize image folders as practice decks with filtering and shuffle options
- **Timer System**: Customizable duration per image with automatic transitions
- **Heatmap Visualization**: GitHub-style contribution graph for tracking daily practice
- **Screenshot Capture**: Save your work directly within the app
- **Multi-language Support**: Korean, English, and Japanese
- **Alarm Notifications**: Schedule practice reminders with Windows integration
- **Practice History**: Automatic recording and statistics of practice sessions
- **Security**: Machine ID-based encryption for user-specific data storage

## Technology Stack

- **Framework**: PyQt6
- **Encryption**: cryptography (Fernet with SHA-256 + machine ID-based key derivation)
- **Notifications**: win11toast, plyer
- **Build**: PyInstaller
- **Python**: 3.10+

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Windows 10/11 (for notification support)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd Croquis2

# Install dependencies
pip install -r requirements.txt
```

### Running

```bash
python main.py
```

### Building Executable

```bash
# Build with PyInstaller
pyinstaller Croquis.spec

# Output: dist/Croquis/Croquis.exe
```

## Project Structure

```
Croquis2/
├── src/
│   ├── core/
│   │   ├── key_manager.py        # Encryption key management
│   │   ├── alarm_service.py      # Alarm notification service
│   │   └── models.py             # Data models
│   ├── gui/
│   │   ├── image_viewer_window.py  # Image viewer
│   │   └── widgets.py            # Reusable widgets (Heatmap, Screenshot)
│   ├── utils/
│   │   ├── language_manager.py   # Multi-language support
│   │   ├── log_manager.py        # Logging system
│   │   ├── qt_resource_loader.py # Qt resource loader
│   │   └── helpers.py            # Helper functions
│   └── assets/
│       ├── btn/                  # Button images
│       ├── icon.ico              # Application icon
│       └── resources_rc.py       # Compiled Qt resources
├── scripts/
│   ├── compile.py                # Build script
│   └── compile_resources.py      # Qt resource compiler
├── main.py                       # Application entry point
├── requirements.txt              # Python dependencies
├── translations.csv              # Translation data (ko/en/ja)
└── Croquis.spec                 # PyInstaller configuration
```

## Security Features

- **Dynamic Encryption Key**: Generated from Machine UUID + OS username + application salt
- **Data Encryption**: All deck information and settings encrypted at rest using Fernet (AES-128)
- **Cross-Platform Key Generation**: 
  - Windows: Registry MachineGuid
  - macOS: IOPlatformUUID
  - Linux: /etc/machine-id
- **User Isolation**: Each user can only access their own encrypted data
- **Secure Key Derivation**: SHA-256 hashing with zlib compression

## Usage

### Creating a Deck

1. Click **Edit Deck** button
2. Click **Select Folder** to add image directory
3. Optionally add individual images
4. Configure shuffle, tag filters
5. Save deck

### Starting Practice

1. Select deck from dropdown
2. Set timer duration (seconds)
3. Optionally enable Study Mode (infinite timer)
4. Click **Start**

### Keyboard Shortcuts (Viewer)

- `Space`: Next image
- `S` or `Enter`: Take screenshot
- `Esc`: Close viewer

### Setting Alarms

1. Click **Alarm** button
2. Set time and select days
3. Enable alarm
4. App will notify at scheduled times

## Data Storage

- **Deck Files**: Encrypted `.deck` files in `deck/` folder
- **History**: Practice records in `dat/croquis_history.dat`
- **Settings**: User preferences in `dat/settings.dat`
- **Screenshots**: Drawing pairs in `croquis_pairs/` folder
- **Logs**: Daily logs in `logs/` folder

## Development

### Modular Architecture

The codebase follows a clean modular structure:

- **Core**: Business logic (encryption, alarms, models)
- **GUI**: User interface components (windows, widgets)
- **Utils**: Shared utilities (logging, translations, helpers)

### Running from Source

```bash
# Install dependencies
pip install -r requirements.txt

# Run application
python main.py
```

### Building

```bash
# Build executable
pyinstaller Croquis.spec

# Output: dist/Croquis/
```

## Troubleshooting

### Icon Not Showing
- Verify `src/assets/icon.ico` exists
- Rebuild: `pyinstaller Croquis.spec`

### Translations Not Loading
- Ensure `translations.csv` is in project root
- Check CSV format: `key,ko,en,ja` header

### Alarms Not Working
- Run as administrator for startup registration
- Check Windows notification permissions in Settings

### Heatmap Not Visible
- Ensure `dat/croquis_history.dat` exists and is readable
- Check file permissions

## System Requirements

- **OS**: Windows 10/11
- **Python**: 3.10+
- **RAM**: 512MB minimum
- **Disk Space**: 200MB (including dependencies)

## License

This project is provided as-is for educational and personal use.

## Changelog

### v1.0.1 (Current)
- Fixed heatmap visibility and sizing
- Improved center alignment for heatmap widget
- Enhanced UI layout for better component visibility
- Code cleanup and optimization

### v1.0.0
- Refactored monolithic codebase into modular architecture
- Enhanced security with machine ID-based encryption
- Added heatmap visualization for practice tracking
- Implemented screenshot capture functionality
- Multi-language support (Korean/English/Japanese)
- Improved alarm service with Windows integration

## Contributing

Contributions are welcome! Please submit pull requests or open issues for bugs and feature requests.

