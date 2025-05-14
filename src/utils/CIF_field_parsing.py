"""Module containing CIF checking functionality and field definition loading."""

# import os

class CIFField:
    """Class representing a CIF field definition."""
    def __init__(self, name, default_value, description=""):
        self.name = name
        self.default_value = default_value
        self.description = description

def load_cif_field_definitions(filepath):
    """Load CIF field definitions from a CIF-style file.
    
    The file format is CIF-like with each line having:
    _field_name value # description
    or
    # _field_name: description
    _field_name value
    
    Values can be quoted or unquoted. The function preserves the quotation style.
    Comments starting with # can contain field descriptions.
    """
    try:
        all_fields = []
        descriptions = {}
        
        # First pass: collect descriptions from comments
        with open(filepath, 'r') as f:
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
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#') or line.startswith('//'):
                    continue
                
                # Handle inline comments
                if '#' in line:
                    line = line.split('#', 1)[0].strip()
                
                # Split on first whitespace to separate field from value
                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    continue
                    
                field, value = parts
                description = descriptions.get(field, '')
                    
                # Add options to description if present in comments
                if 'options:' in description.lower():
                    options_idx = description.lower().find('options:')
                    options_text = description[options_idx:].strip()
                    description = f"{description[:options_idx].strip()}\n{options_text}"
                
                # Create a CIFField object instead of a tuple
                all_fields.append(CIFField(field, value, description))
                
        return all_fields
    except Exception as e:
        print(f"Error loading CIF field definitions: {e}")
        return []


class CIFFieldChecker:
    """Class that manages CIF field checking with support for multiple field sets."""
    
    def __init__(self):
        self.field_sets = {}
        
    def load_field_set(self, name, filepath):
        """Load a named set of field definitions from a file."""
        fields = load_cif_field_definitions(filepath)
        if fields:
            self.field_sets[name] = fields
            return True
        return False
    
    def get_field_set(self, name):
        """Get a list of fields for a named set."""
        return self.field_sets.get(name, [])
