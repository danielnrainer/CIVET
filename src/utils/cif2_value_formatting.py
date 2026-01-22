"""
CIF2 Value Formatting Utilities
===============================

This module provides utilities for properly formatting CIF2 values according
to the CIF2 specification (https://www.iucr.org/resources/cif/cif2).

Key CIF2 requirements:
1. Characters [, ], {, } have special meaning in CIF2 (list/table delimiters)
   - Values containing these must be quoted if whitespace-delimited
2. Triple-quoted strings (''' or \""") are supported for multiline values
   - Alternative to semicolon-delimited text blocks
3. Single and double quotes can be used for simple quoted strings
"""

import re
from typing import Tuple, Optional


# Characters that require quoting in CIF2 whitespace-delimited values
CIF2_SPECIAL_CHARS = set('[]{}')

# Characters that always require some form of quoting
WHITESPACE_CHARS = set(' \t\n\r')


def needs_quoting(value: str) -> bool:
    """
    Check if a CIF2 value needs to be quoted.
    
    A value needs quoting if it contains:
    - Whitespace (spaces, tabs, newlines)
    - CIF2 special characters: [ ] { }
    - Single or double quotes (need opposite quote type or triple quotes)
    - Starts with underscore, hash, dollar, semicolon, or quote
    - Is empty
    - Looks like a CIF keyword (data_, loop_, save_, etc.)
    
    Args:
        value: The value to check
        
    Returns:
        True if the value needs quoting, False otherwise
    """
    if not value:
        return True  # Empty values need quoting
    
    # Check for whitespace
    if any(c in WHITESPACE_CHARS for c in value):
        return True
    
    # Check for CIF2 special characters
    if any(c in CIF2_SPECIAL_CHARS for c in value):
        return True
    
    # Check for quotes within the value
    if "'" in value or '"' in value:
        return True
    
    # Check for special starting characters
    if value[0] in '_#$;\'\"':
        return True
    
    # Check for CIF keywords
    lower_value = value.lower()
    if lower_value.startswith(('data_', 'loop_', 'save_', 'global_', 'stop_')):
        return True
    
    # Check for reserved words
    if lower_value in ('.', '?'):
        return False  # These are valid unquoted
    
    return False


def is_multiline(value: str) -> bool:
    """
    Check if a value should be treated as multiline.
    
    Args:
        value: The value to check
        
    Returns:
        True if the value contains newlines, False otherwise
    """
    return '\n' in value if value else False


def format_cif2_value(value: str, prefer_triple_quotes: bool = False) -> str:
    """
    Format a value for CIF2 output with proper quoting.
    
    This function ensures the value is properly formatted according to CIF2 rules:
    - Simple values: returned as-is
    - Values with spaces/special chars: single or double quoted
    - Values with quotes: use opposite quote type or triple quotes
    - Multiline values: use semicolon blocks or triple quotes
    
    Args:
        value: The value to format
        prefer_triple_quotes: If True, prefer triple quotes over semicolons for multiline
        
    Returns:
        The properly formatted value string
    """
    if value is None:
        return '?'
    
    value = str(value)
    
    if not value:
        return "''"  # Empty string
    
    # Check if it's a special CIF value
    if value in ('.', '?'):
        return value
    
    # Check if multiline
    if is_multiline(value):
        return format_multiline_value(value, prefer_triple_quotes)
    
    # Check if quoting is needed
    if not needs_quoting(value):
        return value
    
    # Choose appropriate quoting
    return choose_quote_style(value)


def choose_quote_style(value: str) -> str:
    """
    Choose the appropriate quoting style for a single-line value.
    
    Priority:
    1. Single quotes if value doesn't contain single quotes
    2. Double quotes if value doesn't contain double quotes
    3. Triple single quotes as fallback
    
    Args:
        value: The value to quote
        
    Returns:
        The quoted value string
    """
    has_single = "'" in value
    has_double = '"' in value
    
    if not has_single:
        return f"'{value}'"
    elif not has_double:
        return f'"{value}"'
    else:
        # Value contains both quote types - use triple quotes
        # Choose the one that doesn't appear at the start/end
        if not value.endswith("'"):
            return f"'''{value}'''"
        else:
            return f'"""{value}"""'


def format_multiline_value(value: str, prefer_triple_quotes: bool = False) -> str:
    """
    Format a multiline value for CIF2 output.
    
    Options:
    1. Semicolon-delimited text block (traditional, wide compatibility)
    2. Triple-quoted string (CIF2-specific, more compact)
    
    Args:
        value: The multiline value to format
        prefer_triple_quotes: If True, use triple quotes instead of semicolons
        
    Returns:
        The formatted multiline value string
    """
    if prefer_triple_quotes:
        # Check which triple quote style to use
        has_triple_single = "'''" in value
        has_triple_double = '"""' in value
        
        if not has_triple_single:
            return f"'''\n{value}\n'''"
        elif not has_triple_double:
            return f'"""\n{value}\n"""'
        else:
            # Both triple quote styles present - fall back to semicolons
            pass
    
    # Use semicolon-delimited format (traditional)
    lines = value.split('\n')
    return ';\n' + '\n'.join(lines) + '\n;'


def parse_triple_quoted_string(text: str, start_pos: int) -> Tuple[Optional[str], int]:
    """
    Parse a triple-quoted string from CIF2 content.
    
    Args:
        text: The full text content
        start_pos: Position where the triple quote starts
        
    Returns:
        Tuple of (parsed_value, end_position) or (None, start_pos) if not valid
    """
    if start_pos + 3 > len(text):
        return None, start_pos
    
    # Determine quote style
    quote_char = text[start_pos]
    if quote_char not in ('"', "'"):
        return None, start_pos
    
    triple_quote = quote_char * 3
    
    # Check if it's actually a triple quote
    if text[start_pos:start_pos + 3] != triple_quote:
        return None, start_pos
    
    # Find the closing triple quote
    content_start = start_pos + 3
    end_pos = text.find(triple_quote, content_start)
    
    if end_pos == -1:
        return None, start_pos  # Unclosed triple quote
    
    content = text[content_start:end_pos]
    
    # Strip leading/trailing newline if present (per CIF2 spec)
    if content.startswith('\n'):
        content = content[1:]
    if content.endswith('\n'):
        content = content[:-1]
    
    return content, end_pos + 3


def is_triple_quoted(text: str, pos: int = 0) -> bool:
    """
    Check if text at position starts with a triple quote.
    
    Args:
        text: The text to check
        pos: Position to check at
        
    Returns:
        True if triple quote found, False otherwise
    """
    if pos + 3 > len(text):
        return False
    
    three_chars = text[pos:pos + 3]
    return three_chars in ("'''", '"""')


def escape_for_cif2(value: str) -> str:
    """
    Ensure a value is safe for CIF2 by applying necessary quoting.
    
    This is a convenience function that handles all CIF2 special cases:
    - Brackets [ ] { } are properly quoted
    - Whitespace triggers quoting
    - Multiline values use appropriate format
    
    Args:
        value: The raw value
        
    Returns:
        A CIF2-safe formatted value
    """
    return format_cif2_value(value, prefer_triple_quotes=False)


def contains_cif2_special_chars(value: str) -> bool:
    """
    Check if a value contains CIF2 special characters that need quoting.
    
    Special characters in CIF2: [ ] { }
    These delimit list and table values and must be quoted in regular values.
    
    Args:
        value: The value to check
        
    Returns:
        True if the value contains CIF2 special characters
    """
    if not value:
        return False
    return any(c in CIF2_SPECIAL_CHARS for c in value)
