"""Module containing CIF checking functionality and field definition loading."""

import ast
import operator
import re

# Safe operators for expression evaluation
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def safe_eval_expr(expr_str, field_values):
    """
    Safely evaluate a mathematical expression with field value substitution.
    
    Args:
        expr_str: Expression string like "_field1 / (_field2 * 60)"
        field_values: Dict mapping field names to their numeric values
        
    Returns:
        Evaluated result as float, or None if evaluation fails
    """
    try:
        # Substitute field names with their values
        substituted = expr_str
        for field_name, value in field_values.items():
            # Use word boundaries to avoid partial matches
            pattern = re.escape(field_name) + r'(?![a-zA-Z0-9_\.])'
            substituted = re.sub(pattern, str(value), substituted)
        
        # Check if any field references remain (unresolved)
        remaining_fields = re.findall(r'_[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)*', substituted)
        if remaining_fields:
            return None  # Some fields couldn't be resolved
        
        # Parse and evaluate safely
        tree = ast.parse(substituted, mode='eval')
        return _eval_node(tree.body)
    except Exception:
        return None

def _eval_node(node):
    """Recursively evaluate an AST node for safe math expressions."""
    if isinstance(node, ast.Constant):  # Python 3.8+
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    elif isinstance(node, ast.Num):  # Python 3.7 compatibility
        return float(node.n)
    elif isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            return SAFE_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported operator: {op_type}")
    elif isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            return SAFE_OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type}")
    elif isinstance(node, ast.Expression):
        return _eval_node(node.body)
    else:
        raise ValueError(f"Unsupported node type: {type(node)}")


class CIFField:
    """Class representing a CIF field definition."""
    def __init__(self, name, default_value, description="", action="CHECK", suggestions=None, rename_to=None, expression=None):
        self.name = name
        self.default_value = default_value
        self.description = description
        self.action = action  # "CHECK", "DELETE", "EDIT", "APPEND", "RENAME", or "CALCULATE"
        self.suggestions = suggestions or []
        self.rename_to = rename_to  # Target field name for RENAME action
        self.expression = expression  # Mathematical expression for CALCULATE action

def load_cif_field_rules(filepath):
    """Load CIF field rules from a CIF-style file.
    
    The file format is CIF-like with each line having:
    _field_name value # description
    or
    # _field_name: description
    _field_name value
    
    Special actions can be specified with prefixes:
    DELETE: _field_name  # This will remove the field entirely
    EDIT: _field_name new_value  # This will replace the field's value
    APPEND: _field_name append_text  # This will append text to existing multiline value
    RENAME: _old_name _new_name  # This will rename a field to a new name
    CALCULATE: _field = expression  # Calculate field value from expression using other fields
    _field_name value  # Normal check (default behavior)
    
    Values can be quoted or unquoted. The function preserves the quotation style.
    Comments starting with # can contain field descriptions.
    """
    try:
        all_fields = []
        descriptions = {}
        field_map = {}
        field_order = []
        
        # First pass: collect descriptions from comments
        with open(filepath, 'r', encoding='utf-8') as f:
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
        
        # Second pass: collect field definitions and aggregate suggestions
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#') or line.startswith('//'):
                    continue
                
                # Handle inline comments
                comment_desc = ""
                if '#' in line:
                    line, comment_desc = line.split('#', 1)
                    line = line.strip()
                    comment_desc = comment_desc.strip()
                
                # Detect action type (DELETE:, EDIT:, APPEND:, RENAME:, CALCULATE:, or default CHECK)
                action = "CHECK"
                rename_to = None
                expression = None
                if line.upper().startswith('DELETE:'):
                    action = "DELETE"
                    line = line[7:].strip()  # Remove "DELETE:" prefix
                elif line.upper().startswith('EDIT:'):
                    action = "EDIT"
                    line = line[5:].strip()  # Remove "EDIT:" prefix
                elif line.upper().startswith('APPEND:'):
                    action = "APPEND"
                    line = line[7:].strip()  # Remove "APPEND:" prefix
                elif line.upper().startswith('RENAME:'):
                    action = "RENAME"
                    line = line[7:].strip()  # Remove "RENAME:" prefix
                    # RENAME expects: _old_name _new_name
                    parts = line.split()
                    if len(parts) >= 2 and parts[0].startswith('_') and parts[1].startswith('_'):
                        field = parts[0]
                        rename_to = parts[1]
                        description = descriptions.get(field, comment_desc) or comment_desc
                        if field not in field_map:
                            field_obj = CIFField(field, "", description, action, [], rename_to)
                            field_map[field] = field_obj
                            field_order.append(field)
                    continue
                elif line.upper().startswith('CALCULATE:'):
                    action = "CALCULATE"
                    line = line[10:].strip()  # Remove "CALCULATE:" prefix
                    # CALCULATE expects: _target_field = expression
                    if '=' in line:
                        field_part, expr_part = line.split('=', 1)
                        field = field_part.strip()
                        expression = expr_part.strip()
                        if field.startswith('_') and expression:
                            description = descriptions.get(field, comment_desc) or comment_desc
                            if field not in field_map:
                                field_obj = CIFField(field, "", description, action, [], None, expression)
                                field_map[field] = field_obj
                                field_order.append(field)
                    continue
                
                # For DELETE action, we only need the field name
                if action == "DELETE":
                    if line.startswith('_'):
                        field = line
                        description = descriptions.get(field, comment_desc) or comment_desc
                        if field not in field_map:
                            field_obj = CIFField(field, "", description, action, [])
                            field_map[field] = field_obj
                            field_order.append(field)
                    continue
                
                # For CHECK and EDIT actions, we need field and value
                parts = line.split(maxsplit=1)
                if len(parts) < 1:
                    continue
                elif len(parts) == 1:
                    field = parts[0]
                    value = ""
                else:
                    field, value = parts
                    
                # Skip if not a valid field name
                if not field.startswith('_'):
                    continue
                
                description = descriptions.get(field, comment_desc) or comment_desc
                
                # Add options to description if present in comments
                if description and 'options:' in description.lower():
                    options_idx = description.lower().find('options:')
                    options_text = description[options_idx:].strip()
                    description = f"{description[:options_idx].strip()}\n{options_text}"
                
                # Aggregate repeated fields into suggestions for dropdowns (not for EDIT/APPEND)
                existing = field_map.get(field)
                if existing and existing.action == "CHECK" and action == "CHECK":
                    if value and value not in existing.suggestions:
                        existing.suggestions.append(value)
                    if not existing.default_value and value:
                        existing.default_value = value
                    if not existing.description and description:
                        existing.description = description
                elif existing and existing.action == "APPEND" and action == "APPEND":
                    # Aggregate multiple APPEND entries for the same field
                    if value:
                        # Concatenate with blank line separator
                        if existing.default_value:
                            existing.default_value += "\n\n" + value
                        else:
                            existing.default_value = value
                else:
                    suggestions = [value] if value else []
                    field_obj = CIFField(field, value, description, action, suggestions)
                    field_map[field] = field_obj
                    field_order.append(field)
                
        # Preserve file order while returning aggregated fields
        for field_name in field_order:
            all_fields.append(field_map[field_name])
        return all_fields
    except Exception as e:
        print(f"Error loading CIF field definitions: {e}")
        return []


class CIFFieldChecker:
    """Class that manages CIF field checking with support for multiple field sets."""
    
    def __init__(self):
        self.field_sets = {}
        
    def load_field_set(self, name, filepath):
        """Load a named set of field rules from a file."""
        fields = load_cif_field_rules(filepath)
        if fields:
            self.field_sets[name] = fields
            return True
        return False
    
    def get_field_set(self, name):
        """Get a list of fields for a named set."""
        return self.field_sets.get(name, [])

    def apply_field_operations(self, text_content, field_set_name):
        """Apply DELETE, EDIT, and RENAME operations to CIF content.
        
        Args:
            text_content (str): The CIF file content
            field_set_name (str): Name of the field set to apply
            
        Returns:
            tuple: (modified_content, operations_applied)
        """
        fields = self.get_field_set(field_set_name)
        if not fields:
            return text_content, []
        
        lines = text_content.splitlines()
        operations_applied = []
        
        for field_def in fields:
            if field_def.action == "DELETE":
                lines, deleted = self._delete_field(lines, field_def.name)
                if deleted:
                    operations_applied.append(f"DELETED: {field_def.name}")
            elif field_def.action == "EDIT":
                lines, edited = self._edit_field(lines, field_def.name, field_def.default_value)
                if edited:
                    operations_applied.append(f"EDITED: {field_def.name} -> {field_def.default_value}")
            elif field_def.action == "RENAME":
                lines, renamed = self._rename_field(lines, field_def.name, field_def.rename_to)
                if renamed:
                    operations_applied.append(f"RENAMED: {field_def.name} -> {field_def.rename_to}")
        
        return '\n'.join(lines), operations_applied
    
    def _delete_field(self, lines, field_name):
        """Delete a field from the CIF content.
        
        Args:
            lines (list): List of lines in the CIF file
            field_name (str): Name of field to delete
            
        Returns:
            tuple: (modified_lines, was_deleted)
        """
        modified_lines = []
        deleted = False
        
        for line in lines:
            if line.strip().startswith(field_name):
                # Skip this line (delete it)
                deleted = True
                continue
            modified_lines.append(line)
        
        return modified_lines, deleted
    
    def _edit_field(self, lines, field_name, new_value):
        """Edit a field's value in the CIF content.
        
        Args:
            lines (list): List of lines in the CIF file
            field_name (str): Name of field to edit
            new_value (str): New value for the field
            
        Returns:
            tuple: (modified_lines, was_edited)
        """
        modified_lines = []
        edited = False
        
        for line in lines:
            if line.strip().startswith(field_name):
                # Replace the line with new value
                if new_value:
                    modified_lines.append(f"{field_name}    {new_value}")
                else:
                    # If new_value is empty, skip the line (same as delete)
                    edited = True
                    continue
                edited = True
            else:
                modified_lines.append(line)
        
        return modified_lines, edited
    
    def _append_field(self, lines, field_name, append_text):
        """Append text to a multiline field's value in the CIF content.
        
        Args:
            lines (list): List of lines in the CIF file
            field_name (str): Name of field to append to
            append_text (str): Text to append (will be added with blank line separator)
            
        Returns:
            tuple: (modified_lines, was_appended)
        """
        modified_lines = []
        appended = False
        in_multiline = False
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check if this is the target field with semicolon delimiter
            if line.strip().startswith(field_name):
                # Check if it's a multiline value starting with semicolon
                if i + 1 < len(lines) and lines[i + 1].strip() == ';':
                    # Add field name and opening semicolon
                    modified_lines.append(line)
                    modified_lines.append(lines[i + 1])
                    i += 2
                    in_multiline = True
                    
                    # Copy content until closing semicolon
                    while i < len(lines):
                        if lines[i].strip() == ';':
                            # Found closing semicolon - append new content before it
                            modified_lines.append('')  # Blank line separator
                            modified_lines.append(append_text)
                            modified_lines.append(lines[i])  # Closing semicolon
                            appended = True
                            in_multiline = False
                            i += 1
                            break
                        else:
                            modified_lines.append(lines[i])
                            i += 1
                    continue
                else:
                    # Not a multiline field - just copy as-is
                    modified_lines.append(line)
            else:
                modified_lines.append(line)
            
            i += 1
        
        return modified_lines, appended

    def _rename_field(self, lines, old_name, new_name):
        """Rename a field in the CIF content.
        
        This is used to correct erroneously named fields output by some programs.
        For example, Olex2 outputs _refine_diff_density_max for 3D ED data,
        but the correct name should be _refine_diff.potential_max.
        
        Args:
            lines (list): List of lines in the CIF file
            old_name (str): Current (incorrect) field name
            new_name (str): Correct field name to rename to
            
        Returns:
            tuple: (modified_lines, was_renamed)
        """
        import re
        modified_lines = []
        renamed = False
        i = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Check for exact field name match (including loop columns)
            # Match the old field name at the start of the line
            if stripped.startswith(old_name):
                # Get the rest after the field name
                rest = stripped[len(old_name):]
                # Check it's a complete field name (followed by whitespace, value, or end of line)
                if rest == '' or rest[0] in ' \t':
                    # Preserve leading whitespace
                    leading_ws = line[:len(line) - len(line.lstrip())]
                    # Replace old name with new name
                    new_line = leading_ws + new_name + rest
                    modified_lines.append(new_line)
                    renamed = True
                    i += 1
                    continue
            
            modified_lines.append(line)
            i += 1
        
        return modified_lines, renamed
