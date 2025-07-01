from PyQt6.QtWidgets import (QMainWindow, QWidget, QTextEdit, 
                           QPushButton, QVBoxLayout, QHBoxLayout, QMenu,
                           QFileDialog, QMessageBox, QLineEdit, QCheckBox, 
                           QDialog, QLabel, QFontDialog)
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import (QTextCharFormat, QSyntaxHighlighter, QColor, QFont, 
                        QFontMetrics, QTextCursor, QTextDocument)
import os
import json
from utils.CIF_field_parsing import CIFFieldChecker


# Dialog result codes for consistency
RESULT_ABORT = 2
RESULT_STOP_SAVE = 3

def load_cif_field_definitions(filepath):
    """Load CIF field definitions from a CIF-style file.
    
    The file format is CIF-like with each line having:
    _field_name value # description
    or
    # _field_name: description
    _field_name value
    
    Values can be quoted or unquoted. The function preserves the quotation style.
    Comments starting with # can contain field descriptions.
    """
    try:
        all_fields = []
        descriptions = {}
        
        # First pass: collect descriptions from comments
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                # Description on its own line
                if line.startswith('#'):
                    parts = line[1:].strip().split(':', 1)
                    if len(parts) == 2 and parts[0].strip().startswith('_'):
                        field_name = parts[0].strip()
                        descriptions[field_name] = parts[1].strip()
                # Description at end of line
                elif '#' in line and not line.startswith('//'):
                    value_part, comment_part = line.split('#', 1)
                    if value_part.strip().startswith('_'):
                        field_name = value_part.split()[0].strip()
                        descriptions[field_name] = comment_part.strip()
        
        # Second pass: collect field definitions
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#') or line.startswith('//'):
                    continue
                
                # Handle inline comments
                if '#' in line:
                    line = line.split('#', 1)[0].strip()
                
                # Split on first whitespace to separate field from value
                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    continue
                    
                field, value = parts
                description = descriptions.get(field, '')
                    
                # Add options to description if present in comments
                if 'options:' in description.lower():
                    options_idx = description.lower().find('options:')
                    options_text = description[options_idx:].strip()
                    description = f"{description[:options_idx].strip()}\n{options_text}"
                
                # Store the field definition with value and description
                all_fields.append((field, value, description))
                
        return all_fields
    except Exception as e:
        print(f"Error loading CIF field definitions: {e}")
        return []

class CIFSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # Field names (starting with _)
        self.field_format = QTextCharFormat()
        self.field_format.setForeground(QColor("#0000FF"))  # Blue
        self.highlighting_rules.append((
            QRegularExpression(r'_\w+(?:\.\w+)*'),
            self.field_format
        ))
        
        # Values in quotes
        self.value_format = QTextCharFormat()
        self.value_format.setForeground(QColor("#008000"))  # Green
        self.highlighting_rules.append((
            QRegularExpression(r"'[^']*'"),
            self.value_format
        ))
        
        # Multi-line values format
        self.multiline_format = QTextCharFormat()
        self.multiline_format.setForeground(QColor("#800080"))  # Purple
        
        # State for tracking multiline blocks
        self.in_multiline = False

    def highlightBlock(self, text):
        # Check if previous block was in a multiline state
        if self.previousBlockState() == 1:
            self.in_multiline = True
        else:
            self.in_multiline = False
            
        # Apply standard rules first
        for pattern, format in self.highlighting_rules:
            matches = pattern.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)
        
        # Handle multiline values
        if text.startswith(';'):
            self.setFormat(0, len(text), self.multiline_format)
            self.in_multiline = not self.in_multiline
        elif self.in_multiline:
            self.setFormat(0, len(text), self.multiline_format)
        
        # Set state for next block
        self.setCurrentBlockState(1 if self.in_multiline else 0)

class MultilineInputDialog(QDialog):
    # Define result codes as class attributes
    RESULT_ABORT = 2  # User wants to abort all changes
    RESULT_STOP_SAVE = 3  # User wants to stop but save changes

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Text")
        layout = QVBoxLayout(self)
        
        self.textEdit = QTextEdit()
        self.textEdit.setText(text)
        layout.addWidget(self.textEdit)
        
        buttonBox = QHBoxLayout()
        
        # Save (OK) button
        saveButton = QPushButton("OK")
        saveButton.clicked.connect(self.accept)
        
        # Cancel button
        cancelButton = QPushButton("Cancel Current")
        cancelButton.clicked.connect(self.reject)
        
        # Abort button
        abortButton = QPushButton("Abort All Changes")
        abortButton.clicked.connect(self.abort_changes)
        
        # Stop & Save button
        stopSaveButton = QPushButton("Stop && Save")
        stopSaveButton.clicked.connect(self.stop_and_save)
        
        buttonBox.addWidget(saveButton)
        buttonBox.addWidget(cancelButton)
        buttonBox.addWidget(abortButton)
        buttonBox.addWidget(stopSaveButton)
        layout.addLayout(buttonBox)
        
        self.setMinimumWidth(800)  # Increased width to accommodate buttons
        self.setMinimumHeight(400)

    def getText(self):
        return self.textEdit.toPlainText()
        
    def abort_changes(self):
        self.done(self.RESULT_ABORT)
        
    def stop_and_save(self):
        self.done(self.RESULT_STOP_SAVE)

class CIFInputDialog(QDialog):
    # Define result codes as class attributes
    RESULT_ABORT = 2  # User wants to abort all changes
    RESULT_STOP_SAVE = 3  # User wants to stop but save changes

    def __init__(self, title, text, value="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        
        layout = QVBoxLayout(self)
        
        # Add text label
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        
        # Add input field
        self.inputField = QLineEdit(self)
        self.inputField.setText(value)
        layout.addWidget(self.inputField)
        
        # Add buttons
        buttonBox = QHBoxLayout()
        
        okButton = QPushButton("OK")
        okButton.clicked.connect(self.accept)
        
        cancelButton = QPushButton("Cancel Current")
        cancelButton.clicked.connect(self.reject)
        
        abortButton = QPushButton("Abort All Changes")
        abortButton.clicked.connect(self.abort_changes)
        
        stopSaveButton = QPushButton("Stop && Save")
        stopSaveButton.clicked.connect(self.stop_and_save)
        
        buttonBox.addWidget(okButton)
        buttonBox.addWidget(cancelButton)
        buttonBox.addWidget(abortButton)
        buttonBox.addWidget(stopSaveButton)
        
        layout.addLayout(buttonBox)
        self.setMinimumWidth(600)

    def getValue(self):
        return self.inputField.text()
        
    def abort_changes(self):
        self.done(self.RESULT_ABORT)
        
    def stop_and_save(self):
        self.done(self.RESULT_STOP_SAVE)

    @staticmethod
    def getText(parent, title, text, value=""):
        dialog = CIFInputDialog(title, text, value, parent)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            return dialog.getValue(), QDialog.DialogCode.Accepted
        elif result == CIFInputDialog.RESULT_ABORT:
            return None, CIFInputDialog.RESULT_ABORT
        elif result == CIFInputDialog.RESULT_STOP_SAVE:
            return dialog.getValue(), CIFInputDialog.RESULT_STOP_SAVE
        else:
            return None, QDialog.DialogCode.Rejected

class CIFEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.modified = False
        self.recent_files = []
        self.max_recent_files = 5
        
        # Initialize field checker
        self.field_checker = CIFFieldChecker()
        config_path = os.path.dirname(__file__)
        
        # Load both field definition sets
        self.field_checker.load_field_set('3DED', os.path.join(config_path, 'field_definitions.cif_ed'))
        self.field_checker.load_field_set('HP', os.path.join(config_path, 'field_definitions.cif_hp'))
        
        # Load settings
        self.load_settings()
        
        self.init_ui()
        self.select_initial_file()

    def load_settings(self):
        """Load editor settings from JSON file"""
        self.settings = {
            'font_family': 'Courier New',
            'font_size': 10,
            'line_numbers_enabled': True,
            'syntax_highlighting_enabled': True,
            'show_ruler': True  # New setting for the ruler
        }
        
        settings_path = os.path.join(os.path.dirname(__file__), 'editor_settings.json')
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        """Save editor settings to JSON file"""
        settings_path = os.path.join(os.path.dirname(__file__), 'editor_settings.json')
        try:
            with open(settings_path, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def apply_settings(self):
        """Apply current settings to the editor"""
        # Create font from settings
        font = QFont(self.settings['font_family'], self.settings['font_size'])
        
        # Create a QFontMetrics object to measure character width
        metrics = QFontMetrics(font)
        char_width = metrics.horizontalAdvance('x')  # Width of a typical character
          # Position the ruler at 80 characters
        ruler_x = int(char_width * 80 + self.text_editor.document().documentMargin())
        self.ruler.setGeometry(ruler_x, 0, 1, self.text_editor.height())
        self.ruler.setVisible(self.settings['show_ruler'])
        
        # Apply font to editor and line numbers
        self.text_editor.setFont(font)
        self.line_numbers.setFont(font)
        
        # Update other settings
        self.line_numbers.setVisible(self.settings['line_numbers_enabled'])
        if hasattr(self, 'highlighter'):
            self.highlighter.setDocument(
                self.text_editor.document() if self.settings['syntax_highlighting_enabled'] 
                else None
            )

    def change_font(self):
        """Open font dialog to change editor font"""
        current_font = self.text_editor.font()
        font, ok = QFontDialog.getFont(current_font, self,
                                     "Select Editor Font",
                                     QFontDialog.FontDialogOption.MonospacedFonts)
        if ok:
            self.settings['font_family'] = font.family()
            self.settings['font_size'] = font.pointSize()
            self.apply_settings()
            self.save_settings()
            
    def toggle_line_numbers(self):
        """Toggle line numbers visibility"""
        self.settings['line_numbers_enabled'] = not self.settings['line_numbers_enabled']
        self.apply_settings()
        self.save_settings()
        
    def toggle_syntax_highlighting(self):
        """Toggle syntax highlighting"""
        self.settings['syntax_highlighting_enabled'] = not self.settings['syntax_highlighting_enabled']
        self.apply_settings()
        self.save_settings()
        
    def toggle_ruler(self):
        """Toggle ruler visibility"""
        self.settings['show_ruler'] = not self.settings['show_ruler']
        self.ruler.setVisible(self.settings['show_ruler'])
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
        self.status_bar.addPermanentWidget(self.path_label)
        self.status_bar.addPermanentWidget(self.cursor_label)
          # Create text editor with line numbers
        text_widget = QWidget()
        text_layout = QHBoxLayout(text_widget)
        
        self.line_numbers = QTextEdit()
        self.line_numbers.setFixedWidth(50)
        self.line_numbers.setReadOnly(True)
        self.line_numbers.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.text_editor = QTextEdit()
        self.text_editor.textChanged.connect(self.handle_text_changed)
        self.text_editor.cursorPositionChanged.connect(self.update_cursor_position)

        # Create ruler overlay
        self.ruler = QWidget(self.text_editor)
        self.ruler.setFixedWidth(1)  # 1 pixel wide line
        self.ruler.setStyleSheet("background-color: #E0E0E0;")  # Light gray color
        self.ruler.hide()  # Initially hidden until we position it

        # Apply font and other settings
        self.apply_settings()
        
        # Sync scrolling between line numbers and text editor
        self.text_editor.verticalScrollBar().valueChanged.connect(
            self.line_numbers.verticalScrollBar().setValue)
        
        text_layout.addWidget(self.line_numbers)
        text_layout.addWidget(self.text_editor)
        main_layout.addWidget(text_widget)
        
        # Create button layout = QHBoxLayout()
        button_layout = QHBoxLayout()
        
        # Create buttons
        check_3ded_button = QPushButton("Start Checks (3DED)")
        check_3ded_button.clicked.connect(self.start_checks_3ded)
        check_hp_button = QPushButton("Start Checks (HP)")
        check_hp_button.clicked.connect(self.start_checks_hp)
        refine_details_button = QPushButton("Edit Refinement Details")
        refine_details_button.clicked.connect(self.check_refine_special_details)
        format_button = QPushButton("Reformat File")
        format_button.clicked.connect(self.reformat_file)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_file)
        
        # Add buttons to layout
        button_layout.addWidget(check_3ded_button)
        button_layout.addWidget(check_hp_button)
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
        
        check_3ded_action = action_menu.addAction("Start Checks (3DED)")
        check_3ded_action.triggered.connect(self.start_checks_3ded)
        
        check_hp_action = action_menu.addAction("Start Checks (HP)")
        check_hp_action.triggered.connect(self.start_checks_hp)
        
        refine_details_action = action_menu.addAction("Edit Refinement Details")
        refine_details_action.triggered.connect(self.check_refine_special_details)
        
        format_action = action_menu.addAction("Reformat File")
        format_action.triggered.connect(self.reformat_file)

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
        line_numbers_action.setChecked(self.settings['line_numbers_enabled'])
        line_numbers_action.triggered.connect(self.toggle_line_numbers)
        
        ruler_action = view_menu.addAction("Show 80-Char Ruler")
        ruler_action.setCheckable(True)
        ruler_action.setChecked(self.settings['show_ruler'])
        ruler_action.triggered.connect(self.toggle_ruler)
        
        syntax_action = view_menu.addAction("Syntax Highlighting")
        syntax_action.setCheckable(True)
        syntax_action.setChecked(self.settings['syntax_highlighting_enabled'])
        syntax_action.triggered.connect(self.toggle_syntax_highlighting)
        
        # Enable undo/redo
        self.text_editor.setUndoRedoEnabled(True)

        # Apply syntax highlighter
        self.highlighter = CIFSyntaxHighlighter(self.text_editor.document())

        # Apply saved settings
        self.apply_settings()

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
            self.update_status_bar()
            self.update_line_numbers()
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
        # errors = self.validate_cif()
        # if errors:
        #     error_text = "\n".join(errors)
        #     reply = QMessageBox.warning(
        #         self, "CIF Validation Errors",
        #         f"The following validation errors were found:\n\n{error_text}\n\nSave anyway?",
        #         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        #     if reply == QMessageBox.StandardButton.No:
        #         return
                
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
                    current_value)
                
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
            default_value if default_value else "")
        
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
    
    def check_refine_special_details(self):
        """Check and edit _refine_special_details field, creating it if needed."""
        lines = self.text_editor.toPlainText().splitlines()
        start_line = None
        end_line = None
        found = False
        
        # Look for the field
        for i, line in enumerate(lines):
            if line.startswith("_refine_special_details"):
                start_line = i
                found = True
                break
                
        template = (
                   "STRUCTURE REFINEMENT\n"
                   "- Refinement method\n"
                   "- Special constraints and restraints\n"
                   "- Special treatments"
                   )
        
        if found:
            # Find the content between semicolons
            content_lines = []
            in_content = False
            
            for i in range(start_line + 1, len(lines)):
                line = lines[i].strip()
                if line == ";":
                    if not in_content:
                        in_content = True
                        continue
                    else:
                        end_line = i
                        break
                if in_content:
                    content_lines.append(lines[i])
            
            if content_lines:
                content = "\n".join(content_lines)
            else:
                content = template
        else:
            content = template
        
        # Open dialog for editing
        dialog = MultilineInputDialog(content, self)
        dialog.setWindowTitle("Edit Refinement Special Details")
        result = dialog.exec()
        
        if result in [MultilineInputDialog.RESULT_ABORT, MultilineInputDialog.RESULT_STOP_SAVE]:
            return result
        elif result == QDialog.DialogCode.Accepted:
            updated_content = dialog.getText()
            
            # Format the complete field with proper CIF syntax
            formatted_content = [
                "_refine_special_details",
                ";",
                updated_content,
                ";"
            ]
            
            # Update or insert the content
            if found and end_line is not None:
                lines[start_line:end_line + 1] = formatted_content
            else:
                if lines and lines[-1].strip():  # If last line is not empty
                    lines.append("")  # Add blank line before new field
                lines.extend(formatted_content)
            
            self.text_editor.setText("\n".join(lines))
            
        return result

    def start_checks_3ded(self):
        """Start checking CIF fields using 3DED field definitions."""
        # Store the initial state for potential restore
        initial_state = self.text_editor.toPlainText()
        
        # Get the 3DED field set
        fields = self.field_checker.get_field_set('3DED')
        if not fields:
            QMessageBox.warning(self, "Warning", 
                              "No 3DED field definitions loaded.")
            return
            
        try:
            # Process all required fields
            for field in fields:
                # Check each field
                result = self.check_line(field.name, field.default_value, description=field.description)
                if result == CIFInputDialog.RESULT_ABORT:
                    # Restore original state
                    self.text_editor.setText(initial_state)
                    QMessageBox.information(self, "Changes Aborted",
                                       "All changes have been discarded.")
                    return
                elif result == CIFInputDialog.RESULT_STOP_SAVE:
                    QMessageBox.information(self, "Checks Stopped",
                                       "Changes have been saved. Remaining checks skipped.")
                    return
            
            # Always check refine special details last
            result = self.check_refine_special_details()
            if result == MultilineInputDialog.RESULT_ABORT:
                # Restore original state
                self.text_editor.setText(initial_state)
                QMessageBox.information(self, "Changes Aborted",
                                   "All changes have been discarded.")
                return
            elif result == MultilineInputDialog.RESULT_STOP_SAVE:
                QMessageBox.information(self, "Checks Stopped",
                                   "Changes have been saved. Remaining checks skipped.")
                return

            # Check for _chemical_absolute_configuration
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
                    self.check_line("_chemical_absolute_configuration", default_value='dyn', multiline=False, description="Specify if/how absolute structure was determined.")
                else:
                    self.add_missing_line("_chemical_absolute_configuration", lines, default_value='dyn', multiline=False, description="Specify if/how absolute structure was determined.")
            
            QMessageBox.information(self, "Checks Complete", 
                                  "All 3DED CIF checks completed successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error",
                             f"An error occurred during checks:\n{str(e)}")

    def start_checks_hp(self):
        """Start checking CIF fields using HP (high pressure) field definitions."""
        # Store the initial state for potential restore
        initial_state = self.text_editor.toPlainText()
        
        # Get the HP field set
        fields = self.field_checker.get_field_set('HP')
        if not fields:
            QMessageBox.warning(self, "Warning", 
                              "No HP field definitions loaded.")
            return
            
        try:
            # Process all required fields
            for field in fields:
                # Check each field
                result = self.check_line(field.name, field.default_value, description=field.description)
                if result == CIFInputDialog.RESULT_ABORT:
                    # Restore original state
                    self.text_editor.setText(initial_state)
                    QMessageBox.information(self, "Changes Aborted",
                                       "All changes have been discarded.")
                    return
                elif result == CIFInputDialog.RESULT_STOP_SAVE:
                    QMessageBox.information(self, "Checks Stopped",
                                       "Changes have been saved. Remaining checks skipped.")
                    return

            # Always check refine special details last
            result = self.check_refine_special_details()
            if result == MultilineInputDialog.RESULT_ABORT:
                # Restore original state
                self.text_editor.setText(initial_state)
                QMessageBox.information(self, "Changes Aborted",
                                   "All changes have been discarded.")
                return
            elif result == MultilineInputDialog.RESULT_STOP_SAVE:
                QMessageBox.information(self, "Checks Stopped",
                                   "Changes have been saved. Remaining checks skipped.")
                return
            
            QMessageBox.information(self, "Checks Complete", 
                                  "All HP CIF checks completed successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error",
                             f"An error occurred during checks:\n{str(e)}")    
    def reformat_file(self):
        """Reformat CIF file to handle long lines and properly format values, preserving semicolon blocks."""
        lines = self.text_editor.toPlainText().splitlines()
        new_lines = []
        in_multiline_block = False
        for line in lines:
            if line.strip() == ';':
                in_multiline_block = not in_multiline_block
                new_lines.append(line)
                continue
            if in_multiline_block:
                new_lines.append(line)
            else:
                # Handle CIF field values (lines starting with _)
                if line.startswith('_') and len(line) > 80:
                    key, value = line.split(maxsplit=1)
                    # Strip quotes if present
                    value = value.strip().strip("'\"")
                    formatted_value = self.insert_line_breaks(value, 80)
                    # Use semicolon-delimited format for long values
                    new_lines.append(f"{key} \n;\n{formatted_value}\n;")
                # Handle quoted values that are too long
                elif line.lstrip().startswith(("'", '"')) and len(line) > 80:
                    # Strip quotes and convert to semicolon-delimited format
                    value = line.lstrip().strip("'\"")
                    formatted_value = self.insert_line_breaks(value, 80)
                    new_lines.append(f";\n{formatted_value}\n;")
                # Keep short lines unchanged
                elif len(line) <= 80:
                    new_lines.append(line)
                # Handle other long lines
                elif len(line) > 80:
                    formatted_value = self.insert_line_breaks(line.lstrip(), 80)
                    new_lines.append(formatted_value)
        self.text_editor.setText("\n".join(new_lines))
        QMessageBox.information(self, "Reformatting Completed",
                              "The file has been successfully reformatted.")

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
        self.update_line_numbers()
        self.update_status_bar()
    
    def update_line_numbers(self):
        text = self.text_editor.toPlainText()
        num_lines = text.count('\n') + 1
        numbers = '\n'.join(str(i) for i in range(1, num_lines + 1))
        self.line_numbers.setText(numbers)
        
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

    def resizeEvent(self, event):
        """Handle resize events to update the ruler position"""
        super().resizeEvent(event)
        if hasattr(self, 'ruler'):
            self.ruler.setGeometry(self.ruler.x(), 0, 1, self.text_editor.height())

    def show_find_dialog(self):
        """Show a dialog for finding text in the editor"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Find")
        layout = QVBoxLayout(dialog)
        
        # Search input
        search_label = QLabel("Find what:")
        search_input = QLineEdit()
        layout.addWidget(search_label)
        layout.addWidget(search_input)
        
        # Options
        case_checkbox = QCheckBox("Match case")
        layout.addWidget(case_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        find_next_button = QPushButton("Find Next")
        find_next_button.clicked.connect(lambda: self.find_text(
            search_input.text(), 
            case_sensitive=case_checkbox.isChecked()
        ))
        button_layout.addWidget(find_next_button)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()

    def show_replace_dialog(self):
        """Show a dialog for finding and replacing text in the editor"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Find and Replace")
        layout = QVBoxLayout(dialog)
        
        # Find input
        find_label = QLabel("Find what:")
        find_input = QLineEdit()
        layout.addWidget(find_label)
        layout.addWidget(find_input)
        
        # Replace input
        replace_label = QLabel("Replace with:")
        replace_input = QLineEdit()
        layout.addWidget(replace_label)
        layout.addWidget(replace_input)
        
        # Options
        case_checkbox = QCheckBox("Match case")
        layout.addWidget(case_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        find_next_button = QPushButton("Find Next")
        find_next_button.clicked.connect(lambda: self.find_text(
            find_input.text(), 
            case_sensitive=case_checkbox.isChecked()
        ))
        
        replace_button = QPushButton("Replace")
        replace_button.clicked.connect(lambda: self.replace_text(
            find_input.text(),
            replace_input.text(),
            case_sensitive=case_checkbox.isChecked()
        ))
        
        replace_all_button = QPushButton("Replace All")
        replace_all_button.clicked.connect(lambda: self.replace_all_text(
            find_input.text(),
            replace_input.text(),
            case_sensitive=case_checkbox.isChecked()
        ))
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        
        button_layout.addWidget(find_next_button)
        button_layout.addWidget(replace_button)
        button_layout.addWidget(replace_all_button)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()

    def find_text(self, text, case_sensitive=False):
        """Find the next occurrence of text in the editor"""
        flags = QTextDocument.FindFlag.FindBackward
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
            
        cursor = self.text_editor.textCursor()
        found = self.text_editor.find(text)
        
        if not found:
            # If not found, try from the start
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.text_editor.setTextCursor(cursor)
            found = self.text_editor.find(text)
            
            if not found:
                QMessageBox.information(self, "Find", f"Cannot find '{text}'")

    def replace_text(self, find_text, replace_text, case_sensitive=False):
        """Replace the next occurrence of find_text with replace_text"""
        cursor = self.text_editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == find_text:
            cursor.insertText(replace_text)
            
        self.find_text(find_text, case_sensitive)

    def replace_all_text(self, find_text, replace_text, case_sensitive=False):
        """Replace all occurrences of find_text with replace_text"""
        cursor = self.text_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.text_editor.setTextCursor(cursor)
        
        count = 0
        while self.text_editor.find(find_text):
            cursor = self.text_editor.textCursor()
            cursor.insertText(replace_text)
            count += 1
            
        if count > 0:
            QMessageBox.information(self, "Replace All", 
                                  f"Replaced {count} occurrence(s)")
        else:
            QMessageBox.information(self, "Replace All", 
                                  f"Cannot find '{find_text}'")