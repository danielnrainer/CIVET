"""
CIF Dictionary Manager with Lazy Loading
========================================

Efficient manager for CIF core dictionary that provides:
- Lazy loading of field definitions
- Field alias resolution (CIF1 <-> CIF2)
- CIF format version detection
- Field validation and compliance checking

"""

import os
import re
import json
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class CIFVersion(Enum):
    """CIF format version enumeration"""
    CIF1 = "1.1"
    CIF2 = "2.0"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class FieldInfo:
    """Information about a CIF field from the dictionary"""
    name: str
    category: str
    type: str
    description: str
    aliases: List[str]
    deprecated: bool = False
    cif_version: str = "1.1"  # Minimum version required
    examples: List[str] = None
    
    def __post_init__(self):
        if self.examples is None:
            self.examples = []


class CIFDictionaryManager:
    """
    Lazy-loading CIF dictionary manager for efficient field lookup and alias resolution.
    """
    
    def __init__(self, cif_core_path: Optional[str] = None):
        """
        Initialize the dictionary manager.
        
        Args:
            cif_core_path: Path to cif_core.dic file. If None, uses default location.
        """
        if cif_core_path is None:
            # Default to the cif_core.dic in the project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            cif_core_path = os.path.join(project_root, "cif_core.dic")
        
        self.cif_core_path = cif_core_path
        self._field_cache: Dict[str, FieldInfo] = {}
        self._alias_map: Dict[str, str] = {}  # Maps aliases to canonical names
        self._categories_loaded: Set[str] = set()
        self._all_fields_loaded = False
        
        # Common field patterns for quick detection
        self._cif1_patterns = [
            r'^_[a-zA-Z][a-zA-Z0-9_\-\[\]()]*$',  # Simple underscore naming (with hyphens/brackets)
            r'^_[a-zA-Z][a-zA-Z0-9_\-\[\]()]*_[a-zA-Z0-9_\-\[\]()]+$'  # Category_item format (with hyphens/brackets)
        ]
        
        self._cif2_patterns = [
            r'^_[a-zA-Z][a-zA-Z0-9_\-\[\]()]*\.[a-zA-Z][a-zA-Z0-9_\-\[\]()]*$'  # Category.item format (with hyphens/brackets)
        ]
        
    def detect_cif_version(self, content: str) -> CIFVersion:
        """
        Detect the CIF version from file content.
        
        Args:
            content: CIF file content as string
            
        Returns:
            CIFVersion enum indicating the detected version
        """
        lines = content.strip().split('\n')
        
        # Check for explicit version declaration
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line.startswith('#\\#CIF_2.0'):
                return CIFVersion.CIF2
            elif line.startswith('#\\#CIF_1.1'):
                return CIFVersion.CIF1
        
        # Analyze field patterns
        cif1_fields = 0
        cif2_fields = 0
        
        # Find all field names in the content (including hyphens and special chars)
        field_pattern = re.compile(r'^(\s*)(_[a-zA-Z][a-zA-Z0-9_.\-\[\]()]*)', re.MULTILINE)
        
        for match in field_pattern.finditer(content):
            field_name = match.group(2)
            
            # Check if it matches CIF2 pattern (contains dot)
            if '.' in field_name:
                cif2_fields += 1
            else:
                # Check if it's a known CIF1 field or pattern
                cif1_fields += 1
        
        # Determine version based on field patterns
        if cif2_fields > 0 and cif1_fields > 0:
            return CIFVersion.MIXED
        elif cif2_fields > 0:
            return CIFVersion.CIF2
        elif cif1_fields > 0:
            return CIFVersion.CIF1
        else:
            return CIFVersion.UNKNOWN
    
    def get_field_info(self, field_name: str) -> Optional[FieldInfo]:
        """
        Get information about a CIF field, loading it lazily if needed.
        
        Args:
            field_name: Name of the field to look up
            
        Returns:
            FieldInfo object or None if field not found
        """
        # Normalize field name
        field_name = field_name.lower().strip()
        
        # Check cache first
        if field_name in self._field_cache:
            return self._field_cache[field_name]
        
        # Check if it's an alias
        canonical_name = self._alias_map.get(field_name)
        if canonical_name and canonical_name in self._field_cache:
            return self._field_cache[canonical_name]
        
        # Load the field from dictionary
        field_info = self._load_field_from_dictionary(field_name)
        if field_info:
            self._field_cache[field_name] = field_info
            
            # Cache aliases
            for alias in field_info.aliases:
                self._alias_map[alias.lower()] = field_name
        
        return field_info
    
    def get_canonical_name(self, field_name: str) -> str:
        """
        Get the canonical (modern) name for a field, resolving aliases.
        
        Args:
            field_name: Field name (possibly an alias)
            
        Returns:
            Canonical field name
        """
        field_name = field_name.lower().strip()
        
        # Check if we have it in alias map
        canonical = self._alias_map.get(field_name)
        if canonical:
            return canonical
        
        # Try to load field info
        field_info = self.get_field_info(field_name)
        if field_info:
            return field_info.name
        
        # Return original if not found
        return field_name
    
    def get_aliases(self, field_name: str) -> List[str]:
        """
        Get all known aliases for a field.
        
        Args:
            field_name: Field name to get aliases for
            
        Returns:
            List of alias names
        """
        field_info = self.get_field_info(field_name)
        if field_info:
            return field_info.aliases.copy()
        return []
    
    def is_deprecated(self, field_name: str) -> bool:
        """
        Check if a field is deprecated.
        
        Args:
            field_name: Field name to check
            
        Returns:
            True if field is deprecated
        """
        field_info = self.get_field_info(field_name)
        if field_info:
            return field_info.deprecated
        return False
    
    def get_modern_equivalent(self, old_field_name: str) -> Optional[str]:
        """
        Get the modern CIF2 equivalent of an old CIF1 field name.
        
        Args:
            old_field_name: Old/deprecated field name
            
        Returns:
            Modern field name or None if no equivalent exists
        """
        field_info = self.get_field_info(old_field_name)
        if not field_info:
            return None
        
        # If this field is deprecated, look for non-deprecated aliases
        if field_info.deprecated:
            for alias in field_info.aliases:
                alias_info = self.get_field_info(alias)
                if alias_info and not alias_info.deprecated:
                    return alias_info.name
        
        # Return the field itself if it's not deprecated
        if not field_info.deprecated:
            return field_info.name
        
        return None
    
    def _load_field_from_dictionary(self, field_name: str) -> Optional[FieldInfo]:
        """
        Load a field definition from the CIF core dictionary.
        
        Args:
            field_name: Name of field to load
            
        Returns:
            FieldInfo object or None if not found
        """
        if not os.path.exists(self.cif_core_path):
            return None
        
        try:
            with open(self.cif_core_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for the field definition in the dictionary
            # This is a simplified parser - in practice, you'd want a full CIF parser
            return self._parse_field_definition(content, field_name)
            
        except Exception as e:
            print(f"Error loading field '{field_name}' from dictionary: {e}")
            return None
    
    def _parse_field_definition(self, content: str, field_name: str) -> Optional[FieldInfo]:
        """
        Parse a field definition from CIF dictionary content.
        
        This is a simplified implementation. For production use, consider using
        a proper CIF parsing library.
        
        Args:
            content: CIF dictionary content
            field_name: Field to find
            
        Returns:
            FieldInfo object or None if not found
        """
        # For now, return a basic FieldInfo for known common fields
        # This would need to be expanded with proper CIF dictionary parsing
        
        known_fields = {
            '_diffrn_source': FieldInfo(
                name='_diffrn_source.description',
                category='diffrn_source',
                type='text',
                description='General class of the source of radiation',
                aliases=['_diffrn_source'],
                deprecated=False,
                cif_version='2.0'
            ),
            '_diffrn_source_type': FieldInfo(
                name='_diffrn_source.make',
                category='diffrn_source',
                type='text', 
                description='Make, model or name of the radiation source',
                aliases=['_diffrn_source_type'],
                deprecated=True,
                cif_version='1.1'
            ),
            '_diffrn_radiation_wavelength': FieldInfo(
                name='_diffrn_radiation_wavelength.value',
                category='diffrn_radiation_wavelength',
                type='float',
                description='Wavelength of radiation',
                aliases=['_diffrn_radiation_wavelength'],
                deprecated=True,
                cif_version='1.1'
            ),
            '_diffrn_radiation.probe': FieldInfo(
                name='_diffrn_radiation.probe',
                category='diffrn_radiation',
                type='text',
                description='Nature of the radiation probe',
                aliases=[],
                deprecated=False,
                cif_version='2.0'
            )
        }
        
        return known_fields.get(field_name.lower())
    
    def validate_mixed_cif(self, content: str) -> Dict[str, Any]:
        """
        Validate a potentially mixed CIF file and identify issues.
        
        Args:
            content: CIF file content
            
        Returns:
            Dictionary with validation results and suggested fixes
        """
        version = self.detect_cif_version(content)
        issues = []
        suggestions = []
        
        if version == CIFVersion.MIXED:
            # Find mixed usage patterns (including hyphens and special chars)
            field_pattern = re.compile(r'^(\s*)(_[a-zA-Z][a-zA-Z0-9_.\-\[\]()]*)', re.MULTILINE)
            
            cif1_fields = []
            cif2_fields = []
            
            for match in field_pattern.finditer(content):
                field_name = match.group(2)
                if '.' in field_name:
                    cif2_fields.append(field_name)
                else:
                    cif1_fields.append(field_name)
            
            issues.append(f"Mixed CIF1/CIF2 format detected")
            issues.append(f"Found {len(cif1_fields)} CIF1-style fields and {len(cif2_fields)} CIF2-style fields")
            
            suggestions.append("Convert to consistent CIF2 format")
            suggestions.append("Update deprecated field names to modern equivalents")
        
        return {
            'version': version,
            'issues': issues,
            'suggestions': suggestions,
            'is_valid': version in [CIFVersion.CIF1, CIFVersion.CIF2]
        }


# Convenience functions for common operations

def detect_cif_version(cif_content: str) -> CIFVersion:
    """Convenience function to detect CIF version."""
    manager = CIFDictionaryManager()
    return manager.detect_cif_version(cif_content)


def get_modern_field_name(old_field_name: str) -> Optional[str]:
    """Convenience function to get modern field name."""
    manager = CIFDictionaryManager()
    return manager.get_modern_equivalent(old_field_name)


def validate_cif_format(cif_content: str) -> Dict[str, Any]:
    """Convenience function to validate CIF format."""
    manager = CIFDictionaryManager()
    return manager.validate_mixed_cif(cif_content)