"""CIF syntax highlighting for the text editor."""

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QTextCharFormat, QSyntaxHighlighter, QColor, QFont


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
        
        # Check for loop end conditions
        # A loop ends when we encounter:
        # 1. A CIF header (data_, save_, global_, stop_)
        # 2. A new loop_ statement
        # 3. A field that starts with _ after we've already been in the data phase
        if self.in_loop:
            # Check for CIF headers that definitely end a loop
            if (stripped_text.lower().startswith('data_') or
                stripped_text.lower().startswith('save_') or
                stripped_text.lower().startswith('global_') or
                stripped_text.lower().startswith('stop_')):
                # This marks the end of the current loop
                self.in_loop = False
                self.in_loop_data = False
                self.setCurrentBlockState(0)
                # Continue processing this line as a normal header below
            
            # Check if we're starting a new loop
            elif stripped_text.lower() == 'loop_':
                # New loop starts, end current loop and start new one
                self.setFormat(0, len(text), self.loop_keyword_format)
                self.in_loop = True
                self.in_loop_data = False
                self.setCurrentBlockState(2)
                return
            
            # Check if this is a field starting with _ after we've been in data phase
            elif (self.in_loop_data and stripped_text.startswith('_')):
                # A field after loop data indicates the loop has ended
                self.in_loop = False
                self.in_loop_data = False
                self.setCurrentBlockState(0)
                # Continue processing this line as a normal field below
            
            # If we're in a loop and this line has content
            elif stripped_text:
                if stripped_text.startswith('_'):
                    # This is a loop field definition
                    if self.in_loop_data:
                        # We were in data phase but now see a field - loop ended
                        self.in_loop = False
                        self.in_loop_data = False
                        self.setCurrentBlockState(0)
                        # Continue processing as normal field
                    else:
                        # Continue in loop field definition state
                        self.setCurrentBlockState(2)
                else:
                    # This is not a field, so it must be loop data
                    if not self.in_loop_data:
                        # Transition from field definitions to data
                        self.in_loop_data = True
                    self.setCurrentBlockState(3)
            else:
                # Empty line in loop - this ends the loop if we're in data phase
                if self.in_loop_data:
                    # Empty line after loop data ends the loop
                    self.in_loop = False
                    self.in_loop_data = False
                    self.setCurrentBlockState(0)
                else:
                    # Empty line in field definition phase - maintain loop state
                    self.setCurrentBlockState(2)
        else:
            # Not in a loop
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
