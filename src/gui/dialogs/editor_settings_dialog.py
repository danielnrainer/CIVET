"""
Editor Settings Dialog

Allows users to customize editor preferences like font, line numbers, syntax highlighting, and ruler.
Settings are persisted to the user's configuration directory.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
                            QCheckBox, QPushButton, QFontComboBox, QGroupBox,
                            QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.user_config import (
    load_settings, set_setting, DEFAULT_SETTINGS, get_settings_path
)


class EditorSettingsDialog(QDialog):
    """Dialog for editing editor settings."""
    
    def __init__(self, parent=None, on_settings_changed=None):
        """
        Initialize the editor settings dialog.
        
        Args:
            parent: Parent widget
            on_settings_changed: Callback function called when settings are applied (on OK button)
        """
        super().__init__(parent)
        self.setWindowTitle("Editor Settings")
        self.setMinimumWidth(400)
        self.on_settings_changed = on_settings_changed
        
        # Load current settings
        all_settings = load_settings()
        self.editor_settings = all_settings.get('editor', {})
        
        # Ensure all required keys exist
        for key, value in DEFAULT_SETTINGS['editor'].items():
            if key not in self.editor_settings:
                self.editor_settings[key] = value
        
        self.init_ui()
        self.load_settings_into_ui()
    
    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        
        # Font settings group
        font_group = QGroupBox("Font")
        font_layout = QVBoxLayout()
        
        # Font family
        font_family_layout = QHBoxLayout()
        font_family_layout.addWidget(QLabel("Font:"))
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.editor_settings.get('font_family', 'Consolas')))
        font_family_layout.addWidget(self.font_combo)
        font_layout.addLayout(font_family_layout)
        
        # Font size
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("Font Size:"))
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setMinimum(6)
        self.font_size_spinbox.setMaximum(32)
        self.font_size_spinbox.setValue(self.editor_settings.get('font_size', 10))
        self.font_size_spinbox.setSuffix(" pt")
        font_size_layout.addWidget(self.font_size_spinbox)
        font_size_layout.addStretch()
        font_layout.addLayout(font_size_layout)
        
        font_group.setLayout(font_layout)
        layout.addWidget(font_group)
        
        # Display settings group
        display_group = QGroupBox("Display")
        display_layout = QVBoxLayout()
        
        self.line_numbers_checkbox = QCheckBox("Show Line Numbers")
        self.line_numbers_checkbox.setChecked(
            self.editor_settings.get('line_numbers_enabled', True)
        )
        display_layout.addWidget(self.line_numbers_checkbox)
        
        self.syntax_highlighting_checkbox = QCheckBox("Enable Syntax Highlighting")
        self.syntax_highlighting_checkbox.setChecked(
            self.editor_settings.get('syntax_highlighting_enabled', True)
        )
        display_layout.addWidget(self.syntax_highlighting_checkbox)
        
        self.ruler_checkbox = QCheckBox("Show 80-Character Ruler")
        self.ruler_checkbox.setChecked(
            self.editor_settings.get('show_ruler', True)
        )
        display_layout.addWidget(self.ruler_checkbox)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept_and_save)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_settings_into_ui(self):
        """Load settings from config into UI components."""
        # Block signals while loading to prevent triggering callbacks
        self.font_combo.blockSignals(True)
        self.font_size_spinbox.blockSignals(True)
        self.line_numbers_checkbox.blockSignals(True)
        self.syntax_highlighting_checkbox.blockSignals(True)
        self.ruler_checkbox.blockSignals(True)
        
        self.font_combo.setCurrentFont(QFont(self.editor_settings.get('font_family', 'Consolas')))
        self.font_size_spinbox.setValue(self.editor_settings.get('font_size', 10))
        self.line_numbers_checkbox.setChecked(self.editor_settings.get('line_numbers_enabled', True))
        self.syntax_highlighting_checkbox.setChecked(self.editor_settings.get('syntax_highlighting_enabled', True))
        self.ruler_checkbox.setChecked(self.editor_settings.get('show_ruler', True))
        
        # Unblock signals after loading
        self.font_combo.blockSignals(False)
        self.font_size_spinbox.blockSignals(False)
        self.line_numbers_checkbox.blockSignals(False)
        self.syntax_highlighting_checkbox.blockSignals(False)
        self.ruler_checkbox.blockSignals(False)
    
    def _update_settings_from_ui(self):
        """Update settings dictionary from UI components."""
        self.editor_settings['font_family'] = self.font_combo.currentFont().family()
        self.editor_settings['font_size'] = self.font_size_spinbox.value()
        self.editor_settings['line_numbers_enabled'] = self.line_numbers_checkbox.isChecked()
        self.editor_settings['syntax_highlighting_enabled'] = self.syntax_highlighting_checkbox.isChecked()
        self.editor_settings['show_ruler'] = self.ruler_checkbox.isChecked()
    
    def accept_and_save(self):
        """Accept dialog and save settings to user config."""
        # Update settings from UI
        self._update_settings_from_ui()
        
        # Apply settings to editor if callback provided
        if self.on_settings_changed:
            self.on_settings_changed(self.editor_settings)
        
        # Save to user config
        try:
            set_setting('editor.font_family', self.editor_settings['font_family'])
            set_setting('editor.font_size', self.editor_settings['font_size'])
            set_setting('editor.line_numbers_enabled', self.editor_settings['line_numbers_enabled'])
            set_setting('editor.syntax_highlighting_enabled', self.editor_settings['syntax_highlighting_enabled'])
            set_setting('editor.show_ruler', self.editor_settings['show_ruler'])
            
            self.accept()
        except Exception as e:
            QMessageBox.warning(
                self, "Error",
                f"Failed to save settings:\n{str(e)}"
            )
    
    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self, "Reset to Defaults",
            "Are you sure you want to reset all editor settings to their defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Reset in memory
            self.editor_settings = DEFAULT_SETTINGS['editor'].copy()
            
            # Reload UI
            self.load_settings_into_ui()
            
            # Save to user config
            try:
                set_setting('editor.font_family', self.editor_settings['font_family'])
                set_setting('editor.font_size', self.editor_settings['font_size'])
                set_setting('editor.line_numbers_enabled', self.editor_settings['line_numbers_enabled'])
                set_setting('editor.syntax_highlighting_enabled', self.editor_settings['syntax_highlighting_enabled'])
                set_setting('editor.show_ruler', self.editor_settings['show_ruler'])
                
                # Apply to editor if callback provided
                if self.on_settings_changed:
                    self.on_settings_changed(self.editor_settings)
                
                QMessageBox.information(self, "Reset Complete", "Editor settings have been reset to defaults.")
            except Exception as e:
                QMessageBox.warning(
                    self, "Error",
                    f"Failed to reset settings:\n{str(e)}"
                )
