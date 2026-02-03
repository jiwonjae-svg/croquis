"""
Core Module
Contains business logic: encryption, key management, data processing, state management
"""

from .key_manager import KeyManager, get_key_manager, encrypt_data, decrypt_data
from .models import CroquisSettings, CroquisRecord
from .alarm import check_and_trigger_alarms
from .app_state import AppState, get_app_state

__all__ = [
    'KeyManager',
    'get_key_manager',
    'encrypt_data',
    'decrypt_data',
    'CroquisSettings',
    'CroquisRecord',
    'check_and_trigger_alarms',
    'AppState',
    'get_app_state',
]

