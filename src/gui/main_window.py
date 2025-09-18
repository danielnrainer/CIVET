from PyQt6.QtWidgets import (QMainWindow, QWidget, QTextEdit, 
                           QPushButton, QVBoxLayout, QHBoxLayout, QMenu,
                           QFileDialog, QMessageBox, QLineEdit, QCheckBox, 
                           QDialog, QLabel, QFontDialog, QGroupBox, QRadioButton,
                           QButtonGroup)
from PyQt6.QtCore import Qt, QRegularExpression, QTimer
from PyQt6.QtGui import (QTextCharFormat, QSyntaxHighlighter, QColor, QFont, 
                        QFontMetrics, QTextCursor, QTextDocument)
import os
import json
from typing import Dict, List, Tuple
from utils.CIF_field_parsing import CIFFieldChecker
from utils.CIF_parser import CIFParser
from utils.cif_dictionary_manager import CIFDictionaryManager, CIFVersion
from utils.cif_format_converter import CIFFormatConverter
from utils.field_rules_validator import FieldRulesValidator
from .dialogs import (CIFInputDialog, MultilineInputDialog, CheckConfigDialog, 
                     RESULT_ABORT, RESULT_STOP_SAVE)
from .dialogs.dictionary_info_dialog import DictionaryInfoDialog
from .dialogs.field_conflict_dialog import FieldConflictDialog
from .dialogs.field_rules_validation_dialog import FieldRulesValidationDialog
from .dialogs.dictionary_suggestion_dialog import show_dictionary_suggestions
from .editor import CIFSyntaxHighlighter, CIFTextEditor


class CIFEditor(QMainWindow):
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
        self.current_cif_version = CIFVersion.UNKNOWN
        
        # Initialize field definition validator
        self.field_rules_validator = FieldRulesValidator(self.dict_manager, self.format_converter)
        
        # Load field definition set from config directory
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        definitions_path = os.path.join(project_root, 'config', 'field_rules')
        self.field_checker.load_field_set('3DED', os.path.join(definitions_path, '3ded.cif_rules'))
        self.field_checker.load_field_set('HP', os.path.join(definitions_path, 'hp.cif_rules'))
        
        # Field definition selection variables
        self.custom_field_rules_file = None
        self.current_field_set = '3DED'  # Default to 3DED
        
        self.init_ui()
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
        self.setWindowTitle("EDCIF-check")
        self.setGeometry(100, 100, 900, 700)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create status bar
        self.status_bar = self.statusBar()
        self.path_label = QLabel()
        self.cursor_label = QLabel()
        self.cif_version_label = QLabel("CIF Version: Unknown")
        self.dictionary_label = QLabel("Dictionary: Default")
        self.status_bar.addPermanentWidget(self.path_label)
        self.status_bar.addPermanentWidget(self.cif_version_label)
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
        
        # Radio buttons for built-in field definitions
        radio_layout = QHBoxLayout()
        
        self.radio_3ded = QRadioButton("3D ED")
        self.radio_3ded.setChecked(True)  # Default selection
        self.radio_3ded.toggled.connect(lambda checked: self.set_field_set('3DED') if checked else None)
        
        self.radio_custom = QRadioButton("Custom File")
        self.radio_custom.toggled.connect(lambda checked: self.set_field_set('Custom') if checked else None)
        
        # Add radio buttons to group and layout
        self.field_rules_group.addButton(self.radio_3ded)
        self.field_rules_group.addButton(self.radio_custom)
        
        radio_layout.addWidget(self.radio_3ded)
        radio_layout.addWidget(self.radio_custom)
        
        # Custom file selection layout
        custom_file_layout = QHBoxLayout()
        self.custom_file_button = QPushButton("Select Custom File...")
        self.custom_file_button.clicked.connect(self.select_custom_field_rules_file)
        self.custom_file_button.setEnabled(False)  # Initially disabled
        
        self.custom_file_label = QLabel("No custom file selected")
        self.custom_file_label.setStyleSheet("color: gray; font-style: italic;")
        
        custom_file_layout.addWidget(self.custom_file_button)
        custom_file_layout.addWidget(self.custom_file_label)
        custom_file_layout.addStretch()
        
        field_selection_layout.addLayout(radio_layout)
        field_selection_layout.addLayout(custom_file_layout)
        
        main_layout.addWidget(field_selection_group)
        
        # Create button layout
        button_layout = QHBoxLayout()
        
        # Create buttons
        start_checks_button = QPushButton("Start Checks")
        start_checks_button.clicked.connect(self.start_checks)
        refine_details_button = QPushButton("Edit Refinement Details")
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
        save_as_action.triggered.connect(self.save_file_as)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        
        # Actions menu
        action_menu = menubar.addMenu("Actions")
        
        start_checks_action = action_menu.addAction("Start Checks")
        start_checks_action.triggered.connect(self.start_checks)
        
        refine_details_action = action_menu.addAction("Edit Refinement Details")
        refine_details_action.triggered.connect(self.check_refine_special_details)
        
        format_action = action_menu.addAction("Reformat File")
        format_action.triggered.connect(self.reformat_file)

        # CIF Format menu
        format_menu = menubar.addMenu("CIF Format")
        
        detect_version_action = format_menu.addAction("Detect CIF Version")
        detect_version_action.triggered.connect(self.detect_cif_version)
        
        format_menu.addSeparator()
        
        convert_to_cif1_action = format_menu.addAction("Convert to CIF1")
        convert_to_cif1_action.triggered.connect(self.convert_to_cif1)
        
        convert_to_cif2_action = format_menu.addAction("Convert to CIF2")
        convert_to_cif2_action.triggered.connect(self.convert_to_cif2)
        
        format_menu.addSeparator()
        
        fix_mixed_action = format_menu.addAction("Fix Mixed Format")
        fix_mixed_action.triggered.connect(self.fix_mixed_format)
        
        resolve_aliases_action = format_menu.addAction("Resolve Field Aliases")
        resolve_aliases_action.triggered.connect(self.standardize_cif_fields)

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
        
        settings_menu.addSeparator()
        
        load_dict_action = settings_menu.addAction("Replace Core CIF Dictionary...")
        load_dict_action.triggered.connect(self.load_custom_dictionary)
        
        add_dict_action = settings_menu.addAction("Add Additional CIF Dictionary...")
        add_dict_action.triggered.connect(self.add_additional_dictionary)
        
        suggest_dict_action = settings_menu.addAction("Suggest Dictionaries for Current CIF...")
        suggest_dict_action.triggered.connect(self.suggest_dictionaries)
        
        settings_menu.addSeparator()
        
        # Field definition validation
        validate_field_defs_action = settings_menu.addAction("Validate Field Rules...")
        validate_field_defs_action.triggered.connect(self.validate_field_rules)
        
        # Enable undo/redo
        self.text_editor.setUndoRedoEnabled(True)

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
            with open(filepath, "r") as file:
                content = file.read()
            self.text_editor.setText(content)
            self.current_file = filepath
            self.modified = False
            
            # Detect CIF version
            self.detect_and_update_cif_version(content)
            
            self.update_status_bar()
            self.add_to_recent_files(filepath)
            self.setWindowTitle(f"EDCIF-check - {filepath}")
            
            # Prompt for dictionary suggestions after opening CIF file
            if not initial:  # Don't prompt during initial app startup
                self.prompt_for_dictionary_suggestions(content)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")

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

    def validate_cif(self):
        """Basic CIF syntax validation"""
        text = self.text_editor.toPlainText()
        lines = text.splitlines()
        errors = []
        
        # Check for basic CIF syntax rules
        in_multiline = False
        for i, line in enumerate(lines, 1):
            # Check for semicolon-delimited values
            if line.startswith(';'):
                in_multiline = not in_multiline
                continue
                
            if not in_multiline:
                # Check for field names
                if line.strip() and not line.strip().startswith('#'):
                    if line.strip().startswith('_'):
                        parts = line.split(maxsplit=1)
                        if len(parts) < 2:
                            errors.append(f"Line {i}: Field '{line.strip()}' has no value")
                    # Check quoted values
                    elif "'" in line or '"' in line:
                        quote_char = "'" if "'" in line else '"'
                        if line.count(quote_char) % 2 != 0:
                            errors.append(f"Line {i}: Unmatched quote")
        
        if in_multiline:
            errors.append("Unclosed multiline value (missing semicolon)")
            
        return errors

    def save_to_file(self, filepath):
        try:
            with open(filepath, "w") as file:
                content = self.text_editor.toPlainText().strip()
                file.write(content)
            self.current_file = filepath
            self.modified = False
            self.update_status_bar()
            QMessageBox.information(self, "Success", 
                                  f"File saved successfully:\n{filepath}")
            self.setWindowTitle(f"EDCIF-check - {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")

    def check_line(self, prefix, default_value=None, multiline=False, description=""):
        """Check and potentially update a CIF field value."""
        removable_chars = "'"
        lines = self.text_editor.toPlainText().splitlines()
        
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                current_value = " ".join(line.split()[1:])
                value, result = CIFInputDialog.getText(
                    self, "Edit Line",
                    f"Edit the line:\n{line}\n\nDescription: {description}\n\nSuggested value: {default_value}\n\n",
                    current_value, default_value)
                
                if result in [CIFInputDialog.RESULT_ABORT, CIFInputDialog.RESULT_STOP_SAVE]:
                    return result
                elif result == QDialog.DialogCode.Accepted and value:
                    # Preserve original quoting style - only quote if value has spaces or special chars
                    stripped_value = value.strip(removable_chars)
                    if ' ' in stripped_value or ',' in stripped_value:
                        formatted_value = f"'{stripped_value}'"
                    else:
                        formatted_value = stripped_value
                    lines[i] = f"{prefix} {formatted_value}"
                    self.text_editor.setText("\n".join(lines))
                return result

        QMessageBox.warning(self, "Line Not Found",
                          f"The line starting with '{prefix}' was not found.")
        return self.add_missing_line(prefix, lines, default_value, multiline, description)

    def add_missing_line(self, prefix, lines, default_value=None, multiline=False, description=""):
        """Add a missing CIF field with value."""
        value, result = CIFInputDialog.getText(
            self, "Add Missing Line",
            f"The line starting with '{prefix}' is missing.\n\nDescription: {description}\nSuggested value: {default_value}",
            default_value if default_value else "", default_value)
        
        if result in [CIFInputDialog.RESULT_ABORT, CIFInputDialog.RESULT_STOP_SAVE]:
            return result
            
        removable_chars = "'"
        if result != QDialog.DialogCode.Accepted:
            return result
            
        if not value:
            value = "?"

        stripped_value = value.strip(removable_chars)
        if multiline:
            insert_index = len(lines)
            for i, line in enumerate(lines):
                if line.startswith(prefix.split("_")[0]):
                    insert_index = i + 1
            lines.insert(insert_index, 
                        f"{prefix} \n;\n{stripped_value}\n;")
        else:
            # Only quote if value has spaces or special chars
            if ' ' in stripped_value or ',' in stripped_value:
                formatted_value = f"'{stripped_value}'"
            else:
                formatted_value = stripped_value
            lines.append(f"{prefix} {formatted_value}")
        
        self.text_editor.setText("\n".join(lines))
        return result    
    
    def check_line_with_config(self, prefix, default_value=None, multiline=False, description="", config=None):
        """Check and potentially update a CIF field value with configuration options."""
        if config is None:
            config = {'auto_fill_missing': False, 'skip_matching_defaults': False}
        
        removable_chars = "'"
        lines = self.text_editor.toPlainText().splitlines()
        
        # Check if field exists
        field_found = False
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                field_found = True
                current_value = " ".join(line.split()[1:]).strip(removable_chars)
                
                # If skip_matching_defaults is enabled and current value matches default
                if config.get('skip_matching_defaults', False) and default_value:
                    # Clean both values for comparison
                    clean_current = current_value.strip().strip("'\"")
                    clean_default = str(default_value).strip().strip("'\"")
                    if clean_current == clean_default:
                        return QDialog.DialogCode.Accepted  # Skip this field
                
                # Show normal edit dialog
                value, result = CIFInputDialog.getText(
                    self, "Edit Line",
                    f"Edit the line:\n{line}\n\nDescription: {description}\n\nSuggested value: {default_value}\n\n",
                    current_value, default_value)
                
                if result in [CIFInputDialog.RESULT_ABORT, CIFInputDialog.RESULT_STOP_SAVE]:
                    return result
                elif result == QDialog.DialogCode.Accepted and value:
                    # Preserve original quoting style - only quote if value has spaces or special chars
                    stripped_value = value.strip(removable_chars)
                    if ' ' in stripped_value or ',' in stripped_value:
                        formatted_value = f"'{stripped_value}'"
                    else:
                        formatted_value = stripped_value
                    lines[i] = f"{prefix} {formatted_value}"
                    self.text_editor.setText("\n".join(lines))
                return result
        
        # Field not found - handle missing field
        if not field_found:
            return self.add_missing_line_with_config(prefix, lines, default_value, multiline, description, config)
        
        return QDialog.DialogCode.Accepted
    
    def add_missing_line_with_config(self, prefix, lines, default_value=None, multiline=False, description="", config=None):
        """Add a missing CIF field with value, respecting configuration options."""
        if config is None:
            config = {'auto_fill_missing': False, 'skip_matching_defaults': False}
        
        # If auto_fill_missing is enabled, add the field silently with default value
        if config.get('auto_fill_missing', False) and default_value:
            removable_chars = "'"
            stripped_value = str(default_value).strip(removable_chars)
            
            if multiline:
                insert_index = len(lines)
                for i, line in enumerate(lines):
                    if line.startswith(prefix.split("_")[0]):
                        insert_index = i + 1
                lines.insert(insert_index, 
                            f"{prefix} \n;\n{stripped_value}\n;")
            else:
                # Only quote if value has spaces or special chars
                if ' ' in stripped_value or ',' in stripped_value:
                    formatted_value = f"'{stripped_value}'"
                else:
                    formatted_value = stripped_value
                lines.append(f"{prefix} {formatted_value}")
            
            self.text_editor.setText("\n".join(lines))
            return QDialog.DialogCode.Accepted
        
        # Otherwise, use the normal missing line dialog
        return self.add_missing_line(prefix, lines, default_value, multiline, description)
    
    def check_refine_special_details(self):
        """Check and edit _refine_special_details field, creating it if needed."""
        content = self.text_editor.toPlainText()
        
        # Parse the CIF content using the new parser
        self.cif_parser.parse_file(content)
        
        # Detect CIF version to determine the correct field name
        detected_version = self.dict_manager.detect_cif_version(content)
        
        # Determine the appropriate field name based on CIF version
        if detected_version == CIFVersion.CIF2:
            field_name = '_refine.special_details'
        else:
            # Default to CIF1 format (covers CIF1, UNKNOWN, and MIXED)
            field_name = '_refine_special_details'
        
        template = (
            "STRUCTURE REFINEMENT\n"
            "- Refinement method\n"
            "- Special constraints and restraints\n"
            "- Special treatments"
        )
        
        # Get current value from the appropriate field name, or use template
        current_value = self.cif_parser.get_field_value(field_name)
        if current_value is None:
            current_value = template
        
        # Open dialog for editing
        dialog = MultilineInputDialog(current_value, self)
        dialog.setWindowTitle("Edit Refinement Special Details")
        result = dialog.exec()
        
        if result in [MultilineInputDialog.RESULT_ABORT, MultilineInputDialog.RESULT_STOP_SAVE]:
            return result
        elif result == QDialog.DialogCode.Accepted:
            updated_content = dialog.getText()
            
            # Update the field in the parser using the appropriate field name
            self.cif_parser.set_field_value(field_name, updated_content)
            
            # Generate updated CIF content and update the text editor
            updated_cif = self.cif_parser.generate_cif_content()
            self.text_editor.setText(updated_cif)
            self.modified = True
            self.update_status_bar()
            
            return QDialog.DialogCode.Accepted
        
        return QDialog.DialogCode.Rejected

    def set_field_set(self, field_set_name):
        """Set the current field set selection."""
        self.current_field_set = field_set_name
        
        # Enable/disable custom file button based on selection
        if field_set_name == 'Custom':
            self.custom_file_button.setEnabled(True)
            if not self.custom_field_rules_file:
                self.custom_file_label.setText("Please select a custom file")
                self.custom_file_label.setStyleSheet("color: red; font-style: italic;")
        else:
            self.custom_file_button.setEnabled(False)
            self.custom_file_label.setText("No custom file selected")
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
                    "• Mixed CIF1/CIF2 formats\n"
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
                        
                        if dialog.exec() == QDialog.DialogCode.Accepted:
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
    
    def start_checks(self):
        """Start checking CIF fields using the selected field definition set."""
        # Validate field set selection
        if self.current_field_set == 'Custom':
            if not self.custom_field_rules_file:
                QMessageBox.warning(
                    self,
                    "No Custom File Selected",
                    "Please select a custom field definition file first."
                )
                return
            
            # Check if custom field set is loaded
            fields = self.field_checker.get_field_set('Custom')
            if not fields:
                QMessageBox.warning(
                    self,
                    "Custom File Not Loaded",
                    "The custom field definition file could not be loaded. "
                    "Please select a valid file."
                )
                return
        
        # Mandatory validation before starting checks (if not done already)
        if not self._ensure_field_rules_validated():
            return  # User cancelled or validation failed
        
        # Show configuration dialog first
        config_dialog = CheckConfigDialog(self)
        if config_dialog.exec() != QDialog.DialogCode.Accepted:
            return  # User cancelled
        
        # Get configuration settings
        config = config_dialog.get_config()
        
        # Store the initial state for potential restore
        initial_state = self.text_editor.toPlainText()
        
        # Single field set processing
        success = self._process_single_field_set(config, initial_state)
        if not success:
            return
        
        # If we get here, checks completed successfully
        if config.get('reformat_after_checks', False):
            self.reformat_file()
        
        self.setWindowTitle("EDCIF-check")
        QMessageBox.information(self, "Checks Complete", "Field checking completed successfully!")

    def _process_single_field_set(self, config, initial_state):
        """Process a single field set (3DED, HP, or Custom)."""
        try:
            # Get the selected field set
            fields = self.field_checker.get_field_set(self.current_field_set)
            if not fields:
                QMessageBox.warning(self, "Warning", f"No {self.current_field_set} field definitions loaded.")
                return False
            
            # Update window title to show which field set is being used
            field_set_display = {
                '3DED': '3D ED',
                'HP': 'HP',
                'Custom': f'Custom ({os.path.basename(self.custom_field_rules_file) if self.custom_field_rules_file else "Unknown"})'
            }
            
            self.setWindowTitle(f"EDCIF-check - Checking with {field_set_display.get(self.current_field_set, self.current_field_set)} fields")
            
            # Parse the current CIF content
            content = self.text_editor.toPlainText()
            self.cif_parser.parse_file(content)
            
            # For custom sets, handle DELETE/EDIT operations first
            if self.current_field_set == 'Custom':
                current_content = content
                operations_applied = []
                
                for field_def in fields:
                    if hasattr(field_def, 'action'):
                        if field_def.action == 'DELETE':
                            lines = current_content.splitlines()
                            lines, deleted = self.field_checker._delete_field(lines, field_def.name)
                            if deleted:
                                operations_applied.append(f"DELETED: {field_def.name}")
                                current_content = '\n'.join(lines)
                        elif field_def.action == 'EDIT':
                            lines = current_content.splitlines()
                            lines, edited = self.field_checker._edit_field(lines, field_def.name, field_def.default_value)
                            if edited:
                                operations_applied.append(f"EDITED: {field_def.name} -> {field_def.default_value}")
                                current_content = '\n'.join(lines)
                
                # Update content after DELETE/EDIT operations
                if operations_applied:
                    self.text_editor.setText(current_content)
                    ops_summary = '\n'.join(operations_applied)
                    QMessageBox.information(self, "Operations Applied", 
                                          f"Applied {len(operations_applied)} operations:\n\n{ops_summary}")
            
            # Process CHECK actions (standard field checking)
            for field_def in fields:
                # Skip DELETE/EDIT actions as they're already processed
                if hasattr(field_def, 'action') and field_def.action in ['DELETE', 'EDIT']:
                    continue
                    
                result = self.check_line_with_config(
                    field_def.name,
                    field_def.default_value,
                    False,
                    field_def.description,
                    config
                )
                
                if result == RESULT_ABORT:
                    self.text_editor.setText(initial_state)
                    self.setWindowTitle("EDCIF-check")
                    QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                    return False
                elif result == RESULT_STOP_SAVE:
                    break
            
            # Apply special 3DED handling if needed
            if self.current_field_set == '3DED':
                self._apply_3ded_special_checks(config, initial_state)
            
            return True
            
        except Exception as e:
            self.text_editor.setText(initial_state)
            self.setWindowTitle("EDCIF-check")
            QMessageBox.critical(self, "Error During Checks", f"An error occurred: {str(e)}")
            return False
    
    def _apply_3ded_special_checks(self, config, initial_state):
        """Apply special 3DED checks for space groups and absolute configuration."""
        sohncke_groups = [1, 3, 4, 5, 16, 17, 18, 19, 20, 21, 22, 23, 24, 75, 76, 77, 78, 79, 80, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 143, 144, 145, 146, 149, 150, 151, 152, 153, 154, 155, 168, 169, 170, 171, 172, 173, 177, 178, 179, 180, 181, 182, 195, 196, 197, 198, 199, 207, 208, 209, 210, 211, 212, 213, 214]
        SG_number = None
        lines = self.text_editor.toPlainText().splitlines()
        
        # Find space group number
        for line in lines:
            if line.startswith("_space_group_IT_number"):
                parts = line.split()
                if len(parts) > 1:
                    try:
                        SG_number = int(parts[1].strip("'\""))
                    except Exception:
                        pass
                break
        
        # Check if we need absolute configuration handling
        if SG_number is not None and SG_number in sohncke_groups:
            found = False
            for line in lines:
                if line.startswith("_chemical_absolute_configuration"):
                    found = True
                    break
            
            if found:
                result = self.check_line_with_config(
                    "_chemical_absolute_configuration", 
                    default_value='dyn', 
                    multiline=False, 
                    description="Specify if/how absolute structure was determined.", 
                    config=config
                )
                if result == RESULT_ABORT:
                    self.text_editor.setText(initial_state)
                    self.setWindowTitle("EDCIF-check")
                    QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                    return False
                elif result == RESULT_STOP_SAVE:
                    return True
            else:
                result = self.add_missing_line_with_config(
                    "_chemical_absolute_configuration", 
                    lines, 
                    default_value='dyn', 
                    multiline=False, 
                    description="Specify if/how absolute structure was determined.", 
                    config=config
                )
                if result == RESULT_ABORT:
                    self.text_editor.setText(initial_state)
                    self.setWindowTitle("EDCIF-check")
                    QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                    return False
                elif result == RESULT_STOP_SAVE:
                    return True
            
            # Check for z-score if configuration is 'dyn'
            lines = self.text_editor.toPlainText().splitlines()  # Re-get lines after potential changes
            chemical_absolute_config_value = None
            for line in lines:
                if line.startswith("_chemical_absolute_configuration") or line.startswith("_chemical.absolute_configuration"):
                    parts = line.split()
                    if len(parts) > 1:
                        chemical_absolute_config_value = parts[1].strip("'\"")
                        break
            
            if chemical_absolute_config_value == 'dyn':
                # Check if _refine_ls.abs_structure_z-score exists
                found_z_score = False
                for line in lines:
                    if line.startswith("_refine_ls.abs_structure_z-score"):
                        found_z_score = True
                        break
                
                if found_z_score:
                    result = self.check_line_with_config(
                        "_refine_ls.abs_structure_z-score", 
                        default_value='', 
                        multiline=False, 
                        description="Z-score for absolute structure determination from dynamical refinement.", 
                        config=config
                    )
                    if result == RESULT_ABORT:
                        self.text_editor.setText(initial_state)
                        self.setWindowTitle("EDCIF-check")
                        QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                        return False
                    elif result == RESULT_STOP_SAVE:
                        return True
                else:
                    result = self.add_missing_line_with_config(
                        "_refine_ls.abs_structure_z-score", 
                        lines, 
                        default_value='', 
                        multiline=False, 
                        description="Z-score for absolute structure determination from dynamical refinement.", 
                        config=config
                    )
                    if result == RESULT_ABORT:
                        self.text_editor.setText(initial_state)
                        self.setWindowTitle("EDCIF-check")
                        QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                        return False
                    elif result == RESULT_STOP_SAVE:
                        return True
        
        return True

    def reformat_file(self):
        """Reformat CIF file to handle long lines and properly format values, preserving semicolon blocks."""
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
        
        # Schedule CIF version detection (delayed to avoid constant updates)
        if hasattr(self, 'version_detect_timer'):
            self.version_detect_timer.stop()
        else:
            self.version_detect_timer = QTimer()
            self.version_detect_timer.setSingleShot(True)
            self.version_detect_timer.timeout.connect(lambda: self.detect_and_update_cif_version())
        
        self.version_detect_timer.start(1000)  # 1 second delay
    
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
    
    def detect_and_update_cif_version(self, content=None):
        """Detect CIF version and update the status display"""
        if content is None:
            content = self.text_editor.toPlainText()
        
        self.current_cif_version = self.dict_manager.detect_cif_version(content)
        self.update_cif_version_display()
    
    def update_cif_version_display(self):
        """Update the CIF version display in the status bar"""
        version_text = {
            CIFVersion.CIF1: "CIF Version: 1.x",
            CIFVersion.CIF2: "CIF Version: 2.0",
            CIFVersion.MIXED: "CIF Version: Mixed (1.x/2.0)",
            CIFVersion.UNKNOWN: "CIF Version: Unknown"
        }
        
        color = {
            CIFVersion.CIF1: "green",
            CIFVersion.CIF2: "blue", 
            CIFVersion.MIXED: "orange",
            CIFVersion.UNKNOWN: "red"
        }
        
        text = version_text.get(self.current_cif_version, "CIF Version: Unknown")
        self.cif_version_label.setText(text)
        self.cif_version_label.setStyleSheet(f"color: {color.get(self.current_cif_version, 'black')}")
    
    def detect_cif_version(self):
        """Menu action to detect and display CIF version information"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        version = self.dict_manager.detect_cif_version(content)
        self.current_cif_version = version
        self.update_cif_version_display()
        
        # Show detailed information
        version_info = {
            CIFVersion.CIF1: "CIF version 1.x detected\nThis file uses traditional CIF1 format.",
            CIFVersion.CIF2: "CIF version 2.0 detected\nThis file uses modern CIF2 format with UTF-8 encoding.",
            CIFVersion.MIXED: "Mixed CIF format detected\nThis file contains both CIF1 and CIF2 elements.\nConsider using 'Fix Mixed Format' to resolve.",
            CIFVersion.UNKNOWN: "Unknown CIF format\nCould not determine CIF version from the content."
        }
        
        QMessageBox.information(self, "CIF Version Detection", 
                              version_info.get(version, "Unknown format detected."))
    
    def convert_to_cif1(self):
        """Convert current CIF content to CIF1 format"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            converted_content, changes = self.format_converter.convert_to_cif1(content)
            if converted_content != content:
                self.text_editor.setText(converted_content)
                self.modified = True
                self.current_cif_version = CIFVersion.CIF1
                self.update_cif_version_display()
                change_summary = f"Made {len(changes)} changes:\n" + "\n".join(changes[:5])
                if len(changes) > 5:
                    change_summary += f"\n... and {len(changes)-5} more"
                QMessageBox.information(self, "Conversion Complete", 
                                      f"File successfully converted to CIF1 format.\n\n{change_summary}")
            else:
                QMessageBox.information(self, "No Changes", 
                                      "File is already in CIF1 format or no conversion was needed.")
        except Exception as e:
            QMessageBox.critical(self, "Conversion Error", 
                               f"Failed to convert to CIF1:\n{str(e)}")
    
    def convert_to_cif2(self):
        """Convert current CIF content to CIF2 format"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            converted_content, changes = self.format_converter.convert_to_cif2(content)
            if converted_content != content:
                self.text_editor.setText(converted_content)
                self.modified = True
                self.current_cif_version = CIFVersion.CIF2
                self.update_cif_version_display()
                change_summary = f"Made {len(changes)} changes:\n" + "\n".join(changes[:5])
                if len(changes) > 5:
                    change_summary += f"\n... and {len(changes)-5} more"
                QMessageBox.information(self, "Conversion Complete", 
                                      f"File successfully converted to CIF2 format.\n" +
                                      f"Note: Save with UTF-8 encoding.\n\n{change_summary}")
            else:
                QMessageBox.information(self, "No Changes", 
                                      "File is already in CIF2 format or no conversion was needed.")
        except Exception as e:
            QMessageBox.critical(self, "Conversion Error", 
                               f"Failed to convert to CIF2:\n{str(e)}")
    
    def fix_mixed_format(self):
        """Fix mixed CIF format by converting to consistent format"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        # First detect current version
        version = self.dict_manager.detect_cif_version(content)
        if version != CIFVersion.MIXED:
            QMessageBox.information(self, "No Mixed Format", 
                                  "File does not appear to have mixed CIF format.")
            return
        
        # Ask user which format to convert to
        reply = QMessageBox.question(self, "Choose Target Format",
                                   "Convert mixed format to:\n\n" +
                                   "Yes: CIF2 (recommended for new files)\n" +
                                   "No: CIF1 (for legacy compatibility)\n" +
                                   "Cancel: Abort conversion",
                                   QMessageBox.StandardButton.Yes |
                                   QMessageBox.StandardButton.No |
                                   QMessageBox.StandardButton.Cancel)
        
        if reply == QMessageBox.StandardButton.Cancel:
            return
        
        try:
            if reply == QMessageBox.StandardButton.Yes:
                # Convert to CIF2
                fixed_content, changes = self.format_converter.fix_mixed_format(content, target_version=CIFVersion.CIF2)
                target_version = CIFVersion.CIF2
                format_name = "CIF2"
            else:
                # Convert to CIF1
                fixed_content, changes = self.format_converter.fix_mixed_format(content, target_version=CIFVersion.CIF1)
                target_version = CIFVersion.CIF1
                format_name = "CIF1"
            
            if fixed_content != content:
                self.text_editor.setText(fixed_content)
                self.modified = True
                self.current_cif_version = target_version
                self.update_cif_version_display()
                change_summary = f"Made {len(changes)} changes:\n" + "\n".join(changes[:5])
                if len(changes) > 5:
                    change_summary += f"\n... and {len(changes)-5} more"
                QMessageBox.information(self, "Format Fixed", 
                                      f"Mixed format successfully resolved to {format_name}.\n\n{change_summary}")
            else:
                QMessageBox.information(self, "No Changes", 
                                      "No format issues were found to fix.")
        except Exception as e:
            QMessageBox.critical(self, "Fix Error", 
                               f"Failed to fix mixed format:\n{str(e)}")

    def standardize_cif_fields(self):
        """Resolve CIF field alias conflicts with user control"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            # Check for alias conflicts first
            conflicts = self.dict_manager.detect_field_aliases_in_cif(content)
            
            if not conflicts:
                QMessageBox.information(self, "No Alias Conflicts", 
                                      "No field alias conflicts were found.\n\n" +
                                      "This tool only resolves cases where the same field " +
                                      "appears in multiple forms (e.g., both _diffrn_source_type " +
                                      "and _diffrn_source_make in the same file).")
                return
            
            # Show conflict summary and let user choose resolution approach
            conflict_summary = f"Found {len(conflicts)} field alias conflicts:\n\n"
            for canonical, alias_list in conflicts.items():
                conflict_summary += f"• {canonical}:\n"
                for alias in alias_list:
                    conflict_summary += f"    - {alias}\n"
                conflict_summary += "\n"
            
            # Ask user how they want to resolve conflicts
            reply = QMessageBox.question(self, "Field Alias Conflicts Found",
                                       conflict_summary + 
                                       "How would you like to resolve these conflicts?\n\n" +
                                       "• Yes: Let me choose for each conflict individually\n" +
                                       "• No: Auto-resolve using CIF2 format + first available values\n" +
                                       "• Cancel: Don't resolve conflicts",
                                       QMessageBox.StandardButton.Yes |
                                       QMessageBox.StandardButton.No |
                                       QMessageBox.StandardButton.Cancel)
            
            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.Yes:
                # Let user resolve conflicts individually
                dialog = FieldConflictDialog(conflicts, content, self, self.dict_manager)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    resolutions = dialog.get_resolutions()
                else:
                    return  # User cancelled
            else:
                # Auto-resolve using CIF2 format + first available values
                resolutions = self._auto_resolve_conflicts(conflicts, content)
            
            # Apply the resolutions
            if resolutions:
                resolved_content, changes = self.dict_manager.apply_field_conflict_resolutions(content, resolutions)
                
                if changes:
                    self.text_editor.setText(resolved_content)
                    self.modified = True
                    
                    change_summary = f"Successfully resolved {len(conflicts)} field alias conflicts:\n\n"
                    for change in changes:
                        change_summary += f"• {change}\n"
                    
                    QMessageBox.information(self, "Conflicts Resolved", change_summary)
                else:
                    QMessageBox.information(self, "No Changes Made", 
                                          "No changes were needed to resolve the conflicts.")
                
        except Exception as e:
            QMessageBox.critical(self, "Conflict Resolution Error", 
                               f"Failed to resolve field alias conflicts:\n{str(e)}")
    
    def _auto_resolve_conflicts(self, conflicts: Dict[str, List[str]], cif_content: str) -> Dict[str, Tuple[str, str]]:
        """Auto-resolve conflicts using CIF2 format and first available values"""
        resolutions = {}
        
        lines = cif_content.split('\n')
        
        for canonical_field, alias_list in conflicts.items():
            # Use CIF2 format (canonical field)
            chosen_field = canonical_field
            
            # Find the first available value
            chosen_value = ""
            for alias in alias_list:
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped.startswith(alias + ' '):
                        parts = line_stripped.split(None, 1)
                        if len(parts) > 1:
                            chosen_value = parts[1]
                            break
                if chosen_value:
                    break
            
            # Fallback if no value found
            if not chosen_value:
                chosen_value = "?"
            
            resolutions[canonical_field] = (chosen_field, chosen_value)
        
        return resolutions

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
            if not new_dict_manager._cif1_to_cif2 and not new_dict_manager._cif2_to_cif1:
                raise ValueError("The selected file does not appear to contain valid CIF dictionary mappings.")
            
            # If we get here, the dictionary loaded successfully
            self.dict_manager = new_dict_manager
            self.format_converter = CIFFormatConverter(self.dict_manager)
            
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
                
                # Update status displays
                self.update_dictionary_status()
                
                dict_name = os.path.basename(file_path)
                self.status_bar.showMessage(f"Successfully added dictionary: {dict_name}", 5000)
                
                # Get dictionary info for the success message
                dict_info = self.dict_manager.get_dictionary_info()
                total_dicts = dict_info['total_dictionaries']
                total_mappings = dict_info['total_cif1_mappings']
                
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
            dialog.exec()
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Dictionary info dialog error: {error_details}")
            QMessageBox.critical(self, "Error", 
                               f"Failed to show dictionary information:\n{str(e)}\n\nCheck console for details.")
    
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
                    
                    return dialog.exec() == QDialog.DialogCode.Accepted
                
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
        if self.current_field_set == 'Custom' and self.custom_field_rules_file:
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
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(
                self, "Validation Error",
                f"Failed to validate field definition file:\n{str(e)}"
            )
