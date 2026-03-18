"""
Editor Settings Dialog

Allows users to customize editor preferences like font, line numbers, syntax highlighting, and ruler.
Settings are persisted to the user's configuration directory.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
                            QCheckBox, QPushButton, QFontComboBox, QGroupBox,
                            QMessageBox, QComboBox, QColorDialog, QGridLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.user_config import (
    load_settings, set_setting, DEFAULT_SETTINGS, get_settings_path
)


class EditorSettingsDialog(QDialog):
    """Dialog for editing editor settings."""

    COLOR_LABELS = [
        ('field_default', 'Fallback data names'),
        ('valid', 'Valid fields'),
        ('registered_local', 'Registered local-prefix fields'),
        ('user_allowed', 'User-allowed fields'),
        ('unknown', 'Unknown fields'),
        ('malformed', 'Malformed fields'),
        ('deprecated', 'Deprecated fields'),
        ('value', 'Quoted values'),
        ('multiline', 'Multiline values'),
        ('loop_keyword', 'loop_ keyword'),
        ('loop_field', 'Loop field names'),
        ('loop_data', 'Loop data values'),
    ]
    
    def __init__(self, parent=None, on_settings_changed=None):
        """
        Initialize the editor settings dialog.
        
        Args:
            parent: Parent widget
            on_settings_changed: Callback function called when settings are applied (on OK button)
        """
        super().__init__(parent)
        self.setWindowTitle("Editor Settings")
        self.setMinimumWidth(520)
        self.on_settings_changed = on_settings_changed
        
        # Load current settings
        all_settings = load_settings()
        self.editor_settings = all_settings.get('editor', {})
        self.dialog_settings = all_settings.get('dialogs', {})
        self.color_buttons = {}
        
        # Ensure all required keys exist
        for key, value in DEFAULT_SETTINGS['editor'].items():
            if key not in self.editor_settings:
                self.editor_settings[key] = value

        default_colors = DEFAULT_SETTINGS['editor']['syntax_highlighting_colors']
        current_colors = self.editor_settings.get('syntax_highlighting_colors', {})
        merged_colors = default_colors.copy()
        if isinstance(current_colors, dict):
            merged_colors.update(current_colors)
        self.editor_settings['syntax_highlighting_colors'] = merged_colors

        for key, value in DEFAULT_SETTINGS.get('dialogs', {}).items():
            if key not in self.dialog_settings:
                self.dialog_settings[key] = value
        
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

        # Syntax highlighting colors group
        colors_group = QGroupBox("Syntax Highlighting Colors")
        colors_layout = QVBoxLayout()

        colors_help = QLabel(
            "Choose the colours used for syntax highlighting. These settings also drive the "
            "Syntax Highlighting Guide shown from the Help menu."
        )
        colors_help.setWordWrap(True)
        colors_layout.addWidget(colors_help)

        colors_grid = QGridLayout()
        colors_grid.setColumnStretch(1, 1)

        for row, (key, label_text) in enumerate(self.COLOR_LABELS):
            label = QLabel(label_text + ":")
            colors_grid.addWidget(label, row, 0)

            button = QPushButton()
            button.setMinimumWidth(120)
            button.clicked.connect(lambda checked, color_key=key: self.choose_color(color_key))
            self.color_buttons[key] = button
            colors_grid.addWidget(button, row, 1)

            reset_button = QPushButton("Default")
            reset_button.clicked.connect(lambda checked, color_key=key: self.reset_color_to_default(color_key))
            colors_grid.addWidget(reset_button, row, 2)

        colors_layout.addLayout(colors_grid)
        colors_group.setLayout(colors_layout)
        layout.addWidget(colors_group)

        # Dialog behavior settings group
        dialog_group = QGroupBox("Dialog Behavior")
        dialog_layout = QVBoxLayout()

        default_mode_row = QHBoxLayout()
        default_mode_row.addWidget(QLabel("Default Dialog Interaction:"))
        self.default_dialog_mode_combo = QComboBox()
        self.default_dialog_mode_combo.addItem("Browse editor (read-only) while open", "browse_readonly")
        self.default_dialog_mode_combo.addItem("Classic modal (lock editor while open)", "modal_lock_editor")
        default_mode_row.addWidget(self.default_dialog_mode_combo)
        dialog_layout.addLayout(default_mode_row)

        dialog_mode_row = QHBoxLayout()
        dialog_mode_row.addWidget(QLabel("Validation Results Dialog:"))
        self.validation_dialog_mode_combo = QComboBox()
        self.validation_dialog_mode_combo.addItem("Use default", "inherit_default")
        self.validation_dialog_mode_combo.addItem("Browse editor (read-only) while open", "browse_readonly")
        self.validation_dialog_mode_combo.addItem("Classic modal (lock editor while open)", "modal_lock_editor")
        dialog_mode_row.addWidget(self.validation_dialog_mode_combo)
        dialog_layout.addLayout(dialog_mode_row)

        dialog_help = QLabel(
            "Controls how result dialogs interact with the main editor. "
            "This setting is designed to be reused by additional dialogs in the future."
        )
        dialog_help.setWordWrap(True)
        dialog_layout.addWidget(dialog_help)

        dialog_group.setLayout(dialog_layout)
        layout.addWidget(dialog_group)
        
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
        self.default_dialog_mode_combo.blockSignals(True)
        self.validation_dialog_mode_combo.blockSignals(True)
        
        self.font_combo.setCurrentFont(QFont(self.editor_settings.get('font_family', 'Consolas')))
        self.font_size_spinbox.setValue(self.editor_settings.get('font_size', 10))
        self.line_numbers_checkbox.setChecked(self.editor_settings.get('line_numbers_enabled', True))
        self.syntax_highlighting_checkbox.setChecked(self.editor_settings.get('syntax_highlighting_enabled', True))
        self.ruler_checkbox.setChecked(self.editor_settings.get('show_ruler', True))

        default_mode = self.dialog_settings.get('default_interaction_mode', 'browse_readonly')
        default_index = self.default_dialog_mode_combo.findData(default_mode)
        if default_index < 0:
            default_index = self.default_dialog_mode_combo.findData('browse_readonly')
        self.default_dialog_mode_combo.setCurrentIndex(max(default_index, 0))

        mode_value = self.dialog_settings.get('data_name_validation_results_mode', 'inherit_default')
        mode_index = self.validation_dialog_mode_combo.findData(mode_value)
        if mode_index < 0:
            mode_index = self.validation_dialog_mode_combo.findData('inherit_default')
        self.validation_dialog_mode_combo.setCurrentIndex(max(mode_index, 0))

        for color_key in self.color_buttons:
            self._update_color_button(color_key)
        
        # Unblock signals after loading
        self.font_combo.blockSignals(False)
        self.font_size_spinbox.blockSignals(False)
        self.line_numbers_checkbox.blockSignals(False)
        self.syntax_highlighting_checkbox.blockSignals(False)
        self.ruler_checkbox.blockSignals(False)
        self.default_dialog_mode_combo.blockSignals(False)
        self.validation_dialog_mode_combo.blockSignals(False)
    
    def _update_settings_from_ui(self):
        """Update settings dictionary from UI components."""
        self.editor_settings['font_family'] = self.font_combo.currentFont().family()
        self.editor_settings['font_size'] = self.font_size_spinbox.value()
        self.editor_settings['line_numbers_enabled'] = self.line_numbers_checkbox.isChecked()
        self.editor_settings['syntax_highlighting_enabled'] = self.syntax_highlighting_checkbox.isChecked()
        self.editor_settings['show_ruler'] = self.ruler_checkbox.isChecked()
        self.dialog_settings['default_interaction_mode'] = self.default_dialog_mode_combo.currentData()
        self.dialog_settings['data_name_validation_results_mode'] = self.validation_dialog_mode_combo.currentData()

    def _update_color_button(self, color_key: str) -> None:
        """Refresh the label and preview for one color button."""
        color_value = self.editor_settings['syntax_highlighting_colors'].get(
            color_key,
            DEFAULT_SETTINGS['editor']['syntax_highlighting_colors'][color_key]
        )
        button = self.color_buttons[color_key]
        button.setText(color_value.upper())

        color = QColor(color_value)
        text_color = '#000000'
        if color.isValid() and color.lightness() < 128:
            text_color = '#FFFFFF'

        button.setStyleSheet(
            f"background-color: {color_value}; color: {text_color}; font-family: Consolas, monospace;"
        )

    def choose_color(self, color_key: str) -> None:
        """Open a color picker for a syntax-highlighting color."""
        current_value = self.editor_settings['syntax_highlighting_colors'].get(
            color_key,
            DEFAULT_SETTINGS['editor']['syntax_highlighting_colors'][color_key]
        )
        current_color = QColor(current_value)
        color = QColorDialog.getColor(current_color, self, "Select Syntax Highlighting Color")
        if not color.isValid():
            return

        self.editor_settings['syntax_highlighting_colors'][color_key] = color.name().upper()
        self._update_color_button(color_key)

    def reset_color_to_default(self, color_key: str) -> None:
        """Reset one syntax-highlighting color to its default value."""
        self.editor_settings['syntax_highlighting_colors'][color_key] = (
            DEFAULT_SETTINGS['editor']['syntax_highlighting_colors'][color_key]
        )
        self._update_color_button(color_key)
    
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
            set_setting('editor.syntax_highlighting_colors', self.editor_settings['syntax_highlighting_colors'])
            set_setting('dialogs.default_interaction_mode', self.dialog_settings['default_interaction_mode'])
            set_setting('dialogs.data_name_validation_results_mode', self.dialog_settings['data_name_validation_results_mode'])
            
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
            self.editor_settings['syntax_highlighting_colors'] = DEFAULT_SETTINGS['editor']['syntax_highlighting_colors'].copy()
            self.dialog_settings = DEFAULT_SETTINGS.get('dialogs', {}).copy()
            
            # Reload UI
            self.load_settings_into_ui()
            
            # Save to user config
            try:
                set_setting('editor.font_family', self.editor_settings['font_family'])
                set_setting('editor.font_size', self.editor_settings['font_size'])
                set_setting('editor.line_numbers_enabled', self.editor_settings['line_numbers_enabled'])
                set_setting('editor.syntax_highlighting_enabled', self.editor_settings['syntax_highlighting_enabled'])
                set_setting('editor.show_ruler', self.editor_settings['show_ruler'])
                set_setting('editor.syntax_highlighting_colors', self.editor_settings['syntax_highlighting_colors'])
                set_setting('dialogs.default_interaction_mode', self.dialog_settings.get('default_interaction_mode', 'browse_readonly'))
                set_setting('dialogs.data_name_validation_results_mode', self.dialog_settings.get('data_name_validation_results_mode', 'inherit_default'))
                
                # Apply to editor if callback provided
                if self.on_settings_changed:
                    self.on_settings_changed(self.editor_settings)
                
                QMessageBox.information(self, "Reset Complete", "Editor settings have been reset to defaults.")
            except Exception as e:
                QMessageBox.warning(
                    self, "Error",
                    f"Failed to reset settings:\n{str(e)}"
                )
