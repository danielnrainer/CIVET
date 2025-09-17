"""
Enhanced CIF Deprecation Handler
===============================

Extends the CIF dictionary parser to properly handle deprecated fields by:
1. Identifying deprecated fields from the dictionary
2. Finding their modern replacements  
3. Providing migration suggestions
4. Tracking deprecation dates where available

This addresses deprecation patterns found in cif_core.dic:
- _definition_replaced.by: Modern replacement field
- _alias.deprecation_date: When the field was deprecated  
- **DEPRECATED** or DEPRECATED in descriptions
- "DEPRECATED. Use [field]" patterns
"""

import re
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class DeprecationInfo:
    """Information about a deprecated CIF field"""
    field_name: str
    is_deprecated: bool = False
    replacement_field: Optional[str] = None
    deprecation_date: Optional[str] = None
    deprecation_reason: Optional[str] = None
    severity: str = "warning"  # "warning", "error", "info"


class CIFDeprecationManager:
    """
    Manager for handling CIF field deprecations based on the official dictionary.
    
    Parses deprecation information from cif_core.dic and provides:
    - Deprecation status checking
    - Modern replacement suggestions
    - Migration recommendations
    """
    
    def __init__(self, cif_core_path: Optional[str] = None):
        if cif_core_path is None:
            # Default to cif_core.dic in project root
            project_root = Path(__file__).parent.parent.parent
            cif_core_path = project_root / "cif_core.dic"
        
        self.cif_core_path = Path(cif_core_path)
        self._deprecation_info: Dict[str, DeprecationInfo] = {}
        self._parsed = False
    
    def parse_deprecations(self) -> Dict[str, DeprecationInfo]:
        """
        Parse deprecation information from the CIF core dictionary.
        
        Returns:
            Dictionary mapping field names to deprecation info
        """
        if self._parsed:
            return self._deprecation_info
            
        print("Parsing CIF deprecation information...")
        
        if not self.cif_core_path.exists():
            raise FileNotFoundError(f"CIF core dictionary not found at: {self.cif_core_path}")
            
        with open(self.cif_core_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        self._parse_save_blocks_for_deprecation(content)
        
        self._parsed = True
        print(f"Found {len(self._deprecation_info)} deprecated/replaced fields")
        
        return self._deprecation_info
    
    def _parse_save_blocks_for_deprecation(self, content: str) -> None:
        """Parse save blocks to extract deprecation information"""
        
        # Find all save blocks: save_name ... save_
        save_pattern = r'save_([^\s]+)\s*\n(.*?)\nsave_\s*(?=\n|$)'
        
        for match in re.finditer(save_pattern, content, re.DOTALL):
            save_name = match.group(1).strip()
            block_content = match.group(2)
            
            # Skip category blocks
            if save_name.isupper() or not self._has_field_definition(block_content):
                continue
                
            self._extract_deprecation_info(block_content)
    
    def _has_field_definition(self, block_content: str) -> bool:
        """Check if a block contains a field definition"""
        return '_definition.id' in block_content
    
    def _extract_deprecation_info(self, block_content: str) -> None:
        """Extract deprecation information from a field block"""
        
        # Get the main field name
        def_id_match = re.search(r"_definition\.id\s+'([^']+)'", block_content)
        if not def_id_match:
            return
            
        main_field = def_id_match.group(1)
        
        # Check for replacement information
        replacement_match = re.search(r"_definition_replaced\.by\s+'([^']+)'", block_content)
        replacement_by_dot = '_definition_replaced.by       .' in block_content
        
        replacement_field = None
        if replacement_match:
            replacement_field = replacement_match.group(1)
        elif replacement_by_dot:
            replacement_field = None  # Deprecated but no direct replacement
        
        # Check for deprecation markers in description
        description_deprecated = self._check_description_deprecation(block_content)
        
        # A field is considered deprecated if:
        # 1. It has _definition_replaced.by (regardless of whether marked DEPRECATED in text)
        # 2. OR it has DEPRECATED in description text
        has_replacement_marker = replacement_match is not None or replacement_by_dot
        is_deprecated = has_replacement_marker or description_deprecated[0]
        
        if is_deprecated:
            # Determine deprecation reason
            if description_deprecated[1]:
                reason = description_deprecated[1]
            elif replacement_field:
                reason = f"Superseded by {replacement_field}"
            elif replacement_by_dot:
                reason = "Deprecated with no direct replacement"
            else:
                reason = "Deprecated field"
            
            # Determine severity
            if has_replacement_marker:
                severity = "warning"  # Has explicit replacement info
            else:
                severity = "info"     # Only marked in description
                
            info = DeprecationInfo(
                field_name=main_field,
                is_deprecated=True,
                replacement_field=replacement_field,
                deprecation_reason=reason,
                severity=severity
            )
            self._deprecation_info[main_field] = info
        
        # Handle aliases with explicit deprecation dates (these are definitely deprecated)
        alias_deprecations = self._extract_alias_deprecations(block_content)
        for alias, dep_date in alias_deprecations.items():
            if alias not in self._deprecation_info:
                info = DeprecationInfo(
                    field_name=alias,
                    is_deprecated=True,
                    replacement_field=main_field,
                    deprecation_date=dep_date,
                    deprecation_reason=f"Superseded by {main_field}",
                    severity="warning"
                )
                self._deprecation_info[alias] = info
        
        # Skip Case 5 (aliases without explicit deprecation) for now
        # We no longer automatically treat CIF1 aliases as deprecated
    
    def _check_description_deprecation(self, block_content: str) -> Tuple[bool, Optional[str]]:
        """Check if the description contains deprecation markers"""
        
        # Extract description text
        desc_match = re.search(r'_description\.text\s*\n;\s*(.*?)\s*;', block_content, re.DOTALL)
        if not desc_match:
            return False, None
            
        description = desc_match.group(1)
        
        # Check for deprecation markers
        if re.search(r'\*\*DEPRECATED\*\*|DEPRECATED\.|^DEPRECATED', description, re.MULTILINE | re.IGNORECASE):
            # Extract replacement field from description
            use_match = re.search(r'Use\s+([_\w.]+)', description)
            if use_match:
                return True, f"Use {use_match.group(1)} instead"
            
            # Extract replacement from "Replaced by" text
            replaced_match = re.search(r"Replaced by\s+'([^']+)'", description)
            if replaced_match:
                return True, f"Replaced by {replaced_match.group(1)}"
            
            return True, "Deprecated field"
        
        return False, None
    
    def _extract_alias_deprecations(self, block_content: str) -> Dict[str, Optional[str]]:
        """Extract aliases with their deprecation dates (only if they have actual dates)"""
        
        deprecations = {}
        
        # Look for loop with deprecation dates
        loop_pattern = r'loop_\s*\n\s*_alias\.definition_id\s*\n\s*_alias\.deprecation_date\s*\n(.*?)(?=\n\s*[_a-zA-Z]|\n\s*save_|\Z)'
        loop_match = re.search(loop_pattern, block_content, re.DOTALL)
        
        if loop_match:
            alias_data = loop_match.group(1).strip()
            for line in alias_data.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split()
                    if len(parts) >= 2:
                        field_name = parts[0].strip("'")
                        dep_date = parts[1] if parts[1] != '.' else None
                        
                        # Only consider it deprecated if it has an actual date
                        # If dep_date is None (was '.'), it's just a regular alias
                        if dep_date is not None:
                            deprecations[field_name] = dep_date
        
        return deprecations
    
    def is_deprecated(self, field_name: str) -> bool:
        """Check if a field is deprecated"""
        if not self._parsed:
            self.parse_deprecations()
        return field_name in self._deprecation_info
    
    def get_deprecation_info(self, field_name: str) -> Optional[DeprecationInfo]:
        """Get deprecation information for a field"""
        if not self._parsed:
            self.parse_deprecations()
        return self._deprecation_info.get(field_name)
    
    def get_replacement(self, deprecated_field: str) -> Optional[str]:
        """Get the modern replacement for a deprecated field"""
        info = self.get_deprecation_info(deprecated_field)
        return info.replacement_field if info else None
    
    def get_all_deprecated_fields(self) -> List[str]:
        """Get all deprecated field names"""
        if not self._parsed:
            self.parse_deprecations()
        return list(self._deprecation_info.keys())
    
    def get_migration_suggestion(self, deprecated_field: str) -> Optional[str]:
        """Get a human-readable migration suggestion"""
        info = self.get_deprecation_info(deprecated_field)
        if not info:
            return None
        
        if info.replacement_field:
            suggestion = f"Replace '{deprecated_field}' with '{info.replacement_field}'"
            if info.deprecation_date:
                suggestion += f" (deprecated since {info.deprecation_date})"
        else:
            suggestion = f"Field '{deprecated_field}' is deprecated"
            if info.deprecation_reason:
                suggestion += f": {info.deprecation_reason}"
        
        return suggestion


if __name__ == "__main__":
    # Test the deprecation manager
    import os
    # Go up two levels from src/utils/ to get to project root
    cif_path = os.path.join(os.path.dirname(__file__), "..", "..", "cif_core.dic")
    manager = CIFDeprecationManager(cif_path)
    manager.parse_deprecations()
    
    # Test some known cases from each category
    test_fields = [
        # Case 1: Both DEPRECATED and _definition_replaced.by
        '_cell_measurement.wavelength',  # → _diffrn_radiation_wavelength.value
        
        # Case 2: _definition_replaced.by but not explicitly marked DEPRECATED
        '_cell_measurement.temperature',  # → _diffrn.ambient_temperature
        
        # Case 3: DEPRECATED with _definition_replaced.by . 
        '_cell_measurement.radiation',  # No direct replacement (.)
        
        # Test some that should NOT be deprecated (Case 5 - aliases)
        '_diffrn_radiation_wavelength',  # Alias for _diffrn_radiation_wavelength.value
        '_cell_length_a',  # Alias for _cell.length_a
    ]
    
    print("\\nDeprecation Analysis:")
    print("=" * 50)
    
    for field in test_fields:
        if manager.is_deprecated(field):
            info = manager.get_deprecation_info(field)
            suggestion = manager.get_migration_suggestion(field)
            print(f"\\n• {field}:")
            print(f"  Status: DEPRECATED")
            print(f"  Replacement: {info.replacement_field or 'None specified'}")
            print(f"  Date: {info.deprecation_date or 'Not specified'}")
            print(f"  Suggestion: {suggestion}")
        else:
            print(f"\\n• {field}: OK (not deprecated)")
    
    print(f"\\nTotal deprecated fields found: {len(manager.get_all_deprecated_fields())}")