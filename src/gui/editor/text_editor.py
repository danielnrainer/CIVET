"""
CIF Text Editor Component

This module provides a comprehensive text editor widget specifically designed 
for CIF files, featuring line numbers, syntax highlighting, find/replace functionality,
and customizable settings.

Settings Persistence:
- Settings are stored in the user's application data directory for cross-session persistence
- User-stored settings always override built-in defaults (see user_config.load_settings())
- Settings can be edited via Settings → Editor Settings... in the main menu
- A "Reset to Defaults" button allows users to restore default settings at any time

Settings Priority (highest to lowest):
1. User-saved settings in CIVET/settings.json
2. Built-in defaults in DEFAULT_SETTINGS
"""

from PyQt6.QtWidgets import (QWidget, QTextEdit, QHBoxLayout, QDialog, QVBoxLayout,
                           QLabel, QLineEdit, QCheckBox, QPushButton, QMessageBox,
                           QFontDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import (QFont, QFontMetrics, QTextCharFormat, QTextCursor, QTextDocument, QTextFormat, QColor, QTextBlockFormat)
import sys
import os

# Add parent directories to path for imports when running as module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.user_config import load_settings, set_setting, DEFAULT_SETTINGS

from .syntax_highlighter import CIFSyntaxHighlighter


class CIFTextEditor(QWidget):
    """
    A comprehensive CIF text editor widget with line numbers, syntax highlighting,
    and advanced editing features.
    
    Settings Behavior:
    - On initialization: Loads settings using load_settings(), which prefers user-saved
      settings over defaults
    - User can modify settings via Settings → Editor Settings... menu
    - Settings are automatically saved to user's config directory
    - User-saved settings always take precedence over defaults
    """
    
    # Signals
    textChanged = pyqtSignal()
    cursorPositionChanged = pyqtSignal()
    modificationChanged = pyqtSignal(bool)

    # Number of digits the line number gutter is sized to fit (right-aligned)
    LINE_NUMBER_DIGITS = 6
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Editor settings (will be populated from user_config)
        self.settings = {
            'font_family': 'Courier New',
            'font_size': 10,
            'line_numbers_enabled': True,
            'syntax_highlighting_enabled': True,
            'show_ruler': True,
            'syntax_highlighting_colors': DEFAULT_SETTINGS['editor']['syntax_highlighting_colors'].copy()
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
        """Load editor settings from unified user config."""
        try:
            all_settings = load_settings()
            editor_settings = all_settings.get('editor', {})
            
            # Map unified settings to local settings structure
            self.settings['font_family'] = editor_settings.get(
                'font_family', DEFAULT_SETTINGS['editor']['font_family'])
            self.settings['font_size'] = editor_settings.get(
                'font_size', DEFAULT_SETTINGS['editor']['font_size'])
            self.settings['line_numbers_enabled'] = editor_settings.get(
                'line_numbers_enabled', DEFAULT_SETTINGS['editor']['line_numbers_enabled'])
            self.settings['syntax_highlighting_enabled'] = editor_settings.get(
                'syntax_highlighting_enabled', DEFAULT_SETTINGS['editor']['syntax_highlighting_enabled'])
            self.settings['show_ruler'] = editor_settings.get(
                'show_ruler', DEFAULT_SETTINGS['editor']['show_ruler'])
            self.settings['syntax_highlighting_colors'] = editor_settings.get(
                'syntax_highlighting_colors', DEFAULT_SETTINGS['editor']['syntax_highlighting_colors']).copy()
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    def save_settings(self):
        """Save editor settings to unified user config."""
        try:
            # Save each setting using the unified config system
            set_setting('editor.font_family', self.settings['font_family'])
            set_setting('editor.font_size', self.settings['font_size'])
            set_setting('editor.line_numbers_enabled', self.settings['line_numbers_enabled'])
            set_setting('editor.syntax_highlighting_enabled', self.settings['syntax_highlighting_enabled'])
            set_setting('editor.show_ruler', self.settings['show_ruler'])
            set_setting('editor.syntax_highlighting_colors', self.settings['syntax_highlighting_colors'])
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

        # Size the line number gutter to comfortably fit up to
        # LINE_NUMBER_DIGITS digits, with a small margin for padding.
        digit_width = metrics.horizontalAdvance('0')
        self.line_numbers.setFixedWidth(digit_width * self.LINE_NUMBER_DIGITS + 16)

        # Update other settings
        self.line_numbers.setVisible(self.settings['line_numbers_enabled'])
        if hasattr(self, 'highlighter'):
            self.highlighter.apply_color_scheme(self.settings.get('syntax_highlighting_colors'))
            self.highlighter.setDocument(
                self.text_editor.document() if self.settings['syntax_highlighting_enabled'] 
                else None
            )
    
    def apply_settings_dict(self, settings_dict):
        """
        Apply settings from a dictionary (used for live preview).
        
        Args:
            settings_dict: Dictionary with editor settings
        """
        self.settings.update(settings_dict)
        self.apply_settings()
    
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

        # Right-align the line numbers (setText() rebuilds the document with
        # default left-aligned blocks, so alignment must be reapplied here).
        cursor = self.line_numbers.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        block_format = QTextBlockFormat()
        block_format.setAlignment(Qt.AlignmentFlag.AlignRight)
        cursor.mergeBlockFormat(block_format)
        cursor.clearSelection()
        self.line_numbers.setTextCursor(cursor)

        # Keep the gutter's scroll position aligned with the main editor.
        # Rebuilding the gutter's document (setText above) can leave its
        # scrollbar clamped to a stale position - e.g. right after loading a
        # file, before the editor's own scrollbar next emits valueChanged -
        # which otherwise shows numbers from the wrong part of the file until
        # the user manually scrolls. Sync immediately, and once more on the
        # next event loop iteration in case the editor's own layout (and thus
        # its scrollbar range/value) hasn't settled yet (e.g. during startup,
        # before the widget has been shown).
        self._sync_line_number_scroll()
        QTimer.singleShot(0, self._sync_line_number_scroll)

    def _sync_line_number_scroll(self):
        """Align the line-number gutter's scroll position with the main editor."""
        self.line_numbers.verticalScrollBar().setValue(
            self.text_editor.verticalScrollBar().value()
        )

    def resizeEvent(self, event):
        """Handle resize events to update the ruler position."""
        super().resizeEvent(event)
        if hasattr(self, 'ruler'):
            self.ruler.setGeometry(self.ruler.x(), 0, 1, self.text_editor.height())
    
    def _build_goto_line_row(self, dialog: QDialog) -> QHBoxLayout:
        """Build a 'Go to line' row, shared by the Find and Find & Replace dialogs."""
        goto_layout = QHBoxLayout()
        goto_layout.addWidget(QLabel("Go to line:"))

        goto_input = QLineEdit()
        goto_input.setPlaceholderText(f"1-{self.get_line_count()}")
        goto_input.setMaximumWidth(80)
        goto_layout.addWidget(goto_input)

        def _go():
            text = goto_input.text().strip()
            if not text:
                return
            try:
                line_number = int(text)
            except ValueError:
                QMessageBox.warning(dialog, "Go to Line", "Please enter a valid line number.")
                return
            total_lines = self.get_line_count()
            if line_number < 1 or line_number > total_lines:
                QMessageBox.warning(
                    dialog, "Go to Line",
                    f"Line {line_number} is out of range (1-{total_lines})."
                )
                return
            self.goto_line(line_number)

        goto_input.returnPressed.connect(_go)
        goto_button = QPushButton("Go")
        goto_button.clicked.connect(_go)
        goto_layout.addWidget(goto_button)
        goto_layout.addStretch()
        return goto_layout

    def show_find_dialog(self):
        """Show a dialog for finding text in the editor."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Find")
        layout = QVBoxLayout(dialog)

        # Search input
        search_label = QLabel("Find:")
        search_input = QLineEdit()
        layout.addWidget(search_label)
        layout.addWidget(search_input)

        # Options
        case_checkbox = QCheckBox("Match case")
        layout.addWidget(case_checkbox)

        # Go to line
        layout.addLayout(self._build_goto_line_row(dialog))

        # Buttons
        button_layout = QHBoxLayout()
        find_next_button = QPushButton("Find Next")
        find_next_button.clicked.connect(lambda: self.find_text(
            search_input.text(), 
            case_sensitive=case_checkbox.isChecked()
        ))
        find_next_button.setDefault(True)
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
        find_label = QLabel("Find:")
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

        # Go to line
        layout.addLayout(self._build_goto_line_row(dialog))

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
    
    def navigate_to_line(self, line_number, align='bottom'):
        """Move cursor to a specific line and optionally align it in the viewport."""
        doc = self.text_editor.document()
        if doc is None:
            return

        total_lines = doc.blockCount()
        if total_lines <= 0:
            return

        try:
            target_line = int(line_number)
        except (TypeError, ValueError):
            return

        target_line = max(1, min(target_line, total_lines))
        block = doc.findBlockByLineNumber(target_line - 1)
        if not block.isValid():
            return

        cursor = self.text_editor.textCursor()
        cursor.setPosition(block.position())
        self.text_editor.setTextCursor(cursor)
        self.text_editor.ensureCursorVisible()

        if align != 'bottom':
            return

        layout = doc.documentLayout()
        viewport = self.text_editor.viewport()
        scrollbar = self.text_editor.verticalScrollBar()
        if layout is None or viewport is None or scrollbar is None:
            return

        block_rect = layout.blockBoundingRect(block)
        desired_scroll = int(round(block_rect.bottom() - viewport.height()))
        desired_scroll = max(scrollbar.minimum(), min(desired_scroll, scrollbar.maximum()))
        scrollbar.setValue(desired_scroll)

    def set_temporary_line_highlights(self, line_numbers, selected_line=None):
        """Highlight a set of 1-based lines, with an optional distinct selected line."""
        doc = self.text_editor.document()
        if doc is None:
            return

        total_lines = doc.blockCount()
        if total_lines <= 0:
            self.text_editor.setExtraSelections([])
            return

        unique_lines = []
        seen = set()
        for line in line_numbers or []:
            try:
                line_num = int(line)
            except (TypeError, ValueError):
                continue
            if line_num < 1 or line_num > total_lines or line_num in seen:
                continue
            seen.add(line_num)
            unique_lines.append(line_num)

        try:
            selected_line_num = int(selected_line) if selected_line is not None else None
        except (TypeError, ValueError):
            selected_line_num = None

        base_format = QTextCharFormat()
        base_format.setBackground(QColor(255, 235, 176, 120))
        base_format.setProperty(QTextFormat.Property.FullWidthSelection, True)

        selected_format = QTextCharFormat()
        selected_format.setBackground(QColor(255, 196, 107, 180))
        selected_format.setProperty(QTextFormat.Property.FullWidthSelection, True)

        selections = []
        for line_num in unique_lines:
            block = doc.findBlockByLineNumber(line_num - 1)
            if not block.isValid():
                continue

            selection = QTextEdit.ExtraSelection()
            cursor = QTextCursor(block)
            cursor.clearSelection()
            selection.cursor = cursor
            selection.format = selected_format if selected_line_num == line_num else base_format
            selections.append(selection)

        self.text_editor.setExtraSelections(selections)

    def clear_temporary_line_highlights(self):
        """Clear transient dialog-driven line highlights."""
        self.text_editor.setExtraSelections([])

    def goto_line(self, line_number):
        """Go to a specific line and keep it at the bottom of the viewport when possible."""
        self.navigate_to_line(line_number, align='bottom')
    
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
