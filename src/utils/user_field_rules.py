"""
User Field Rules Management
============================

Manages custom field rules files stored in the user's CIVET config directory.
Uses the unified user_config module for cross-platform path management.

See user_config.py for directory structure details.
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple

from .user_config import (
    get_user_field_rules_directory as _get_user_field_rules_directory,
    ensure_user_field_rules_directory as _ensure_user_field_rules_directory,
    get_bundled_resource_path
)


def get_user_field_rules_directory() -> str:
    """Get path to user field rules directory (as string for compatibility)."""
    return str(_get_user_field_rules_directory())


def ensure_user_field_rules_directory() -> str:
    """Ensure user field rules directory exists (returns string for compatibility)."""
    return str(_ensure_user_field_rules_directory())


def get_user_field_rules_files() -> List[str]:
    """
    Get list of user-created field rules files.
    
    Returns:
        List of absolute paths to .cif_rules files in user directory
    """
    user_dir = get_user_field_rules_directory()
    
    if not os.path.exists(user_dir):
        return []
    
    try:
        files = []
        for filename in sorted(os.listdir(user_dir)):
            if filename.endswith('.cif_rules'):
                full_path = os.path.join(user_dir, filename)
                if os.path.isfile(full_path):
                    files.append(full_path)
        return files
    except OSError:
        return []


def get_user_field_rules_as_choices() -> List[Tuple[str, str]]:
    """
    Get user field rules files formatted for UI dropdown/menu.
    
    Returns:
        List of (display_name, file_path) tuples
        Display name is based on filename (without .cif_rules extension)
    """
    files = get_user_field_rules_files()
    choices = []
    
    for filepath in files:
        filename = os.path.basename(filepath)
        # Remove .cif_rules extension for display
        display_name = filename.replace('.cif_rules', '')
        choices.append((f"User: {display_name}", filepath))
    
    return choices


def save_field_rules_to_user_dir(content: str, filename: str) -> Tuple[bool, str, Optional[str]]:
    """
    Save field rules content to user's field rules directory.
    
    Args:
        content: The field rules content to save
        filename: Filename to save as (should end with .cif_rules)
        
    Returns:
        Tuple of (success, message, file_path_if_successful)
        success: True if saved successfully
        message: Status message for user feedback
        file_path: Full path to saved file (None if failed)
    """
    try:
        # Ensure directory exists
        user_dir = ensure_user_field_rules_directory()
        
        # Validate filename
        if not filename.endswith('.cif_rules'):
            filename += '.cif_rules'
        
        # Prevent path traversal attacks
        if os.path.sep in filename or filename.startswith('.'):
            return False, "Invalid filename - cannot contain path separators or start with dot", None
        
        file_path = os.path.join(user_dir, filename)
        
        # Write the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True, f"Field rules saved to: {file_path}", file_path
        
    except PermissionError:
        return False, f"Permission denied writing to CIVET directory", None
    except Exception as e:
        return False, f"Error saving field rules: {str(e)}", None


def delete_user_field_rules_file(file_path: str) -> Tuple[bool, str]:
    """
    Delete a user field rules file.
    
    Args:
        file_path: Full path to the .cif_rules file
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Verify it's in user directory (safety check)
        user_dir = get_user_field_rules_directory()
        abs_path = os.path.abspath(file_path)
        
        if not abs_path.startswith(os.path.abspath(user_dir)):
            return False, "Can only delete files from user field rules directory"
        
        if not os.path.exists(abs_path):
            return False, "File not found"
        
        os.remove(abs_path)
        return True, f"Deleted: {os.path.basename(abs_path)}"
        
    except PermissionError:
        return False, "Permission denied deleting file"
    except Exception as e:
        return False, f"Error deleting file: {str(e)}"


def get_bundled_field_rules_files() -> List[Tuple[str, str, Optional[str]]]:
    """
    Get list of bundled field rules files that ship with CIVET.

    Returns:
        List of tuples (display_name, file_path, legacy_path) for bundled
        .cif_rules files.  ``legacy_path`` is the path to the corresponding
        legacy-format variant of that rules file, or ``None`` if no such
        variant exists.

        Convention: ``foo.cif_rules`` automatically gains a ``legacy_path``
        when ``foo_legacy.cif_rules`` is present in the same directory.
        Files whose own stem ends in ``_legacy`` are never given a
        ``legacy_path`` (they *are* the legacy variant).

        Excludes internal files (cleanups, checkcif_compatibility).
    """
    try:
        field_rules_dir = get_bundled_resource_path('field_rules')

        if not field_rules_dir.exists():
            return []

        # Internal files that shouldn't be shown to users
        internal_files = {'cleanups.cif_rules', 'checkcif_compatibility.cif_rules'}

        # Display name mapping for user-friendly names
        display_names = {
            '3ded.cif_rules': '3D ED (Modern)',
            '3ded_legacy.cif_rules': '3D ED (Legacy)',
        }

        files = []
        for filepath in sorted(field_rules_dir.iterdir()):
            if filepath.suffix == '.cif_rules' and filepath.name not in internal_files:
                if filepath.is_file():
                    display_name = display_names.get(
                        filepath.name,
                        filepath.stem.replace('_', ' ').title()
                    )
                    # Look for a paired legacy variant by convention:
                    # foo.cif_rules  →  foo_legacy.cif_rules
                    # Files that already end in _legacy don't get their own pair.
                    if filepath.stem.endswith('_legacy'):
                        legacy_path = None
                    else:
                        candidate = field_rules_dir / f"{filepath.stem}_legacy.cif_rules"
                        legacy_path = str(candidate) if candidate.is_file() else None

                    files.append((display_name, str(filepath), legacy_path))

        return files
    except Exception:
        return []
