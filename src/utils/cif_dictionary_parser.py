"""
CIF Dictionary Parser
=====================

Parses CIF dictionary files (cif_core.dic and others) to extract field definitions and aliases.
Handles both single-line and loop-based alias definitions.
"""

import re
import os
import sys
from typing import Dict, List, Set, Optional, Tuple, NamedTuple, Any
from pathlib import Path
from dataclasses import dataclass


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


@dataclass
class FieldMetadata:
    """Complete metadata for a CIF dictionary field"""
    definition_id: str  # The canonical CIF2 field name (_definition.id)
    aliases: List[FieldAlias]  # All aliases including deprecated ones
    type_contents: Optional[str] = None  # _type.contents (Text, Real, Integer, Code, etc.)
    type_purpose: Optional[str] = None  # _type.purpose (Describe, Measurand, State, etc.)
    type_container: Optional[str] = None  # _type.container (Single, List, Matrix, etc.)
    type_source: Optional[str] = None  # _type.source (Recorded, Derived, etc.)
    description: Optional[str] = None  # _description.text
    category_id: Optional[str] = None  # _name.category_id
    is_replaced: bool = False  # Whether field is replaced/obsolete
    replacement_by: Optional[str] = None  # _definition_replaced.by
    enumeration_values: Optional[List[str]] = None  # Allowed enumeration values if any
    
    def get_all_aliases_names(self) -> List[str]:
        """Get list of all alias names (including deprecated)"""
        return [alias.name for alias in self.aliases if alias.name]
    
    def get_non_deprecated_aliases(self) -> List[str]:
        """Get list of only non-deprecated alias names"""
        return [alias.name for alias in self.aliases if alias.name and not alias.is_deprecated]
    
    def is_deprecated(self) -> bool:
        """Check if this field or any of its aliases are deprecated"""
        return self.is_replaced or any(alias.is_deprecated for alias in self.aliases)


class CIFDictionaryParser:
    """Parser for CIF dictionary files"""
    
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
        
        # New comprehensive tracking
        self._all_known_fields: Set[str] = set()  # All fields (definition_id + all aliases), case-preserved
        self._all_known_fields_lower: Set[str] = set()  # Lowercase version for case-insensitive lookup
        self._field_metadata: Dict[str, FieldMetadata] = {}  # Complete metadata per definition_id
        self._alias_to_definition: Dict[str, str] = {}  # Maps any alias (incl deprecated) -> definition_id
        
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
        """Parse a field definition block to extract complete field metadata"""
        
        # Extract the main definition ID (this is the CIF2 field name)
        def_id_match = re.search(r"_definition\.id\s+'([^']+)'", block_content)
        if not def_id_match:
            return
            
        cif2_field = def_id_match.group(1)
        
        # Extract metadata
        type_contents = self._extract_field_value(block_content, '_type.contents')
        type_purpose = self._extract_field_value(block_content, '_type.purpose')
        type_container = self._extract_field_value(block_content, '_type.container')
        type_source = self._extract_field_value(block_content, '_type.source')
        category_id = self._extract_field_value(block_content, '_name.category_id')
        description = self._extract_multiline_text(block_content, '_description.text')
        
        # Check if this field is replaced/obsolete
        is_replaced = '_definition_replaced.id' in block_content or '_definition_replaced.by' in block_content
        replacement_field = None

        if is_replaced:
            self._replaced_fields.add(cif2_field)
            
            # Try to extract replacement field - handle both single value and loop formats
            # Format 1: Single quoted value: _definition_replaced.by 'field_name'
            replacement_match = re.search(r"_definition_replaced\.by\s+'([^']+)'", block_content)
            if replacement_match:
                replacement_field = replacement_match.group(1)
            else:
                # Format 2: Loop format with multiple replacements
                # Extract the first replacement from the loop (entry with id 1)
                loop_match = re.search(
                    r'loop_\s+_definition_replaced\.id\s+_definition_replaced\.by\s+\d+\s+\'([^\']+)\'',
                    block_content,
                    re.DOTALL
                )
                if loop_match:
                    replacement_field = loop_match.group(1)        # Extract aliases with deprecation information
        aliases = self._extract_aliases_with_deprecation(block_content)
        
        # Extract enumeration values if present
        enumeration_values = self._extract_enumeration_values(block_content)
        
        # Create comprehensive metadata object
        metadata = FieldMetadata(
            definition_id=cif2_field,
            aliases=aliases,
            type_contents=type_contents,
            type_purpose=type_purpose,
            type_container=type_container,
            type_source=type_source,
            description=description,
            category_id=category_id,
            is_replaced=is_replaced,
            replacement_by=replacement_field,
            enumeration_values=enumeration_values
        )
        
        # Store metadata
        self._field_metadata[cif2_field] = metadata
        self._field_aliases[cif2_field] = aliases
        
        # Add definition_id to known fields index
        self._all_known_fields.add(cif2_field)
        self._all_known_fields_lower.add(cif2_field.lower())
        self._alias_to_definition[cif2_field.lower()] = cif2_field
        
        # Process aliases for comprehensive indexing
        for alias_info in aliases:
            if alias_info.name:
                # Add to all known fields (regardless of deprecation)
                self._all_known_fields.add(alias_info.name)
                self._all_known_fields_lower.add(alias_info.name.lower())
                self._alias_to_definition[alias_info.name.lower()] = cif2_field
                
                if alias_info.is_deprecated or is_replaced:
                    self._deprecated_fields.add(alias_info.name)
        
        # Maintain backward compatibility with existing mapping system
        if is_replaced:
            target_field = replacement_field.lower() if replacement_field else cif2_field.lower()
            for alias_info in aliases:
                if alias_info.name:
                    alias_lower = alias_info.name.lower()
                    self._cif1_to_cif2[alias_lower] = target_field
                    if target_field not in self._cif2_to_cif1:
                        self._cif2_to_cif1[target_field] = []
                    if alias_lower not in self._cif2_to_cif1[target_field]:
                        self._cif2_to_cif1[target_field].append(alias_lower)
        else:
            # Add mappings for all aliases (including deprecated ones)
            # This is necessary for format conversion to work properly
            for alias_info in aliases:
                if alias_info.name and alias_info.name != cif2_field:
                    alias_lower = alias_info.name.lower()
                    cif2_lower = cif2_field.lower()
                    self._cif1_to_cif2[alias_lower] = cif2_lower
                    if cif2_lower not in self._cif2_to_cif1:
                        self._cif2_to_cif1[cif2_lower] = []
                    if alias_lower not in self._cif2_to_cif1[cif2_lower]:
                        self._cif2_to_cif1[cif2_lower].append(alias_lower)
    
    def _extract_field_value(self, block_content: str, field_name: str) -> Optional[str]:
        """
        Extract a single field value from a dictionary block.
        
        Args:
            block_content: Content of the save block
            field_name: Name of the field to extract (e.g., '_type.contents')
            
        Returns:
            Field value or None if not found
        """
        # Pattern for single-line field values (quoted or unquoted)
        pattern = rf"{re.escape(field_name)}\s+['\"]?([^'\"\n]+)['\"]?"
        match = re.search(pattern, block_content)
        if match:
            value = match.group(1).strip()
            return value if value else None
        return None
    
    def _extract_multiline_text(self, block_content: str, field_name: str) -> Optional[str]:
        """
        Extract multiline text field (typically delimited by semicolons).
        
        Args:
            block_content: Content of the save block
            field_name: Name of the field to extract (e.g., '_description.text')
            
        Returns:
            Multiline text content or None if not found
        """
        # Pattern for semicolon-delimited text blocks
        pattern = rf"{re.escape(field_name)}\s*\n;\s*(.*?)\n;"
        match = re.search(pattern, block_content, re.DOTALL)
        if match:
            text = match.group(1).strip()
            return text if text else None
        return None
    
    def _extract_enumeration_values(self, block_content: str) -> Optional[List[str]]:
        """
        Extract enumeration values if present in the field definition.
        
        Args:
            block_content: Content of the save block
            
        Returns:
            List of allowed enumeration values or None if not an enumeration field
        """
        # Look for _enumeration.default or _enumeration_set.state patterns
        # Pattern 1: Simple enumeration list in loop
        loop_pattern = r'loop_\s*\n\s*_enumeration(?:_set)?\.(?:state|detail)\s*\n(.*?)(?=\n\s*[_a-zA-Z]|\n\s*save_|\Z)'
        match = re.search(loop_pattern, block_content, re.DOTALL)
        
        if match:
            enum_data = match.group(1).strip()
            values = []
            for line in enum_data.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract quoted or unquoted values
                    parts = line.split()
                    if parts:
                        value = parts[0]
                        if value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        values.append(value)
            return values if values else None
        
        return None
                    
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
        
        # Check exact case first
        if field_name in self._deprecated_fields or field_name in self._replaced_fields:
            return True
            
        # Check case-insensitive by comparing lowercase versions
        field_lower = field_name.lower()
        deprecated_lower = {f.lower() for f in self._deprecated_fields}
        replaced_lower = {f.lower() for f in self._replaced_fields}
        
        return field_lower in deprecated_lower or field_lower in replaced_lower
        
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
        """
        Check if a field is known in the dictionary (including all aliases, even deprecated).
        
        This method checks against the comprehensive index which includes:
        - definition_id fields
        - All aliases (both deprecated and non-deprecated)
        - Replaced/obsolete fields
        
        Args:
            field_name: Field name to check (case-insensitive)
            
        Returns:
            True if field is known in the dictionary
        """
        if not self._parsed:
            self.parse_dictionary()
        
        # Use the comprehensive lowercase index for O(1) lookup
        return field_name.lower() in self._all_known_fields_lower
    
    def get_definition_id(self, field_name: str) -> Optional[str]:
        """
        Get the canonical definition_id for any field name (including aliases).
        
        Args:
            field_name: Any field name (can be definition_id or alias)
            
        Returns:
            The canonical definition_id or None if field not found
        """
        if not self._parsed:
            self.parse_dictionary()
        
        return self._alias_to_definition.get(field_name.lower())
    
    def get_field_metadata(self, field_name: str) -> Optional[FieldMetadata]:
        """
        Get complete metadata for a field (lookup by definition_id or alias).
        
        Args:
            field_name: Field name (can be definition_id or any alias)
            
        Returns:
            FieldMetadata object or None if field not found
        """
        if not self._parsed:
            self.parse_dictionary()
        
        # First resolve to definition_id
        definition_id = self.get_definition_id(field_name)
        if definition_id:
            return self._field_metadata.get(definition_id)
        
        return None
    
    def get_field_type_contents(self, field_name: str) -> Optional[str]:
        """
        Get the type.contents value for a field (Text, Real, Integer, Code, etc.).
        
        Args:
            field_name: Field name (can be definition_id or any alias)
            
        Returns:
            Type contents string or None if field not found
        """
        metadata = self.get_field_metadata(field_name)
        return metadata.type_contents if metadata else None
    
    def get_all_aliases(self, field_name: str, include_deprecated: bool = True) -> List[str]:
        """
        Get all aliases for a field.
        
        Args:
            field_name: Field name (can be definition_id or any alias)
            include_deprecated: Whether to include deprecated aliases
            
        Returns:
            List of alias names (including the definition_id itself)
        """
        metadata = self.get_field_metadata(field_name)
        if not metadata:
            return []
        
        if include_deprecated:
            aliases = metadata.get_all_aliases_names()
        else:
            aliases = metadata.get_non_deprecated_aliases()
        
        # Always include the definition_id
        if metadata.definition_id not in aliases:
            aliases.insert(0, metadata.definition_id)
        
        return aliases
    
    def get_replacement_field(self, field_name: str) -> Optional[str]:
        """
        Get the replacement field for a deprecated/replaced field.
        
        This is a convenience method to quickly find what field should be used
        instead of a deprecated one.
        
        Args:
            field_name: Field name (can be definition_id or any alias)
            
        Returns:
            The replacement field name, or None if:
            - Field is not deprecated/replaced
            - Field has no replacement specified (deprecated with no successor)
            - Field is not found in dictionary
            
        Example:
            >>> parser.get_replacement_field('_cell_measurement.pressure')
            '_diffrn.ambient_pressure'
            
            >>> parser.get_replacement_field('_cell_measurement_pressure')  # alias works too
            '_diffrn.ambient_pressure'
            
            >>> parser.get_replacement_field('_cell_measurement.radiation')  # no replacement
            None
        """
        metadata = self.get_field_metadata(field_name)
        if metadata and metadata.is_replaced:
            return metadata.replacement_by
        return None
    
    def get_deprecation_info(self, field_name: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive deprecation information for a field.
        
        Args:
            field_name: Field name (can be definition_id or any alias)
            
        Returns:
            Dictionary with deprecation details, or None if field not found:
            {
                'is_deprecated': bool,
                'is_replaced': bool,
                'replacement_by': str or None,
                'definition_id': str,
                'description': str (may contain deprecation notice)
            }
        """
        metadata = self.get_field_metadata(field_name)
        if not metadata:
            return None
        
        return {
            'is_deprecated': metadata.is_deprecated(),
            'is_replaced': metadata.is_replaced,
            'replacement_by': metadata.replacement_by,
            'definition_id': metadata.definition_id,
            'description': metadata.description
        }
    
    def format_deprecated_section(self, deprecated_fields: List[str], 
                                   include_replacements: bool = True) -> str:
        """
        Format deprecated fields into a clearly marked section for CIF files.
        
        This creates a section that preserves deprecated fields for legacy software
        compatibility while clearly indicating they are deprecated.
        
        Args:
            deprecated_fields: List of deprecated field names found in the CIF
            include_replacements: If True, add comments showing replacement fields
            
        Returns:
            Formatted string with deprecated fields section, or empty string if no fields
            
        Example output:
            ###############################################################################
            # DEPRECATED FIELDS - Retained for legacy software compatibility
            # These fields have modern replacements and should not be used in new files
            ###############################################################################
            _cell_measurement_pressure      100.0    # Use _diffrn.ambient_pressure
            _cell_measurement_wavelength    0.71073  # Use _diffrn_radiation_wavelength.value
            ###############################################################################
        """
        if not deprecated_fields:
            return ""
        
        # Filter to only actual deprecated fields
        actual_deprecated = []
        for field in deprecated_fields:
            if self.is_field_deprecated(field):
                actual_deprecated.append(field)
        
        if not actual_deprecated:
            return ""
        
        lines = []
        lines.append("#" * 79)
        lines.append("# DEPRECATED FIELDS - Retained for legacy software compatibility")
        lines.append("# These fields have modern replacements and should not be used in new files")
        lines.append("#" * 79)
        
        # Add each deprecated field with optional replacement comment
        for field in actual_deprecated:
            if include_replacements:
                replacement = self.get_replacement_field(field)
                if replacement:
                    lines.append(f"# {field:<45} → Use {replacement}")
                else:
                    lines.append(f"# {field:<45} → Deprecated (no direct replacement)")
            else:
                lines.append(f"# {field}")
        
        lines.append("#" * 79)
        lines.append("")  # Empty line after section
        
        return "\n".join(lines)
    
    def separate_active_and_deprecated_fields(self, fields_with_values: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Separate CIF fields into active and deprecated dictionaries.
        
        Args:
            fields_with_values: Dictionary mapping field names to their values
            
        Returns:
            Tuple of (active_fields_dict, deprecated_fields_dict)
            
        Example:
            active, deprecated = parser.separate_active_and_deprecated_fields({
                '_cell_length_a': '10.5',
                '_cell_measurement_pressure': '100.0',
                '_diffrn.ambient_temperature': '293'
            })
            # active = {'_cell_length_a': '10.5', '_diffrn.ambient_temperature': '293'}
            # deprecated = {'_cell_measurement_pressure': '100.0'}
        """
        active_fields = {}
        deprecated_fields = {}
        
        for field, value in fields_with_values.items():
            if self.is_known_field(field) and self.is_field_deprecated(field):
                deprecated_fields[field] = value
            else:
                active_fields[field] = value
        
        return active_fields, deprecated_fields


# Test the parser
if __name__ == "__main__":
    parser = CIFDictionaryParser()
    
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
        print("-" * 70)
        for cif1_field, expected in test_fields:
            cif2_field = parser.get_cif2_field(cif1_field)
            print(f"{cif1_field:25} -> {cif2_field or 'NOT FOUND':25} | {expected}")
        
        print(f"\nTesting reverse conversions:")
        print("-" * 70)
        print(f"_geom_torsion.angle -> {parser.get_cif1_field('_geom_torsion.angle')}")
        print(f"_cell.length_a -> {parser.get_cif1_field('_cell.length_a')}")
        
        # Test new comprehensive lookup functionality
        print(f"\n\nTesting comprehensive field lookup (is_known_field):")
        print("-" * 70)
        
        # Test with definition_id
        test_cases = [
            '_diffrn.ambient_temperature',  # CIF2 definition_id
            '_diffrn_ambient_temperature',  # CIF1 alias
            '_diffrn_ambient_temp',  # Another alias
            '_diffrn.ambient_temp',  # Yet another alias
            '_diffrn_radiation_detector',  # Deprecated alias
            '_unknown_field_xyz',  # Unknown field
        ]
        
        for field in test_cases:
            is_known = parser.is_known_field(field)
            definition = parser.get_definition_id(field)
            is_deprecated = parser.is_field_deprecated(field)
            type_contents = parser.get_field_type_contents(field)
            
            status = []
            if is_known:
                status.append("KNOWN")
            if is_deprecated:
                status.append("DEPRECATED")
            if not is_known:
                status.append("UNKNOWN")
            
            status_str = " | ".join(status)
            
            print(f"\nField: {field}")
            print(f"  Status: {status_str}")
            if definition:
                print(f"  Definition ID: {definition}")
            if type_contents:
                print(f"  Type Contents: {type_contents}")
        
        # Test getting all aliases
        print(f"\n\nTesting alias lookup:")
        print("-" * 70)
        test_field = '_diffrn.ambient_temperature'
        all_aliases = parser.get_all_aliases(test_field, include_deprecated=True)
        non_deprecated = parser.get_all_aliases(test_field, include_deprecated=False)
        
        print(f"Field: {test_field}")
        print(f"All aliases: {', '.join(all_aliases)}")
        print(f"Non-deprecated aliases: {', '.join(non_deprecated)}")
        
        # Test metadata extraction
        print(f"\n\nTesting metadata extraction:")
        print("-" * 70)
        metadata = parser.get_field_metadata('_diffrn.ambient_temperature')
        if metadata:
            print(f"Definition ID: {metadata.definition_id}")
            print(f"Type Contents: {metadata.type_contents}")
            print(f"Type Purpose: {metadata.type_purpose}")
            print(f"Type Container: {metadata.type_container}")
            print(f"Category: {metadata.category_id}")
            print(f"Is Replaced: {metadata.is_replaced}")
            if metadata.description:
                desc_short = metadata.description[:100] + "..." if len(metadata.description) > 100 else metadata.description
                print(f"Description: {desc_short}")
            print(f"Aliases ({len(metadata.aliases)}):")
            for alias in metadata.aliases[:5]:  # Show first 5
                dep_str = f" (deprecated {alias.deprecation_date})" if alias.is_deprecated else ""
                print(f"  - {alias.name}{dep_str}")
        
        print(f"\n\nParser Statistics:")
        print("-" * 70)
        print(f"Total CIF1 -> CIF2 mappings: {len(cif1_to_cif2)}")
        print(f"Total CIF2 definitions: {len(cif2_to_cif1)}")
        print(f"Total known fields (all): {len(parser._all_known_fields)}")
        print(f"Total with complete metadata: {len(parser._field_metadata)}")
        print(f"Total deprecated fields: {len(parser._deprecated_fields)}")
        print(f"Total replaced fields: {len(parser._replaced_fields)}")
        
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()
