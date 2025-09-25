"""
Comprehensive CIF file parser and field manager.

This module handles parsing actual CIF file content, extracting field values,
and managing both single-line and multiline CIF fields. It also provides
functionality for reformatting CIF files with proper line length handling.

This is different from CIF_field_parsing.py, which handles field definition
templates for validation purposes.

Classes:
    CIFField: Represents an actual field instance parsed from a CIF file
    CIFLoop: Represents a CIF loop structure with multiple fields and data rows
    CIFParser: Main parser class for processing CIF file content
"""

import re
from typing import Dict, Any, List, Tuple, Optional


class CIFField:
    """Represents a single CIF field instance parsed from a CIF file.
    
    This contains the actual value and metadata of a field found in a CIF file.
    This is different from CIFField in CIF_field_parsing.py, which
    represents field definition templates for validation.
    """
    
    def __init__(self, name: str, value: Any = None, is_multiline: bool = False, 
                 line_number: int = None, raw_lines: List[str] = None):
        self.name = name
        self.value = value
        self.is_multiline = is_multiline
        self.line_number = line_number  # Starting line number in the file
        self.raw_lines = raw_lines or []  # Original lines from the file
    
    def __repr__(self):
        return f"CIFField(name='{self.name}', value='{self.value}', multiline={self.is_multiline})"


class CIFLoop:
    """Represents a CIF loop structure with field names and data rows."""
    
    def __init__(self, field_names: List[str], data_rows: List[List[str]], line_number: int = None):
        self.field_names = field_names
        self.data_rows = data_rows
        self.line_number = line_number
    
    def __repr__(self):
        return f"CIFLoop(fields={len(self.field_names)}, rows={len(self.data_rows)})"


class CIFParser:
    """Main parser class for processing CIF file content."""
    
    def __init__(self):
        self.fields: Dict[str, CIFField] = {}
        self.loops: List[CIFLoop] = []
        self.content_blocks: List[Dict] = []  # Ordered list of fields, loops, and header lines
        self.header_lines: List[str] = []  # Store important header lines like data_
        
    def add_legacy_compatibility_fields(self, dict_manager) -> str:
        """
        Add deprecated fields alongside their modern equivalents for validation tool compatibility.
        
        This addresses the issue where modern CIF dictionaries have deprecated certain fields
        but validation tools (like checkCIF/PLAT) haven't been updated to recognize the modern
        equivalents. By including both versions with the same value, we ensure compatibility
        with both old and new validation systems.
        
        Args:
            dict_manager: CIFDictionaryManager instance for field conversion
            
        Returns:
            Report string describing what compatibility fields were added
        """
        if not dict_manager:
            return "No dictionary manager provided"
            
        added_fields = []
        
        # Define critical deprecated fields that validation tools often still require
        critical_deprecated_fields = [
            '_cell_measurement_temperature',
            '_cell_measurement_reflns_used',
            '_cell_measurement_pressure',
            '_cell_measurement_radiation',
            '_cell_measurement_wavelength',
            '_diffrn_source',
            '_diffrn_radiation_type',
            '_diffrn_radiation_wavelength'
        ]
        
        # Check each critical field
        for deprecated_field in critical_deprecated_fields:
            # Get the modern equivalent
            modern_field_cif2 = dict_manager.get_modern_equivalent(deprecated_field, prefer_format="CIF2")
            modern_field_cif1 = dict_manager.get_modern_equivalent(deprecated_field, prefer_format="CIF1")
            
            # Choose the modern field (prefer the one that exists in our CIF)
            modern_field = None
            if modern_field_cif2 and modern_field_cif2 in self.fields:
                modern_field = modern_field_cif2
            elif modern_field_cif1 and modern_field_cif1 in self.fields:
                modern_field = modern_field_cif1
            elif modern_field_cif2:  # Default to CIF2 if neither exists
                modern_field = modern_field_cif2
            elif modern_field_cif1:  # Fallback to CIF1
                modern_field = modern_field_cif1
            
            # If we have a modern field with a value and the deprecated field doesn't exist
            if (modern_field and 
                modern_field in self.fields and 
                self.fields[modern_field].value and 
                self.fields[modern_field].value != "(in loop)" and
                deprecated_field not in self.fields):
                
                # Create the deprecated field with the same value
                modern_field_obj = self.fields[modern_field]
                deprecated_field_obj = CIFField(
                    name=deprecated_field,
                    value=modern_field_obj.value,
                    is_multiline=modern_field_obj.is_multiline,
                    line_number=None,  # Will be placed appropriately when generating content
                    raw_lines=[]
                )
                
                self.fields[deprecated_field] = deprecated_field_obj
                
                # Add to content blocks right after the modern field
                self._insert_compatibility_field_in_blocks(deprecated_field_obj, modern_field)
                
                added_fields.append(f"{deprecated_field} = {modern_field_obj.value} (from {modern_field})")
        
        # Generate report
        if added_fields:
            report = f"Added {len(added_fields)} compatibility field(s) for legacy validation tools:\n"
            for field_info in added_fields:
                report += f"  • {field_info}\n"
            report += "\nThese deprecated fields have the same values as their modern equivalents."
        else:
            report = "No compatibility fields needed - either modern equivalents not found or deprecated fields already exist."
            
        return report
    
    def _insert_compatibility_field_in_blocks(self, deprecated_field_obj: CIFField, modern_field_name: str):
        """Insert a compatibility field in the content blocks right after its modern equivalent."""
        # Find the modern field in content blocks
        for i, block in enumerate(self.content_blocks):
            if (block.get('type') == 'field' and 
                block.get('content') and 
                hasattr(block['content'], 'name') and
                block['content'].name == modern_field_name):
                
                # Insert the deprecated field right after the modern one
                self.content_blocks.insert(i + 1, {
                    'type': 'field',
                    'content': deprecated_field_obj
                })
                break
        else:
            # If modern field not found in blocks, append at the end
            self.content_blocks.append({
                'type': 'field', 
                'content': deprecated_field_obj
            })
        
    def parse_file(self, content: str) -> Dict[str, CIFField]:
        """Parse CIF content and return a dictionary of fields."""
        self.fields = {}
        self.loops = []
        self.content_blocks = []
        self.header_lines = []
        lines = content.splitlines()
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                i += 1
                continue
            
            # Check for data block identifier and other important header lines
            if (line.lower().startswith('data_') or 
                line.lower().startswith('save_') or 
                line.lower().startswith('global_') or
                line.lower().startswith('stop_')):
                self.header_lines.append(line)
                self.content_blocks.append({'type': 'header', 'content': line})
                i += 1
                continue
            
            # Check for loop structure
            if line.lower().startswith('loop_'):
                loop, lines_consumed = self._parse_loop(lines, i)
                if loop:
                    self.loops.append(loop)
                    self.content_blocks.append({'type': 'loop', 'content': loop})
                    # Add loop fields to main fields dict for compatibility
                    for field_name in loop.field_names:
                        if field_name not in self.fields:
                            self.fields[field_name] = CIFField(name=field_name, value="(in loop)", line_number=i + 1)
                i += lines_consumed
                continue
            
            # Check if this line starts a field definition
            if line.startswith('_'):
                field_name, value, lines_consumed = self._parse_field(lines, i)
                if field_name:
                    field = CIFField(
                        name=field_name,
                        value=value,
                        is_multiline=self._is_multiline_value(value),
                        line_number=i + 1,
                        raw_lines=lines[i:i+lines_consumed]
                    )
                    self.fields[field_name] = field
                    self.content_blocks.append({'type': 'field', 'content': field})
                i += lines_consumed
            else:
                i += 1
                
        return self.fields
    
    def _parse_loop(self, lines: List[str], start_index: int) -> Tuple[Optional[CIFLoop], int]:
        """Parse a CIF loop structure starting at the given line index.
        
        Returns:
            Tuple of (CIFLoop object or None, lines_consumed)
        """
        i = start_index + 1  # Skip the 'loop_' line
        field_names = []
        
        # Parse field names
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                i += 1
                continue
            
            # Check if this is a field name
            if line.startswith('_'):
                field_names.append(line)
                i += 1
            else:
                # We've reached the data section
                break
        
        if not field_names:
            return None, i - start_index
        
        # Parse data rows
        data_rows = []
        current_row = []
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip comments but not empty lines
            if line.startswith('#'):
                i += 1
                continue
            
            # Empty line ends the loop
            if not line:
                break
            
            # Check if we've reached the end of the loop (next field or loop)
            if line.startswith('_') or line.lower().startswith('loop_'):
                break
            
            # Check for multiline values (semicolon blocks) in the data
            values, multiline_consumed = self._parse_loop_data_line(lines, i)
            current_row.extend(values)
            
            # Advance by the number of lines consumed (including multiline blocks)
            i += multiline_consumed
            
            # Check if we have a complete row
            if len(current_row) >= len(field_names):
                # Extract one complete row
                row = current_row[:len(field_names)]
                data_rows.append(row)
                current_row = current_row[len(field_names):]
        
        # Handle any remaining partial row
        if current_row:
            # Pad with empty values if needed
            while len(current_row) < len(field_names):
                current_row.append('')
            data_rows.append(current_row)
        
        loop = CIFLoop(field_names, data_rows, start_index + 1)
        return loop, i - start_index
    
    def _parse_data_line(self, line: str) -> List[str]:
        """Parse a line of data values, handling quoted strings properly."""
        values = []
        i = 0
        
        while i < len(line):
            # Skip whitespace
            while i < len(line) and line[i].isspace():
                i += 1
            
            if i >= len(line):
                break
            
            # Handle quoted strings
            if line[i] in ("'", '"'):
                quote_char = line[i]
                i += 1  # Skip opening quote
                value = ""
                
                while i < len(line):
                    if line[i] == quote_char:
                        # Found closing quote
                        i += 1
                        break
                    value += line[i]
                    i += 1
                
                values.append(value)
            else:
                # Handle unquoted value
                value = ""
                while i < len(line) and not line[i].isspace():
                    value += line[i]
                    i += 1
                
                if value:
                    values.append(value)
        
        return values

    def _parse_loop_data_line(self, lines: List[str], start_index: int) -> Tuple[List[str], int]:
        """Parse a line of loop data values, handling multiline semicolon blocks.
        
        Returns:
            Tuple of (values, lines_consumed)
        """
        line = lines[start_index].strip()
        
        # Special case: check if this line is just a semicolon (multiline block start)
        if line == ';':
            multiline_value, consumed = self._parse_multiline_in_loop(lines, start_index + 1, 0)
            return [multiline_value], consumed + 1  # +1 for the semicolon line itself
        
        # Otherwise, parse values from this line normally
        values = self._parse_data_line(line)
        return values, 1

    def _parse_multiline_in_loop(self, lines: List[str], start_index: int, char_index: int) -> Tuple[str, int]:
        """Parse a multiline value within loop data starting from after a semicolon.
        
        Returns:
            Tuple of (multiline_value, total_lines_consumed_after_semicolon)
        """
        value_lines = []
        i = start_index
        
        # Parse lines until closing semicolon
        while i < len(lines):
            line = lines[i]
            
            # Check for closing semicolon
            if line.strip() == ';':
                i += 1
                break
            
            # Add line to multiline value (preserve original formatting)
            value_lines.append(line.rstrip())
            i += 1
        
        multiline_value = '\n'.join(value_lines)
        lines_consumed = i - start_index
        return multiline_value, lines_consumed
    
    def _parse_field(self, lines: List[str], start_index: int) -> Tuple[str, str, int]:
        """Parse a single field starting at the given line index.
        
        Returns:
            Tuple of (field_name, value, lines_consumed)
        """
        line = lines[start_index].strip()
        
        # Parse field name
        parts = line.split(maxsplit=1)
        if not parts or not parts[0].startswith('_'):
            return None, None, 1
        
        field_name = parts[0]
        
        # Check if value is on the same line
        if len(parts) > 1:
            value_part = parts[1].strip()
            
            # Check if it's a quoted string
            if (value_part.startswith("'") and value_part.endswith("'")) or \
               (value_part.startswith('"') and value_part.endswith('"')):
                return field_name, value_part[1:-1], 1
            
            # Check if it starts a multiline block
            if value_part == ';':
                return self._parse_multiline_value(lines, start_index + 1, field_name)
            
            # Check if content starts on same line as opening semicolon (;content...)
            if value_part.startswith(';') and len(value_part) > 1:
                return self._parse_multiline_value_with_content_on_first_line(lines, start_index, field_name)
            
            # Regular single-line value
            return field_name, value_part, 1
        
        # Value might be on the next line(s)
        if start_index + 1 < len(lines):
            next_line = lines[start_index + 1].strip()
            
            # Check if next line starts multiline block
            if next_line == ';':
                return self._parse_multiline_value(lines, start_index + 2, field_name)
            
            # Check if next line contains content starting with semicolon (;content...)
            if next_line.startswith(';') and len(next_line) > 1:
                return self._parse_multiline_value_with_content_on_first_line(lines, start_index + 1, field_name)
            
            # Single line value on next line
            if next_line and not next_line.startswith('_'):
                # Handle quoted values
                if (next_line.startswith("'") and next_line.endswith("'")) or \
                   (next_line.startswith('"') and next_line.endswith('"')):
                    return field_name, next_line[1:-1], 2
                return field_name, next_line, 2
        
        # No value found
        return field_name, None, 1
    
    def _parse_multiline_value(self, lines: List[str], start_index: int, field_name: str) -> Tuple[str, str, int]:
        """Parse a multiline value starting after the opening semicolon."""
        value_lines = []
        i = start_index
        
        # Handle case where content starts on the same line as opening semicolon
        if start_index > 0:
            prev_line = lines[start_index - 1].strip()
            if prev_line.startswith(';') and len(prev_line) > 1:
                # Content starts on same line as opening semicolon
                content = prev_line[1:].strip()
                if content:
                    value_lines.append(content)
                # Adjust to look for closing semicolon
                start_index_actual = start_index
            else:
                start_index_actual = start_index
        else:
            start_index_actual = start_index
        
        # Parse lines until closing semicolon
        while i < len(lines):
            line = lines[i]
            
            # Check for closing semicolon
            if line.strip() == ';':
                lines_consumed = i - start_index + 2  # +2 for opening and closing semicolons
                return field_name, '\n'.join(value_lines), lines_consumed
            
            # Add line to value (preserve original spacing)
            value_lines.append(line)
            i += 1
        
        # If we reach here, no closing semicolon was found
        lines_consumed = len(lines) - start_index + 1
        return field_name, '\n'.join(value_lines), lines_consumed
    
    def _parse_multiline_value_with_content_on_first_line(self, lines: List[str], start_index: int, field_name: str) -> Tuple[str, str, int]:
        """Parse multiline value where content starts on same line as opening semicolon."""
        line = lines[start_index].strip()
        
        # Extract content after the opening semicolon
        if line.startswith(';'):
            first_content = line[1:].strip()
            value_lines = [first_content] if first_content else []
            
            # Look for remaining lines until closing semicolon
            i = start_index + 1
            while i < len(lines):
                current_line = lines[i]
                
                # Check for closing semicolon
                if current_line.strip() == ';':
                    lines_consumed = i - start_index + 1
                    return field_name, '\n'.join(value_lines), lines_consumed
                
                # Add line to value (preserve original spacing)
                value_lines.append(current_line)
                i += 1
            
            # No closing semicolon found
            lines_consumed = len(lines) - start_index
            return field_name, '\n'.join(value_lines), lines_consumed
        
        # Fallback to regular parsing
        return field_name, None, 1
    
    def _is_multiline_value(self, value: str) -> bool:
        """Check if a value should be treated as multiline."""
        if not value:
            return False
        return '\n' in value or len(value) > 80
    
    def get_field(self, field_name: str) -> Optional[CIFField]:
        """Get a field by name."""
        return self.fields.get(field_name)
    
    def get_field_value(self, field_name: str) -> Optional[str]:
        """Get a field's value by name."""
        field = self.fields.get(field_name)
        return field.value if field else None
    
    def set_field_value(self, field_name: str, value: str):
        """Set a field's value."""
        if field_name in self.fields:
            self.fields[field_name].value = value
            self.fields[field_name].is_multiline = self._is_multiline_value(value)
        else:
            # Create new field
            new_field = CIFField(
                name=field_name,
                value=value,
                is_multiline=self._is_multiline_value(value)
            )
            self.fields[field_name] = new_field
            
            # Add to content_blocks so it appears in generated content
            self.content_blocks.append({
                'type': 'field',
                'content': new_field
            })
    
    def generate_cif_content(self) -> str:
        """Generate CIF content from the current fields and loops, preserving order."""
        lines = []
        
        # Use content_blocks to preserve the original order of fields, loops, and headers
        for i, block in enumerate(self.content_blocks):
            if block['type'] == 'header':
                # Add header lines (like data_xxxx)
                lines.append(block['content'])
            elif block['type'] == 'field':
                field = block['content']
                formatted_lines = self._format_field(field)
                lines.extend(formatted_lines)
            elif block['type'] == 'loop':
                loop = block['content']
                formatted_lines = self._format_loop(loop)
                lines.extend(formatted_lines)
                
                # Always add empty line after loop, regardless of what follows
                lines.append('')
        
        # If no content_blocks (backward compatibility), fall back to headers + fields
        if not self.content_blocks:
            # Add header lines first
            for header in self.header_lines:
                lines.append(header)
            
            # Then add fields
            for field_name, field in self.fields.items():
                if field.value != "(in loop)":  # Skip fields that are part of loops
                    formatted_lines = self._format_field(field)
                    lines.extend(formatted_lines)
        
        # Remove trailing empty lines
        while lines and lines[-1] == '':
            lines.pop()
        
        return '\n'.join(lines)
    
    def _format_loop(self, loop: CIFLoop) -> List[str]:
        """Format a CIF loop for output with proper line length handling.
        
        In CIF format:
        - loop_ starts the loop
        - Field names follow, each on its own line
        - Data rows follow, where each row contains values for all fields
        - When a row is too long, it can continue on the next line(s)
        - Values are separated by whitespace
        """
        lines = ['loop_']
        
        # Add field names
        for field_name in loop.field_names:
            lines.append(field_name)
        
        # Add data rows with proper line length handling
        for row in loop.data_rows:
            # Format each value in the row, handling multiline values specially
            formatted_values = []
            for value in row:
                # Handle empty string values - replace with ? (unknown value indicator)
                if value == '':
                    formatted_values.append('?')
                # Check if this is a multiline value (contains newlines)
                elif '\n' in value:
                    # Use semicolon block format for multiline values
                    formatted_values.append(';')  # Opening semicolon
                    formatted_values.extend(value.split('\n'))  # Each line as separate element
                    formatted_values.append(';')  # Closing semicolon
                # Quote values that need quoting (single-line values only)
                elif self._needs_quotes(value):
                    formatted_values.append(f"'{value}'")
                else:
                    formatted_values.append(value)
            
            # Now output the values with special handling for multiline blocks
            self._add_data_row_with_multiline_handling(lines, formatted_values)
        
        return lines
    
    def _add_data_row_with_line_breaks(self, lines: List[str], values: List[str]):
        """Add a data row to lines, breaking across multiple lines if needed to respect 80-char limit.
        
        This maintains the CIF format where a logical row can span multiple physical lines.
        Loop data lines should have leading spaces to distinguish them from field definitions.
        """
        if not values:
            return
        
        current_line_values = []
        current_line_length = 0
        is_first_line = True
        
        for value in values:
            value_length = len(value)
            
            # Check if we can add this value to the current line
            # Account for space before value (except for first value on line)
            space_needed = 1 if current_line_values else 0
            
            # For continuation lines, account for leading space indentation
            line_prefix_length = 0 if is_first_line else 1  # 1 space for continuation lines
            
            if current_line_length + space_needed + value_length + line_prefix_length <= 80:
                # Add to current line
                current_line_values.append(value)
                current_line_length += space_needed + value_length
            else:
                # Current line is full, output it and start a new line
                if current_line_values:
                    if is_first_line:
                        lines.append(' '.join(current_line_values))
                        is_first_line = False
                    else:
                        lines.append(' ' + ' '.join(current_line_values))  # Add leading space
                
                # Start new line with this value
                current_line_values = [value]
                current_line_length = value_length
        
        # Add the final line if it has content
        if current_line_values:
            if is_first_line:
                lines.append(' '.join(current_line_values))
            else:
                lines.append(' ' + ' '.join(current_line_values))  # Add leading space

    def _add_data_row_with_multiline_handling(self, lines: List[str], values: List[str]):
        """Add a data row to lines, with special handling for multiline semicolon blocks."""
        if not values:
            return
        
        i = 0
        current_line_values = []
        
        while i < len(values):
            value = values[i]
            
            # Check if this is a multiline block (starts with semicolon)
            if value == ';':
                # Output any accumulated single-line values first
                if current_line_values:
                    lines.append(' '.join(current_line_values))
                    current_line_values = []
                
                # Output opening semicolon on its own line
                lines.append(';')
                i += 1
                
                # Output multiline content
                while i < len(values) and values[i] != ';':
                    lines.append(values[i])
                    i += 1
                
                # Output closing semicolon
                if i < len(values) and values[i] == ';':
                    lines.append(';')
                    i += 1
            else:
                # Regular value - add to current line
                current_line_values.append(value)
                i += 1
        
        # Output any remaining single-line values
        if current_line_values:
            lines.append(' '.join(current_line_values))
    
    def _format_field(self, field: CIFField) -> List[str]:
        """Format a CIF field for output with proper alignment and 80-character line length handling.
        
        Values are aligned to column 36 for improved readability. If the field name is too long
        (≥35 characters), falls back to 2 spaces between field name and value.
        """
        if field.value is None or field.value == "(in loop)":
            return [field.name]
        
        # Check if we should use multiline format based on content or length
        needs_multiline = self._should_use_multiline_format(field.name, field.value)
        
        if needs_multiline or field.is_multiline:
            # Use multiline format with proper line breaking
            lines = [field.name, ';']
            
            # Break long lines within the multiline content
            content_lines = field.value.split('\n')
            for content_line in content_lines:
                if len(content_line) <= 80:
                    lines.append(content_line)
                else:
                    # Break long lines into multiple lines
                    broken_lines = self._break_long_line(content_line, 80)
                    lines.extend(broken_lines)
            
            lines.append(';')
            return lines
        else:
            # Single line format with proper quoting and length checking
            value = field.value
            
            # Handle empty string values - replace with ? (unknown value indicator)
            if value == '':
                formatted_value = '?'
            else:
                # Determine if we need quotes
                needs_quotes = self._needs_quotes(value)
                formatted_value = f"'{value}'" if needs_quotes else value
            
            # Calculate spacing to align values to column 36 (0-indexed = 35)
            field_name_length = len(field.name)
            target_column = 35  # 0-indexed, so this is column 36 in 1-indexed terms
            
            if field_name_length < target_column - 1:  # -1 to leave at least 1 space
                # Can align to target column
                spaces_needed = target_column - field_name_length
                spacing = ' ' * spaces_needed
            else:
                # Field name too long, use minimum 2 spaces
                spacing = '  '
            
            # Check total line length
            total_length = field_name_length + len(spacing) + len(formatted_value)
            
            if total_length <= 80:
                # Fits on one line
                return [f"{field.name}{spacing}{formatted_value}"]
            else:
                # Too long for single line, use multiline format
                return [field.name, ';', value, ';']
    
    def _needs_quotes(self, value: str) -> bool:
        """Determine if a value needs to be quoted."""
        if not value:
            return False
        
        # Quote if contains spaces, commas, starts with semicolon or hash
        return (' ' in value or ',' in value or 
                value.startswith(';') or value.startswith('#') or
                value.startswith("'") or value.startswith('"'))
    
    def _break_long_line(self, text: str, max_length: int) -> List[str]:
        """Break a long line into multiple lines at word boundaries."""
        if len(text) <= max_length:
            return [text]
        
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            # Check if adding this word would exceed the limit
            word_length = len(word)
            space_needed = 1 if current_line else 0  # Space before word (if not first word)
            
            if current_length + space_needed + word_length <= max_length:
                # Add word to current line
                current_line.append(word)
                current_length += space_needed + word_length
            else:
                # Start new line
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length
        
        # Add the last line if there are remaining words
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def list_fields(self) -> List[str]:
        """Return a list of all field names."""
        return list(self.fields.keys())
    
    def has_field(self, field_name: str) -> bool:
        """Check if a field exists."""
        return field_name in self.fields
    
    def reformat_for_line_length(self, content: str) -> str:
        """Reformat CIF content to ensure no line exceeds 80 characters.
        
        Args:
            content: The CIF content to reformat
            
        Returns:
            Reformatted CIF content with proper line length handling and preserved loop structures
        """
        # Parse the content first
        self.parse_file(content)
        
        # Reformat individual fields based on 80-character rule (loops are preserved as-is)
        for field_name, field in self.fields.items():
            if field.value is not None and field.value != "(in loop)":
                # Recalculate multiline status based on 80-character rule
                should_be_multiline = self._should_use_multiline_format(field.name, field.value)
                field.is_multiline = should_be_multiline
        
        # Generate and return the reformatted content
        return self.generate_cif_content()
    
    def _should_use_multiline_format(self, field_name: str, value: str) -> bool:
        """Determine if a field should use multiline format based on length and content."""
        if not value:
            return False
        
        # Always use multiline if value contains newlines
        if '\n' in value:
            return True
        
        # Calculate total line length (field name + spacing + quoted value)
        needs_quotes = self._needs_quotes(value)
        formatted_value = f"'{value}'" if needs_quotes else value
        total_length = len(field_name) + 4 + len(formatted_value)  # 4 spaces for formatting
        
        return total_length > 80
