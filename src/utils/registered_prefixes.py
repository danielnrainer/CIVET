"""
Registered CIF Prefixes Module for CIVET.

This module provides access to IUCr registered prefixes for CIF data names,
loaded from external JSON files for easy customization. Registered prefixes
allow organizations to define their own CIF data names without conflicting
with official dictionary definitions.

The module loads prefixes from:
1. User config directory (if exists): %APPDATA%/CIVET/registered_prefixes.json (Windows)
   or ~/.config/CIVET/registered_prefixes.json (Linux/macOS)
2. Bundled default file (fallback): <app_dir>/registered_prefixes.json

Reference: https://www.iucr.org/resources/cif/registries/prefix-registry
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional, Set, Dict, Tuple


# Module-level cache for loaded prefix data
_prefix_data: Optional[Dict] = None
_data_source: Optional[str] = None


def get_config_directory() -> Path:
    """
    Get the CIVET configuration directory path.
    
    On Windows: %APPDATA%/CIVET
    On macOS: ~/Library/Application Support/CIVET
    On Linux: ~/.config/CIVET
    
    Returns:
        Path to the configuration directory.
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


def ensure_config_directory() -> Path:
    """
    Ensure the CIVET configuration directory exists.
    
    Returns:
        Path to the configuration directory.
    """
    config_dir = get_config_directory()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_bundled_prefixes_path() -> Path:
    """
    Get the path to the bundled registered_prefixes.json file.
    
    Handles both development and PyInstaller bundled scenarios.
    
    Returns:
        Path to the bundled JSON file.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        # Running in development - go up from src/utils to project root
        base_path = Path(__file__).parent.parent.parent
    
    return base_path / 'dictionaries' / 'registered_prefixes.json'


def get_user_prefixes_path() -> Path:
    """
    Get the path to the user's custom registered_prefixes.json file.
    
    Returns:
        Path to the user config JSON file (may not exist).
    """
    return get_config_directory() / 'registered_prefixes.json'


def _load_prefix_data() -> Tuple[Dict, str]:
    """
    Load prefix data from JSON file.
    
    Tries user config first, falls back to bundled file.
    
    Returns:
        Tuple of (prefix_data dict, source path string)
    """
    global _prefix_data, _data_source
    
    if _prefix_data is not None:
        return _prefix_data, _data_source
    
    user_path = get_user_prefixes_path()
    bundled_path = get_bundled_prefixes_path()
    
    # Try user config first
    if user_path.exists():
        try:
            with open(user_path, 'r', encoding='utf-8') as f:
                _prefix_data = json.load(f)
                _data_source = str(user_path)
                return _prefix_data, _data_source
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load user prefix file {user_path}: {e}")
            print("Falling back to bundled prefixes.")
    
    # Fall back to bundled file
    if bundled_path.exists():
        try:
            with open(bundled_path, 'r', encoding='utf-8') as f:
                _prefix_data = json.load(f)
                _data_source = str(bundled_path)
                return _prefix_data, _data_source
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error: Could not load bundled prefix file {bundled_path}: {e}")
    
    # Ultimate fallback - return empty data
    _prefix_data = {"prefixes": {}, "category_dictionary_suggestions": {}}
    _data_source = "none (using empty defaults)"
    return _prefix_data, _data_source


def reload_prefix_data() -> str:
    """
    Force reload of prefix data from files.
    
    Useful after user edits their custom prefix file.
    
    Returns:
        The source path from which data was loaded.
    """
    global _prefix_data, _data_source
    _prefix_data = None
    _data_source = None
    _, source = _load_prefix_data()
    return source


def get_prefix_data_source() -> str:
    """
    Get the path from which prefix data was loaded.
    
    Returns:
        Path string to the loaded JSON file, or description if using defaults.
    """
    _load_prefix_data()
    return _data_source


def get_registered_prefixes() -> Set[str]:
    """
    Get the set of all registered prefix names.
    
    Returns:
        Set of registered prefix strings.
    """
    data, _ = _load_prefix_data()
    return set(data.get("prefixes", {}).keys())


def get_registered_prefixes_lower() -> Set[str]:
    """
    Get the set of registered prefixes in lowercase for case-insensitive matching.
    
    Returns:
        Set of lowercase registered prefix strings.
    """
    return {p.lower() for p in get_registered_prefixes()}


def get_prefix_info(prefix: str) -> Optional[str]:
    """
    Get the description/info for a registered prefix.
    
    Args:
        prefix: The prefix to look up (case-insensitive).
        
    Returns:
        The description string if the prefix is registered, None otherwise.
        
    Examples:
        >>> get_prefix_info('shelx')
        'SHELX crystallographic software suite'
        >>> get_prefix_info('CCDC')
        'Cambridge Crystallographic Data Centre'
    """
    if not prefix:
        return None
    
    data, _ = _load_prefix_data()
    prefixes = data.get("prefixes", {})
    
    # Try exact match first
    if prefix in prefixes:
        return prefixes[prefix].get("description")
    
    # Try case-insensitive match
    prefix_lower = prefix.lower()
    for registered, info in prefixes.items():
        if registered.lower() == prefix_lower:
            return info.get("description")
    
    return None


def is_registered_prefix(field_name: str) -> bool:
    """
    Check if a CIF field name uses a registered prefix.
    
    Registered prefixes appear after the leading underscore and before
    the next underscore in a CIF data name. For example, in
    '_shelx_res_file', the prefix is 'shelx'.
    
    Args:
        field_name: The CIF field name to check (with or without leading underscore).
        
    Returns:
        True if the field uses a registered prefix, False otherwise.
        
    Examples:
        >>> is_registered_prefix('_shelx_res_file')
        True
        >>> is_registered_prefix('_ccdc_geom_bond_type')
        True
        >>> is_registered_prefix('_cell_length_a')
        False
    """
    prefix = get_prefix_from_field(field_name)
    if prefix is None:
        return False
    return prefix.lower() in get_registered_prefixes_lower()


def get_prefix_from_field(field_name: str) -> Optional[str]:
    """
    Extract the prefix portion from a CIF field name.
    
    The prefix is the first segment after the leading underscore,
    before the next underscore. This function extracts potential
    prefixes but does not validate if they are registered.
    
    Args:
        field_name: The CIF field name (with or without leading underscore).
        
    Returns:
        The prefix string if found, or None if the field has no prefix
        structure (e.g., single-segment names).
        
    Examples:
        >>> get_prefix_from_field('_shelx_res_file')
        'shelx'
        >>> get_prefix_from_field('_ccdc_geom_bond_type')
        'ccdc'
        >>> get_prefix_from_field('_cell_length_a')
        'cell'
        >>> get_prefix_from_field('_diffrn.ambient_temperature')
        'diffrn'
    """
    if not field_name:
        return None
    
    # Remove leading underscore if present
    name = field_name.lstrip('_')
    
    if not name:
        return None
    
    # Handle modern dot notation (category.attribute)
    if '.' in name:
        # For modern format, the category is before the dot
        category = name.split('.')[0]
        # Check if category itself has underscore (rare but possible)
        if '_' in category:
            return category.split('_')[0]
        return category
    
    # Handle legacy underscore notation
    if '_' in name:
        return name.split('_')[0]
    
    # Single segment name (no prefix structure)
    return None


def suggest_dictionary_for_prefix(prefix: str) -> Optional[str]:
    """
    Suggest a CIF dictionary to load based on a field prefix.
    
    This function helps users load relevant dictionaries when they
    encounter fields with specific prefixes. The suggestions are
    based on common associations between prefixes and dictionaries.
    
    Args:
        prefix: The prefix to look up (case-insensitive for registered prefixes).
        
    Returns:
        The suggested dictionary filename, or None if no suggestion available.
        
    Examples:
        >>> suggest_dictionary_for_prefix('shelx')
        'cif_shelxl.dic'
        >>> suggest_dictionary_for_prefix('pd_')
        'cif_pow.dic'
        >>> suggest_dictionary_for_prefix('pdbx')
        'mmcif.dic'
        >>> suggest_dictionary_for_prefix('unknown')
        None
    """
    if not prefix:
        return None
    
    data, _ = _load_prefix_data()
    
    # Check if it's a registered prefix with a dictionary suggestion
    prefixes = data.get("prefixes", {})
    prefix_lower = prefix.lower()
    
    for registered, info in prefixes.items():
        if registered.lower() == prefix_lower:
            suggestion = info.get("suggested_dictionary")
            if suggestion:
                return suggestion
    
    # Check category dictionary suggestions (e.g., pd_, mm_, etc.)
    category_suggestions = data.get("category_dictionary_suggestions", {})
    
    # Try exact match first
    if prefix in category_suggestions:
        return category_suggestions[prefix]
    
    # Try case-insensitive match
    for pattern, dictionary in category_suggestions.items():
        if pattern.lower() == prefix_lower:
            return dictionary
    
    # Check if prefix starts with a known pattern (for underscore patterns)
    for pattern, dictionary in category_suggestions.items():
        if pattern.endswith('_') and prefix_lower.startswith(pattern.rstrip('_').lower()):
            return dictionary
    
    return None


def get_all_prefix_info() -> Dict[str, Dict]:
    """
    Get all registered prefix information.
    
    Returns:
        Dict mapping prefix names to their info dicts (description, suggested_dictionary).
    """
    data, _ = _load_prefix_data()
    return data.get("prefixes", {}).copy()


def get_category_dictionary_suggestions() -> Dict[str, str]:
    """
    Get category-based dictionary suggestions.
    
    Returns:
        Dict mapping category patterns (e.g., 'pd_') to dictionary filenames.
    """
    data, _ = _load_prefix_data()
    return data.get("category_dictionary_suggestions", {}).copy()


# Legacy compatibility - these are now functions that return fresh data
# For code that imports these as module-level constants

def _get_REGISTERED_CIF_PREFIXES() -> Set[str]:
    """Get registered prefixes set (legacy compatibility)."""
    return get_registered_prefixes()


def _get_REGISTERED_CIF_PREFIXES_LOWER() -> Set[str]:
    """Get lowercase registered prefixes set (legacy compatibility)."""
    return get_registered_prefixes_lower()


def _get_REGISTERED_CIF_PREFIXES_INFO() -> Dict[str, str]:
    """Get prefix descriptions dict (legacy compatibility)."""
    return {
        p: info.get('description', '') 
        for p, info in get_all_prefix_info().items()
    }


# For backward compatibility with code that imports these constants directly
# We load them once at module import time
# Note: These will be stale if reload_prefix_data() is called
REGISTERED_CIF_PREFIXES: Set[str] = set()
REGISTERED_CIF_PREFIXES_LOWER: Set[str] = set()
REGISTERED_CIF_PREFIXES_INFO: Dict[str, str] = {}


def _initialize_legacy_constants():
    """Initialize legacy module-level constants on first import."""
    global REGISTERED_CIF_PREFIXES, REGISTERED_CIF_PREFIXES_LOWER, REGISTERED_CIF_PREFIXES_INFO
    REGISTERED_CIF_PREFIXES = _get_REGISTERED_CIF_PREFIXES()
    REGISTERED_CIF_PREFIXES_LOWER = _get_REGISTERED_CIF_PREFIXES_LOWER()
    REGISTERED_CIF_PREFIXES_INFO = _get_REGISTERED_CIF_PREFIXES_INFO()


# Initialize on module load
_initialize_legacy_constants()
