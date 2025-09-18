"""
CIF Core Dictionary Parser
=========================

Parses the official cif_core.dic file to extract field definitions and aliases.
Handles both single-line and loop-based alias definitions.
"""

import re
import os
import sys
from typing import Dict, List, Set, Optional, Tuple, NamedTuple
from pathlib import Path


def get_resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource file.
    Works in both development and PyInstaller environments.
    
    Args:
        relative_path: Relative path to the resource file
        
    Returns:
        Absolute path to the resource file
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Development environment - use the project root
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    
    return os.path.join(base_path, relative_path)


class FieldAlias(NamedTuple):
    """Represents a field alias with optional deprecation information"""
    name: str
    deprecation_date: Optional[str] = None
    
    @property 
    def is_deprecated(self) -> bool:
        """Check if this alias is deprecated"""
        return self.deprecation_date is not None and self.deprecation_date != '.'


class CIFCoreParser:
    """Parser for the official CIF core dictionary file"""
    
    def __init__(self, cif_core_path: Optional[str] = None):
        if cif_core_path is None:
            # Use resource path function to find bundled dictionary
            cif_core_path = get_resource_path("dictionaries/cif_core.dic")
        
        self.cif_core_path = Path(cif_core_path)
        self._cif1_to_cif2: Optional[Dict[str, str]] = None
        self._cif2_to_cif1: Optional[Dict[str, List[str]]] = None
        self._deprecated_fields: Set[str] = set()  # Track deprecated fields
        self._replaced_fields: Set[str] = set()  # Track replaced/obsolete fields
        self._field_aliases: Dict[str, List[FieldAlias]] = {}  # Track all aliases with deprecation info
        self._parsed = False
        
    def parse_dictionary(self) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        """
        Parse the CIF core dictionary and extract field mappings.
        
        Returns:
            Tuple of (cif1_to_cif2_mapping, cif2_to_cif1_mapping)
        """
        if self._parsed:
            return self._cif1_to_cif2, self._cif2_to_cif1
            
        print("Parsing CIF core dictionary...")
        
        if not self.cif_core_path.exists():
            raise FileNotFoundError(f"CIF core dictionary not found at: {self.cif_core_path}")
            
        self._cif1_to_cif2 = {}
        self._cif2_to_cif1 = {}
        self._deprecated_fields = set()
        self._replaced_fields = set()
        self._field_aliases = {}
        
        with open(self.cif_core_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        self._parse_save_blocks(content)
        
        self._parsed = True
        print(f"Parsed {len(self._cif1_to_cif2)} field mappings from CIF core dictionary")
        print(f"Found {len(self._deprecated_fields)} deprecated fields")
        print(f"Found {len(self._replaced_fields)} replaced/obsolete fields")
        
        return self._cif1_to_cif2, self._cif2_to_cif1
        
    def _parse_save_blocks(self, content: str) -> None:
        """Parse all save blocks to extract field definitions and aliases"""
        
        # Find all save blocks: save_name ... save_
        save_pattern = r'save_([^\s]+)\s*\n(.*?)\nsave_\s*(?=\n|$)'
        
        for match in re.finditer(save_pattern, content, re.DOTALL):
            save_name = match.group(1).strip()
            block_content = match.group(2)
            
            # Skip category blocks (all uppercase or no field definition)
            if save_name.isupper() or not self._has_field_definition(block_content):
                continue
                
            self._parse_field_block(save_name, block_content)
            
    def _has_field_definition(self, block_content: str) -> bool:
        """Check if a block contains a field definition"""
        return '_definition.id' in block_content
        
    def _parse_field_block(self, save_name: str, block_content: str) -> None:
        """Parse a field definition block to extract the CIF2 field and its CIF1 aliases"""
        
        # Extract the main definition ID (this is the CIF2 field name)
        def_id_match = re.search(r"_definition\.id\s+'([^']+)'", block_content)
        if not def_id_match:
            return
            
        cif2_field = def_id_match.group(1)
        
        # Check if this field is replaced/obsolete
        is_replaced = '_definition_replaced.id' in block_content or '_definition_replaced.by' in block_content
        replacement_field = None
        
        if is_replaced:
            self._replaced_fields.add(cif2_field)
            
            # Extract the replacement field name if available
            replacement_match = re.search(r"_definition_replaced\.by\s+'([^']+)'", block_content)
            if replacement_match:
                replacement_field = replacement_match.group(1)
            
            # Still process aliases, but mark them as deprecated
            aliases = self._extract_aliases_with_deprecation(block_content)
            self._field_aliases[cif2_field] = aliases
            
            # For replaced fields, create mappings to the replacement field (if available)
            # or to the original field (if no replacement specified)
            target_field = replacement_field.lower() if replacement_field else cif2_field.lower()
            
            for alias_info in aliases:
                if alias_info.name:
                    self._deprecated_fields.add(alias_info.name)
                    
                    # Still create mappings for replaced fields to help users convert
                    alias_lower = alias_info.name.lower()
                    self._cif1_to_cif2[alias_lower] = target_field
                    
                    # CIF2 -> CIF1 reverse mapping
                    if target_field not in self._cif2_to_cif1:
                        self._cif2_to_cif1[target_field] = []
                    if alias_lower not in self._cif2_to_cif1[target_field]:
                        self._cif2_to_cif1[target_field].append(alias_lower)
            return
        
        # Extract aliases with deprecation information
        aliases = self._extract_aliases_with_deprecation(block_content)
        
        # Store all alias information
        self._field_aliases[cif2_field] = aliases
        
        # Add mappings only for non-deprecated aliases
        for alias_info in aliases:
            if alias_info.name and alias_info.name != cif2_field:
                if alias_info.is_deprecated:
                    # Track deprecated field but don't add to active mappings
                    self._deprecated_fields.add(alias_info.name)
                else:
                    # CIF1 -> CIF2 mapping (only for non-deprecated)
                    # Normalize field names to lowercase for consistent lookups
                    self._cif1_to_cif2[alias_info.name.lower()] = cif2_field.lower()
                    
                    # CIF2 -> CIF1 reverse mapping (only for non-deprecated)
                    cif2_lower = cif2_field.lower()
                    if cif2_lower not in self._cif2_to_cif1:
                        self._cif2_to_cif1[cif2_lower] = []
                    alias_lower = alias_info.name.lower()
                    if alias_lower not in self._cif2_to_cif1[cif2_lower]:
                        self._cif2_to_cif1[cif2_lower].append(alias_lower)
                    
    def _extract_aliases_with_deprecation(self, block_content: str) -> List[FieldAlias]:
        """Extract all alias definitions from a field block with deprecation information"""
        aliases = []
        
        # Pattern 1: Single alias on one line (no deprecation info available)
        # _alias.definition_id          '_field_name'
        single_alias_pattern = r"_alias\.definition_id\s+'([^']+)'"
        for match in re.finditer(single_alias_pattern, block_content):
            aliases.append(FieldAlias(match.group(1)))
            
        # Pattern 2: Loop-based aliases with optional deprecation dates
        # loop_
        #   _alias.definition_id
        #   _alias.deprecation_date  # Optional
        #      '_field1'    2003-01-01
        #      '_field2'    .
        loop_pattern = r'loop_\s*\n\s*_alias\.definition_id\s*\n\s*_alias\.deprecation_date\s*\n(.*?)(?=\n\s*[_a-zA-Z]|\n\s*save_|\Z)'
        loop_match = re.search(loop_pattern, block_content, re.DOTALL)
        
        if loop_match:
            alias_data = loop_match.group(1).strip()
            for line in alias_data.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Handle lines with deprecation dates: '_field_name'  date
                    parts = line.split()
                    if len(parts) >= 2:
                        field_name = parts[0]
                        deprecation_date = parts[1]
                        # Remove quotes if present
                        if field_name.startswith("'") and field_name.endswith("'"):
                            field_name = field_name[1:-1]
                        aliases.append(FieldAlias(field_name, deprecation_date))
                    elif len(parts) == 1:
                        # Just field name, no deprecation date
                        field_name = parts[0]
                        if field_name.startswith("'") and field_name.endswith("'"):
                            field_name = field_name[1:-1]
                        aliases.append(FieldAlias(field_name))
        else:
            # Check for loop without deprecation dates
            loop_pattern_simple = r'loop_\s*\n\s*_alias\.definition_id\s*\n(.*?)(?=\n\s*[_a-zA-Z]|\n\s*save_|\Z)'
            loop_match_simple = re.search(loop_pattern_simple, block_content, re.DOTALL)
            
            if loop_match_simple:
                alias_data = loop_match_simple.group(1).strip()
                for line in alias_data.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Just field names, no deprecation info
                        parts = line.split()
                        if parts:
                            field_name = parts[0]
                            # Remove quotes if present
                            if field_name.startswith("'") and field_name.endswith("'"):
                                field_name = field_name[1:-1]
                            aliases.append(FieldAlias(field_name))
                        
        return aliases
        
    def is_field_deprecated(self, field_name: str) -> bool:
        """Check if a field is deprecated or replaced (obsolete)"""
        if not self._parsed:
            self.parse_dictionary()
        return field_name in self._deprecated_fields or field_name in self._replaced_fields
        
    def get_field_aliases_info(self, cif2_field: str) -> List[FieldAlias]:
        """Get all alias information for a CIF2 field including deprecation status"""
        if not self._parsed:
            self.parse_dictionary()
        return self._field_aliases.get(cif2_field, [])
        
    def get_non_deprecated_aliases(self, cif2_field: str) -> List[str]:
        """Get only non-deprecated aliases for a CIF2 field"""
        if not self._parsed:
            self.parse_dictionary()
        aliases_info = self._field_aliases.get(cif2_field, [])
        return [alias.name for alias in aliases_info if not alias.is_deprecated]
        
    def get_cif2_field(self, cif1_field: str) -> Optional[str]:
        """Get the CIF2 field name for a CIF1 field"""
        if not self._parsed:
            self.parse_dictionary()
        return self._cif1_to_cif2.get(cif1_field)
        
    def get_cif1_field(self, cif2_field: str) -> Optional[str]:
        """Get the primary CIF1 field name for a CIF2 field (first non-deprecated alias without dots)"""
        if not self._parsed:
            self.parse_dictionary()
            
        # Get only non-deprecated aliases
        aliases = self.get_non_deprecated_aliases(cif2_field)
        
        # Find the first alias without dots (CIF1 format)
        for alias in aliases:
            if '.' not in alias:
                return alias
                
        # If no underscore-only alias found, return the first non-deprecated one
        return aliases[0] if aliases else None
        
    def is_known_field(self, field_name: str) -> bool:
        """Check if a field is known in the dictionary"""
        if not self._parsed:
            self.parse_dictionary()
            
        return (field_name in self._cif1_to_cif2 or 
                field_name in self._cif2_to_cif1)


# Test the parser
if __name__ == "__main__":
    parser = CIFCoreParser()
    
    try:
        cif1_to_cif2, cif2_to_cif1 = parser.parse_dictionary()
        
        # Test key examples
        test_fields = [
            ('_geom_torsion', 'Expected: _geom_torsion.angle'),
            ('_cell_length_a', 'Expected: _cell.length_a'),
            ('_space_group_IT_number', 'Expected: _space_group.IT_number'),
            ('_atom_site_fract_x', 'Expected: _atom_site.fract_x'),
        ]
        
        print("\nTesting CIF1 -> CIF2 conversions:")
        print("-" * 50)
        for cif1_field, expected in test_fields:
            cif2_field = parser.get_cif2_field(cif1_field)
            print(f"{cif1_field:25} -> {cif2_field or 'NOT FOUND':25} | {expected}")
            
        print(f"\nTesting reverse conversions:")
        print("-" * 50)
        print(f"_geom_torsion.angle -> {parser.get_cif1_field('_geom_torsion.angle')}")
        print(f"_cell.length_a -> {parser.get_cif1_field('_cell.length_a')}")
        
        print(f"\nParser Statistics:")
        print(f"Total CIF1 -> CIF2 mappings: {len(cif1_to_cif2)}")
        print(f"Total CIF2 definitions: {len(cif2_to_cif1)}")
        
    except Exception as e:
        print(f"Error: {e}")