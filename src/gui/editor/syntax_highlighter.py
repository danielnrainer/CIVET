"""CIF syntax highlighting for the text editor."""

from typing import Callable, Optional

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QTextCharFormat, QSyntaxHighlighter, QColor, QFont


class CIFSyntaxHighlighter(QSyntaxHighlighter):
    """
    CIF syntax highlighter with optional validation-aware field highlighting.
    
    The highlighter can be configured with a field validator callback that
    determines the category of each field name. This allows for different
    colors based on whether a field is:
    - valid: Known in the CIF dictionary (blue)
    - registered: Uses a registered IUCr prefix (cyan/teal)
    - user_allowed: User has allowed this prefix/field (cyan/teal)
    - unknown: Not recognized in any dictionary (orange)
    - deprecated: Field is deprecated (dark yellow with strikethrough)
    
    If no validator is set, all fields are highlighted in blue (backwards compatible).
    """
    
    # Validation result constants
    VALID = "valid"
    REGISTERED = "registered"
    USER_ALLOWED = "user_allowed"
    UNKNOWN = "unknown"
    DEPRECATED = "deprecated"
    
    # Block state constants for multi-line constructs
    STATE_NORMAL = 0
    STATE_SEMICOLON_MULTILINE = 1
    STATE_LOOP_FIELDS = 2
    STATE_LOOP_DATA = 3
    STATE_TRIPLE_SINGLE_QUOTE = 4  # Inside ''' ... '''
    STATE_TRIPLE_DOUBLE_QUOTE = 5  # Inside """ ... """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # Field validator callback - set by main_window to avoid circular imports
        self._field_validator: Optional[Callable[[str], str]] = None
        
        # Field names (starting with _ at beginning of line, including hyphens, brackets, slashes, etc.)
        # This is the default format used when no validator is set
        self.field_format = QTextCharFormat()
        self.field_format.setForeground(QColor("#0000FF"))  # Blue
        
        # Field name pattern for manual matching (not in highlighting_rules when validator is set)
        self._field_pattern = QRegularExpression(r'^\s*(_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*)')
        
        # Add to highlighting rules (used only when no validator is set)
        self.highlighting_rules.append((
            QRegularExpression(r'^\s*_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*'),
            self.field_format
        ))
        
        # Validation-aware field formats
        self._init_validation_formats()
        
        # Values in quotes (single and double)
        self.value_format = QTextCharFormat()
        self.value_format.setForeground(QColor("#008000"))  # Green
        
        # Single-quoted strings
        self.highlighting_rules.append((
            QRegularExpression(r"'[^']*'"),
            self.value_format
        ))
        
        # Double-quoted strings
        self.highlighting_rules.append((
            QRegularExpression(r'"[^"]*"'),
            self.value_format
        ))
        
        # Triple-quoted strings (CIF2) - must come before single quotes in processing
        # Triple single quotes
        self.highlighting_rules.append((
            QRegularExpression(r"'''.*?'''"),
            self.value_format
        ))
        
        # Triple double quotes
        self.highlighting_rules.append((
            QRegularExpression(r'""".*?"""'),
            self.value_format
        ))
        
        # Multi-line values format (semicolon blocks and multiline triple quotes)
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
    
    def _init_validation_formats(self):
        """Initialize text formats for different validation categories."""
        # Valid format - same as default field format (blue)
        self.valid_format = QTextCharFormat()
        self.valid_format.setForeground(QColor("#0000FF"))  # Blue
        
        # Registered local format - for fields with registered IUCr prefixes
        self.registered_local_format = QTextCharFormat()
        self.registered_local_format.setForeground(QColor("#008B8B"))  # Cyan/Teal (DarkCyan)
        
        # User-allowed format - same as registered local (cyan/teal)
        self.user_allowed_format = QTextCharFormat()
        self.user_allowed_format.setForeground(QColor("#008B8B"))  # Cyan/Teal (DarkCyan)
        
        # Unknown format - for unrecognized fields
        self.unknown_format = QTextCharFormat()
        self.unknown_format.setForeground(QColor("#FF6600"))  # Orange
        
        # Deprecated format - for deprecated fields
        self.deprecated_format = QTextCharFormat()
        self.deprecated_format.setForeground(QColor("#B8860B"))  # Dark yellow/gold (DarkGoldenrod)
        self.deprecated_format.setFontStrikeOut(True)  # Strikethrough
    
    def set_field_validator(self, validator_callback: Optional[Callable[[str], str]]):
        """
        Set a callback function that validates field names.
        
        The callback takes a field name (str) and returns one of:
        - "valid" - Known in dictionary
        - "registered" - Uses registered IUCr prefix
        - "user_allowed" - User has allowed this prefix/field
        - "unknown" - Not recognized
        - "deprecated" - Deprecated field
        
        If set to None, the highlighter reverts to default behavior
        (all fields highlighted in blue).
        
        After setting, call rehighlight() to apply the new validation.
        
        Args:
            validator_callback: The validation function, or None to disable validation highlighting.
        """
        self._field_validator = validator_callback
    
    def has_field_validator(self) -> bool:
        """Check if a field validator callback is currently set."""
        return self._field_validator is not None
    
    def _get_format_for_field(self, field_name: str) -> QTextCharFormat:
        """
        Get the appropriate text format for a field name based on validation.
        
        Args:
            field_name: The CIF field name (including leading underscore).
            
        Returns:
            The QTextCharFormat to use for this field.
        """
        if self._field_validator is None:
            return self.field_format  # Default blue
        
        try:
            category = self._field_validator(field_name)
            
            if category == self.VALID:
                return self.valid_format
            elif category == self.REGISTERED:
                return self.registered_local_format
            elif category == self.USER_ALLOWED:
                return self.user_allowed_format
            elif category == self.UNKNOWN:
                return self.unknown_format
            elif category == self.DEPRECATED:
                return self.deprecated_format
            else:
                # Unknown category, use default
                return self.field_format
        except Exception:
            # If validation fails, use default format
            return self.field_format

    def highlightBlock(self, text):
        # Check previous block state
        prev_state = self.previousBlockState()
        if prev_state == self.STATE_SEMICOLON_MULTILINE:
            self.in_multiline = True
            self.in_loop = False
            self.in_loop_data = False
        elif prev_state == self.STATE_LOOP_FIELDS:
            self.in_loop = True
            self.in_loop_data = False
            self.in_multiline = False
        elif prev_state == self.STATE_LOOP_DATA:
            self.in_loop = True
            self.in_loop_data = True
            self.in_multiline = False
        elif prev_state == self.STATE_TRIPLE_SINGLE_QUOTE:
            # Inside a multi-line triple single-quoted string
            self._handle_multiline_triple_quote(text, "'''", self.STATE_TRIPLE_SINGLE_QUOTE)
            return
        elif prev_state == self.STATE_TRIPLE_DOUBLE_QUOTE:
            # Inside a multi-line triple double-quoted string
            self._handle_multiline_triple_quote(text, '"""', self.STATE_TRIPLE_DOUBLE_QUOTE)
            return
        else:
            self.in_multiline = False
            self.in_loop = False
            self.in_loop_data = False
        
        stripped_text = text.strip()
        
        # Handle multiline semicolon values first
        if text.startswith(';'):
            self.setFormat(0, len(text), self.multiline_format)
            self.in_multiline = not self.in_multiline
            if self.in_multiline:
                self.setCurrentBlockState(self.STATE_SEMICOLON_MULTILINE)
            else:
                self.setCurrentBlockState(self.STATE_NORMAL)
            return
        elif self.in_multiline:
            self.setFormat(0, len(text), self.multiline_format)
            self.setCurrentBlockState(self.STATE_SEMICOLON_MULTILINE)
            return
        
        # Check for triple-quoted strings that start on this line
        if self._check_triple_quote_start(text):
            return
        
        # Check for loop start
        if stripped_text.lower() == 'loop_':
            self.setFormat(0, len(text), self.loop_keyword_format)
            self.in_loop = True
            self.in_loop_data = False
            self.setCurrentBlockState(self.STATE_LOOP_FIELDS)
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
                self.setCurrentBlockState(self.STATE_NORMAL)
                # Continue processing this line as a normal header below
            
            # Check if we're starting a new loop
            elif stripped_text.lower() == 'loop_':
                # New loop starts, end current loop and start new one
                self.setFormat(0, len(text), self.loop_keyword_format)
                self.in_loop = True
                self.in_loop_data = False
                self.setCurrentBlockState(self.STATE_LOOP_FIELDS)
                return
            
            # Check if this is a field starting with _ after we've been in data phase
            elif (self.in_loop_data and stripped_text.startswith('_')):
                # A field after loop data indicates the loop has ended
                self.in_loop = False
                self.in_loop_data = False
                self.setCurrentBlockState(self.STATE_NORMAL)
                # Continue processing this line as a normal field below
            
            # If we're in a loop and this line has content
            elif stripped_text:
                if stripped_text.startswith('_'):
                    # This is a loop field definition
                    if self.in_loop_data:
                        # We were in data phase but now see a field - loop ended
                        self.in_loop = False
                        self.in_loop_data = False
                        self.setCurrentBlockState(self.STATE_NORMAL)
                        # Continue processing as normal field
                    else:
                        # Continue in loop field definition state
                        self.setCurrentBlockState(self.STATE_LOOP_FIELDS)
                else:
                    # This is not a field, so it must be loop data
                    if not self.in_loop_data:
                        # Transition from field definitions to data
                        self.in_loop_data = True
                    self.setCurrentBlockState(self.STATE_LOOP_DATA)
            else:
                # Empty line in loop - this ends the loop if we're in data phase
                if self.in_loop_data:
                    # Empty line after loop data ends the loop
                    self.in_loop = False
                    self.in_loop_data = False
                    self.setCurrentBlockState(self.STATE_NORMAL)
                else:
                    # Empty line in field definition phase - maintain loop state
                    self.setCurrentBlockState(self.STATE_LOOP_FIELDS)
        else:
            # Not in a loop
            self.setCurrentBlockState(self.STATE_NORMAL)
        
        # Apply background highlighting for loop data
        if self.in_loop_data and stripped_text and not stripped_text.startswith('#'):
            self.setFormat(0, len(text), self.loop_data_format)
        
        # Apply validation-aware field highlighting if validator is set
        if self._field_validator is not None:
            self._apply_validated_field_highlighting(text, stripped_text)
        else:
            # Apply standard rules (backwards compatible - no validation)
            self._apply_standard_rules(text, stripped_text)
        
        # Special formatting for loop field names (applies after field highlighting)
        # Only use the default loop_field_format if no validator is set
        if self.in_loop and not self.in_loop_data and stripped_text.startswith('_'):
            if self._field_validator is not None:
                # Use validated highlighting even for loop fields
                self._apply_validated_loop_field_highlighting(text, stripped_text)
            else:
                self.setFormat(0, len(text), self.loop_field_format)
    
    def _check_triple_quote_start(self, text: str) -> bool:
        """Check if line contains a triple-quoted string start.
        
        Handles both single-line triple-quoted strings (starts and ends on same line)
        and multi-line triple-quoted strings that continue to next lines.
        
        Returns True if this line was handled as a triple-quote line.
        """
        # Look for triple quotes in the text
        for quote_type, state in [("'''", self.STATE_TRIPLE_SINGLE_QUOTE), 
                                  ('"""', self.STATE_TRIPLE_DOUBLE_QUOTE)]:
            start_pos = text.find(quote_type)
            if start_pos != -1:
                # Found a triple quote start
                # Look for matching end on same line
                end_pos = text.find(quote_type, start_pos + 3)
                if end_pos != -1:
                    # Single-line triple-quoted string
                    # Apply format from start to end (inclusive of closing quotes)
                    self.setFormat(start_pos, end_pos + 3 - start_pos, self.value_format)
                    # Apply standard highlighting to parts before and after
                    # Continue with normal processing for the rest
                    return False  # Let normal processing continue for the rest of the line
                else:
                    # Multi-line triple-quoted string starts here
                    self.setFormat(start_pos, len(text) - start_pos, self.multiline_format)
                    self.setCurrentBlockState(state)
                    return True
        return False
    
    def _handle_multiline_triple_quote(self, text: str, quote_type: str, state: int):
        """Handle a line that's inside a multi-line triple-quoted string.
        
        Applies multiline format and checks if the string ends on this line.
        """
        end_pos = text.find(quote_type)
        if end_pos != -1:
            # String ends on this line
            self.setFormat(0, end_pos + 3, self.multiline_format)
            self.setCurrentBlockState(self.STATE_NORMAL)
            # Note: any content after the closing quotes on this line
            # will not be highlighted correctly in this simple implementation
        else:
            # String continues
            self.setFormat(0, len(text), self.multiline_format)
            self.setCurrentBlockState(state)
    
    def _apply_standard_rules(self, text: str, stripped_text: str):
        """Apply standard highlighting rules without validation (backwards compatible)."""
        for pattern, format in self.highlighting_rules:
            matches = pattern.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                # Don't override loop data formatting for basic patterns
                if not (self.in_loop_data and pattern.pattern() in [r'^\s*_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*', r"'[^']*'"]):
                    self.setFormat(match.capturedStart(), match.capturedLength(), format)
    
    def _apply_validated_field_highlighting(self, text: str, stripped_text: str):
        """Apply validation-aware highlighting to field names."""
        # First, apply non-field highlighting rules (quotes, etc.)
        for pattern, format in self.highlighting_rules:
            # Skip the field pattern - we'll handle it with validation
            if pattern.pattern() == r'^\s*_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*':
                continue
            matches = pattern.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                # Don't override loop data formatting
                if not (self.in_loop_data and pattern.pattern() == r"'[^']*'"):
                    self.setFormat(match.capturedStart(), match.capturedLength(), format)
        
        # Now handle field names with validation
        # Don't apply field highlighting if we're in loop data mode
        if self.in_loop_data:
            return
        
        # Match field name at start of line
        match = self._field_pattern.match(text)
        if match.hasMatch():
            # Extract just the field name (group 1 captures the underscore and name)
            field_name = match.captured(1)
            start = match.capturedStart(1)
            length = match.capturedLength(1)
            
            # Get the appropriate format based on validation
            format = self._get_format_for_field(field_name)
            self.setFormat(start, length, format)
    
    def _apply_validated_loop_field_highlighting(self, text: str, stripped_text: str):
        """Apply validation-aware highlighting to loop field definitions."""
        # For loop fields, we want to use the validation colors but possibly
        # with a slightly different style to indicate they're in a loop
        match = self._field_pattern.match(text)
        if match.hasMatch():
            field_name = match.captured(1)
            start = match.capturedStart(1)
            length = match.capturedLength(1)
            
            # Get the validation-based format
            base_format = self._get_format_for_field(field_name)
            
            # Create a loop-aware format based on the validation result
            loop_format = QTextCharFormat(base_format)
            # Make loop fields italic to distinguish them from regular fields
            loop_format.setFontItalic(True)
            
            self.setFormat(start, length, loop_format)
