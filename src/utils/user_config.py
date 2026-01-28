"""
User Configuration Management for CIVET
========================================

Provides a unified, cross-platform approach to managing user configuration
and data directories. All user-specific data is stored in the OS-appropriate
application data directory:

    Windows: %APPDATA%/CIVET/
    macOS:   ~/Library/Application Support/CIVET/
    Linux:   ~/.config/CIVET/

Directory structure:
    CIVET/
    ├── settings.json           # Editor and application settings
    ├── registered_prefixes.json  # User-customized CIF prefixes
    ├── dictionaries/           # User-downloaded CIF dictionaries
    └── field_rules/            # User-created field rules files
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Default settings for the application
DEFAULT_SETTINGS = {
    "editor": {
        "font_family": "Consolas",
        "font_size": 10,
        "line_numbers_enabled": True,
        "syntax_highlighting_enabled": True,
        "show_ruler": True
    },
    "general": {
        "last_directory": "",
        "recent_files": []
    }
}

# Module-level cache for settings
_settings_cache: Optional[Dict] = None


def get_user_config_directory() -> Path:
    """
    Get the CIVET user configuration directory path.
    
    This is the root directory for all user-specific data.
    
    Returns:
        Path to the configuration directory:
        - Windows: %APPDATA%/CIVET
        - macOS: ~/Library/Application Support/CIVET
        - Linux: ~/.config/CIVET
    """
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        return Path(base) / 'CIVET'
    elif sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'CIVET'
    else:
        # Linux and other Unix-like systems
        xdg_config = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
        return Path(xdg_config) / 'CIVET'


def ensure_user_config_directory() -> Path:
    """
    Ensure the CIVET configuration directory exists.
    
    Returns:
        Path to the configuration directory.
    """
    config_dir = get_user_config_directory()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


# --- Subdirectory accessors ---

def get_user_dictionaries_directory() -> Path:
    """Get path to user dictionaries directory."""
    return get_user_config_directory() / 'dictionaries'


def ensure_user_dictionaries_directory() -> Path:
    """Ensure user dictionaries directory exists."""
    path = get_user_dictionaries_directory()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_user_field_rules_directory() -> Path:
    """Get path to user field rules directory."""
    return get_user_config_directory() / 'field_rules'


def ensure_user_field_rules_directory() -> Path:
    """Ensure user field rules directory exists."""
    path = get_user_field_rules_directory()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_user_prefixes_path() -> Path:
    """Get path to user's custom registered_prefixes.json file."""
    return get_user_config_directory() / 'registered_prefixes.json'


def get_settings_path() -> Path:
    """Get path to user settings file."""
    return get_user_config_directory() / 'settings.json'


# --- Settings management ---

def load_settings() -> Dict[str, Any]:
    """
    Load user settings from the settings file.
    
    Returns default settings if file doesn't exist or is invalid.
    Settings are cached after first load.
    
    Returns:
        Dictionary of settings.
    """
    global _settings_cache
    
    if _settings_cache is not None:
        return _settings_cache
    
    settings_path = get_settings_path()
    settings = DEFAULT_SETTINGS.copy()
    
    try:
        if settings_path.exists():
            with open(settings_path, 'r', encoding='utf-8') as f:
                saved_settings = json.load(f)
            # Deep merge saved settings with defaults
            settings = _deep_merge(DEFAULT_SETTINGS, saved_settings)
    except Exception as e:
        print(f"Warning: Could not load settings: {e}")
    
    _settings_cache = settings
    return settings


def save_settings(settings: Dict[str, Any]) -> bool:
    """
    Save settings to the user settings file.
    
    Args:
        settings: Dictionary of settings to save.
        
    Returns:
        True if save succeeded, False otherwise.
    """
    global _settings_cache
    
    try:
        ensure_user_config_directory()
        settings_path = get_settings_path()
        
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        
        _settings_cache = settings
        return True
    except Exception as e:
        print(f"Warning: Could not save settings: {e}")
        return False


def get_setting(key_path: str, default: Any = None) -> Any:
    """
    Get a specific setting value using dot notation.
    
    Args:
        key_path: Dot-separated path to setting (e.g., "editor.font_size")
        default: Default value if setting not found.
        
    Returns:
        The setting value or default.
    """
    settings = load_settings()
    keys = key_path.split('.')
    
    value = settings
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    
    return value


def set_setting(key_path: str, value: Any) -> bool:
    """
    Set a specific setting value using dot notation.
    
    Args:
        key_path: Dot-separated path to setting (e.g., "editor.font_size")
        value: Value to set.
        
    Returns:
        True if save succeeded, False otherwise.
    """
    settings = load_settings()
    keys = key_path.split('.')
    
    # Navigate to parent and set value
    current = settings
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    
    current[keys[-1]] = value
    return save_settings(settings)


def clear_settings_cache():
    """Clear the settings cache to force reload on next access."""
    global _settings_cache
    _settings_cache = None


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """
    Deep merge two dictionaries.
    
    Override values take precedence over base values.
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


# --- Utility functions ---

def get_bundled_resource_path(relative_path: str) -> Path:
    """
    Get the path to a bundled resource file.
    
    Handles both development and PyInstaller bundled scenarios.
    
    Args:
        relative_path: Path relative to the project/bundle root.
        
    Returns:
        Absolute path to the resource.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        # Development environment - go up from src/utils to project root
        base_path = Path(__file__).parent.parent.parent
    
    return base_path / relative_path


def open_user_config_directory() -> bool:
    """
    Open the user config directory in the system file explorer.
    
    Returns:
        True if successful, False otherwise.
    """
    import subprocess
    
    try:
        config_dir = ensure_user_config_directory()
        
        if sys.platform == 'win32':
            os.startfile(str(config_dir))
        elif sys.platform == 'darwin':
            subprocess.run(['open', str(config_dir)], check=True)
        else:
            subprocess.run(['xdg-open', str(config_dir)], check=True)
        
        return True
    except Exception as e:
        print(f"Error opening config directory: {e}")
        return False


def get_config_info() -> Dict[str, str]:
    """
    Get information about the current configuration setup.
    
    Returns:
        Dictionary with paths and status information.
    """
    config_dir = get_user_config_directory()
    
    return {
        'config_directory': str(config_dir),
        'settings_file': str(get_settings_path()),
        'dictionaries_directory': str(get_user_dictionaries_directory()),
        'field_rules_directory': str(get_user_field_rules_directory()),
        'prefixes_file': str(get_user_prefixes_path()),
        'config_exists': config_dir.exists(),
        'settings_exists': get_settings_path().exists(),
    }
