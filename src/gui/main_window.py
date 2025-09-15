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
from utils.CIF_field_parsing import CIFFieldChecker
from utils.CIF_parser import CIFParser
from utils.cif_dictionary_manager import CIFDictionaryManager, CIFVersion
from utils.cif_format_converter import CIFFormatConverter
from .dialogs import (CIFInputDialog, MultilineInputDialog, CheckConfigDialog, 
                     RESULT_ABORT, RESULT_STOP_SAVE)
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
        
        # Load both field definition sets
        self.field_checker.load_field_set('3DED', os.path.join(config_path, 'field_definitions.cif_ed'))
        self.field_checker.load_field_set('HP', os.path.join(config_path, 'field_definitions.cif_hp'))
        
        # Field definition selection variables
        self.custom_field_definition_file = None
        self.current_field_set = '3DED'  # Default to 3DED
        
        self.init_ui()
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
        self.status_bar.addPermanentWidget(self.path_label)
        self.status_bar.addPermanentWidget(self.cif_version_label)
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
        self.field_definition_group = QButtonGroup()
        
        # Radio buttons for built-in field definitions
        radio_layout = QHBoxLayout()
        
        self.radio_3ded = QRadioButton("3D ED")
        self.radio_3ded.setChecked(True)  # Default selection
        self.radio_3ded.toggled.connect(lambda checked: self.set_field_set('3DED') if checked else None)
        
        self.radio_hp = QRadioButton("HP")
        self.radio_hp.toggled.connect(lambda checked: self.set_field_set('HP') if checked else None)
        
        self.radio_custom = QRadioButton("Custom File")
        self.radio_custom.toggled.connect(lambda checked: self.set_field_set('Custom') if checked else None)
        
        # Add radio buttons to group and layout
        self.field_definition_group.addButton(self.radio_3ded)
        self.field_definition_group.addButton(self.radio_hp)
        self.field_definition_group.addButton(self.radio_custom)
        
        radio_layout.addWidget(self.radio_3ded)
        radio_layout.addWidget(self.radio_hp)
        radio_layout.addWidget(self.radio_custom)
        
        # Custom file selection layout
        custom_file_layout = QHBoxLayout()
        self.custom_file_button = QPushButton("Select Custom File...")
        self.custom_file_button.clicked.connect(self.select_custom_field_file)
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
        
        template = (
            "STRUCTURE REFINEMENT\n"
            "- Refinement method\n"
            "- Special constraints and restraints\n"
            "- Special treatments"
        )
        
        # Get current value or use template
        current_value = self.cif_parser.get_field_value('_refine_special_details')
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
            
            # Update the field in the parser
            self.cif_parser.set_field_value('_refine_special_details', updated_content)
            
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
            if not self.custom_field_definition_file:
                self.custom_file_label.setText("Please select a custom file")
                self.custom_file_label.setStyleSheet("color: red; font-style: italic;")
        else:
            self.custom_file_button.setEnabled(False)
            self.custom_file_label.setText("No custom file selected")
            self.custom_file_label.setStyleSheet("color: gray; font-style: italic;")
    
    def select_custom_field_file(self):
        """Open file dialog to select a custom field definition file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Field Definition File",
            "",
            "Field Definition Files (*.cif_ed *.cif_hp *.cif_defs);;All Files (*)"
        )
        
        if file_path:
            try:
                # Try to load the custom field definition file
                self.field_checker.load_field_set('Custom', file_path)
                self.custom_field_definition_file = file_path
                
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
    
    def start_checks(self):
        """Start checking CIF fields using the selected field definition set."""
        # Validate field set selection
        if self.current_field_set == 'Custom':
            if not self.custom_field_definition_file:
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
        
        # Show configuration dialog first
        config_dialog = CheckConfigDialog(self)
        if config_dialog.exec() != QDialog.DialogCode.Accepted:
            return  # User cancelled
        
        # Get configuration settings
        config = config_dialog.get_config()
        
        # Store the initial state for potential restore
        initial_state = self.text_editor.toPlainText()
        
        # Get the selected field set
        fields = self.field_checker.get_field_set(self.current_field_set)
        if not fields:
            QMessageBox.warning(
                self,
                "Warning", 
                f"No {self.current_field_set} field definitions loaded."
            )
            return
        
        # Update window title to show which field set is being used
        field_set_display = {
            '3DED': '3D ED',
            'HP': 'HP',
            'Custom': f'Custom ({os.path.basename(self.custom_field_definition_file) if self.custom_field_definition_file else "Unknown"})'
        }
        
        self.setWindowTitle(f"EDCIF-check - Checking with {field_set_display.get(self.current_field_set, self.current_field_set)} fields")
        
        # Parse the current CIF content
        content = self.text_editor.toPlainText()
        self.cif_parser.parse_file(content)
        
        # Start the checking process
        try:
            for field_def in fields:
                result = self.check_line_with_config(
                    field_def.name,
                    field_def.default_value,
                    False,  # multiline - will be auto-detected
                    field_def.description,
                    config
                )
                
                # Handle special result codes
                if result == RESULT_ABORT:
                    # User wants to abort - restore initial state
                    self.text_editor.setText(initial_state)
                    self.setWindowTitle("EDCIF-check")
                    QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                    return
                elif result == RESULT_STOP_SAVE:
                    # User wants to stop but keep changes
                    break
            
            # Special handling for 3DED: Check for _chemical_absolute_configuration in Sohncke space groups
            if self.current_field_set == '3DED':
                sohncke_groups = [1, 3, 4, 5, 16, 17, 18, 19, 20, 21, 22, 23, 24, 75, 76, 77, 78, 79, 80, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 143, 144, 145, 146, 149, 150, 151, 152, 153, 154, 155, 168, 169, 170, 171, 172, 173, 177, 178, 179, 180, 181, 182, 195, 196, 197, 198, 199, 207, 208, 209, 210, 211, 212, 213, 214]
                SG_number = None
                lines = self.text_editor.toPlainText().splitlines()
                for line in lines:
                    if line.startswith("_space_group_IT_number"):
                        parts = line.split()
                        if len(parts) > 1:
                            try:
                                SG_number = int(parts[1].strip("'\""))
                            except Exception:
                                pass
                        break
                if SG_number is not None and SG_number in sohncke_groups:
                    found = False
                    for line in lines:
                        if line.startswith("_chemical_absolute_configuration"):
                            found = True
                            break
                    if found:
                        result = self.check_line_with_config("_chemical_absolute_configuration", default_value='dyn', multiline=False, description="Specify if/how absolute structure was determined.", config=config)
                        if result == RESULT_ABORT:
                            # User wants to abort - restore initial state
                            self.text_editor.setText(initial_state)
                            self.setWindowTitle("EDCIF-check")
                            QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                            return
                        elif result == RESULT_STOP_SAVE:
                            # User wants to stop but keep changes - proceed to completion
                            pass
                    else:
                        result = self.add_missing_line_with_config("_chemical_absolute_configuration", lines, default_value='dyn', multiline=False, description="Specify if/how absolute structure was determined.", config=config)
                        if result == RESULT_ABORT:
                            # User wants to abort - restore initial state
                            self.text_editor.setText(initial_state)
                            self.setWindowTitle("EDCIF-check")
                            QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                            return
                        elif result == RESULT_STOP_SAVE:
                            # User wants to stop but keep changes - proceed to completion
                            pass
            
            # If we get here, checks completed successfully
            if config.get('reformat_after_checks', False):
                self.reformat_file()
            
            self.setWindowTitle("EDCIF-check")
            QMessageBox.information(self, "Checks Complete", "Field checking completed successfully!")
            
        except Exception as e:
            # Error occurred - restore initial state
            self.text_editor.setText(initial_state)
            self.setWindowTitle("EDCIF-check")
            QMessageBox.critical(self, "Error During Checks", f"An error occurred: {str(e)}")

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