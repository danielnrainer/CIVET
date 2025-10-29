"""
CIF Format Converter
====================

Converts between CIF1 and CIF2 formats, handling:
- Field name modernization (deprecated → current)
- Format compliance fixing (mixed → pure)
- Version header management
- Data type conversions where applicable
- modern-only field support (fields without CIF1 aliases)
- Duplicate/alias detection and removal
- checkCIF compatibility (retaining legacy notation for unsupported modern fields)

"""

import re
import os
from typing import Dict, List, Tuple, Optional, Set
from .cif_dictionary_manager import CIFDictionaryManager, CIFVersion


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        import sys
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    
    return os.path.join(base_path, relative_path)


class CIFFormatConverter:
    """
    Converts CIF files between different format versions and fixes compliance issues.
    Includes support for electron diffraction extension fields.
    """
    
    def __init__(self, dictionary_manager: Optional[CIFDictionaryManager] = None):
        """
        Initialize the converter.
        
        Args:
            dictionary_manager: Optional pre-configured dictionary manager
        """
        self.dict_manager = dictionary_manager or CIFDictionaryManager()
        self.checkcif_compatibility_fields = self._load_checkcif_compatibility_fields()
    
    def _load_checkcif_compatibility_fields(self) -> Set[str]:
        """
        Load the list of fields that need legacy notation for checkCIF compatibility.
        
        Returns:
            Set of field names (in legacy underscore notation) that need dual format
        """
        try:
            # Try field_rules directory first (production location)
            config_path = get_resource_path(os.path.join('field_rules', 'checkcif_compatibility.cif_rules'))
            if not os.path.exists(config_path):
                # Try alternative path for development
                config_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                    'field_rules', 
                    'checkcif_compatibility.cif_rules'
                )
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    fields = set()
                    for line in f:
                        line = line.strip()
                        # Skip comments and empty lines
                        if line and not line.startswith('#'):
                            fields.add(line)
                    return fields
            else:
                # Fallback hardcoded list if file not found
                return {
                    '_diffrn_measurement_device_type',
                    '_atom_site_aniso_label',
                    '_geom_angle',
                    '_cell_measurement_temperature'
                }
        except Exception as e:
            print(f"Warning: Could not load checkCIF compatibility fields: {e}")
            # Return hardcoded fallback
            return {
                '_diffrn_measurement_device_type',
                '_atom_site_aniso_label',
                '_geom_angle',
                '_cell_measurement_temperature'
            }
    
    def convert_to_cif2(self, cif_content: str, remove_duplicates: bool = True) -> Tuple[str, List[str]]:
        """
        Convert CIF content to CIF2 format.
        
        Args:
            cif_content: Original CIF content
            remove_duplicates: If True, remove duplicate/alias fields after conversion
            
        Returns:
            Tuple of (converted_content, list_of_changes_made)
        """
        lines = cif_content.split('\n')
        converted_lines = []
        changes = []
        unknown_fields = []  # Track unknown fields
        checkcif_legacy_retained = []  # Track fields retained for checkCIF
        deprecated_fields_found = {}  # Track deprecated fields BEFORE conversion: field_name -> value
        
        # Add CIF2 header if not present
        header_added = False
        if not any(line.strip().startswith('#\\#CIF_2.0') for line in lines[:5]):
            converted_lines.append('#\\#CIF_2.0')
            converted_lines.append('')
            changes.append("Added CIF2 version header")
            header_added = True
        
        # Track loop state for proper field conversion within loops
        in_loop = False
        loop_field_count = 0
        
        for i, line in enumerate(lines):
            original_line = line
            
            # Before converting, check if this line contains a deprecated field
            field_match = re.match(r'^(\s*)(_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*)\s+(.+)$', line)
            if field_match:
                indent, field_name, value = field_match.groups()
                if self.dict_manager.is_field_deprecated(field_name):
                    # Store the deprecated field for later processing
                    deprecated_fields_found[field_name] = value
            
            # Check for loop start/end
            if line.strip() == 'loop_':
                in_loop = True
                loop_field_count = 0
                converted_line = line
            elif in_loop and line.strip().startswith('_'):
                # This is a loop field definition
                loop_field_count += 1
                converted_line = self._convert_line_to_cif2(line, unknown_fields)
            elif in_loop and line.strip() and not line.strip().startswith('_') and not line.strip().startswith('#'):
                # This might be loop data (not a field definition)
                # Check if we've seen field definitions and now have data
                if loop_field_count > 0:
                    # This is loop data, don't convert field names in data
                    converted_line = line
                else:
                    # Still in field definitions
                    converted_line = self._convert_line_to_cif2(line, unknown_fields)
            elif in_loop and (line.strip() == '' or line.strip().startswith('data_') or line.strip() == 'loop_'):
                # End of loop (empty line, new data block, or new loop)
                in_loop = False
                loop_field_count = 0
                if line.strip().startswith('_'):
                    converted_line = self._convert_line_to_cif2(line, unknown_fields)
                else:
                    converted_line = line
            else:
                # Regular line processing
                converted_line = self._convert_line_to_cif2(line, unknown_fields)
            
            if converted_line != original_line:
                changes.append(f"Line {i+1+(2 if header_added else 0)}: {original_line.strip()} → {converted_line.strip()}")
            
            converted_lines.append(converted_line)
        
        # Post-processing pipeline:
        converted_content = '\n'.join(converted_lines)
        
        # 1. Remove duplicates first
        if remove_duplicates:
            converted_content, dup_changes = self._remove_duplicate_aliases(converted_content)
            changes.extend(dup_changes)
        
        # 2. Handle deprecated fields (add deprecated section)
        # Pass the deprecated fields we found during initial scan
        converted_content, deprecated_changes = self._handle_deprecated_fields(
            converted_content, 
            deprecated_fields_found
        )
        changes.extend(deprecated_changes)
        
        # 3. Add legacy notation for checkCIF compatibility fields
        converted_content, compat_changes = self._add_checkcif_legacy_notation(converted_content)
        changes.extend(compat_changes)
        
        # Add warnings for unknown fields
        if unknown_fields:
            changes.append(f"WARNING: {len(unknown_fields)} unknown field(s): {', '.join(set(unknown_fields))}")
        
        return converted_content, changes
    
    def convert_to_cif1(self, cif_content: str) -> Tuple[str, List[str]]:
        """
        Convert CIF content to CIF1 format.
        
        Args:
            cif_content: Original CIF content
            
        Returns:
            Tuple of (converted_content, list_of_changes_made)
        """
        lines = cif_content.split('\n')
        converted_lines = []
        changes = []
        unknown_fields = []  # Track unknown fields
        
        # Track loop state for proper field conversion within loops
        in_loop = False
        loop_field_count = 0
        
        for i, line in enumerate(lines):
            # Skip CIF2 version headers
            if line.strip().startswith('#\\#CIF_2.0'):
                changes.append(f"Line {i+1}: Removed CIF2 version header")
                continue
            
            # Add CIF1 header if this was the first line and we're replacing CIF2 header
            if i == 0 and line.strip().startswith('#\\#CIF_2.0'):
                converted_lines.append('#\\#CIF_1.1')
                converted_lines.append('')
                changes.append("Added CIF1 version header")
                continue
            
            original_line = line
            
            # Check for loop start/end
            if line.strip() == 'loop_':
                in_loop = True
                loop_field_count = 0
                converted_line = line
            elif in_loop and line.strip().startswith('_'):
                # This is a loop field definition
                loop_field_count += 1
                converted_line = self._convert_line_to_cif1(line, unknown_fields)
            elif in_loop and line.strip() and not line.strip().startswith('_') and not line.strip().startswith('#'):
                # This might be loop data (not a field definition)
                # Check if we've seen field definitions and now have data
                if loop_field_count > 0:
                    # This is loop data, don't convert field names in data
                    converted_line = line
                else:
                    # Still in field definitions
                    converted_line = self._convert_line_to_cif1(line, unknown_fields)
            elif in_loop and (line.strip() == '' or line.strip().startswith('data_') or line.strip() == 'loop_'):
                # End of loop (empty line, new data block, or new loop)
                in_loop = False
                loop_field_count = 0
                if line.strip().startswith('_'):
                    converted_line = self._convert_line_to_cif1(line, unknown_fields)
                else:
                    converted_line = line
            else:
                # Regular line processing
                converted_line = self._convert_line_to_cif1(line, unknown_fields)
            
            if converted_line != original_line:
                changes.append(f"Line {i+1}: {original_line.strip()} → {converted_line.strip()}")
            
            converted_lines.append(converted_line)
        
        # Add warnings for unknown fields
        if unknown_fields:
            changes.append(f"WARNING: {len(unknown_fields)} unknown field(s): {', '.join(set(unknown_fields))}")
        
        return '\n'.join(converted_lines), changes
    
    def fix_mixed_format(self, cif_content: str, target_version: CIFVersion = CIFVersion.CIF2) -> Tuple[str, List[str]]:
        """
        Fix a mixed-format CIF file to be compliant with specified version.
        
        Args:
            cif_content: Mixed-format CIF content
            target_version: Target CIF version (CIF1 or CIF2)
            
        Returns:
            Tuple of (fixed_content, list_of_changes_made)
        """
        if target_version == CIFVersion.CIF2:
            return self.convert_to_cif2(cif_content)
        elif target_version == CIFVersion.CIF1:
            return self.convert_to_cif1(cif_content)
        else:
            raise ValueError(f"Cannot convert to {target_version}")
    
    def _convert_line_to_cif2(self, line: str, unknown_fields: List[str] = None) -> str:
        """
        Convert a single line to CIF2 format.
        
        Args:
            line: Line to convert
            unknown_fields: List to track unknown fields (optional)
            
        Returns:
            Converted line
        """
        # Skip comments and empty lines
        if line.strip().startswith('#') or not line.strip():
            return line
        
        # Check if line starts with a field name (allow hyphens, dots, brackets, slashes, etc.)
        # Handle both cases: field with value and field without value (loop definitions)
        field_match = re.match(r'^(\s*)(_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*)\s*(.*)$', line)
        if not field_match:
            return line
        
        indent, field_name, rest = field_match.groups()
        
        # Check if field is known in dictionary
        if unknown_fields is not None and not self.dict_manager.is_known_field(field_name):
            unknown_fields.append(field_name)
        
        # Convert field name using dictionary lookup
        converted_field = self._convert_field_to_cif2(field_name)
        if converted_field != field_name:
            if rest.strip():  # Has value after field name
                return f"{indent}{converted_field} {rest}"
            else:  # Field name only (loop definition)
                return f"{indent}{converted_field}"
        
        return line
    
    def _convert_line_to_cif1(self, line: str, unknown_fields: List[str] = None) -> str:
        """
        Convert a single line to CIF1 format.
        
        Args:
            line: Line to convert
            unknown_fields: List to track unknown fields (optional)
            
        Returns:
            Converted line
        """
        # Skip comments and empty lines
        if line.strip().startswith('#') or not line.strip():
            return line
        
        # Check if line starts with a CIF field name (allow dots, hyphens, brackets, slashes, etc.)
        # Handle both cases: field with value and field without value (loop definitions)
        field_match = re.match(r'^(\s*)(_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*)\s*(.*)$', line)
        if not field_match:
            return line
        
        indent, field_name, rest = field_match.groups()
        
        # Check if field is known in dictionary
        if unknown_fields is not None and not self.dict_manager.is_known_field(field_name):
            unknown_fields.append(field_name)
        
        # Convert field name using dictionary lookup
        converted_field = self._convert_field_to_cif1(field_name)
        if converted_field != field_name:
            if rest.strip():  # Has value after field name
                return f"{indent}{converted_field} {rest}"
            else:  # Field name only (loop definition)
                return f"{indent}{converted_field}"
        
        return line
    
    def _convert_field_to_cif2(self, field_name: str) -> str:
        """
        Convert a CIF1 field name to CIF2 format using the CIF core dictionary.
        
        For deprecated fields with modern replacements (e.g., _cell_measurement_temperature
        -> _diffrn.ambient_temperature), this uses the modern replacement.
        
        For non-deprecated fields, this uses the CIF2 alias (e.g., _space_group_it_number
        -> _space_group.IT_number).
        
        Args:
            field_name: CIF1 field name (e.g., '_cell_length_a')
            
        Returns:
            CIF2 field name (e.g., '_cell.length_a') based on dictionary lookups
        """
        # Check if this is a deprecated field with a modern replacement
        # (e.g., _cell_measurement_temperature -> _diffrn.ambient_temperature)
        if self.dict_manager.is_field_deprecated(field_name):
            modern_replacement = self.dict_manager.get_modern_replacement(field_name)
            if modern_replacement and modern_replacement != field_name:
                return modern_replacement
        
        # Otherwise, use standard CIF2 equivalent (alias conversion)
        # (e.g., _space_group_it_number -> _space_group.IT_number)
        cif2_equivalent = self.dict_manager.get_cif2_equivalent(field_name)
        
        if cif2_equivalent:
            return cif2_equivalent
            
        # If not found in dictionary, return original field name unchanged
        # (This preserves unknown/custom fields)
        return field_name
    
    def _convert_field_to_cif1(self, field_name: str) -> str:
        """
        Convert a CIF2 field name to CIF1 format using the CIF core dictionary.
        
        Args:
            field_name: CIF2 field name (e.g., '_cell.length_a')
            
        Returns:
            CIF1 field name (e.g., '_cell_length_a') based on dictionary lookups
        """
        # Use dictionary lookup for accurate conversion
        cif1_equivalent = self.dict_manager.get_cif1_equivalent(field_name)
        
        if cif1_equivalent:
            return cif1_equivalent
            
        # If not found in dictionary, return original field name unchanged
        # (This preserves unknown/custom fields)
        return field_name
    
    def _should_use_dot_notation(self, category: str) -> bool:
        """
        Check if a category should use dot notation in CIF2 by examining the dictionary.
        
        Args:
            category: The category name (e.g., 'audit', 'cell', 'atom_site')
            
        Returns:
            True if this category should use dot notation in CIF2
        """
        # Check if we can find any fields in the dictionary that use this category with dots
        test_patterns = [
            f'_{category}.', # Look for fields starting with _category.
        ]
        
        # Try to find a field info that would indicate dot notation is used
        for pattern in test_patterns:
            # This is a simplified check - in a full implementation we'd scan the dictionary
            # For now, we'll use a reasonable set of known CIF2 categories
            known_cif2_categories = {
                'cell', 'atom_site', 'atom_type', 'space_group', 'symmetry',
                'diffrn', 'diffrn_source', 'diffrn_detector', 'diffrn_radiation', 
                'diffrn_reflns', 'diffrn_standards', 'diffrn_orient_matrix', 'diffrn_measurement',
                'refine', 'refln', 'chemical', 'chemical_formula', 'exptl_crystal',
                'exptl_absorpt', 'publ', 'publ_section', 'database', 'citation',
                'computing', 'geom_bond', 'geom_angle', 'geom_torsion', 'geom_hbond',
                # Add the missing categories
                'audit', 'journal', 'citation_author', 'citation_editor',
                'database_code', 'software', 'computing_data_collection',
                'computing_cell_refinement', 'computing_data_reduction',
                'computing_structure_solution', 'computing_structure_refinement',
                'computing_molecular_graphics', 'computing_publication_material'
            }
            
            if category in known_cif2_categories:
                return True
                
        return False

    def get_conversion_preview(self, cif_content: str, target_version: CIFVersion) -> Dict:
        """
        Get a preview of what changes would be made in conversion.
        
        Args:
            cif_content: Original CIF content
            target_version: Target CIF version
            
        Returns:
            Dictionary with preview information
        """
        current_version = self.dict_manager.detect_cif_version(cif_content)
        
        if target_version == CIFVersion.CIF2:
            _, changes = self.convert_to_cif2(cif_content)
        elif target_version == CIFVersion.CIF1:
            _, changes = self.convert_to_cif1(cif_content)
        else:
            return {
                'error': f'Cannot convert to {target_version}',
                'changes': []
            }
        
        # Analyze the types of changes
        field_changes = []
        header_changes = []
        other_changes = []
        
        for change in changes:
            if 'header' in change.lower():
                header_changes.append(change)
            elif '→' in change:  # Field name change
                field_changes.append(change)
            else:
                other_changes.append(change)
        
        return {
            'current_version': current_version,
            'target_version': target_version,
            'total_changes': len(changes),
            'field_changes': field_changes,
            'header_changes': header_changes,
            'other_changes': other_changes,
            'preview_safe': len(changes) < 50  # Arbitrary threshold for "safe" preview
        }
    
    def add_field_mapping(self, old_field: str, new_field: str):
        """
        Add a custom field mapping for conversions.
        
        Args:
            old_field: Old/deprecated field name
            new_field: Modern field name
        """
        self.field_mappings[old_field.lower()] = new_field.lower()
        self.reverse_mappings[new_field.lower()] = old_field.lower()
    
    def validate_conversion_safety(self, cif_content: str, target_version: CIFVersion) -> Dict:
        """
        Validate that a conversion can be performed safely without data loss.
        
        Args:
            cif_content: CIF content to validate
            target_version: Target version for conversion
            
        Returns:
            Dictionary with safety analysis
        """
        current_version = self.dict_manager.detect_cif_version(cif_content)
        warnings = []
        errors = []
        
        # Check for potential data loss scenarios
        if target_version == CIFVersion.CIF1:
            # Converting to CIF1 might lose some CIF2 features
            if current_version == CIFVersion.CIF2:
                # Check for modern-only constructs (lists, tables, etc.)
                if '[' in cif_content or '{' in cif_content:
                    warnings.append("CIF2 list/table constructs detected - may not be compatible with CIF1")
                
                # Check for triple-quoted strings
                if '"""' in cif_content or "'''" in cif_content:
                    warnings.append("CIF2 triple-quoted strings detected - will be converted to text fields")
        
        # Check for unknown field mappings
        field_pattern = re.compile(r'^(\s*)(_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*)', re.MULTILINE)
        unmapped_fields = []
        
        for match in field_pattern.finditer(cif_content):
            field_name = match.group(2).lower()
            
            if target_version == CIFVersion.CIF2:
                if field_name not in self.field_mappings and not '.' in field_name:
                    # This might be an old field without a known mapping
                    unmapped_fields.append(field_name)
            elif target_version == CIFVersion.CIF1:
                if field_name not in self.reverse_mappings and '.' in field_name:
                    # This might be a CIF2 field without a CIF1 equivalent
                    unmapped_fields.append(field_name)
        
        if unmapped_fields:
            warnings.append(f"Fields without known mappings: {', '.join(set(unmapped_fields[:5]))}")
            if len(unmapped_fields) > 5:
                warnings.append(f"... and {len(unmapped_fields) - 5} more")
        
        return {
            'safe': len(errors) == 0,
            'warnings': warnings,
            'errors': errors,
            'current_version': current_version,
            'target_version': target_version
        }
    
    def _remove_duplicate_aliases(self, cif_content: str) -> Tuple[str, List[str]]:
        """
        Remove duplicate field definitions that are aliases of each other.
        Keeps the modern (CIF2) version and removes legacy aliases.
        
        Args:
            cif_content: CIF content with potential duplicates
            
        Returns:
            Tuple of (cleaned_content, list_of_changes)
        """
        lines = cif_content.split('\n')
        seen_fields = {}  # field_canonical -> (line_number, field_name_used)
        lines_to_remove = set()
        changes = []
        
        # First pass: identify all field definitions and their canonical forms
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Match field definitions (both standalone and in loops)
            field_match = re.match(r'^(_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*)\s', line)
            if field_match:
                field_name = field_match.group(1)
                
                # Get canonical form (modern/CIF2 version)
                cif2_equiv = self.dict_manager.get_cif2_equivalent(field_name)
                if not cif2_equiv:
                    cif2_equiv = field_name  # Use as-is if no mapping
                
                # Check if we've seen this canonical field before
                if cif2_equiv in seen_fields:
                    prev_line, prev_field = seen_fields[cif2_equiv]
                    # Determine which one to keep (prefer modern notation)
                    if '.' in field_name and '.' not in prev_field:
                        # Current is modern, previous is legacy - remove previous
                        lines_to_remove.add(prev_line)
                        seen_fields[cif2_equiv] = (i, field_name)
                        changes.append(f"Removed duplicate legacy field {prev_field} (kept modern {field_name})")
                    else:
                        # Previous is modern or both same format - remove current
                        lines_to_remove.add(i)
                        changes.append(f"Removed duplicate field {field_name} (kept {prev_field})")
                else:
                    seen_fields[cif2_equiv] = (i, field_name)
        
        # Second pass: rebuild content without removed lines
        cleaned_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
        
        return '\n'.join(cleaned_lines), changes
    
    def _add_checkcif_legacy_notation(self, cif_content: str) -> Tuple[str, List[str]]:
        """
        Ensure legacy notation is present for fields that checkCIF doesn't recognize in modern format.
        This ensures the legacy field exists alongside any modern version IN THE MAIN SECTION.
        
        Strategy:
        1. Only scan the main section (before the DEPRECATED section if present)
        2. If a compatibility field exists in modern form - add the legacy version
        3. Both versions will coexist in the main section
        
        Args:
            cif_content: CIF content with modern field names
            
        Returns:
            Tuple of (content_with_legacy_fields, list_of_changes)
        """
        if not self.checkcif_compatibility_fields:
            return cif_content, []
        
        lines = cif_content.split('\n')
        changes = []
        insertions = []  # (line_index, field_name, value, indent)
        existing_fields = {}  # field_name -> (line_index, value, indent)
        
        # Find where the deprecated section starts (if it exists)
        deprecated_section_start = None
        for i, line in enumerate(lines):
            if '# DEPRECATED FIELDS' in line:
                deprecated_section_start = i
                break
        
        # First pass: catalog all existing fields IN THE MAIN SECTION ONLY
        scan_end = deprecated_section_start if deprecated_section_start is not None else len(lines)
        for i in range(scan_end):
            line = lines[i]
            field_match = re.match(r'^(\s*)(_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*)\s+(.+)$', line)
            if field_match:
                indent, field_name, value = field_match.groups()
                existing_fields[field_name] = (i, value, indent)
        
        # Second pass: ensure legacy versions exist for all compatibility fields
        # Check each compatibility field to see if it or its modern equivalent exists
        for legacy_field in self.checkcif_compatibility_fields:
            # CRITICAL: Skip deprecated fields to prevent duplicates
            # Deprecated fields will be handled by _handle_deprecated_fields() 
            # and added to the dedicated deprecated section
            if self.dict_manager.is_field_deprecated(legacy_field):
                # Check if this deprecated field has a modern replacement that exists
                modern_replacement = self.dict_manager.get_modern_replacement(legacy_field)
                if modern_replacement and modern_replacement in existing_fields:
                    # The modern replacement exists, so the deprecated field will be
                    # added to the deprecated section. Don't add it to main section.
                    continue
                # If no modern replacement exists, fall through to normal handling
            
            legacy_present = legacy_field in existing_fields
            
            # Find if there's a modern version of this field
            modern_equiv = self.dict_manager.get_cif2_equivalent(legacy_field)
            modern_present = modern_equiv and modern_equiv in existing_fields
            
            if modern_present and not legacy_present:
                # Modern field exists but legacy doesn't - add legacy after modern
                line_idx, value, indent = existing_fields[modern_equiv]
                insertions.append((line_idx + 1, legacy_field, value, indent))
                changes.append(f"Added legacy field {legacy_field} for checkCIF compatibility (alongside {modern_equiv})")
            elif legacy_present and not modern_present:
                # Legacy exists but no modern - this is fine, checkCIF will be happy
                # No action needed
                pass
            elif legacy_present and modern_present:
                # Both exist - this is fine, leave them both
                pass
            # If neither exists, the field isn't in this CIF file - skip
        
        # Insert legacy fields (in reverse order to maintain line indices)
        for insert_idx, field_name, value, indent in reversed(insertions):
            legacy_line = f"{indent}{field_name} {value}"
            lines.insert(insert_idx, legacy_line)
        
        return '\n'.join(lines), changes

    def _handle_deprecated_fields(
        self, 
        cif_content: str, 
        deprecated_fields_found: Dict[str, str]
    ) -> Tuple[str, List[str]]:
        """
        Add deprecated fields to a dedicated "DEPRECATED" section at the end.
        
        Note: Deprecated fields have already been converted to their modern equivalents
        during the initial conversion pass. This method just creates the deprecated section.
        
        Strategy:
        1. Use the pre-identified deprecated fields (found before conversion)
        2. Create a dedicated section at the end with all deprecated fields
        3. Annotate each with its modern replacement if available
        
        Args:
            cif_content: CIF content (already converted to modern format)
            deprecated_fields_found: Dict of deprecated field names and their values
                                    (captured before conversion happened)
            
        Returns:
            Tuple of (content_with_deprecated_section, list_of_changes)
        """
        if not deprecated_fields_found:
            return cif_content, []
        
        lines = cif_content.split('\n')
        changes = []
        
        # Find the last non-empty line (excluding trailing empty lines)
        last_content_idx = len(lines) - 1
        while last_content_idx >= 0 and not lines[last_content_idx].strip():
            last_content_idx -= 1
        
        # Add deprecated section
        deprecated_section = [
            '',
            '',
            '# ============================================================================',
            '# DEPRECATED FIELDS (retained for compatibility with older software)',
            '# ============================================================================',
            '# The following fields are deprecated in the CIF specification.',
            '# Modern equivalents have been used above where available.',
            '# These deprecated forms are retained here for backward compatibility.',
            '# ============================================================================',
            ''
        ]
        
        # Calculate max field name length for alignment (cap at 40 to respect 80-char limit)
        max_field_len = min(40, max(len(f) for f in deprecated_fields_found.keys()))
        
        # Add all deprecated fields with their original values
        for field_name in sorted(deprecated_fields_found.keys()):
            value = deprecated_fields_found[field_name]
            replacement = self.dict_manager.get_modern_replacement(field_name)
            
            # Format: field_name padded to max_field_len, then value
            field_padded = field_name.ljust(max_field_len)
            deprecated_line = f"{field_padded} {value}"
            deprecated_section.append(deprecated_line)
            
            # Add replacement comment on next line
            if replacement and replacement != field_name:
                deprecated_section.append(f"# Replaced by: {replacement}")
            else:
                deprecated_section.append("# No modern replacement")
        
        # Add end marker for deprecated section
        deprecated_section.extend([
            '',
            '# ============================================================================',
            '# END OF DEPRECATED FIELDS SECTION',
            '# ============================================================================',
            ''
        ])
        
        # Insert the deprecated section
        lines = lines[:last_content_idx + 1] + deprecated_section + lines[last_content_idx + 1:]
        
        changes.append(f"Added DEPRECATED section with {len(deprecated_fields_found)} field(s)")
        
        return '\n'.join(lines), changes

