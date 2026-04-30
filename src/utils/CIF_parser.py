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
    
    # Value type constants
    TYPE_REGULAR = "regular"
    TYPE_LIST = "list"       # CIF2 list: [val1 val2 ...]
    TYPE_TABLE = "table"     # CIF2 table: {"key": val ...}

    def __init__(self, name: str, value: Any = None, is_multiline: bool = False, 
                 line_number: int = None, raw_lines: List[str] = None,
                 value_type: str = None):
        self.name = name
        self.value = value
        self.is_multiline = is_multiline
        self.line_number = line_number  # Starting line number in the file
        self.raw_lines = raw_lines or []  # Original lines from the file
        self.value_type = value_type or self.TYPE_REGULAR
    
    @property
    def is_list(self) -> bool:
        return self.value_type == self.TYPE_LIST

    @property
    def is_table(self) -> bool:
        return self.value_type == self.TYPE_TABLE

    def __repr__(self):
        extra = f", type={self.value_type}" if self.value_type != self.TYPE_REGULAR else ""
        return f"CIFField(name='{self.name}', value='{self.value}', multiline={self.is_multiline}{extra})"


class CIFLoop:
    """Represents a CIF loop structure with field names and data rows."""
    
    def __init__(self, field_names: List[str], data_rows: List[List[str]], line_number: int = None):
        self.field_names = field_names
        self.data_rows = data_rows
        self.line_number = line_number
        # Set when the last row of the loop was padded because the total number
        # of data values was not a multiple of the number of field names.
        self.has_incomplete_last_row: bool = False
        # Actual value count in the last row before padding (0 if complete).
        self.incomplete_row_actual_count: int = 0
    
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
        
        The deprecated fields are placed in a clearly marked section at the end of the CIF file.
        
        Args:
            dict_manager: CIFDictionaryManager instance for field conversion
            
        Returns:
            Report string describing what compatibility fields were added
        """
        if not dict_manager:
            return "No dictionary manager provided"
            
        added_fields = []
        deprecated_field_objs = []
        
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
            modern_field_cif2 = dict_manager.get_modern_equivalent(deprecated_field, prefer_format="modern")
            modern_field_cif1 = dict_manager.get_modern_equivalent(deprecated_field, prefer_format="legacy")
            
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
                    line_number=None,  # Will be placed in deprecated section
                    raw_lines=[]
                )
                
                self.fields[deprecated_field] = deprecated_field_obj
                deprecated_field_objs.append(deprecated_field_obj)
                
                added_fields.append(f"{deprecated_field} = {modern_field_obj.value} (from {modern_field})")
        
        # If we added any deprecated fields, create a deprecated section at the end
        if deprecated_field_objs:
            self._add_deprecated_section_to_blocks(deprecated_field_objs, dict_manager)
        
        # Generate report
        if added_fields:
            report = f"Added {len(added_fields)} compatibility field(s) for legacy validation tools:\n"
            for field_info in added_fields:
                report += f"  • {field_info}\n"
            report += "\nThese deprecated fields are placed in a marked section at the end of the file."
        else:
            report = "No compatibility fields needed - either modern equivalents not found or deprecated fields already exist."
            
        return report
    
    def _add_deprecated_section_to_blocks(self, deprecated_field_objs: List[CIFField], dict_manager):
        """
        Add a formatted deprecated section at the end of the content blocks.
        
        If a deprecated section already exists, append the new fields to it.
        If no deprecated section exists, create a new one.
        
        The section is added as a special block that won't be reparsed during reformatting.
        This ensures inline comments remain on the same line as field values.
        
        Args:
            deprecated_field_objs: List of CIFField objects for deprecated fields
            dict_manager: Dictionary manager to get replacement field info
        """
        # Check if a deprecated section already exists
        deprecated_section_start = None
        deprecated_section_end = None
        
        for i, block in enumerate(self.content_blocks):
            if (block.get('type') == 'comment' and 
                block.get('content') == '# DEPRECATED FIELDS - Retained for legacy software compatibility'):
                deprecated_section_start = i
                # Find the closing border
                for j in range(i + 1, len(self.content_blocks)):
                    if (self.content_blocks[j].get('type') == 'comment' and
                        self.content_blocks[j].get('content') == '#' * 79):
                        deprecated_section_end = j
                        break
                break
        
        if deprecated_section_start is not None and deprecated_section_end is not None:
            # Deprecated section exists - insert new fields before the closing border
            insert_position = deprecated_section_end
            
            # Add each deprecated field before the closing border
            for field_obj in deprecated_field_objs:
                # Get replacement field info and add as a comment BEFORE the field
                try:
                    replacement = dict_manager.get_modern_equivalent(field_obj.name, prefer_format="modern")
                    if not replacement:
                        replacement = dict_manager.get_modern_equivalent(field_obj.name, prefer_format="legacy")
                    
                    if replacement:
                        comment_text = f"# -> Use {replacement} instead"
                    else:
                        comment_text = "# -> Deprecated (no direct replacement)"
                except:
                    comment_text = "# -> Deprecated"
                
                # Insert the replacement info as a separate comment line
                self.content_blocks.insert(insert_position, {
                    'type': 'comment',
                    'content': comment_text
                })
                insert_position += 1
                
                # Format the field line with proper alignment (no inline comment)
                # Calculate spacing for alignment
                field_name_length = len(field_obj.name)
                value_str = str(field_obj.value)
                target_column = 35
                
                if field_name_length < target_column - 1:
                    spacing = ' ' * (target_column - field_name_length)
                else:
                    spacing = '  '
                
                # Create formatted line (without inline comment for better readability)
                formatted_line = f"{field_obj.name}{spacing}{value_str}"
                
                # Insert as a special deprecated field block that won't be reformatted
                self.content_blocks.insert(insert_position, {
                    'type': 'deprecated_field',
                    'content': formatted_line
                })
                insert_position += 1
        else:
            # No deprecated section exists - create a new one
            # Add a blank line before the section
            self.content_blocks.append({
                'type': 'empty',
                'content': ''
            })
            
            # Add the header border
            self.content_blocks.append({
                'type': 'comment',
                'content': '#' * 79
            })
            
            # Add section title
            self.content_blocks.append({
                'type': 'comment',
                'content': '# DEPRECATED FIELDS - Retained for legacy software compatibility'
            })
            
            self.content_blocks.append({
                'type': 'comment',
                'content': '# These fields have modern replacements and should not be used in new files'
            })
            
            self.content_blocks.append({
                'type': 'comment',
                'content': '#' * 79
            })
            
            # Add each deprecated field as a special formatted block
            # This prevents them from being reparsed and reformatted
            for field_obj in deprecated_field_objs:
                # Get replacement field info and add as a comment BEFORE the field
                # This ensures the field line stays within 80 characters
                try:
                    replacement = dict_manager.get_modern_equivalent(field_obj.name, prefer_format="modern")
                    if not replacement:
                        replacement = dict_manager.get_modern_equivalent(field_obj.name, prefer_format="legacy")
                    
                    if replacement:
                        comment_text = f"# -> Use {replacement} instead"
                    else:
                        comment_text = "# -> Deprecated (no direct replacement)"
                except:
                    comment_text = "# -> Deprecated"
                
                # Add the replacement info as a separate comment line
                self.content_blocks.append({
                    'type': 'comment',
                    'content': comment_text
                })
                
                # Format the field line with proper alignment (no inline comment)
                # Calculate spacing for alignment
                field_name_length = len(field_obj.name)
                value_str = str(field_obj.value)
                target_column = 35
                
                if field_name_length < target_column - 1:
                    spacing = ' ' * (target_column - field_name_length)
                else:
                    spacing = '  '
                
                # Create formatted line (without inline comment for better readability)
                formatted_line = f"{field_obj.name}{spacing}{value_str}"
                
                # Add as a special deprecated field block that won't be reformatted
                self.content_blocks.append({
                    'type': 'deprecated_field',
                    'content': formatted_line
                })
            
            # Add closing border
            self.content_blocks.append({
                'type': 'comment',
                'content': '#' * 79
            })
        
    def parse_file(self, content: str) -> Dict[str, CIFField]:
        """Parse CIF content and return a dictionary of fields."""
        self.fields = {}
        self.loops = []
        self.content_blocks = []
        self.header_lines = []
        lines = content.splitlines()
        i = 0
        
        # Track if we're in a deprecated section
        in_deprecated_section = False
        
        while i < len(lines):
            raw_line = lines[i]
            line = raw_line.strip()
            
            # Preserve empty lines
            if not line:
                self.content_blocks.append({'type': 'empty', 'content': ''})
                i += 1
                continue
            
            # Preserve comment lines
            if line.startswith('#'):
                self.content_blocks.append({'type': 'comment', 'content': line})
                
                # Check if this is the start or end of a deprecated section
                if '# DEPRECATED FIELDS' in line:
                    in_deprecated_section = True
                elif line == '#' * 79 and in_deprecated_section:
                    # Check if this is the closing border (next line should not be deprecated field)
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if not next_line.startswith('_'):
                            in_deprecated_section = False
                
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
                # Check if we're in a deprecated section - if so, preserve the entire line
                if in_deprecated_section:
                    # This is a deprecated field line with inline comment
                    # Preserve it as-is without parsing
                    self.content_blocks.append({'type': 'deprecated_field', 'content': line})
                    i += 1
                    continue
                
                # Normal field parsing
                field_name, value, lines_consumed, value_type = self._parse_field(lines, i)
                if field_name:
                    field = CIFField(
                        name=field_name,
                        value=value,
                        is_multiline=self._is_multiline_value(value),
                        line_number=i + 1,
                        raw_lines=lines[i:i+lines_consumed],
                        value_type=value_type,
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
        
        # Parse field names.
        # Per CIF grammar (token-based): the loop header consists of all
        # consecutive '_'-starting tokens.  The first non-'_' token ends the
        # header phase, even if it appears on the *same line* as a field name.
        # e.g.  `_diffrn_radiation_wavelength  0.71073`  → field name is only
        # `_diffrn_radiation_wavelength`; `0.71073` starts the data section.
        initial_data_values: List[str] = []  # inline values found after a field name

        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                i += 1
                continue

            # Check if this line begins with a field name
            if line.startswith('_'):
                # Only the first whitespace-separated token is the field name
                space_pos = -1
                for ci, ch in enumerate(line):
                    if ch in (' ', '\t'):
                        space_pos = ci
                        break
                if space_pos == -1:
                    # Whole line is the field name, no inline value
                    field_names.append(line)
                    i += 1
                else:
                    # Field name with inline value(s) — header phase ends here
                    field_name = line[:space_pos]
                    field_names.append(field_name)
                    rest = line[space_pos:].strip()
                    if rest:
                        initial_data_values.extend(self._parse_data_line(rest))
                    i += 1
                    break  # data section starts
            else:
                # We've reached the data section
                break

        if not field_names:
            return None, i - start_index

        # Parse data rows
        data_rows = []
        current_row = list(initial_data_values)  # may be non-empty if inline values found
        
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
            
            # Drain ALL complete rows from the accumulated values before moving on.
            # Using while (not if) ensures a line that carries multiple rows' worth of
            # values doesn't leave extras silently in current_row.
            while len(current_row) >= len(field_names):
                row = current_row[:len(field_names)]
                data_rows.append(row)
                current_row = current_row[len(field_names):]
        
        # Handle any remaining partial row.
        # Drain complete rows first — this handles the case where initial_data_values
        # (inline values found on the same line as a field name) filled a whole row
        # but the data phase was never entered (e.g. the next line starts with '_').
        while len(current_row) >= len(field_names):
            row = current_row[:len(field_names)]
            data_rows.append(row)
            current_row = current_row[len(field_names):]

        has_incomplete = False
        incomplete_count = 0
        if current_row:
            incomplete_count = len(current_row)
            has_incomplete = True
            # Pad with empty values so rows always have the right width
            while len(current_row) < len(field_names):
                current_row.append('')
            data_rows.append(current_row)
        
        loop = CIFLoop(field_names, data_rows, start_index + 1)
        loop.has_incomplete_last_row = has_incomplete
        loop.incomplete_row_actual_count = incomplete_count
        return loop, i - start_index
    
    def _parse_data_line(self, line: str) -> List[str]:
        """Parse a line of data values, handling quoted and triple-quoted strings properly.
        
        Handles CIF2 triple-quoted strings (''' and \""") as well as single-quoted strings.
        """
        values = []
        i = 0
        
        while i < len(line):
            # Skip whitespace
            while i < len(line) and line[i].isspace():
                i += 1
            
            if i >= len(line):
                break
            
            # Check for triple-quoted strings (CIF2)
            if i + 2 < len(line) and line[i] in ("'", '"') and line[i:i+3] in ("'''", '"""'):
                triple_quote = line[i:i+3]
                i += 3  # Skip opening triple quote
                value = ""
                
                # Find closing triple quote
                while i < len(line):
                    if i + 2 < len(line) and line[i:i+3] == triple_quote:
                        i += 3  # Skip closing triple quote
                        break
                    value += line[i]
                    i += 1
                
                values.append(value)
            # Handle single/double quoted strings
            elif line[i] in ("'", '"'):
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

    def _has_unclosed_triple_quote(self, text: str) -> bool:
        """Check if text contains an unclosed CIF2 triple-quoted string (\"\"\" or ''').

        Used to detect whether a loop data line begins a triple-quoted string value
        that spans multiple lines (per the CIF2-EBNF: triple-quoted-string content
        may contain any allchars including line terminators).
        """
        i = 0
        while i < len(text):
            c = text[i]
            if c in ('"', "'"):
                if i + 2 < len(text) and text[i:i+3] in ('"""', "'''"):
                    delim = text[i:i+3]
                    end = text.find(delim, i + 3)
                    if end == -1:
                        return True  # Unclosed triple-quote found
                    i = end + 3
                    continue
            i += 1
        return False

    def _parse_loop_data_line(self, lines: List[str], start_index: int) -> Tuple[List[str], int]:
        """Parse a line of loop data values, handling multiline semicolon blocks and
        CIF2 multi-line triple-quoted strings.
        
        Returns:
            Tuple of (values, lines_consumed)
        """
        raw_line = lines[start_index]
        line = raw_line.strip()

        # Multiline loop values can start as either:
        # 1) a standalone ';' line, or
        # 2) ';content...' on the same line (valid CIF syntax, CIF2-EBNF text-field).
        if raw_line.startswith(';'):
            first_line_content = raw_line[1:]
            multiline_value, consumed = self._parse_multiline_in_loop(
                lines,
                start_index + 1,
                first_line_content=first_line_content,
            )
            return [multiline_value], consumed + 1  # +1 for opening delimiter line

        # Be lenient with leading whitespace before ';' even if not strictly CIF-compliant.
        if line == ';':
            multiline_value, consumed = self._parse_multiline_in_loop(lines, start_index + 1)
            return [multiline_value], consumed + 1  # +1 for opening delimiter line

        # CIF2: triple-quoted strings (\"\"\" or ''') may span multiple lines.
        # Collect continuation lines until all triple-quotes on this line are balanced.
        if '"""' in line or "'''" in line:
            collected = [line]
            total_consumed = 1
            while self._has_unclosed_triple_quote('\n'.join(collected)):
                if start_index + total_consumed >= len(lines):
                    break
                cont_line = lines[start_index + total_consumed]
                cont_stripped = cont_line.strip()
                # Stop at structural tokens (would be a malformed CIF anyway)
                if (cont_stripped.startswith('_') or
                        cont_stripped.lower().startswith('loop_') or
                        cont_stripped.lower().startswith('data_') or
                        cont_stripped.lower().startswith('save_')):
                    break
                collected.append(cont_line.rstrip('\n\r'))
                total_consumed += 1
            if total_consumed > 1:
                values = self._parse_data_line('\n'.join(collected))
                return values, total_consumed

        # Otherwise, parse values from this line normally
        values = self._parse_data_line(line)
        return values, 1

    def _parse_multiline_in_loop(
        self,
        lines: List[str],
        start_index: int,
        first_line_content: str = "",
    ) -> Tuple[str, int]:
        """Parse a multiline value within loop data starting from after a semicolon.
        
        Returns:
            Tuple of (multiline_value, total_lines_consumed_after_semicolon)
        """
        value_lines = []
        if first_line_content:
            value_lines.append(first_line_content)
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
    
    def _parse_field(self, lines: List[str], start_index: int) -> Tuple[str, str, int, str]:
        """Parse a single field starting at the given line index.
        
        Returns:
            Tuple of (field_name, value, lines_consumed, value_type)
            value_type is one of CIFField.TYPE_REGULAR, TYPE_LIST, TYPE_TABLE.
        """
        line = lines[start_index].strip()
        
        # Parse field name
        parts = line.split(maxsplit=1)
        if not parts or not parts[0].startswith('_'):
            return None, None, 1, CIFField.TYPE_REGULAR
        
        field_name = parts[0]
        
        # Check if value is on the same line
        if len(parts) > 1:
            value_part = parts[1].strip()

            # Check for CIF2 triple-quoted strings (""" or ''') before single-quote check
            for triple_delim in ('"""', "'''"):
                if value_part.startswith(triple_delim):
                    after_open = value_part[3:]
                    end_pos = after_open.find(triple_delim)
                    if end_pos != -1:
                        # Complete triple-quoted string on the same line
                        return field_name, after_open[:end_pos], 1, CIFField.TYPE_REGULAR
                    else:
                        # Multi-line triple-quoted string: collect continuation lines
                        value_parts = [after_open]
                        j = start_index + 1
                        while j < len(lines):
                            seg = lines[j]
                            end_pos = seg.find(triple_delim)
                            if end_pos != -1:
                                value_parts.append(seg[:end_pos])
                                j += 1
                                break
                            value_parts.append(seg.rstrip('\n\r'))
                            j += 1
                        return field_name, '\n'.join(value_parts), j - start_index, CIFField.TYPE_REGULAR

            # Check if it's a quoted string
            if (value_part.startswith("'") and value_part.endswith("'")) or \
               (value_part.startswith('"') and value_part.endswith('"')):
                return field_name, value_part[1:-1], 1, CIFField.TYPE_REGULAR
            
            # Check if it starts a multiline block
            if value_part == ';':
                name, val, consumed = self._parse_multiline_value(lines, start_index + 1, field_name)
                return name, val, consumed, CIFField.TYPE_REGULAR
            
            # Check if content starts on same line as opening semicolon (;content...)
            if value_part.startswith(';') and len(value_part) > 1:
                name, val, consumed = self._parse_multiline_value_with_content_on_first_line(lines, start_index, field_name)
                return name, val, consumed, CIFField.TYPE_REGULAR
            
            # CIF2 list value: starts with [
            if value_part.startswith('['):
                val, consumed, vtype = self._parse_bracket_value(
                    lines, start_index, value_part, '[', ']', CIFField.TYPE_LIST)
                return field_name, val, consumed, vtype

            # CIF2 table value: starts with {
            if value_part.startswith('{'):
                val, consumed, vtype = self._parse_bracket_value(
                    lines, start_index, value_part, '{', '}', CIFField.TYPE_TABLE)
                return field_name, val, consumed, vtype

            # Regular single-line value
            return field_name, value_part, 1, CIFField.TYPE_REGULAR
        
        # Value might be on the next line(s)
        if start_index + 1 < len(lines):
            next_line = lines[start_index + 1].strip()
            
            # Check if next line starts multiline block
            if next_line == ';':
                name, val, consumed = self._parse_multiline_value(lines, start_index + 2, field_name)
                return name, val, consumed, CIFField.TYPE_REGULAR
            
            # Check if next line contains content starting with semicolon (;content...)
            if next_line.startswith(';') and len(next_line) > 1:
                name, val, consumed = self._parse_multiline_value_with_content_on_first_line(lines, start_index + 1, field_name)
                return name, val, consumed, CIFField.TYPE_REGULAR
            
            # CIF2 list on next line
            if next_line.startswith('['):
                val, consumed, vtype = self._parse_bracket_value(
                    lines, start_index + 1, next_line, '[', ']', CIFField.TYPE_LIST)
                return field_name, val, consumed + 1, vtype  # +1 for field name line

            # CIF2 table on next line
            if next_line.startswith('{'):
                val, consumed, vtype = self._parse_bracket_value(
                    lines, start_index + 1, next_line, '{', '}', CIFField.TYPE_TABLE)
                return field_name, val, consumed + 1, vtype  # +1 for field name line

            # Single line value on next line
            if next_line and not next_line.startswith('_'):
                # Check for CIF2 triple-quoted strings before single-quote check
                for triple_delim in ('"""', "'''"):
                    if next_line.startswith(triple_delim):
                        after_open = next_line[3:]
                        end_pos = after_open.find(triple_delim)
                        if end_pos != -1:
                            # Complete triple-quoted string on next line
                            return field_name, after_open[:end_pos], 2, CIFField.TYPE_REGULAR
                        else:
                            # Multi-line triple-quoted string
                            value_parts = [after_open]
                            j = start_index + 2  # +1 field line, +1 triple-quote open line
                            while j < len(lines):
                                seg = lines[j]
                                end_pos = seg.find(triple_delim)
                                if end_pos != -1:
                                    value_parts.append(seg[:end_pos])
                                    j += 1
                                    break
                                value_parts.append(seg.rstrip('\n\r'))
                                j += 1
                            return field_name, '\n'.join(value_parts), j - start_index, CIFField.TYPE_REGULAR

                # Handle quoted values
                if (next_line.startswith("'") and next_line.endswith("'")) or \
                   (next_line.startswith('"') and next_line.endswith('"')):
                    return field_name, next_line[1:-1], 2, CIFField.TYPE_REGULAR
                return field_name, next_line, 2, CIFField.TYPE_REGULAR
        
        # No value found
        return field_name, None, 1, CIFField.TYPE_REGULAR

    def _parse_bracket_value(
        self, lines: List[str], start_index: int, first_value: str,
        open_char: str, close_char: str, value_type: str,
    ) -> Tuple[str, int, str]:
        """Parse a CIF2 list ([...]) or table ({...}) value that may span multiple lines.
        
        Handles nesting, quoted strings inside brackets, and multi-line constructs.
        
        Args:
            lines: All content lines
            start_index: Index of the line where the bracket value begins
            first_value: The text after the field name (may be the entire value)
            open_char: Opening bracket character ('[' or '{')
            close_char: Closing bracket character (']' or '}')
            value_type: CIFField.TYPE_LIST or CIFField.TYPE_TABLE
            
        Returns:
            Tuple of (collected_value, lines_consumed, value_type)
        """
        depth = 0
        collected = []
        in_single_quote = False
        in_double_quote = False
        
        # Start from the line that contains the opening bracket
        i = start_index
        # The first_value is the rest-of-line after the field name.
        # We need to scan from start_index onwards.
        # On the first line, only the value portion (first_value) is relevant,
        # but we want the raw line for multi-line reconstruction.
        
        while i < len(lines):
            if i == start_index:
                # Use the portion after the field name for scanning
                scan_text = first_value
            else:
                scan_text = lines[i]
            
            # Scan character by character for bracket depth
            j = 0
            while j < len(scan_text):
                ch = scan_text[j]
                
                # Handle quoted strings (skip their content)
                if ch in ("'", '"') and not in_single_quote and not in_double_quote:
                    # Check triple quote
                    if j + 2 < len(scan_text) and scan_text[j:j+3] in ("'''", '"""'):
                        triple = scan_text[j:j+3]
                        end = scan_text.find(triple, j + 3)
                        if end != -1:
                            j = end + 3
                            continue
                    # Single/double quote
                    if ch == "'":
                        in_single_quote = True
                    else:
                        in_double_quote = True
                    j += 1
                    continue
                
                if in_single_quote:
                    if ch == "'":
                        in_single_quote = False
                    j += 1
                    continue
                    
                if in_double_quote:
                    if ch == '"':
                        in_double_quote = False
                    j += 1
                    continue
                
                if ch == open_char:
                    depth += 1
                elif ch == close_char:
                    depth -= 1
                    if depth == 0:
                        # Closing bracket found
                        if i == start_index:
                            collected.append(first_value)
                        else:
                            collected.append(lines[i])
                        value = '\n'.join(collected)
                        lines_consumed = i - start_index + 1
                        return value, lines_consumed, value_type
                j += 1
            
            # Didn't close on this line; accumulate
            if i == start_index:
                collected.append(first_value)
            else:
                collected.append(lines[i])
            i += 1
        
        # Reached end of file without finding closing bracket — return what we have
        value = '\n'.join(collected)
        return value, len(lines) - start_index, value_type
    
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
        
        # Use content_blocks to preserve the original order of fields, loops, headers, and comments
        for i, block in enumerate(self.content_blocks):
            if block['type'] == 'header':
                # Add header lines (like data_xxxx)
                lines.append(block['content'])
            elif block['type'] == 'empty':
                # Add empty line
                lines.append('')
            elif block['type'] == 'comment':
                # Add comment line (including special headers and borders)
                lines.append(block['content'])
            elif block['type'] == 'deprecated_field':
                # Add pre-formatted deprecated field line (won't be reformatted)
                lines.append(block['content'])
            elif block['type'] == 'inline_comment':
                # This was already handled as part of the previous field
                # (or will be - skip it here)
                continue
            elif block['type'] == 'field':
                field = block['content']
                
                # Check if this is a deprecated field with an inline comment following
                if block.get('is_deprecated') and i + 1 < len(self.content_blocks):
                    next_block = self.content_blocks[i + 1]
                    if (next_block.get('type') == 'inline_comment' and 
                        next_block.get('for_field') == field.name):
                        # Format field with inline comment
                        formatted_lines = self._format_field_with_comment(field, next_block['content'])
                        lines.extend(formatted_lines)
                    else:
                        # Regular field formatting
                        formatted_lines = self._format_field(field)
                        lines.extend(formatted_lines)
                else:
                    # Regular field formatting
                    formatted_lines = self._format_field(field)
                    lines.extend(formatted_lines)
            elif block['type'] == 'loop':
                loop = block['content']
                formatted_lines = self._format_loop(loop)
                lines.extend(formatted_lines)
                
                # Add empty line after loop if next block is not already an empty line
                if i + 1 < len(self.content_blocks):
                    next_block = self.content_blocks[i + 1]
                    if next_block['type'] != 'empty':
                        lines.append('')
                else:
                    # This is the last block, add empty line
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
        """Add a data row to lines, with special handling for multiline semicolon blocks and 80-char limit."""
        if not values:
            return
        
        i = 0
        current_line_values = []
        current_line_length = 0
        is_first_line = True
        
        while i < len(values):
            value = values[i]
            
            # Check if this is a multiline block (starts with semicolon)
            if value == ';':
                # Output any accumulated single-line values first
                if current_line_values:
                    if is_first_line:
                        lines.append(' '.join(current_line_values))
                        is_first_line = False
                    else:
                        lines.append(' ' + ' '.join(current_line_values))
                    current_line_values = []
                    current_line_length = 0
                
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
                # Regular value - check if it fits on current line
                value_length = len(value)
                space_needed = 1 if current_line_values else 0  # Space before value (except first)
                line_prefix_length = 0 if is_first_line else 1  # Leading space for continuation
                
                if current_line_length + space_needed + value_length + line_prefix_length <= 80:
                    # Add to current line
                    current_line_values.append(value)
                    current_line_length += space_needed + value_length
                    i += 1
                else:
                    # Current line is full, output it and start a new line
                    if current_line_values:
                        if is_first_line:
                            lines.append(' '.join(current_line_values))
                            is_first_line = False
                        else:
                            lines.append(' ' + ' '.join(current_line_values))
                    
                    # Start new line with this value
                    current_line_values = [value]
                    current_line_length = value_length
                    i += 1
        
        # Output any remaining single-line values
        if current_line_values:
            if is_first_line:
                lines.append(' '.join(current_line_values))
            else:
                lines.append(' ' + ' '.join(current_line_values))
    
    def _format_field_with_comment(self, field: CIFField, comment: str) -> List[str]:
        """
        Format a field with an inline comment (for deprecated fields).
        
        Example output:
        _cell_measurement_pressure       100.0    # → Use _diffrn.ambient_pressure instead
        """
        if field.value is None or field.value == "(in loop)":
            return [f"{field.name}    {comment}"]
        
        # For deprecated fields, format with alignment and inline comment
        field_name_length = len(field.name)
        value_str = str(field.value)
        
        # Calculate spacing for value alignment
        target_column = 35
        if field_name_length < target_column - 1:
            spacing = ' ' * (target_column - field_name_length)
        else:
            spacing = '  '
        
        # Format: field_name    value    comment
        return [f"{field.name}{spacing}{value_str}    {comment}"]
    
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
        """Determine if a value needs to be quoted.
        
        According to CIF specification, values must be quoted if they contain:
        - Whitespace (spaces, tabs, newlines)
        - Reserved characters: [ ] { } (cannot be used in whitespace-delimited values)
        - Special leading characters: ; # ' "
        - Commas
        """
        if not value:
            return False
        
        # Quote if contains spaces, commas, reserved brackets/braces, or starts with special chars
        return (' ' in value or ',' in value or 
                '[' in value or ']' in value or '{' in value or '}' in value or
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
        
        This function intelligently reformats only CIF field values that need it,
        while preserving:
        - Comment lines (starting with #)
        - Loop structures (reformatted internally but structure preserved)
        - Header lines (data_, save_, global_, stop_)
        - Empty lines
        - Special sections (like deprecated fields sections)
        
        Args:
            content: The CIF content to reformat
            
        Returns:
            Reformatted CIF content with proper line length handling
        """
        # Parse the content first
        self.parse_file(content)
        
        # Reformat individual fields based on 80-character rule
        # Only single-line and multiline fields are reformatted
        # Loops are preserved as-is during parsing and regeneration
        for field_name, field in self.fields.items():
            if field.value is not None and field.value != "(in loop)":
                # Recalculate multiline status based on 80-character rule
                should_be_multiline = self._should_use_multiline_format(field.name, field.value)
                field.is_multiline = should_be_multiline
        
        # Generate and return the reformatted content
        # The generate_cif_content() method preserves all comment lines,
        # headers, and loops exactly as parsed
        return self.generate_cif_content()
    
    def _has_deprecated_section(self, content: str) -> bool:
        """Check if content has a deprecated fields section."""
        deprecated_marker = "# DEPRECATED FIELDS - Retained for legacy software compatibility"
        return deprecated_marker in content
    
    def _reformat_preserving_sections(self, content: str) -> str:
        """
        Reformat CIF content while preserving special sections like deprecated fields.
        
        This splits the content at the deprecated section boundary, reformats the
        active part, and preserves the deprecated section as-is.
        """
        lines = content.split('\n')
        
        # Find the start of the deprecated section
        deprecated_start_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith('#' * 10):  # Look for hashmark border
                # Check if next few lines contain the deprecated marker
                if i + 1 < len(lines) and "DEPRECATED FIELDS" in lines[i + 1]:
                    deprecated_start_idx = i
                    break
        
        if deprecated_start_idx is None:
            # No deprecated section found despite marker, do normal reformat
            return self.reformat_for_line_length(content)
        
        # Split content into active and deprecated sections
        active_lines = lines[:deprecated_start_idx]
        deprecated_lines = lines[deprecated_start_idx:]
        
        # Remove trailing empty lines from active section
        while active_lines and active_lines[-1].strip() == '':
            active_lines.pop()
        
        # Reformat only the active section
        active_content = '\n'.join(active_lines)
        self.parse_file(active_content)
        
        # Reformat individual fields based on 80-character rule
        for field_name, field in self.fields.items():
            if field.value is not None and field.value != "(in loop)":
                should_be_multiline = self._should_use_multiline_format(field.name, field.value)
                field.is_multiline = should_be_multiline
        
        # Generate reformatted active content
        reformatted_active = self.generate_cif_content()
        
        # Combine reformatted active section with preserved deprecated section
        deprecated_content = '\n'.join(deprecated_lines)
        
        # Ensure there's a blank line before the deprecated section
        if not reformatted_active.endswith('\n\n'):
            reformatted_active += '\n'
        
        return reformatted_active + '\n' + deprecated_content
    
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


def _get_civet_signature() -> str:
    """Get the CIVET signature string for audit fields."""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    try:
        from version import __version__, APP_NAME, APP_AUTHOR, GITHUB_URL
    except ImportError:
        __version__ = "unknown"
        APP_NAME = "CIVET"
        APP_AUTHOR = "Daniel N. Rainer"
        GITHUB_URL = "https://github.com/danielnrainer/CIVET"
    return f"\n{APP_NAME} v{__version__} ({APP_AUTHOR}, {GITHUB_URL})"


def _find_audit_field(lines: list, field_names: list) -> tuple:
    """
    Find an audit field in content, checking both modern and legacy notation.
    
    Args:
        lines: List of content lines
        field_names: List of possible field names (e.g., ['_audit.creation_method', '_audit_creation_method'])
    
    Returns:
        Tuple of (field_line_index, is_multiline, actual_field_name) or (-1, False, None) if not found
    """
    for i, line in enumerate(lines):
        line_lower = line.strip().lower()
        for field_name in field_names:
            if line_lower.startswith(field_name.lower()):
                # Check if next non-empty line is semicolon (multiline)
                is_multiline = False
                if i + 1 < len(lines) and lines[i + 1].strip() == ';':
                    is_multiline = True
                return (i, is_multiline, field_name)
    return (-1, False, None)


def _detect_cif_format_simple(content: str) -> str:
    """
    Simple fallback detection of CIF format when CIFDictionaryManager is not available.
    
    This is a simplified version - callers with access to CIFDictionaryManager should
    use dict_manager.detect_cif_format() and pass the result to avoid duplication.
    
    Returns:
        'modern' if dot notation found, 'legacy' otherwise
    """
    # Check for common modern-format fields (fields with dot notation)
    if re.search(r'_[a-zA-Z]+\.[a-zA-Z]', content):
        return 'modern'
    return 'legacy'


def update_audit_creation_method(content: str, cif_format: str = None) -> str:
    """
    Update _audit_creation_method (or _audit.creation_method) to include CIVET information.
    
    Handles both modern (dot) and legacy (underscore) notation.
    If the field exists and is multiline, appends CIVET signature.
    If the field exists as single-line, converts to multiline and appends.
    If the field doesn't exist, creates it using the detected format.
    
    Args:
        content: CIF file content
        cif_format: Optional. 'modern' or 'legacy'. If not provided, auto-detects.
                   Callers with CIFDictionaryManager should use dict_manager.detect_cif_format()
                   and pass the result here.
        
    Returns:
        Updated content with CIVET info in _audit_creation_method
    """
    civet_signature = _get_civet_signature()
    lines = content.split('\n')
    
    # Field name variants (modern first, then legacy)
    method_fields = ['_audit.creation_method', '_audit_creation_method']
    date_fields = ['_audit.creation_date', '_audit_creation_date']
    
    # Detect format to use for new fields (use provided or auto-detect)
    if cif_format is None:
        cif_format = _detect_cif_format_simple(content)
    else:
        cif_format = cif_format.lower()  # Normalize to lowercase
    
    # Check if CIVET is already mentioned anywhere in the audit method field
    field_line_index, is_multiline, found_field_name = _find_audit_field(lines, method_fields)
    
    if field_line_index >= 0:
        # Check if CIVET already present in this field — if so, update to current version
        civet_line_stripped = civet_signature.strip()
        in_field = False
        for i, line in enumerate(lines):
            if i == field_line_index:
                # Check single-line value
                if 'civet' in line.lower():
                    # Replace inline CIVET reference with current version
                    pattern = rf'^({re.escape(found_field_name)}\s+)(.+)$'
                    match = re.match(pattern, line, re.IGNORECASE)
                    if match:
                        old_value = match.group(2).strip().strip("'\"")
                        updated_value = re.sub(
                            r'CIVET\s+v[\d.]+\s*\([^)]*\)',
                            civet_line_stripped,
                            old_value
                        )
                        if updated_value != old_value:
                            lines[i] = f"{found_field_name} '{updated_value}'"
                            return '\n'.join(lines)
                    return content
                in_field = True
            elif in_field:
                if line.strip() == ';' and i > field_line_index + 1:
                    break  # End of multiline
                if 'civet' in line.lower():
                    # Replace existing CIVET line with current signature
                    updated_line = re.sub(
                        r'CIVET\s+v[\d.]+\s*\([^)]*\)',
                        civet_line_stripped,
                        line
                    )
                    if updated_line != line:
                        lines[i] = updated_line
                        return '\n'.join(lines)
                    return content
                if not is_multiline:
                    break  # Single line, stop after checking
    
    result_lines = []
    
    if field_line_index >= 0 and is_multiline:
        # Append to existing multiline field
        i = 0
        while i < len(lines):
            line = lines[i]
            result_lines.append(line)
            
            if i == field_line_index:
                i += 1
                # Copy opening semicolon
                if i < len(lines):
                    result_lines.append(lines[i])
                    i += 1
                
                # Copy content until closing semicolon, then append
                while i < len(lines):
                    if lines[i].strip() == ';':
                        # Append CIVET signature before closing semicolon
                        result_lines.append(civet_signature)
                        result_lines.append(lines[i])  # Closing semicolon
                        i += 1
                        break
                    else:
                        result_lines.append(lines[i])
                        i += 1
                continue
            
            i += 1
    
    elif field_line_index >= 0 and not is_multiline:
        # Convert single-line to multiline and append
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if i == field_line_index:
                # Extract existing value using the actual field name found
                pattern = rf'^{re.escape(found_field_name)}\s+(.+)$'
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    existing_value = match.group(1).strip().strip("'\"")
                    # Convert to multiline format, keeping original field name
                    result_lines.append(found_field_name)
                    result_lines.append(';')
                    result_lines.append(existing_value)
                    result_lines.append(civet_signature)
                    result_lines.append(';')
                else:
                    result_lines.append(line)
            else:
                result_lines.append(line)
            
            i += 1
    
    else:
        # Field doesn't exist - create it
        result_lines = lines[:]
        
        # Determine field name based on detected format
        new_field_name = '_audit.creation_method' if cif_format == 'modern' else '_audit_creation_method'
        
        # Find insertion point (after _audit_creation_date or after data_ block)
        insert_index = None
        date_line_index, date_is_multiline, _ = _find_audit_field(result_lines, date_fields)
        
        if date_line_index >= 0:
            insert_index = date_line_index + 1
            # Skip value line(s)
            if date_is_multiline:
                insert_index += 1  # Skip opening semicolon
                while insert_index < len(result_lines) and result_lines[insert_index].strip() != ';':
                    insert_index += 1
                if insert_index < len(result_lines):
                    insert_index += 1  # Skip closing semicolon
            else:
                # Single line - value is on same line, just move past
                pass
        else:
            # Find data_ block
            for idx, line in enumerate(result_lines):
                if line.strip().lower().startswith('data_'):
                    insert_index = idx + 1
                    break
        
        if insert_index is None:
            insert_index = 1  # After first line
        
        # Insert new field as multiline
        new_field_lines = [
            new_field_name,
            ';',
            civet_signature,
            ';'
        ]
        for j, new_line in enumerate(new_field_lines):
            result_lines.insert(insert_index + j, new_line)
    
    return '\n'.join(result_lines)


def update_audit_creation_date(content: str, cif_format: str = None) -> str:
    """
    Update _audit_creation_date (or _audit.creation_date) to the current date.
    
    Handles both modern (dot) and legacy (underscore) notation.
    If the field exists, updates its value.
    If the field doesn't exist, creates it using the detected format.
    
    Args:
        content: CIF file content
        cif_format: Optional. 'modern' or 'legacy'. If not provided, auto-detects.
                   Callers with CIFDictionaryManager should use dict_manager.detect_cif_format()
                   and pass the result here.
        
    Returns:
        Updated content with current date in _audit_creation_date
    """
    from datetime import date
    
    today = date.today().isoformat()  # Format: YYYY-MM-DD
    lines = content.split('\n')
    
    # Field name variants
    date_fields = ['_audit.creation_date', '_audit_creation_date']
    
    # Detect format for new fields (use provided or auto-detect)
    if cif_format is None:
        cif_format = _detect_cif_format_simple(content)
    else:
        cif_format = cif_format.lower()  # Normalize to lowercase
    
    # Find existing field
    field_line_index, is_multiline, found_field_name = _find_audit_field(lines, date_fields)
    
    result_lines = []
    
    if field_line_index >= 0:
        # Update existing field
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if i == field_line_index:
                if is_multiline:
                    # Replace multiline with single line
                    result_lines.append(f"{found_field_name} {today}")
                    i += 1
                    # Skip the multiline content
                    if i < len(lines) and lines[i].strip() == ';':
                        i += 1  # Skip opening semicolon
                        while i < len(lines) and lines[i].strip() != ';':
                            i += 1
                        if i < len(lines):
                            i += 1  # Skip closing semicolon
                    continue
                else:
                    # Replace single-line value
                    result_lines.append(f"{found_field_name} {today}")
            else:
                result_lines.append(line)
            
            i += 1
    else:
        # Field doesn't exist - create it
        result_lines = lines[:]
        
        # Determine field name based on detected format
        new_field_name = '_audit.creation_date' if cif_format == 'modern' else '_audit_creation_date'
        
        # Find insertion point (after data_ block)
        insert_index = None
        for idx, line in enumerate(result_lines):
            if line.strip().lower().startswith('data_'):
                insert_index = idx + 1
                break
        
        if insert_index is None:
            insert_index = 1  # After first line
        
        # Insert new field as single line
        result_lines.insert(insert_index, f"{new_field_name} {today}")
    
    return '\n'.join(result_lines)
