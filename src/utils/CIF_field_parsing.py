"""Module containing CIF checking functionality and field definition loading."""

# import os

class CIFField:
    """Class representing a CIF field definition."""
    def __init__(self, name, default_value, description="", action="CHECK"):
        self.name = name
        self.default_value = default_value
        self.description = description
        self.action = action  # "CHECK", "DELETE", or "EDIT"

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
    _field_name value  # Normal check (default behavior)
    
    Values can be quoted or unquoted. The function preserves the quotation style.
    Comments starting with # can contain field descriptions.
    """
    try:
        all_fields = []
        descriptions = {}
        
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
        
        # Second pass: collect field definitions
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
                
                # Detect action type (DELETE:, EDIT:, or default CHECK)
                action = "CHECK"
                original_line = line
                
                if line.upper().startswith('DELETE:'):
                    action = "DELETE"
                    line = line[7:].strip()  # Remove "DELETE:" prefix
                elif line.upper().startswith('EDIT:'):
                    action = "EDIT"
                    line = line[5:].strip()  # Remove "EDIT:" prefix
                
                # For DELETE action, we only need the field name
                if action == "DELETE":
                    if line.startswith('_'):
                        field = line
                        value = ""  # No value needed for deletion
                        description = descriptions.get(field, comment_desc)
                        if comment_desc and not description:
                            description = comment_desc
                        all_fields.append(CIFField(field, value, description, action))
                    continue
                
                # For CHECK and EDIT actions, we need field and value
                parts = line.split(maxsplit=1)
                if len(parts) < 1:
                    continue
                elif len(parts) == 1:
                    # Only field name provided
                    field = parts[0]
                    value = ""
                else:
                    field, value = parts
                    
                # Skip if not a valid field name
                if not field.startswith('_'):
                    continue
                
                description = descriptions.get(field, comment_desc)
                if comment_desc and not description:
                    description = comment_desc
                    
                # Add options to description if present in comments
                if 'options:' in description.lower():
                    options_idx = description.lower().find('options:')
                    options_text = description[options_idx:].strip()
                    description = f"{description[:options_idx].strip()}\n{options_text}"
                
                # Create a CIFField object with the appropriate action
                all_fields.append(CIFField(field, value, description, action))
                
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
        """Apply DELETE and EDIT operations to CIF content.
        
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
