"""
CIF Text Editor Component

This module provides a comprehensive text editor widget specifically designed 
for CIF files, featuring line numbers, syntax highlighting, find/replace functionality,
and customizable settings.
"""

from PyQt6.QtWidgets import (QWidget, QTextEdit, QHBoxLayout, QDialog, QVBoxLayout,
                           QLabel, QLineEdit, QCheckBox, QPushButton, QMessageBox,
                           QFontDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (QFont, QFontMetrics, QTextCursor, QTextDocument)
import json
import os
from .syntax_highlighter import CIFSyntaxHighlighter


class CIFTextEditor(QWidget):
    """
    A comprehensive CIF text editor widget with line numbers, syntax highlighting,
    and advanced editing features.
    """
    
    # Signals
    textChanged = pyqtSignal()
    cursorPositionChanged = pyqtSignal()
    modificationChanged = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Editor settings
        self.settings = {
            'font_family': 'Courier New',
            'font_size': 10,
            'line_numbers_enabled': True,
            'syntax_highlighting_enabled': True,
            'show_ruler': True
        }
        
        self.init_ui()
        self.load_settings()
        self.apply_settings()
    
    def init_ui(self):
        """Initialize the text editor UI components."""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Line numbers widget
        self.line_numbers = QTextEdit()
        self.line_numbers.setFixedWidth(50)
        self.line_numbers.setReadOnly(True)
        self.line_numbers.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Main text editor
        self.text_editor = QTextEdit()
        self.text_editor.setUndoRedoEnabled(True)
        
        # Create ruler overlay
        self.ruler = QWidget(self.text_editor)
        self.ruler.setFixedWidth(1)  # 1 pixel wide line
        self.ruler.setStyleSheet("background-color: #E0E0E0;")  # Light gray color
        self.ruler.hide()  # Initially hidden until we position it
        
        # Connect signals
        self.text_editor.textChanged.connect(self._on_text_changed)
        self.text_editor.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self.text_editor.document().modificationChanged.connect(self.modificationChanged.emit)
        
        # Sync scrolling between line numbers and text editor
        self.text_editor.verticalScrollBar().valueChanged.connect(
            self.line_numbers.verticalScrollBar().setValue)
        
        # Add widgets to layout
        layout.addWidget(self.line_numbers)
        layout.addWidget(self.text_editor)
        
        # Initialize syntax highlighter
        self.highlighter = CIFSyntaxHighlighter(self.text_editor.document())
        
        # Update line numbers initially
        self.update_line_numbers()
    
    def load_settings(self):
        """Load editor settings from JSON file."""
        settings_path = os.path.join(os.path.dirname(__file__), '..', 'editor_settings.json')
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    def save_settings(self):
        """Save editor settings to JSON file."""
        settings_path = os.path.join(os.path.dirname(__file__), '..', 'editor_settings.json')
        try:
            with open(settings_path, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def apply_settings(self):
        """Apply current settings to the editor."""
        # Create font from settings
        font = QFont(self.settings['font_family'], self.settings['font_size'])
        
        # Calculate ruler position
        metrics = QFontMetrics(font)
        char_width = metrics.horizontalAdvance('x')
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
        """Open font dialog to change editor font."""
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
        """Toggle line numbers visibility."""
        self.settings['line_numbers_enabled'] = not self.settings['line_numbers_enabled']
        self.apply_settings()
        self.save_settings()
    
    def toggle_syntax_highlighting(self):
        """Toggle syntax highlighting."""
        self.settings['syntax_highlighting_enabled'] = not self.settings['syntax_highlighting_enabled']
        self.apply_settings()
        self.save_settings()
    
    def toggle_ruler(self):
        """Toggle ruler visibility."""
        self.settings['show_ruler'] = not self.settings['show_ruler']
        self.ruler.setVisible(self.settings['show_ruler'])
        self.save_settings()
    
    def get_text(self):
        """Get the current text content."""
        return self.text_editor.toPlainText()
    
    def set_text(self, text):
        """Set the text content."""
        self.text_editor.setText(text)
        self.update_line_numbers()
    
    def append_text(self, text):
        """Append text to the editor."""
        self.text_editor.append(text)
    
    def insert_text(self, text):
        """Insert text at the current cursor position."""
        cursor = self.text_editor.textCursor()
        cursor.insertText(text)
    
    def clear(self):
        """Clear the editor content."""
        self.text_editor.clear()
        self.update_line_numbers()
    
    def undo(self):
        """Undo the last operation."""
        self.text_editor.undo()
    
    def redo(self):
        """Redo the last undone operation."""
        self.text_editor.redo()
    
    def copy(self):
        """Copy selected text to clipboard."""
        self.text_editor.copy()
    
    def cut(self):
        """Cut selected text to clipboard."""
        self.text_editor.cut()
    
    def paste(self):
        """Paste text from clipboard."""
        self.text_editor.paste()
    
    def select_all(self):
        """Select all text."""
        self.text_editor.selectAll()
    
    def get_cursor_position(self):
        """Get current cursor position as (line, column)."""
        cursor = self.text_editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        return line, column
    
    def set_cursor_position(self, line, column=0):
        """Set cursor position to specific line and column."""
        cursor = self.text_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(line - 1):
            cursor.movePosition(QTextCursor.MoveOperation.Down)
        for _ in range(column):
            cursor.movePosition(QTextCursor.MoveOperation.Right)
        self.text_editor.setTextCursor(cursor)
    
    def get_current_line_info(self):
        """Get information about the current line."""
        cursor = self.text_editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        current_line = cursor.block().text()
        line_length = len(current_line)
        return line, column, current_line, line_length
    
    def is_modified(self):
        """Check if the document has been modified."""
        return self.text_editor.document().isModified()
    
    def set_modified(self, modified=True):
        """Set the document modified state."""
        self.text_editor.document().setModified(modified)
    
    def _on_text_changed(self):
        """Handle text change events."""
        self.update_line_numbers()
        self.textChanged.emit()
    
    def _on_cursor_position_changed(self):
        """Handle cursor position change events."""
        self.cursorPositionChanged.emit()
    
    def update_line_numbers(self):
        """Update the line numbers display."""
        text = self.text_editor.toPlainText()
        num_lines = text.count('\n') + 1
        numbers = '\n'.join(str(i) for i in range(1, num_lines + 1))
        self.line_numbers.setText(numbers)
    
    def resizeEvent(self, event):
        """Handle resize events to update the ruler position."""
        super().resizeEvent(event)
        if hasattr(self, 'ruler'):
            self.ruler.setGeometry(self.ruler.x(), 0, 1, self.text_editor.height())
    
    def show_find_dialog(self):
        """Show a dialog for finding text in the editor."""
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
        """Show a dialog for finding and replacing text in the editor."""
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
        """Find the next occurrence of text in the editor."""
        flags = QTextDocument.FindFlag(0)  # No flags by default
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
            
        cursor = self.text_editor.textCursor()
        found = self.text_editor.find(text, flags)
        
        if not found:
            # If not found, try from the start
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.text_editor.setTextCursor(cursor)
            found = self.text_editor.find(text, flags)
            
            if not found:
                QMessageBox.information(self, "Find", f"Cannot find '{text}'")
        
        return found
    
    def replace_text(self, find_text, replace_text, case_sensitive=False):
        """Replace the next occurrence of find_text with replace_text."""
        cursor = self.text_editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == find_text:
            cursor.insertText(replace_text)
            
        self.find_text(find_text, case_sensitive)
    
    def replace_all_text(self, find_text, replace_text, case_sensitive=False):
        """Replace all occurrences of find_text with replace_text."""
        cursor = self.text_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.text_editor.setTextCursor(cursor)
        
        count = 0
        flags = QTextDocument.FindFlag(0)
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        
        while self.text_editor.find(find_text, flags):
            cursor = self.text_editor.textCursor()
            cursor.insertText(replace_text)
            count += 1
            
        if count > 0:
            QMessageBox.information(self, "Replace All", 
                                  f"Replaced {count} occurrence(s)")
        else:
            QMessageBox.information(self, "Replace All", 
                                  f"Cannot find '{find_text}'")
        
        return count
    
    def goto_line(self, line_number):
        """Go to a specific line number."""
        self.set_cursor_position(line_number, 0)
        self.text_editor.ensureCursorVisible()
    
    def highlight_line(self, line_number):
        """Highlight a specific line."""
        cursor = self.text_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(line_number - 1):
            cursor.movePosition(QTextCursor.MoveOperation.Down)
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        self.text_editor.setTextCursor(cursor)
    
    def get_selected_text(self):
        """Get the currently selected text."""
        return self.text_editor.textCursor().selectedText()
    
    def has_selection(self):
        """Check if there is any text selected."""
        return self.text_editor.textCursor().hasSelection()
    
    def get_line_count(self):
        """Get the total number of lines."""
        return self.text_editor.document().blockCount()
    
    def get_character_count(self):
        """Get the total number of characters."""
        return len(self.text_editor.toPlainText())
    
    def get_word_count(self):
        """Get the total number of words."""
        text = self.text_editor.toPlainText()
        return len(text.split())
