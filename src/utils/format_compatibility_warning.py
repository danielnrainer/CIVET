"""
Format Compatibility Warning Module
====================================

TEMPORARY MODULE - Can be removed once IUCr checkCIF fully supports modern notation.

This module provides warnings to users about potential compatibility issues
when using modern (dot) notation instead of legacy (underscore) notation.

Background:
- Modern notation: _cell.length_a (DDLm-style with dots)
- Legacy notation: _cell_length_a (traditional underscore style)
- Both are valid CIF2 syntax, but checkCIF currently has better support for legacy

To remove this warning system later:
1. Delete this file
2. Remove imports and calls to show_modern_format_warning() from:
   - src/gui/dialogs/format_conversion_dialog.py
   - src/gui/dialogs/field_rules_validation_dialog.py
   - src/gui/main_window.py (if applicable)
"""

from PyQt6.QtWidgets import QMessageBox, QCheckBox
from PyQt6.QtCore import QSettings

# Settings key for "don't show again" preference
SETTINGS_KEY_SUPPRESS_WARNING = "suppress_modern_format_warning"


def is_warning_suppressed() -> bool:
    """Check if user has chosen to suppress the modern format warning."""
    settings = QSettings("CIVET", "CIFChecker")
    return settings.value(SETTINGS_KEY_SUPPRESS_WARNING, False, type=bool)


def set_warning_suppressed(suppressed: bool):
    """Set whether to suppress the modern format warning."""
    settings = QSettings("CIVET", "CIFChecker")
    settings.setValue(SETTINGS_KEY_SUPPRESS_WARNING, suppressed)


def reset_warning():
    """Reset the warning suppression (for testing or settings reset)."""
    set_warning_suppressed(False)


def show_modern_format_warning(parent=None, context: str = "operation") -> bool:
    """
    Show a warning about using modern format due to checkCIF compatibility.
    
    Args:
        parent: Parent widget for the dialog
        context: Description of what the user is trying to do (for message customization)
        
    Returns:
        True if user wants to proceed anyway, False if they want to cancel
    """
    if is_warning_suppressed():
        return True  # User chose to suppress, proceed silently
    
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle("Format Compatibility Notice")
    msg_box.setIcon(QMessageBox.Icon.Warning)
    
    msg_box.setText(
        "<b>Modern Format Compatibility Warning</b><br><br>"
        f"You are about to use <b>modern (dot) notation</b> for {context}."
    )
    
    msg_box.setInformativeText(
        "Due to ongoing discrepancies between modern notation and IUCr checkCIF, "
        "I recommend using <b>legacy (underscore) notation</b> for now.\n\n"
        "Examples:\n"
        "• Legacy: _cell_length_a (recommended)\n"
        "• Modern: _cell.length_a (may cause checkCIF issues)\n\n"
        "This warning will be removed once checkCIF fully supports modern notation."
    )
    
    # Add "Don't show again" checkbox
    checkbox = QCheckBox("Don't show this warning again")
    msg_box.setCheckBox(checkbox)
    
    msg_box.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    msg_box.setDefaultButton(QMessageBox.StandardButton.No)
    
    msg_box.button(QMessageBox.StandardButton.Yes).setText("Proceed with Modern")
    msg_box.button(QMessageBox.StandardButton.No).setText("Use Legacy Instead")
    
    result = msg_box.exec()
    
    # Save preference if checkbox was checked
    if checkbox.isChecked():
        set_warning_suppressed(True)
    
    return result == QMessageBox.StandardButton.Yes
