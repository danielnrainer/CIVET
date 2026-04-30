from PyQt6.QtWidgets import (QMainWindow, QWidget, QTextEdit, 
                           QPushButton, QVBoxLayout, QHBoxLayout, QMenu,
                           QFileDialog, QMessageBox, QLineEdit, QCheckBox, 
                           QDialog, QLabel, QFontDialog, QGroupBox, QRadioButton,
                           QButtonGroup, QComboBox)
from PyQt6.QtCore import Qt, QRegularExpression, QTimer, QEventLoop
from PyQt6.QtGui import (QTextCharFormat, QSyntaxHighlighter, QColor, QFont, 
                        QFontMetrics, QTextCursor, QTextDocument, QIcon)
import os
import json
import sys
import re
from typing import Dict, List, Tuple
from utils.CIF_field_parsing import CIFFieldChecker, safe_eval_expr
from utils.CIF_parser import CIFParser, CIFField, update_audit_creation_method, update_audit_creation_date
from utils.cif_dictionary_manager import CIFDictionaryManager, CIFVersion, FieldNotation, CIFSyntaxVersion
from utils.cif_format_converter import CIFFormatConverter
from utils.field_rules_validator import FieldRulesValidator
from utils.data_name_validator import DataNameValidator, FieldCategory
from utils.registered_prefixes import get_prefix_data_source
from utils.user_config import get_user_config_directory, ensure_user_config_directory, get_user_prefixes_path, get_setting
from utils.cif2_value_formatting import (
    format_cif2_value, is_multiline, needs_quoting,
    validate_cif2_content, fix_cif2_compliance_issues
)
from utils.user_field_rules import (
    get_user_field_rules_files, get_user_field_rules_directory,
    get_bundled_field_rules_files, ensure_user_field_rules_directory
)
from .dialogs import (CIFInputDialog, MultilineInputDialog, CheckConfigDialog, 
                     RESULT_ABORT, RESULT_STOP_SAVE)
from .dialogs.data_name_validation_dialog import DataNameValidationDialog
from .dialogs.dictionary_info_dialog import DictionaryInfoDialog
from .dialogs.field_conflict_dialog import FieldConflictDialog
from .dialogs.field_rules_validation_dialog import FieldRulesValidationDialog
from .dialogs.dictionary_suggestion_dialog import show_dictionary_suggestions
from .dialogs.format_conversion_dialog import suggest_format_conversion
from .dialogs.editor_settings_dialog import EditorSettingsDialog
from .dialogs.critical_issues_dialog import CriticalIssuesDialog
from .dialogs.about_dialog import AboutDialog
from .dialogs.recognised_prefixes_dialog import RecognisedPrefixesDialog
from .dialogs.cif_value_validation_dialog import CIFValueValidationDialog
from .editor import CIFSyntaxHighlighter, CIFTextEditor
from .format_handlers import FormatHandlersMixin
from .field_checking import FieldCheckingMixin


class CIFEditor(FieldCheckingMixin, FormatHandlersMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.modified = False
        self.recent_files = []
        self.max_recent_files = 5
        
        # Initialize field checker and CIF parser
        self.field_checker = CIFFieldChecker()
        self.cif_parser = CIFParser()
        config_path = os.path.dirname(__file__)
        
        # Initialize CIF dictionary manager and format converter
        self.dict_manager = CIFDictionaryManager()
        self.format_converter = CIFFormatConverter(self.dict_manager)
        self.current_cif_version = FieldNotation.UNKNOWN
        
        # Initialize field definition validator
        self.field_rules_validator = FieldRulesValidator(self.dict_manager, self.format_converter)
        
        # Note: Field rules are now loaded dynamically via the UI combo boxes
        # The default built-in field set is loaded after init_ui() completes
        
        # Load user field rules from AppData directory
        self._load_user_field_rules()
        
        # Field definition selection variables
        self.custom_field_rules_file = None
        self.current_field_set = '3DED'  # Default to 3DED
        
        # Initialize data name validator
        self.data_name_validator = DataNameValidator(self.dict_manager)

        # Track dialog-driven read-only state so editor is scrollable while dialogs are open.
        self._dialog_editor_lock_count = 0
        self._editor_readonly_before_dialog = False
        
        self.init_ui()
        
        # Initialize the default built-in field set
        self._on_builtin_combo_changed(0)
        
        # Set up syntax highlighter field validator callback
        def _field_validator_callback(field_name: str) -> str:
            result = self.data_name_validator.validate_field(field_name)
            return result.category.value
        self.cif_text_editor.highlighter.set_field_validator(_field_validator_callback)
        
        self.update_dictionary_status()
        self.select_initial_file()

    def load_settings(self):
        """Load editor settings - delegated to text editor component"""
        # This method is now handled by the CIFTextEditor component
        pass

    def save_settings(self):
        """Save editor settings - delegated to text editor component"""
        # This method is now handled by the CIFTextEditor component
        pass

    def apply_settings(self):
        """Apply current settings - delegated to text editor component"""
        # This method is now handled by the CIFTextEditor component
        pass

    def _load_user_field_rules(self):
        """Load user-created field rules from AppData directory."""
        try:
            user_rules = get_user_field_rules_files()
            for file_path in user_rules:
                try:
                    # Extract filename without extension for the set name
                    filename = os.path.basename(file_path)
                    set_name = filename.replace('.cif_rules', '')
                    # Load with "User:" prefix to distinguish from built-in sets
                    user_set_name = f"User: {set_name}"
                    self.field_checker.load_field_set(user_set_name, file_path)
                except Exception as e:
                    # Silently skip files that fail to load
                    print(f"Warning: Could not load user field rules {file_path}: {e}")
        except Exception as e:
            # Silently handle directory reading errors
            print(f"Warning: Could not read user field rules directory: {e}")

    def _populate_builtin_combo(self):
        """Populate the built-in field rules combo box."""
        self.builtin_combo.clear()
        bundled_rules = get_bundled_field_rules_files()
        
        if not bundled_rules:
            self.builtin_combo.addItem("(No built-in rules found)", {'path': '', 'legacy_path': None})
            return
        
        for display_name, file_path, legacy_path in bundled_rules:
            self.builtin_combo.addItem(display_name, {'path': file_path, 'legacy_path': legacy_path})
        
        # Default to Legacy variant if available
        legacy_index = next(
            (i for i in range(self.builtin_combo.count())
             if 'Legacy' in self.builtin_combo.itemText(i)),
            0,
        )
        self.builtin_combo.setCurrentIndex(legacy_index)
    
    def _populate_user_combo(self):
        """Populate the user field rules combo box."""
        self.user_combo.clear()
        user_rules = get_user_field_rules_files()
        
        if not user_rules:
            self.user_combo.addItem("(No user rules - add files to Config Directory)", "")
            return
        
        for file_path in user_rules:
            filename = os.path.basename(file_path)
            display_name = filename.replace('.cif_rules', '')
            self.user_combo.addItem(display_name, file_path)
    
    def _on_builtin_toggled(self, checked):
        """Handle built-in radio button toggle."""
        self.builtin_combo.setEnabled(checked)
        if checked:
            self.user_combo.setEnabled(False)
            self.refresh_user_btn.setEnabled(False)
            self.custom_file_button.setEnabled(False)
            self._on_builtin_combo_changed(self.builtin_combo.currentIndex())
    
    def _on_user_toggled(self, checked):
        """Handle user radio button toggle."""
        self.user_combo.setEnabled(checked)
        self.refresh_user_btn.setEnabled(checked)
        if checked:
            self.builtin_combo.setEnabled(False)
            self.custom_file_button.setEnabled(False)
            self._on_user_combo_changed(self.user_combo.currentIndex())
    
    def _on_custom_toggled(self, checked):
        """Handle custom file radio button toggle."""
        self.custom_file_button.setEnabled(checked)
        if checked:
            self.builtin_combo.setEnabled(False)
            self.user_combo.setEnabled(False)
            self.refresh_user_btn.setEnabled(False)
            self.set_field_set('Custom')
    
    def _on_builtin_combo_changed(self, index):
        """Handle built-in combo box selection change."""
        if not self.radio_builtin.isChecked():
            return
        
        item_data = self.builtin_combo.currentData()
        if not item_data:
            return
        file_path = item_data.get('path', '')
        if file_path:
            display_name = self.builtin_combo.currentText()
            # Create a unique internal name based on display name
            internal_name = display_name.replace(' ', '_').replace('(', '').replace(')', '')
            try:
                self.field_checker.load_field_set(internal_name, file_path)
                self.current_field_set = internal_name
                self.custom_field_rules_file = file_path
            except Exception as e:
                QMessageBox.warning(self, "Load Error", f"Failed to load field rules:\n{str(e)}")
    
    def _on_user_combo_changed(self, index):
        """Handle user combo box selection change."""
        if not self.radio_user.isChecked():
            return
        
        # index=-1 means the combo is being cleared (e.g. during repopulation)
        # — ignore these transient signals to avoid losing the current_field_set
        if index == -1:
            return
        
        file_path = self.user_combo.currentData()
        if file_path:
            display_name = self.user_combo.currentText()
            internal_name = f"User: {display_name}"
            try:
                self.field_checker.load_field_set(internal_name, file_path)
                self.current_field_set = internal_name
                self.custom_field_rules_file = file_path
            except Exception as e:
                QMessageBox.warning(self, "Load Error", f"Failed to load user field rules:\n{str(e)}")
        else:
            # No valid user rules in combo — clear current_field_set so the old
            # built-in name cannot accidentally be used when User radio is active.
            self.current_field_set = None
            self.custom_field_rules_file = None
    
    def _refresh_user_field_rules(self):
        """Refresh the user field rules combo box and reload from AppData."""
        # Reload user field rules into field_checker
        self._load_user_field_rules()
        # Repopulate combo box
        self._populate_user_combo()
        # If user radio is selected and there are rules, select first one
        if self.radio_user.isChecked() and self.user_combo.count() > 0:
            self._on_user_combo_changed(0)

    def change_font(self):
        """Open font dialog to change editor font"""
        self.cif_text_editor.change_font()
            
    def toggle_line_numbers(self):
        """Toggle line numbers visibility"""
        self.cif_text_editor.toggle_line_numbers()
        
    def toggle_syntax_highlighting(self):
        """Toggle syntax highlighting"""
        self.cif_text_editor.toggle_syntax_highlighting()
        
    def toggle_ruler(self):
        """Toggle ruler visibility"""
        self.cif_text_editor.toggle_ruler()
        self.save_settings()

    def init_ui(self):
        # Set initial window title
        self.update_window_title()
        self.setGeometry(100, 100, 900, 700)
        
        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "civet.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create status bar
        self.status_bar = self.statusBar()
        self.path_label = QLabel()
        self.cursor_label = QLabel()
        # self.cif_version_label = QLabel("CIF Version: Unknown")  # FUTURE: re-enable when needed
        self.modified_label = QLabel()
        self.dictionary_label = QLabel("Dictionary: Default")
        self.status_bar.addPermanentWidget(self.path_label)
        # self.status_bar.addPermanentWidget(self.cif_version_label)  # FUTURE: re-enable when needed
        self.status_bar.addPermanentWidget(self.modified_label)
        self.status_bar.addPermanentWidget(self.dictionary_label)
        self.status_bar.addPermanentWidget(self.cursor_label)
        
        # Create CIF text editor component
        self.cif_text_editor = CIFTextEditor()
        self.cif_text_editor.textChanged.connect(self.handle_text_changed)
        self.cif_text_editor.cursorPositionChanged.connect(self.update_cursor_position)
        
        # Provide access to the underlying text editor for backwards compatibility
        self.text_editor = self.cif_text_editor.text_editor
        self.line_numbers = self.cif_text_editor.line_numbers
        self.ruler = self.cif_text_editor.ruler
        
        main_layout.addWidget(self.cif_text_editor)
        
        # Create field definition selection section
        field_selection_group = QGroupBox("CIF Field Definition Selection")
        field_selection_layout = QVBoxLayout(field_selection_group)
        
        # Create radio button group for field definition selection
        self.field_rules_group = QButtonGroup()
        
        # Row 1: Built-in field rules
        builtin_layout = QHBoxLayout()
        self.radio_builtin = QRadioButton("Built-in:")
        self.radio_builtin.setChecked(True)  # Default selection
        self.radio_builtin.setToolTip("Field rules that ship with CIVET")
        self.radio_builtin.toggled.connect(self._on_builtin_toggled)
        self.field_rules_group.addButton(self.radio_builtin)
        builtin_layout.addWidget(self.radio_builtin)
        
        self.builtin_combo = QComboBox()
        self.builtin_combo.setMinimumWidth(200)
        self.builtin_combo.currentIndexChanged.connect(self._on_builtin_combo_changed)
        self._populate_builtin_combo()
        builtin_layout.addWidget(self.builtin_combo)
        builtin_layout.addStretch()
        field_selection_layout.addLayout(builtin_layout)
        
        # Row 2: User field rules (from AppData)
        user_layout = QHBoxLayout()
        self.radio_user = QRadioButton("User:")
        self.radio_user.setToolTip("Custom field rules from your AppData directory")
        self.radio_user.toggled.connect(self._on_user_toggled)
        self.field_rules_group.addButton(self.radio_user)
        user_layout.addWidget(self.radio_user)
        
        self.user_combo = QComboBox()
        self.user_combo.setMinimumWidth(250)
        self.user_combo.currentIndexChanged.connect(self._on_user_combo_changed)
        self._populate_user_combo()
        self.user_combo.setEnabled(False)  # Initially disabled since Built-in is selected
        user_layout.addWidget(self.user_combo)
        
        self.refresh_user_btn = QPushButton("↻")
        self.refresh_user_btn.setToolTip("Refresh user field rules list")
        self.refresh_user_btn.setMaximumWidth(30)
        self.refresh_user_btn.clicked.connect(self._refresh_user_field_rules)
        self.refresh_user_btn.setEnabled(False)
        user_layout.addWidget(self.refresh_user_btn)
        
        self.open_user_dir_btn = QPushButton("📁")
        self.open_user_dir_btn.setToolTip("Open user field rules directory")
        self.open_user_dir_btn.setMaximumWidth(30)
        self.open_user_dir_btn.clicked.connect(self.open_user_field_rules_directory)
        user_layout.addWidget(self.open_user_dir_btn)
        
        user_layout.addStretch()
        field_selection_layout.addLayout(user_layout)
        
        # Row 3: Custom file selection
        custom_layout = QHBoxLayout()
        self.radio_custom = QRadioButton("Custom File:")
        self.radio_custom.setToolTip("Browse to select any .cif_rules file")
        self.radio_custom.toggled.connect(self._on_custom_toggled)
        self.field_rules_group.addButton(self.radio_custom)
        custom_layout.addWidget(self.radio_custom)
        
        self.custom_file_button = QPushButton("Browse...")
        self.custom_file_button.clicked.connect(self.select_custom_field_rules_file)
        self.custom_file_button.setEnabled(False)  # Initially disabled
        custom_layout.addWidget(self.custom_file_button)
        
        self.custom_file_label = QLabel("No file selected")
        self.custom_file_label.setStyleSheet("color: gray; font-style: italic;")
        custom_layout.addWidget(self.custom_file_label)
        custom_layout.addStretch()
        field_selection_layout.addLayout(custom_layout)
        
        main_layout.addWidget(field_selection_group)
        
        # Create button layout
        button_layout = QHBoxLayout()
        
        # Create buttons
        start_checks_button = QPushButton("Start Checks")
        start_checks_button.clicked.connect(self.start_checks)
        refine_details_button = QPushButton("Edit Refinement Special Details")
        refine_details_button.clicked.connect(self.check_refine_special_details)
        format_button = QPushButton("Reformat File")
        format_button.clicked.connect(self.reformat_file)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_file)
        
        # Add buttons to layout
        button_layout.addWidget(start_checks_button)
        button_layout.addWidget(refine_details_button)
        button_layout.addWidget(format_button)
        button_layout.addWidget(save_button)
        
        main_layout.addLayout(button_layout)        # Create menu bar
        menubar = self.menuBar()
        
        # File menu with recent files
        file_menu = menubar.addMenu("File")
        
        open_action = file_menu.addAction("Open")
        open_action.triggered.connect(self.open_file)
        
        self.recent_menu = QMenu("Recent Files", self)
        file_menu.addMenu(self.recent_menu)
        
        save_as_action = file_menu.addAction("Save As")
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.setShortcut("Ctrl+S")
        save_as_action.triggered.connect(self.save_file_as)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        
        # Actions menu
        action_menu = menubar.addMenu("Actions")
        
        start_checks_action = action_menu.addAction("Start Checks")
        start_checks_action.triggered.connect(self.start_checks)
        
        refine_details_action = action_menu.addAction("Edit Refinement Special Details")
        refine_details_action.triggered.connect(self.check_refine_special_details)
        
        format_action = action_menu.addAction("Reformat File")
        format_action.triggered.connect(self.reformat_file)
        
        action_menu.addSeparator()
        
        validate_names_action = action_menu.addAction("Validate Data Names...")
        validate_names_action.triggered.connect(self.validate_data_names)
        validate_names_action.setToolTip("Validate all data names against loaded dictionaries and registered prefixes")

        validate_values_action = action_menu.addAction("Validate Data Values...")
        validate_values_action.triggered.connect(self.validate_data_values)
        validate_values_action.setToolTip("Check all CIF values against dictionary-defined types and enumerations, and detect loop structure errors")

        # CIF Format menu
        format_menu = menubar.addMenu("CIF Format")
        
        detect_version_action = format_menu.addAction("Detect Notation && Syntax Version")
        detect_version_action.triggered.connect(self.detect_cif_version)
        
        format_menu.addSeparator()
        
        # Field notation conversion
        notation_menu = format_menu.addMenu("Field Notation")
        
        convert_to_legacy_action = notation_menu.addAction("Convert to Legacy Notation")
        convert_to_legacy_action.triggered.connect(self.convert_to_legacy)
        
        convert_to_modern_action = notation_menu.addAction("Convert to Modern Notation")
        convert_to_modern_action.triggered.connect(self.convert_to_modern)
        
        notation_menu.addSeparator()
        
        fix_mixed_action = notation_menu.addAction("Fix Mixed Notation")
        fix_mixed_action.triggered.connect(self.fix_mixed_format)
        
        # CIF syntax version compliance
        syntax_menu = format_menu.addMenu("Syntax Version")
        
        ensure_cif2_action = syntax_menu.addAction("Ensure CIF 2.0 Compliance")
        ensure_cif2_action.triggered.connect(self.ensure_cif2_compliance)
        
        ensure_cif1_action = syntax_menu.addAction("Ensure CIF 1.1 Compliance")
        ensure_cif1_action.triggered.connect(self.ensure_cif1_compliance)
        
        format_menu.addSeparator()
        
        resolve_aliases_action = format_menu.addAction("Resolve Field Aliases")
        resolve_aliases_action.triggered.connect(self.standardize_cif_fields)
        
        fix_malformed_action = format_menu.addAction("Fix Malformed Field Names...")
        fix_malformed_action.triggered.connect(self.fix_malformed_field_names)
        fix_malformed_action.setToolTip("Detect and fix incorrectly formatted field names like _diffrn_total_exposure_time → _diffrn.total_exposure_time")
        
        check_deprecated_action = format_menu.addAction("Check Deprecated Fields")
        check_deprecated_action.triggered.connect(self.check_deprecated_fields)
        
        format_menu.addSeparator()
        
        add_compatibility_action = format_menu.addAction("Add Legacy Compatibility Fields")
        add_compatibility_action.triggered.connect(self.add_legacy_compatibility_fields)
        add_compatibility_action.setToolTip("Add deprecated fields alongside modern equivalents for validation tool compatibility")

        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        # Undo/Redo
        undo_action = edit_menu.addAction("Undo")
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.text_editor.undo)
        
        redo_action = edit_menu.addAction("Redo")
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self.text_editor.redo)
        
        edit_menu.addSeparator()
        
        # Find
        find_action = edit_menu.addAction("Find")
        find_action.setShortcut("Ctrl+F")
        find_action.triggered.connect(self.show_find_dialog)
        
        # Find and Replace
        replace_action = edit_menu.addAction("Find and Replace")
        replace_action.setShortcut("Ctrl+H")
        replace_action.triggered.connect(self.show_replace_dialog)
        
        edit_menu.addSeparator()
        
        reload_action = edit_menu.addAction("Reload File")
        reload_action.setShortcut("Ctrl+Shift+R")
        reload_action.setToolTip("Reload the current file from disk, discarding all unsaved changes")
        reload_action.triggered.connect(self.reload_file)
        
        # View menu for editor settings
        view_menu = menubar.addMenu("View")
        
        font_action = view_menu.addAction("Change Font...")
        font_action.triggered.connect(self.change_font)
        
        line_numbers_action = view_menu.addAction("Show Line Numbers")
        line_numbers_action.setCheckable(True)
        line_numbers_action.setChecked(self.cif_text_editor.settings['line_numbers_enabled'])
        line_numbers_action.triggered.connect(self.toggle_line_numbers)
        
        ruler_action = view_menu.addAction("Show 80-Char Ruler")
        ruler_action.setCheckable(True)
        ruler_action.setChecked(self.cif_text_editor.settings['show_ruler'])
        ruler_action.triggered.connect(self.toggle_ruler)
        
        syntax_action = view_menu.addAction("Syntax Highlighting")
        syntax_action.setCheckable(True)
        syntax_action.setChecked(self.cif_text_editor.settings['syntax_highlighting_enabled'])
        syntax_action.triggered.connect(self.toggle_syntax_highlighting)
        
        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        # Dictionary management section
        dict_info_action = settings_menu.addAction("Dictionary Information...")
        dict_info_action.triggered.connect(self.show_dictionary_info)
        
        load_dict_action = settings_menu.addAction("Replace Core CIF Dictionary...")
        load_dict_action.triggered.connect(self.load_custom_dictionary)
        
        add_dict_action = settings_menu.addAction("Add Additional CIF Dictionary...")
        add_dict_action.triggered.connect(self.add_additional_dictionary)
        
        suggest_dict_action = settings_menu.addAction("Suggest Dictionaries for Current CIF...")
        suggest_dict_action.triggered.connect(self.suggest_dictionaries)
        
        settings_menu.addSeparator()
        
        # Prefix management section
        show_prefixes_action = settings_menu.addAction("View Recognised Prefixes...")
        show_prefixes_action.triggered.connect(self.show_recognised_prefixes)
        
        reload_prefixes_action = settings_menu.addAction("Reload Prefix Configuration")
        reload_prefixes_action.triggered.connect(self.reload_prefix_configuration)
        
        settings_menu.addSeparator()
        
        # Field rules section
        validate_field_defs_action = settings_menu.addAction("Validate Field Rules...")
        validate_field_defs_action.triggered.connect(self.validate_field_rules)
        
        open_user_rules_action = settings_menu.addAction("Open Field Rules Directory...")
        open_user_rules_action.triggered.connect(self.open_user_field_rules_directory)
        
        settings_menu.addSeparator()
        
        # Editor settings section
        editor_settings_action = settings_menu.addAction("Editor Settings...")
        editor_settings_action.triggered.connect(self.show_editor_settings)
        
        settings_menu.addSeparator()
        
        # Config directory access
        open_config_action = settings_menu.addAction("Open Config Directory")
        open_config_action.triggered.connect(self.open_config_directory)
        
        # Help menu
        help_menu = menubar.addMenu("Help")

        syntax_guide_action = help_menu.addAction("Syntax Highlighting Guide...")
        syntax_guide_action.triggered.connect(self.show_syntax_highlighting_guide)

        help_menu.addSeparator()
        
        about_action = help_menu.addAction("About CIVET...")
        about_action.triggered.connect(self.show_about_dialog)
        
        # Enable undo/redo
        self.text_editor.setUndoRedoEnabled(True)

    def update_window_title(self, filepath=None):
        """Update window title with current filename."""
        if filepath:
            filename = os.path.basename(filepath)
            self.setWindowTitle(f"CIVET - {filename}")
        elif self.current_file:
            filename = os.path.basename(self.current_file)
            self.setWindowTitle(f"CIVET - {filename}")
        else:
            self.setWindowTitle("CIVET")

    def extract_field_value(self, lines, field_index, field_name):
        """Extract the value for a CIF field, handling cases where value might be on next line or in semicolon blocks."""
        current_line = lines[field_index]
        
        # First, try to get value from the same line
        line_parts = current_line.split()
        if len(line_parts) > 1:
            # Value is on the same line as field name
            current_value = " ".join(line_parts[1:])
            return current_value.strip()
        
        # If no value on same line, check the next line
        if field_index + 1 < len(lines):
            next_line = lines[field_index + 1].strip()
            
            # Check if it's a semicolon-delimited multiline value
            if next_line == ';':
                # Extract content between semicolons
                multiline_content = []
                for i in range(field_index + 2, len(lines)):
                    line = lines[i]
                    if line.strip() == ';':
                        # Found closing semicolon
                        break
                    multiline_content.append(line)
                
                # Join the multiline content
                if multiline_content:
                    # Remove leading whitespace consistently
                    cleaned_lines = []
                    for line in multiline_content:
                        # Keep the line as-is but strip trailing whitespace
                        cleaned_lines.append(line.rstrip())
                    return '\n'.join(cleaned_lines)
                else:
                    return ""
            
            # Check if next line looks like a regular value (not another field name or empty)
            elif next_line and not next_line.startswith('_') and not next_line.startswith('#'):
                return next_line.strip()
        
        # No value found
        return ""

    def _format_cif_value_for_line(self, value: str) -> str:
        """
        Format a single-line CIF value with proper quoting for CIF2.
        
        Handles CIF2 special characters [ ] { } which require quoting.
        
        Args:
            value: The raw value to format
            
        Returns:
            Properly formatted/quoted value for inclusion on a single line
        """
        if not value:
            return "''"
        
        # Use the modern formatting utility
        formatted = format_cif2_value(value, prefer_triple_quotes=False)
        
        # If the formatter returns a semicolon block, we need to handle separately
        if formatted.startswith(';'):
            # Shouldn't happen for single-line, but use quotes as fallback
            return f"'{value}'"
        
        return formatted
    
    def _insert_multiline_value(self, lines: list, insert_after_index: int, value: str) -> int:
        """
        Insert a multiline value as a semicolon-delimited block.
        
        Args:
            lines: The list of lines to modify
            insert_after_index: Index after which to insert the block
            value: The multiline value content
            
        Returns:
            Number of lines inserted
        """
        value_lines = value.split('\n')
        semicolon_lines = [';'] + value_lines + [';']
        for i, line in enumerate(semicolon_lines):
            lines.insert(insert_after_index + 1 + i, line)
        return len(semicolon_lines)

    def update_field_value(self, lines, field_index, field_name, new_value):
        """
        Update the value for a CIF field, handling various value formats.
        
        Properly handles:
        - Single-line values (with CIF2-compliant quoting for [ ] { })
        - Multiline semicolon-delimited values
        - Values on the same line or next line
        """
        # Strip outer quotes from the new value if present
        stripped_value = new_value.strip()
        if (stripped_value.startswith("'") and stripped_value.endswith("'")) or \
           (stripped_value.startswith('"') and stripped_value.endswith('"')):
            stripped_value = stripped_value[1:-1]
        
        current_line = lines[field_index]
        line_parts = current_line.split()
        is_value_multiline = is_multiline(stripped_value)
        
        if len(line_parts) > 1:
            # Value is on the same line as field name
            if is_value_multiline:
                # Convert to semicolon format
                lines[field_index] = field_name
                self._insert_multiline_value(lines, field_index, stripped_value)
            else:
                # Single line value - use proper CIF2 quoting
                formatted_value = self._format_cif_value_for_line(stripped_value)
                lines[field_index] = f"{field_name} {formatted_value}"
        else:
            # No value on same line, check next line
            if field_index + 1 < len(lines):
                next_line = lines[field_index + 1].strip()
                
                if next_line == ';':
                    # Existing semicolon-delimited value - find and replace block
                    end_index = field_index + 1
                    for i in range(field_index + 2, len(lines)):
                        if lines[i].strip() == ';':
                            end_index = i
                            break
                    
                    # Remove old block
                    del lines[field_index + 1:end_index + 1]
                    
                    # Insert new value
                    if is_value_multiline:
                        self._insert_multiline_value(lines, field_index, stripped_value)
                    else:
                        # Single line - still use semicolon format if replacing a block
                        semicolon_lines = [';', stripped_value, ';']
                        for i, line in enumerate(semicolon_lines):
                            lines.insert(field_index + 1 + i, line)
                
                elif next_line and not next_line.startswith('_') and not next_line.startswith('#'):
                    # Next line has a regular value
                    if is_value_multiline:
                        # Replace with semicolon format
                        lines[field_index + 1] = ';'
                        value_lines = stripped_value.split('\n') + [';']
                        for i, line in enumerate(value_lines):
                            lines.insert(field_index + 2 + i, line)
                    else:
                        # Simple replacement with proper quoting
                        formatted_value = self._format_cif_value_for_line(stripped_value)
                        lines[field_index + 1] = f" {formatted_value}"
                else:
                    # Next line doesn't have value, add to current or as new lines
                    if is_value_multiline:
                        self._insert_multiline_value(lines, field_index, stripped_value)
                    else:
                        formatted_value = self._format_cif_value_for_line(stripped_value)
                        lines[field_index] = f"{field_name} {formatted_value}"
            else:
                # No next line
                if is_value_multiline:
                    self._insert_multiline_value(lines, field_index, stripped_value)
                else:
                    formatted_value = self._format_cif_value_for_line(stripped_value)
                    lines[field_index] = f"{field_name} {formatted_value}"

    def select_initial_file(self):
        file_filter = "CIF Files (*.cif);;All Files (*.*)"
        self.current_file, _ = QFileDialog.getOpenFileName(
            self, "Select a CIF File", "", file_filter)
        if not self.current_file:
            QMessageBox.information(self, "No File Selected", 
                                  "Please select a CIF file to continue.")
        else:
            self.open_file(initial=True)

    def update_recent_files_menu(self):
        self.recent_menu.clear()
        for filepath in self.recent_files:
            action = self.recent_menu.addAction(filepath)
            action.triggered.connect(lambda checked, path=filepath: self.open_recent_file(path))
            
    def open_recent_file(self, filepath):
        if not filepath or not os.path.exists(filepath):
            QMessageBox.warning(self, "File Not Found",
                              f"Could not find file:\n{filepath}")
            self.recent_files.remove(filepath)
            self.update_recent_files_menu()
            return
        self.current_file = filepath
        self.open_file(initial=True)
        
    def add_to_recent_files(self, filepath):
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        self.recent_files.insert(0, filepath)
        if len(self.recent_files) > self.max_recent_files:
            self.recent_files.pop()
        self.update_recent_files_menu()

    def open_file(self, initial=False):
        if not initial:
            file_filter = "CIF Files (*.cif);;All Files (*.*)"
            filepath, _ = QFileDialog.getOpenFileName(
                self, "Open File", "", file_filter)
            if not filepath:
                return
        else:
            filepath = self.current_file

        try:
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()
            
            # ============================================================================
            # TEMPORARILY DISABLED: Format conversion check
            # Due to issues with checkCIF not recognizing modern format, we're sticking
            # with legacy format for now. This check can be easily re-enabled once
            # checkCIF is updated to support modern CIF field names.
            # ============================================================================
            
            # # Detect CIF version first
            # detected_version = self.dict_manager.detect_cif_version(content)
            # 
            # # Suggest conversion to modern format if not already modern
            # if detected_version in [CIFVersion.LEGACY, CIFVersion.MIXED]:
            #     final_content, user_choice, changes = suggest_format_conversion(
            #         content, detected_version, self.format_converter, self
            #     )
            #     
            #     if user_choice == 'cancel':
            #         # User cancelled, don't load the file
            #         return
            #     elif user_choice == 'convert':
            #         # User accepted conversion
            #         content = final_content
            #         self.modified = True  # Mark as modified since content changed
            #         QMessageBox.information(
            #             self, 
            #             "Conversion Complete",
            #             f"File converted to modern CIF format.\n"
            #             f"{len(changes)} field names updated.\n\n"
            #             f"Remember to save the file to preserve changes."
            #         )
            #     # else: user_choice == 'keep_original', use original content
            
            self.text_editor.setText(content)
            self.current_file = filepath
            self.modified = False
            self.cif_text_editor.set_modified(False)
            
            # FUTURE: Re-enable when CIF version display is re-enabled
            # self.detect_and_update_cif_version(content)

            self.update_status_bar()
            self.add_to_recent_files(filepath)
            self.update_window_title(filepath)
            
            # Prompt for dictionary suggestions after opening CIF file
            self.prompt_for_dictionary_suggestions(content)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")

    def reload_file(self):
        """Reload the current file from disk, discarding all unsaved changes."""
        if not self.current_file:
            QMessageBox.information(self, "No File", "No file is currently open.")
            return
        
        if self.modified:
            reply = QMessageBox.question(
                self, "Reload File",
                "You have unsaved changes. Reloading will discard them.\n\n"
                "Do you want to reload?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            with open(self.current_file, "r", encoding="utf-8") as file:
                content = file.read()
            
            self.text_editor.setText(content)
            self.modified = False
            self.cif_text_editor.set_modified(False)
            self.update_status_bar()
            self.update_window_title(self.current_file)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reload file:\n{e}")

    def save_file(self):
        if self.current_file:
            reply = QMessageBox.question(self, "Confirm Save",
                f"Do you want to overwrite the existing file?\n{self.current_file}",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel)
            
            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.Yes:
                self.save_to_file(self.current_file)
                # Update window title after saving
                self.update_window_title(self.current_file)
            else:
                self.save_file_as()
        else:
            self.save_file_as()

    def save_file_as(self):
        file_filter = "CIF Files (*.cif);;All Files (*.*)"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save File As", "", file_filter)
        if filepath:
            self.save_to_file(filepath)

    def save_to_file(self, filepath):
        try:
            content = self.text_editor.toPlainText().strip()
            
            # Check for CIF2 compliance issues (e.g., unquoted brackets)
            issues = validate_cif2_content(content)
            if issues:
                # Auto-fix the issues
                content, fixes = fix_cif2_compliance_issues(content)
                
                # Build message about fixes
                fix_details = []
                for line_num, field, old_val, new_val in fixes:
                    fix_details.append(f"  Line {line_num}: {field}\n    {old_val} → {new_val}")
                
                if fixes:
                    QMessageBox.information(
                        self,
                        "CIF2 Compliance Fixes Applied",
                        f"Quotes were applied to the following values for compliance:\n\n" +
                        "\n".join(fix_details[:5]) +
                        (f"\n... and {len(fixes) - 5} more" if len(fixes) > 5 else "") +
                        "\n\nStrings containing [ ] { } should be quoted in CIFs."
                    )
                    # Update the editor with fixed content
                    self.text_editor.setText(content)
            
            # Preserve existing header; add CIF2 header only if CIF2 constructs detected and no header present
            syntax_ver = self.dict_manager.detect_syntax_version(content)
            if syntax_ver == CIFSyntaxVersion.UNKNOWN:
                # No header present — check if CIF2 constructs exist
                if self.format_converter.detect_cif2_constructs(content):
                    content = self._ensure_cif2_header(content)
            # Detect CIF format using existing dict_manager
            cif_format = self.dict_manager.detect_cif_format(content)
            # Update _audit_creation_date to current date (only on save)
            content = update_audit_creation_date(content, cif_format)
            # Update _audit_creation_method to include CIVET info
            content = update_audit_creation_method(content, cif_format)
            
            with open(filepath, "w", encoding="utf-8") as file:
                file.write(content)
            self.current_file = filepath
            self.modified = False
            self.cif_text_editor.set_modified(False)
            self.update_status_bar()
            QMessageBox.information(self, "Success", 
                                  f"File saved successfully:\n{filepath}")
            self.update_window_title(filepath)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")

    def set_field_set(self, field_set_name):
        """Set the current field set selection."""
        self.current_field_set = field_set_name
        
        # Update custom file label based on selection
        if field_set_name == 'Custom':
            if not self.custom_field_rules_file:
                self.custom_file_label.setText("Please select a file")
                self.custom_file_label.setStyleSheet("color: red; font-style: italic;")
        elif self.custom_field_rules_file:
            # Show the currently loaded file
            filename = os.path.basename(self.custom_field_rules_file)
            self.custom_file_label.setText(filename)
            self.custom_file_label.setStyleSheet("color: green; font-style: normal;")
        else:
            self.custom_file_label.setText("No file selected")
            self.custom_file_label.setStyleSheet("color: gray; font-style: italic;")
    
    def select_custom_field_rules_file(self):
        """Open file dialog to select a custom field definition file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Field Definition File",
            "",
            "Field Rules Files (*.cif_rules);;All Files (*)"
        )
        
        if file_path:
            self._load_custom_field_rules_file(file_path)
    
    def _load_custom_field_rules_file(self, file_path: str, skip_validation: bool = False):
        """Load a custom field definition file with optional validation."""
        try:
            # Read the file content for validation
            with open(file_path, 'r', encoding='utf-8') as f:
                field_rules_content = f.read()
            
            # Offer validation if not skipping
            if not skip_validation:
                reply = QMessageBox.question(
                    self, "Validate Field Definitions",
                    "Would you like to validate this field definition file for common issues?\n\n"
                    "This can help identify and fix:\n"
                    "• Mixed legacy/modern formats\n"
                    "• Duplicate/alias fields\n"
                    "• Unknown fields\n\n"
                    "Recommended for better compatibility.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Get CIF content for format analysis if available
                    cif_content = self.text_editor.toPlainText() if hasattr(self, 'text_editor') else None
                    
                    # Validate the field definitions
                    validation_result = self.field_rules_validator.validate_field_rules(
                        field_rules_content, cif_content
                    )
                    
                    if validation_result.has_issues:
                        # Show validation dialog
                        dialog = FieldRulesValidationDialog(
                            validation_result, field_rules_content, file_path, 
                            self.field_rules_validator, self
                        )
                        
                        # Connect validation completion signal
                        dialog.validation_completed.connect(
                            lambda fixed_content, changes: self._on_validation_completed(
                                file_path, fixed_content, changes
                            )
                        )
                        
                        if self._show_dialog_with_configured_interaction(dialog) == QDialog.DialogCode.Accepted:
                            # Check if fixes were applied
                            if dialog.fixed_content:
                                # Use the fixed content instead
                                field_rules_content = dialog.fixed_content
                    else:
                        QMessageBox.information(
                            self, "Validation Complete",
                            "✅ No issues found in the field definition file!"
                        )
            
            # Try to load the field definition file
            self.field_checker.load_field_set('Custom', file_path)
            self.custom_field_rules_file = file_path
            
            # Update the label to show the selected file
            file_name = os.path.basename(file_path)
            self.custom_file_label.setText(f"Using: {file_name}")
            self.custom_file_label.setStyleSheet("color: green; font-weight: bold;")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Custom File",
                f"Failed to load field definition file:\n{str(e)}\n\n"
                "Please ensure the file is in the correct format."
            )
            self.custom_file_label.setText("Error loading file")
            self.custom_file_label.setStyleSheet("color: red; font-style: italic;")
    
    def _on_validation_completed(self, file_path: str, fixed_content: str, changes: List[str]):
        """Handle completion of field definition validation."""
        try:
            # Write the fixed content to a temporary file and load it
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cif_rules', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(fixed_content)
                temp_path = temp_file.name
            
            # Load the fixed content
            self.field_checker.load_field_set('Custom', temp_path)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            # Show success message
            QMessageBox.information(
                self, "Field Definitions Updated",
                f"Field definitions loaded with {len(changes)} fixes applied:\n\n" +
                "\n".join(f"• {change}" for change in changes[:5]) +
                (f"\n• ... and {len(changes) - 5} more" if len(changes) > 5 else "")
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to load fixed field definitions: {str(e)}"
            )
    
    def _resolve_dialog_interaction_mode(self, mode_setting_key: str) -> str:
        """Resolve an effective dialog interaction mode from defaults/overrides."""
        default_mode = get_setting("dialogs.default_interaction_mode", "browse_readonly")

        if mode_setting_key == "dialogs.default_interaction_mode":
            mode = default_mode
        else:
            mode = get_setting(mode_setting_key, "inherit_default")
            if mode == "inherit_default":
                mode = default_mode

        if mode not in {"browse_readonly", "modal_lock_editor", "allow_editing"}:
            return "browse_readonly"
        return mode

    def _lock_editor_for_dialog(self) -> None:
        """Temporarily lock editor editing while preserving scroll/navigation."""
        if self._dialog_editor_lock_count == 0 and self.text_editor is not None:
            self._editor_readonly_before_dialog = self.text_editor.isReadOnly()
            self.text_editor.setReadOnly(True)
        self._dialog_editor_lock_count += 1

    def _unlock_editor_for_dialog(self) -> None:
        """Release one dialog lock and restore original read-only state when done."""
        if self._dialog_editor_lock_count <= 0:
            return

        self._dialog_editor_lock_count -= 1
        if self._dialog_editor_lock_count == 0 and self.text_editor is not None:
            self.text_editor.setReadOnly(self._editor_readonly_before_dialog)

    def _show_dialog_with_configured_interaction(
        self,
        dialog: QDialog,
        mode_setting_key: str = "dialogs.default_interaction_mode"
    ) -> int:
        """Show a dialog and return its result while honoring interaction settings."""
        mode = self._resolve_dialog_interaction_mode(mode_setting_key)

        if mode == "modal_lock_editor":
            dialog.setModal(True)
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            return int(dialog.exec())

        if mode != "allow_editing":
            self._lock_editor_for_dialog()
        dialog.setModal(False)
        dialog.setWindowModality(Qt.WindowModality.NonModal)

        loop = QEventLoop(self)
        result_code = int(QDialog.DialogCode.Rejected)
        locked = (mode != "allow_editing")

        def _on_dialog_finished(code: int) -> None:
            nonlocal result_code
            result_code = int(code)
            if locked:
                self._unlock_editor_for_dialog()
            if loop.isRunning():
                loop.quit()

        dialog.finished.connect(_on_dialog_finished)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        loop.exec()
        return result_code

    def reformat_file(self):
        """Reformat CIF file to handle long lines and properly format values, preserving semicolon blocks."""
        # Ask for user confirmation before reformatting
        reply = QMessageBox.question(self, "Confirm Reformatting",
                                   "This will reformat the entire CIF file to handle long lines and proper formatting.\n\n"
                                   "This may change existing formatting that you have intentionally applied.\n\n"
                                   "Do you want to proceed with reformatting?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Use the CIF parser's reformatting functionality
            current_content = self.text_editor.toPlainText()
            reformatted_content = self.cif_parser.reformat_for_line_length(current_content)
            
            # Update the text editor with the reformatted content
            self.text_editor.setText(reformatted_content)
            
            QMessageBox.information(self, "Reformatting Completed",
                                  "The file has been successfully reformatted with proper line length handling.")
        except Exception as e:
            QMessageBox.critical(self, "Reformatting Error",
                               f"An error occurred while reformatting:\n{str(e)}")

    def insert_line_breaks(self, text, limit):
        words = text.split()
        line_length = 0
        lines = []
        current_line = []
        
        for word in words:
            if line_length + len(word) + 1 > limit:
                lines.append(" ".join(current_line))
                current_line = [word]
                line_length = len(word)
            else:
                current_line.append(word)
                line_length += len(word) + 1
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return "\n".join(lines)

    def handle_text_changed(self):
        self.modified = True
        self.update_status_bar()

        # FUTURE: Re-enable when CIF version display is re-enabled
        # Schedule CIF version detection (delayed to avoid constant updates)
        # if hasattr(self, 'version_detect_timer'):
        #     self.version_detect_timer.stop()
        # else:
        #     self.version_detect_timer = QTimer()
        #     self.version_detect_timer.setSingleShot(True)
        #     self.version_detect_timer.timeout.connect(lambda: self.detect_and_update_cif_version())
        #
        # self.version_detect_timer.start(1000)  # 1 second delay
    
    def update_cursor_position(self):
        cursor = self.text_editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        current_line = cursor.block().text()
        line_length = len(current_line)
        
        # Update status bar with enhanced position info
        status = f"Ln {line}, Col {column} | Length: {line_length}/80"
        if line_length > 80:
            status += " (Over limit!)"
        self.cursor_label.setText(status)
        # Change color if line is too long
        if line_length > 80:
            self.cursor_label.setStyleSheet("color: red;")
        else:
            self.cursor_label.setStyleSheet("")

    def update_status_bar(self):
        path = self.current_file if self.current_file else "Untitled"
        modified = "*" if self.modified else ""
        self.path_label.setText(f"{path}{modified} | ")
        if self.modified:
            self.modified_label.setText("\u25cf Unsaved changes")
            self.modified_label.setStyleSheet("color: orange; font-weight: bold;")
        elif self.current_file:
            self.modified_label.setText("\u2713 Saved")
            self.modified_label.setStyleSheet("color: green;")
        else:
            self.modified_label.setText("")

    def update_dictionary_status(self):
        """Update the dictionary status label in the status bar"""
        try:
            # Get dictionary information
            dict_info = self.dict_manager.get_dictionary_info()
            total_dicts = dict_info['total_dictionaries']
            
            if total_dicts == 1:
                # Single dictionary - show its name
                dict_path = getattr(self.dict_manager.parser, 'cif_core_path', None)
                if dict_path and dict_path != 'cif_core.dic':
                    dict_name = os.path.basename(dict_path)
                    self.dictionary_label.setText(f"Dictionary: {dict_name}")
                else:
                    self.dictionary_label.setText("Dictionary: Default")
            else:
                # Multiple dictionaries - show count and primary
                primary_dict = dict_info.get('primary_dictionary', '')
                primary_name = os.path.basename(primary_dict) if primary_dict else 'Default'
                additional_count = total_dicts - 1
                
                self.dictionary_label.setText(f"Dictionaries: {primary_name} +{additional_count}")
                
                # Set tooltip with full list
                loaded_dicts = self.dict_manager.get_loaded_dictionaries()
                dict_names = [os.path.basename(path) for path in loaded_dicts]
                tooltip_text = f"Loaded dictionaries:\\n" + "\\n".join([f"• {name}" for name in dict_names])
                self.dictionary_label.setToolTip(tooltip_text)
                
        except Exception:
            # Fallback if there's any issue
            self.dictionary_label.setText("Dictionary: Unknown")

    def show_find_dialog(self):
        """Show a dialog for finding text in the editor"""
        self.cif_text_editor.show_find_dialog()

    def show_replace_dialog(self):
        """Show a dialog for finding and replacing text in the editor"""
        self.cif_text_editor.show_replace_dialog()

    def find_text(self, text, case_sensitive=False):
        """Find the next occurrence of text in the editor"""
        return self.cif_text_editor.find_text(text, case_sensitive)

    def replace_text(self, find_text, replace_text, case_sensitive=False):
        """Replace the next occurrence of find_text with replace_text"""
        self.cif_text_editor.replace_text(find_text, replace_text, case_sensitive)

    def replace_all_text(self, find_text, replace_text, case_sensitive=False):
        """Replace all occurrences of find_text with replace_text"""
        return self.cif_text_editor.replace_all_text(find_text, replace_text, case_sensitive)
    
    def update_cif_version_display(self):
        """Update the CIF version display in the status bar"""
        # FUTURE: Re-enable when CIF version display is re-enabled (restore cif_version_label widget too)
        # notation_text = {
        #     FieldNotation.LEGACY: "Notation: Legacy",
        #     FieldNotation.MODERN: "Notation: Modern",
        #     FieldNotation.MIXED: "Notation: Mixed",
        #     FieldNotation.UNKNOWN: "Notation: Unknown"
        # }
        # color = {
        #     FieldNotation.LEGACY: "green",
        #     FieldNotation.MODERN: "blue",
        #     FieldNotation.MIXED: "orange",
        #     FieldNotation.UNKNOWN: "red"
        # }
        # text = notation_text.get(self.current_cif_version, "Notation: Unknown")
        # self.cif_version_label.setText(text)
        # self.cif_version_label.setStyleSheet(f"color: {color.get(self.current_cif_version, 'black')}")
        pass
    
    def load_custom_dictionary(self):
        """Load a custom CIF dictionary file."""
        try:
            file_filter = "CIF Dictionary Files (*.dic);;All Files (*.*)"
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select CIF Dictionary File", "", file_filter)
            
            if not file_path:
                return  # User cancelled
            
            # Test if the file can be loaded
            from utils.cif_dictionary_manager import CIFDictionaryManager
            from utils.cif_format_converter import CIFFormatConverter
            
            # Show loading message
            self.status_bar.showMessage("Loading dictionary...")
            
            # Create new dictionary manager with custom path
            new_dict_manager = CIFDictionaryManager(file_path)
            
            # Test that it loads correctly by accessing the mappings
            # This will trigger the lazy loading and catch any parse errors
            new_dict_manager._ensure_loaded()
            
            # Check that the dictionary actually contains mappings
            if not new_dict_manager._legacy_to_modern and not new_dict_manager._modern_to_legacy:
                raise ValueError("The selected file does not appear to contain valid CIF dictionary mappings.")
            
            # If we get here, the dictionary loaded successfully
            self.dict_manager = new_dict_manager
            self.format_converter = CIFFormatConverter(self.dict_manager)
            
            # Update data name validator with new dictionary manager
            self.data_name_validator = DataNameValidator(self.dict_manager)
            # Re-setup the syntax highlighter callback
            def _field_validator_callback(field_name: str) -> str:
                result = self.data_name_validator.validate_field(field_name)
                return result.category.value
            self.cif_text_editor.highlighter.set_field_validator(_field_validator_callback)
            self.cif_text_editor.highlighter.rehighlight()
            
            # Update status displays
            self.update_dictionary_status()
            self.status_bar.showMessage(f"Successfully loaded dictionary: {os.path.basename(file_path)}", 5000)
            
            # Show success message
            QMessageBox.information(self, "Dictionary Loaded", 
                                  f"Successfully loaded CIF dictionary:\n{file_path}")
                                  
        except FileNotFoundError:
            QMessageBox.critical(self, "File Error", 
                               f"Dictionary file not found:\n{file_path}")
            self.status_bar.showMessage("Dictionary loading failed", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Dictionary Error", 
                               f"Failed to load CIF dictionary:\n{str(e)}\n\nPlease ensure the file is a valid CIF dictionary.")
            self.status_bar.showMessage("Dictionary loading failed", 3000)

    def add_additional_dictionary(self):
        """Add an additional CIF dictionary to extend field coverage."""
        try:
            file_filter = "CIF Dictionary Files (*.dic);;All Files (*.*)"
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Additional CIF Dictionary", "", file_filter)
            
            if not file_path:
                return  # User cancelled
            
            # Show loading message
            self.status_bar.showMessage("Adding dictionary...")
            
            # Add the dictionary to the existing manager
            success = self.dict_manager.add_dictionary(file_path)
            
            if success:
                # Update the format converter with the enhanced dictionary manager
                self.format_converter = CIFFormatConverter(self.dict_manager)
                
                # Clear data name validator cache since dictionaries changed
                self.data_name_validator.clear_cache()
                self.cif_text_editor.highlighter.rehighlight()
                
                # Update status displays
                self.update_dictionary_status()
                
                dict_name = os.path.basename(file_path)
                self.status_bar.showMessage(f"Successfully added dictionary: {dict_name}", 5000)
                
                # Get dictionary info for the success message
                dict_info = self.dict_manager.get_dictionary_info()
                total_dicts = dict_info['total_dictionaries']
                total_mappings = dict_info['total_legacy_mappings']
                
                QMessageBox.information(self, "Dictionary Added", 
                                      f"Successfully added CIF dictionary:\n{file_path}\n\n"
                                      f"Total dictionaries loaded: {total_dicts}\n"
                                      f"Total field mappings: {total_mappings}")
            else:
                self.status_bar.showMessage("Failed to add dictionary", 3000)
                                  
        except FileNotFoundError:
            QMessageBox.critical(self, "File Error", 
                               f"Dictionary file not found:\n{file_path}")
            self.status_bar.showMessage("Dictionary adding failed", 3000)
        except ValueError as e:
            QMessageBox.critical(self, "Dictionary Error", 
                               f"Invalid dictionary file:\n{str(e)}")
            self.status_bar.showMessage("Dictionary adding failed", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Dictionary Error", 
                               f"Failed to add CIF dictionary:\n{str(e)}\n\nPlease ensure the file is a valid CIF dictionary.")
            self.status_bar.showMessage("Dictionary adding failed", 3000)

    def show_dictionary_info(self):
        """Show detailed dictionary information dialog."""
        try:
            dialog = DictionaryInfoDialog(self.dict_manager, self)
            self._show_dialog_with_configured_interaction(dialog)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Dictionary info dialog error: {error_details}")
            QMessageBox.critical(self, "Error", 
                               f"Failed to show dictionary information:\n{str(e)}\n\nCheck console for details.")
    
    def show_about_dialog(self):
        """Show the About dialog with version and credits."""
        try:
            dialog = AboutDialog(self)
            self._show_dialog_with_configured_interaction(dialog)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"About dialog error: {error_details}")
            QMessageBox.critical(self, "Error", 
                               f"Failed to show About dialog:\n{str(e)}")

    def show_syntax_highlighting_guide(self):
        """Show a quick explanation of syntax highlighting colours and styles."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Syntax Highlighting Guide")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setTextFormat(Qt.TextFormat.RichText)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.setText(self.cif_text_editor.highlighter.get_highlighting_guide_html())
        self._show_dialog_with_configured_interaction(dialog)
    
    def validate_data_names(self):
        """Validate all data names in the current CIF against dictionaries."""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "No CIF content to validate.")
            return
        
        try:
            # Clear validator cache and run validation
            self.data_name_validator.clear_cache()
            report = self.data_name_validator.validate_cif_content(content)
            
            # Show dialog
            dialog = DataNameValidationDialog(report, self.data_name_validator, self)
            
            # Connect the changes_requested signal to apply actions and refresh
            def on_changes_requested():
                self._apply_validation_actions(dialog)
                # Clear cache and re-run validation
                self.data_name_validator.clear_cache()
                new_content = self.text_editor.toPlainText()
                new_report = self.data_name_validator.validate_cif_content(new_content)
                dialog.refresh_validation(new_report)
            
            dialog.changes_requested.connect(on_changes_requested)
            
            # Show dialog with configured editor interaction behavior.
            self._show_dialog_with_configured_interaction(
                dialog,
                "dialogs.data_name_validation_results_mode"
            )
            
            # If any changes were applied during the session, do final cleanup
            if dialog.has_changes_applied():
                self.data_name_validator.clear_cache()
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Data name validation error: {error_details}")
            QMessageBox.critical(self, "Validation Error", 
                               f"Failed to validate data names:\n{str(e)}\n\nCheck console for details.")

    def validate_data_values(self):
        """Validate all CIF data values against dictionary-defined types and enumerations."""
        from utils.CIF_parser import CIFParser
        from utils.cif_data_validator import CIFDataValidator

        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "No CIF content to validate.")
            return

        try:
            parser = CIFParser()
            parser.parse_file(content)

            validator = CIFDataValidator()
            issues = validator.validate(parser, self.dict_manager)

            dialog = CIFValueValidationDialog(issues, self)

            def _goto(line_number: int):
                """Move the text editor cursor to the given 1-based line."""
                doc = self.text_editor.document()
                block = doc.findBlockByLineNumber(line_number - 1)
                if block.isValid():
                    cursor = self.text_editor.textCursor()
                    cursor.setPosition(block.position())
                    self.text_editor.setTextCursor(cursor)
                    self.text_editor.ensureCursorVisible()

            dialog.navigate_to_line.connect(_goto)

            def _refresh():
                try:
                    fresh_content = self.text_editor.toPlainText()
                    fresh_parser = CIFParser()
                    fresh_parser.parse_file(fresh_content)
                    fresh_validator = CIFDataValidator()
                    fresh_issues = fresh_validator.validate(fresh_parser, self.dict_manager)
                    dialog.update_issues(fresh_issues)
                except Exception as e:
                    import traceback
                    print(traceback.format_exc())
                    QMessageBox.warning(dialog, "Refresh Failed", f"Validation failed:\n{str(e)}")

            dialog.refresh_requested.connect(_refresh)

            self._show_dialog_with_configured_interaction(
                dialog,
                "dialogs.cif_value_validation_mode",
            )

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            QMessageBox.critical(
                self, "Validation Error",
                f"Failed to validate data values:\n{str(e)}\n\nCheck console for details.",
            )

    def _apply_validation_actions(self, dialog: DataNameValidationDialog):
        """
        Apply the actions from the validation dialog.
        
        This handles:
        - Deleting fields marked for deletion
        - Adding modern equivalents alongside deprecated fields (keeping both)
        - Correcting embedded local prefix format (e.g., _chemical_oxdiff_formula → _chemical_oxdiff.formula)
        - Fixing malformed field names (e.g., _diffrn_flux_density → _diffrn.flux_density)
        - The dialog already updates the validator's allowed lists
        """
        content = self.text_editor.toPlainText()
        modified = False
        
        # Get fields to delete
        fields_to_delete = dialog.get_fields_to_delete()
        
        # Get deprecated updates (old_name -> new_name) - now we ADD modern alongside deprecated
        deprecated_updates = dialog.get_deprecated_updates()
        
        # Get format corrections (old_name -> corrected_name)
        format_corrections = dialog.get_format_corrections()
        
        # Get malformed fixes (old_name -> correct_name) - these are renames, same as format corrections
        malformed_fixes = dialog.get_malformed_fixes()
        # Merge malformed fixes into format_corrections since they are handled identically
        format_corrections.update(malformed_fixes)
        
        # First, check which modern fields already exist (to avoid duplicates)
        existing_fields = set()
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('_'):
                parts = stripped.split(None, 1)
                if parts:
                    existing_fields.add(parts[0].lower())
        
        # Filter deprecated_updates to only add successor fields that don't already exist
        deprecated_to_add = {}
        for old_name, new_name in deprecated_updates.items():
            if new_name.lower() not in existing_fields:
                deprecated_to_add[old_name] = new_name
        
        if fields_to_delete or deprecated_to_add or format_corrections:
            lines = content.split('\n')
            new_lines = []
            in_multiline = False
            skip_until_semicolon = False
            
            for line in lines:
                # Handle semicolon-delimited multiline values
                stripped = line.strip()
                if stripped.startswith(';'):
                    if skip_until_semicolon:
                        # This is the closing semicolon of a deleted field
                        skip_until_semicolon = False
                        continue
                    in_multiline = not in_multiline
                    new_lines.append(line)
                    continue
                
                if skip_until_semicolon:
                    # Skip lines that are part of a deleted multiline field
                    continue
                
                if in_multiline:
                    new_lines.append(line)
                    continue
                
                # Check if this line contains a field
                if stripped.startswith('_'):
                    parts = stripped.split(None, 1)
                    field_name = parts[0].lower() if parts else ''
                    
                    # Check if field should be deleted
                    if field_name in fields_to_delete:
                        modified = True
                        # Check if this is a multiline value
                        if len(parts) == 1:
                            # Value might be on next line - check for semicolon
                            # We'll handle this by skipping until next non-value line
                            continue
                        elif parts[1].strip().startswith(';'):
                            # Multiline value starting with semicolon
                            skip_until_semicolon = True
                            continue
                        else:
                            # Single line value, skip this line
                            continue
                    
                    # Check if we should add modern equivalent after deprecated field
                    if field_name in deprecated_to_add:
                        new_name = deprecated_to_add[field_name]
                        # Keep the original deprecated line
                        new_lines.append(line)
                        # Add the modern equivalent with the same value after it
                        if len(parts) > 1:
                            # Field has value on same line
                            new_lines.append(f"{new_name} {parts[1]}")
                        else:
                            # Field name only (value on next line) - just add the name
                            new_lines.append(new_name)
                        modified = True
                        continue
                    
                    # Check if field should have format corrected (embedded local prefix)
                    if field_name in format_corrections:
                        corrected_name = format_corrections[field_name]
                        if len(parts) > 1:
                            # Field has value on same line
                            new_lines.append(f"{corrected_name} {parts[1]}")
                        else:
                            # Field name only
                            new_lines.append(corrected_name)
                        modified = True
                        continue
                
                new_lines.append(line)
            
            if modified:
                new_content = '\n'.join(new_lines)
                self.text_editor.setText(new_content)
                self.modified = True
                self.update_status_bar()
                
                # Show summary of changes
                changes_summary = []
                if fields_to_delete:
                    changes_summary.append(f"Deleted {len(fields_to_delete)} field(s)")
                if deprecated_to_add:
                    changes_summary.append(f"Added successors for {len(deprecated_to_add)} deprecated field(s)")
                # format_corrections now includes both embedded prefix fixes and malformed fixes
                num_format = len(format_corrections) - len(malformed_fixes)
                if num_format > 0:
                    changes_summary.append(f"Corrected format of {num_format} field(s)")
                if malformed_fixes:
                    changes_summary.append(f"Fixed {len(malformed_fixes)} malformed field name(s)")
                
                QMessageBox.information(
                    self, 
                    "Changes Applied",
                    "The following changes were applied:\n• " + "\n• ".join(changes_summary)
                )
    
    def show_editor_settings(self):
        """Open editor settings dialog."""
        dialog = EditorSettingsDialog(
            self,
            on_settings_changed=self._apply_editor_settings
        )
        result = self._show_dialog_with_configured_interaction(dialog)
        
        # If user clicked OK, settings were already applied by the callback
        # If user clicked Cancel, no changes were made
    
    def _apply_editor_settings(self, settings):
        """Apply editor settings after user confirms in dialog."""
        try:
            # Update text editor with new settings (use cif_text_editor wrapper, not internal text_editor)
            self.cif_text_editor.apply_settings_dict(settings)
        except Exception as e:
            print(f"Error applying editor settings: {e}")
    
    def suggest_dictionaries(self):
        """Analyze current CIF content and suggest relevant dictionaries."""
        try:
            # Get current CIF content
            cif_content = self.text_editor.toPlainText().strip()
            
            if not cif_content:
                QMessageBox.information(self, "No CIF Content", 
                                      "Please open or write a CIF file first to get dictionary suggestions.")
                return
            
            # Analyze CIF and get suggestions
            suggestions = self.dict_manager.suggest_dictionaries_for_cif(cif_content)
            cif_format = self.dict_manager.detect_cif_format(cif_content)
            
            # Status update callback
            def update_status(message: str):
                """Update the status bar with a message."""
                self.status_bar.showMessage(message, 5000)
                self.update_dictionary_status()
            
            # Show suggestions dialog with dictionary manager for downloading
            show_dictionary_suggestions(
                suggestions, 
                cif_format, 
                None,  # Deprecated load_callback
                self.dict_manager,  # Dictionary manager for downloading
                update_status,  # Status update callback
                self
            )
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Dictionary suggestion error: {error_details}")
            QMessageBox.critical(self, "Error", 
                               f"Failed to analyze CIF for dictionary suggestions:\n{str(e)}\n\nCheck console for details.")
    
    def prompt_for_dictionary_suggestions(self, cif_content: str):
        """Prompt user to get dictionary suggestions when opening a CIF file."""
        try:
            # Quick check if there are any potential suggestions
            suggestions = self.dict_manager.suggest_dictionaries_for_cif(cif_content)
            
            if not suggestions:
                return  # No suggestions available, don't prompt
            
            # Ask user if they want to see dictionary suggestions
            reply = QMessageBox.question(
                self, 
                "Dictionary Suggestions Available",
                f"This CIF file appears to contain specialized data that could benefit from additional dictionaries.\n\n"
                f"Found {len(suggestions)} dictionary suggestion(s) that may enhance field validation and recognition.\n\n"
                "Would you like to see the suggestions?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Use existing suggest_dictionaries method to show the dialog
                self.suggest_dictionaries()
                
        except Exception as e:
            # Don't show error for this - it's just a convenience prompt
            print(f"Dictionary suggestion prompt error: {e}")
    
    
    def _ensure_field_rules_validated(self) -> bool:
        """
        Ensure field definitions are validated before starting checks.
        Returns True if validation passed or was skipped, False if cancelled.
        """
        # Only validate custom field definitions (built-in ones are assumed correct)
        if self.current_field_set != 'Custom' or not self.custom_field_rules_file:
            return True
        
        try:
            # Read the field definition file
            with open(self.custom_field_rules_file, 'r', encoding='utf-8') as f:
                field_rules_content = f.read()
            
            # Get CIF content for format analysis
            cif_content = self.text_editor.toPlainText() if hasattr(self, 'text_editor') else None
            
            # Validate the field definitions
            validation_result = self.field_rules_validator.validate_field_rules(
                field_rules_content, cif_content
            )
            
            if validation_result.has_issues:
                reply = QMessageBox.question(
                    self, "Field Definition Issues Found",
                    f"Issues found in field definitions that may affect checking:\n\n"
                    f"• {len(validation_result.issues)} issues detected\n"
                    f"• Target CIF format: {validation_result.cif_format_detected}\n\n"
                    "It's recommended to fix these issues before starting checks.\n"
                    "Would you like to review and fix them now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Show validation dialog
                    dialog = FieldRulesValidationDialog(
                        validation_result, field_rules_content, self.custom_field_rules_file,
                        self.field_rules_validator, self
                    )
                    
                    # Connect validation completion signal
                    dialog.validation_completed.connect(
                        lambda fixed_content, changes: self._on_validation_completed(
                            self.custom_field_rules_file, fixed_content, changes
                        )
                    )
                    
                    return self._show_dialog_with_configured_interaction(dialog) == QDialog.DialogCode.Accepted
                
                # User chose to proceed without fixing
                return True
            
            # No issues found
            return True
            
        except Exception as e:
            QMessageBox.critical(
                self, "Validation Error",
                f"Failed to validate field definitions:\n{str(e)}\n\n"
                "Proceeding without validation."
            )
            return True
    
    def validate_field_rules(self):
        """Manual field definition validation (Settings menu)."""
        # If we have a custom field rules file loaded (from Custom or User selection), validate it
        if self.custom_field_rules_file:
            # Validate the current custom field definition file
            self._validate_field_rules_file(self.custom_field_rules_file)
        else:
            # Ask user to select a file to validate
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Field Definition File to Validate", "",
                "Field Rules Files (*.cif_rules);;All Files (*)"
            )
            
            if file_path:
                self._validate_field_rules_file(file_path)
    
    def open_config_directory(self):
        """
        Open the CIVET configuration directory in the system file explorer.
        
        Creates the directory if it doesn't exist and shows information about
        what configuration files can be placed there.
        """
        import subprocess
        
        try:
            # Ensure config directory exists
            config_dir = ensure_user_config_directory()
            
            # Open in file explorer
            if sys.platform == 'win32':
                os.startfile(str(config_dir))
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(config_dir)], check=True)
            else:
                subprocess.run(['xdg-open', str(config_dir)], check=True)
            
            # Show info about the config directory
            prefix_source = get_prefix_data_source()
            user_prefixes_file = get_user_prefixes_path()
            
            info_text = (
                f"<b>Configuration Directory:</b><br>"
                f"<code>{config_dir}</code><br><br>"
                f"<b>Contents:</b><br>"
                f"• <b>settings.json</b> - Editor preferences<br>"
                f"• <b>registered_prefixes.json</b> - Custom CIF prefixes<br>"
                f"• <b>dictionaries/</b> - User-downloaded dictionaries<br>"
                f"• <b>field_rules/</b> - Custom validation rules<br><br>"
                f"<b>Current Prefix Source:</b><br>"
                f"<code>{prefix_source}</code>"
            )
            
            if not user_prefixes_file.exists():
                info_text += (
                    "<br><br><b>Tip:</b> To customize registered prefixes, copy "
                    "<code>registered_prefixes.json</code> from the GitHub repository "
                    "to this config folder and edit as needed. "
                    "Restart CIVET to apply changes."
                )
            
            QMessageBox.information(self, "CIVET Config Directory", info_text)
            
        except Exception as e:
            QMessageBox.warning(
                self, "Error",
                f"Could not open config directory:\n{str(e)}"
            )
    
    def open_user_field_rules_directory(self):
        """
        Open the user field rules directory in the system file explorer.
        
        Creates the directory if it doesn't exist and shows information about
        what field rules files can be placed there.
        """
        import subprocess
        from utils.user_field_rules import ensure_user_field_rules_directory
        
        try:
            # Ensure user field rules directory exists
            rules_dir = ensure_user_field_rules_directory()
            
            # Open in file explorer
            if sys.platform == 'win32':
                os.startfile(str(rules_dir))
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(rules_dir)], check=True)
            else:
                subprocess.run(['xdg-open', str(rules_dir)], check=True)
            
            # Show info about the field rules directory
            info_text = (
                f"<b>User Field Rules Directory:</b><br>"
                f"<code>{rules_dir}</code><br><br>"
                f"<b>File Format:</b> .cif_rules files (text format)<br><br>"
                f"<b>How to Use:</b><br>"
                f"1. Create .cif_rules files with your field definitions<br>"
                f"2. Place them in this directory<br>"
                f"3. They will appear as 'User: [filename]' in the field set selector<br>"
                f"4. Restart CIVET if files don't appear<br><br>"
                f"<b>File Format Example:</b><br>"
                f"<code>_diffrn.ambient_temperature 293  # Default value<br>"
                f"_diffrn.ambient_temperature 100      # Additional suggestion</code>"
            )
            
            QMessageBox.information(self, "User Field Rules Directory", info_text)
            
        except Exception as e:
            QMessageBox.warning(
                self, "Error",
                f"Could not open user field rules directory:\n{str(e)}"
            )
    
    def reload_prefix_configuration(self):
        """
        Reload the registered prefixes configuration from JSON files.
        
        Useful after editing the registered_prefixes.json file in the config directory.
        """
        from utils.registered_prefixes import reload_prefix_data, get_prefix_data_source, get_registered_prefixes
        
        try:
            source = reload_prefix_data()
            prefix_count = len(get_registered_prefixes())
            
            # Clear the data name validator cache to use new prefixes
            if hasattr(self, 'data_name_validator'):
                self.data_name_validator.clear_cache()
            
            # Note: We don't call rehighlight() here because it can be very slow
            # for large documents. The new prefixes will be used on the next
            # highlighting pass (e.g., when editing or scrolling).
            
            QMessageBox.information(
                self, "Prefix Configuration Reloaded",
                f"Successfully loaded {prefix_count} registered prefixes.\n\n"
                f"Source: {source}\n\n"
                "Note: Syntax highlighting will update as you edit the document."
            )
            
        except Exception as e:
            QMessageBox.warning(
                self, "Reload Error",
                f"Failed to reload prefix configuration:\n{str(e)}"
            )
    
    def show_recognised_prefixes(self):
        """Show dialog with all recognised CIF data name prefixes."""
        try:
            dialog = RecognisedPrefixesDialog(self.data_name_validator, self)
            self._show_dialog_with_configured_interaction(dialog)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Recognised prefixes dialog error: {error_details}")
            QMessageBox.critical(
                self, "Error",
                f"Failed to show recognised prefixes dialog:\n{str(e)}"
            )
    
    def _validate_field_rules_file(self, file_path: str):
        """Validate a specific field definition file."""
        try:
            # Read the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                field_rules_content = f.read()
            
            # Get CIF content for format analysis if available
            cif_content = self.text_editor.toPlainText() if hasattr(self, 'text_editor') else None
            
            # Validate the field definitions
            validation_result = self.field_rules_validator.validate_field_rules(
                field_rules_content, cif_content
            )
            
            # Show validation dialog
            dialog = FieldRulesValidationDialog(
                validation_result, field_rules_content, file_path,
                self.field_rules_validator, self
            )
            
            # Connect validation completion signal if this is the current custom file
            if file_path == self.custom_field_rules_file:
                dialog.validation_completed.connect(
                    lambda fixed_content, changes: self._on_validation_completed(
                        file_path, fixed_content, changes
                    )
                )
            
            self._show_dialog_with_configured_interaction(dialog)
            
        except Exception as e:
            QMessageBox.critical(
                self, "Validation Error",
                f"Failed to validate field definition file:\n{str(e)}"
            )
