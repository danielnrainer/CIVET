from PyQt6.QtWidgets import (QMainWindow, QWidget, QTextEdit, 
                           QPushButton, QVBoxLayout, QHBoxLayout, QMenu,
                           QFileDialog, QMessageBox, QLineEdit, QCheckBox, 
                           QDialog, QLabel, QFontDialog, QGroupBox)
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import (QTextCharFormat, QSyntaxHighlighter, QColor, QFont, 
                        QFontMetrics, QTextCursor, QTextDocument)
import os
import json
from utils.CIF_field_parsing import CIFFieldChecker
from utils.CIF_parser import CIFParser


# Dialog result codes for consistency
RESULT_ABORT = 2
RESULT_STOP_SAVE = 3

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
        
        # Loop-specific formats
        self.loop_keyword_format = QTextCharFormat()
        self.loop_keyword_format.setForeground(QColor("#FF6600"))  # Orange
        self.loop_keyword_format.setFontWeight(QFont.Weight.Bold)  # Bold
        
        self.loop_field_format = QTextCharFormat()
        self.loop_field_format.setForeground(QColor("#CC6600"))  # Darker orange for loop fields
        
        self.loop_data_format = QTextCharFormat()
        self.loop_data_format.setForeground(QColor("#996600"))  # Even darker orange for loop data
        
        # State for tracking multiline blocks and loops
        self.in_multiline = False
        self.in_loop = False
        self.in_loop_data = False

    def highlightBlock(self, text):
        # Check previous block state
        prev_state = self.previousBlockState()
        if prev_state == 1:
            self.in_multiline = True
            self.in_loop = False
            self.in_loop_data = False
        elif prev_state == 2:
            self.in_loop = True
            self.in_loop_data = False
            self.in_multiline = False
        elif prev_state == 3:
            self.in_loop = True
            self.in_loop_data = True
            self.in_multiline = False
        else:
            self.in_multiline = False
            self.in_loop = False
            self.in_loop_data = False
        
        stripped_text = text.strip()
        
        # Handle multiline values first
        if text.startswith(';'):
            self.setFormat(0, len(text), self.multiline_format)
            self.in_multiline = not self.in_multiline
            if self.in_multiline:
                self.setCurrentBlockState(1)
            else:
                self.setCurrentBlockState(0)
            return
        elif self.in_multiline:
            self.setFormat(0, len(text), self.multiline_format)
            self.setCurrentBlockState(1)
            return
        
        # Check for loop start
        if stripped_text.lower() == 'loop_':
            self.setFormat(0, len(text), self.loop_keyword_format)
            self.in_loop = True
            self.in_loop_data = False
            self.setCurrentBlockState(2)
            return
        # Check if we're in a loop and encounter non-field data (start of data rows)
        elif self.in_loop and stripped_text and not stripped_text.startswith('_') and not stripped_text.startswith('#'):
            self.in_loop_data = True
            self.setCurrentBlockState(3)
        # Check if we're leaving a loop (new field outside loop or new loop)
        elif stripped_text.startswith('_') and not self.in_loop:
            self.in_loop = False
            self.in_loop_data = False
            self.setCurrentBlockState(0)
        elif stripped_text.lower().startswith('loop_'):
            self.in_loop = True
            self.in_loop_data = False
            self.setCurrentBlockState(2)
        elif self.in_loop and not self.in_loop_data:
            self.setCurrentBlockState(2)
        elif self.in_loop and self.in_loop_data:
            self.setCurrentBlockState(3)
        else:
            self.setCurrentBlockState(0)
        
        # Apply background highlighting for loop data
        if self.in_loop_data and stripped_text and not stripped_text.startswith('#'):
            self.setFormat(0, len(text), self.loop_data_format)
        
        # Apply standard rules
        for pattern, format in self.highlighting_rules:
            matches = pattern.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                # Don't override loop data formatting for basic patterns
                if not (self.in_loop_data and pattern.pattern() in [r'_\w+(?:\.\w+)*', r"'[^']*'"]):
                    self.setFormat(match.capturedStart(), match.capturedLength(), format)
        
        # Special formatting for loop field names
        if self.in_loop and not self.in_loop_data and stripped_text.startswith('_'):
            self.setFormat(0, len(text), self.loop_field_format)

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

class CheckConfigDialog(QDialog):
    """Configuration dialog for CIF field checking parameters."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Check Configuration")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        # Initialize configuration settings
        self.auto_fill_missing = False
        self.skip_matching_defaults = False
        self.reformat_after_checks = False
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # Add title and description
        title_label = QLabel("Configure CIF Field Checking")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        description_label = QLabel(
            "Configure how the field checking process should behave:"
        )
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        
        # Create configuration group
        config_group = QGroupBox("Checking Options")
        config_layout = QVBoxLayout(config_group)
        
        # Option 1: Auto-fill missing fields
        self.auto_fill_checkbox = QCheckBox(
            "Automatically fill missing fields with default values\n"
            "(No user prompts for missing fields - they will be added silently)"
        )
        self.auto_fill_checkbox.setChecked(self.auto_fill_missing)
        config_layout.addWidget(self.auto_fill_checkbox)
        
        # Option 2: Skip fields that match defaults
        self.skip_defaults_checkbox = QCheckBox(
            "Skip prompts for fields that already match default values\n"
            "(Fields with correct default values will not prompt for editing)"
        )
        self.skip_defaults_checkbox.setChecked(self.skip_matching_defaults)
        config_layout.addWidget(self.skip_defaults_checkbox)
        
        # Option 3: Reformat file after checks
        self.reformat_checkbox = QCheckBox(
            "Reformat file after checks complete\n"
            "(Automatically reformat CIF file for proper line lengths and formatting)"
        )
        self.reformat_checkbox.setChecked(self.reformat_after_checks)
        config_layout.addWidget(self.reformat_checkbox)
        
        layout.addWidget(config_group)
        
        # Add buttons
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("Start Checks")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        
        layout.addLayout(button_layout)
    
    def get_config(self):
        """Get the current configuration settings."""
        return {
            'auto_fill_missing': self.auto_fill_checkbox.isChecked(),
            'skip_matching_defaults': self.skip_defaults_checkbox.isChecked(),
            'reformat_after_checks': self.reformat_checkbox.isChecked()
        }

class CIFInputDialog(QDialog):
    # Define result codes as class attributes
    RESULT_ABORT = 2  # User wants to abort all changes
    RESULT_STOP_SAVE = 3  # User wants to stop but save changes
    RESULT_USE_DEFAULT = 4  # User wants to use default value

    def __init__(self, title, text, value="", default_value=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.default_value = default_value
        
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
        
        # Add "Use Default" button only if default value is provided
        if default_value is not None and default_value.strip():
            useDefaultButton = QPushButton(f"Use Default ({default_value})")
            useDefaultButton.clicked.connect(self.use_default)
            buttonBox.addWidget(useDefaultButton)
        
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
    
    def use_default(self):
        self.done(self.RESULT_USE_DEFAULT)

    @staticmethod
    def getText(parent, title, text, value="", default_value=None):
        dialog = CIFInputDialog(title, text, value, default_value, parent)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            return dialog.getValue(), QDialog.DialogCode.Accepted
        elif result == CIFInputDialog.RESULT_ABORT:
            return None, CIFInputDialog.RESULT_ABORT
        elif result == CIFInputDialog.RESULT_STOP_SAVE:
            return dialog.getValue(), CIFInputDialog.RESULT_STOP_SAVE
        elif result == CIFInputDialog.RESULT_USE_DEFAULT:
            return default_value, QDialog.DialogCode.Accepted
        else:
            return None, QDialog.DialogCode.Rejected

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
        
        # Create button layout
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

    def start_checks_3ded(self):
        """Start checking CIF fields using 3DED field definitions."""
        # Show configuration dialog first
        config_dialog = CheckConfigDialog(self)
        if config_dialog.exec() != QDialog.DialogCode.Accepted:
            return  # User cancelled
        
        # Get configuration settings
        config = config_dialog.get_config()
        
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
                # Check each field with configuration options
                result = self.check_line_with_config(field.name, field.default_value, 
                                                   description=field.description, 
                                                   config=config)
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
            
            # Reformat file if requested
            if config.get('reformat_after_checks', False):
                try:
                    current_content = self.text_editor.toPlainText()
                    reformatted_content = self.cif_parser.reformat_for_line_length(current_content)
                    self.text_editor.setText(reformatted_content)
                except Exception as e:
                    QMessageBox.warning(self, "Reformatting Warning",
                                       f"Checks completed successfully, but reformatting failed:\n{str(e)}")
            
            QMessageBox.information(self, "Checks Complete", 
                                  "All 3DED CIF checks completed successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error",
                             f"An error occurred during checks:\n{str(e)}")

    def start_checks_hp(self):
        """Start checking CIF fields using HP (high pressure) field definitions."""
        # Show configuration dialog first
        config_dialog = CheckConfigDialog(self)
        if config_dialog.exec() != QDialog.DialogCode.Accepted:
            return  # User cancelled
        
        # Get configuration settings
        config = config_dialog.get_config()
        
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
                # Check each field with configuration options
                result = self.check_line_with_config(field.name, field.default_value, 
                                                   description=field.description, 
                                                   config=config)
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
            
            # Reformat file if requested
            if config.get('reformat_after_checks', False):
                try:
                    current_content = self.text_editor.toPlainText()
                    reformatted_content = self.cif_parser.reformat_for_line_length(current_content)
                    self.text_editor.setText(reformatted_content)
                except Exception as e:
                    QMessageBox.warning(self, "Reformatting Warning",
                                       f"Checks completed successfully, but reformatting failed:\n{str(e)}")
            
            QMessageBox.information(self, "Checks Complete", 
                                  "All HP CIF checks completed successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error",
                             f"An error occurred during checks:\n{str(e)}")    
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