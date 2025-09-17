"""
CIF Dictionary Manager with Lazy Loading
========================================

Efficient manager for CIF core dictionary that provides:
- Lazy loading of field definitions from cif_core.dic
- Field alias resolution (CIF1 <-> CIF2)
- CIF format version detection
- Field validation and compliance checking

Uses the actual cif_core.dic file for accurate field mappings.
"""

import os
import re
import json
import requests
import tempfile
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from urllib.parse import urlparse
from .cif_core_parser import CIFCoreParser


# COMCIFS Dictionary URLs - Hard-coded stable URLs
COMCIFS_DICTIONARIES = {
    'cif_core': {
        # 'url': 'https://github.com/COMCIFS/cif_core/blob/master/cif_core.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/cif_core/refs/heads/master/cif_core.dic',
        'name': 'Core Dictionary (cif_core.dic)',
        'description': 'Standard crystallographic data'
    },
    'cif_pow': {
        # 'url': 'https://github.com/COMCIFS/Powder_Dictionary/blob/master/cif_pow.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/Powder_Dictionary/refs/heads/master/cif_pow.dic',
        'name': 'Powder Dictionary (cif_pow.dic)', 
        'description': 'Powder diffraction data'
    },
    'cif_topo': {
        # 'url': 'https://github.com/COMCIFS/TopoCif/blob/main/cif_topo.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/TopoCif/refs/heads/main/cif_topo.dic',
        'name': 'Topology Dictionary (cif_topo.dic)',
        'description': 'Topology descriptions'
    },
    'cif_mag': {
        # 'url': 'https://github.com/COMCIFS/magnetic_dic/blob/main/cif_mag.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/magnetic_dic/refs/heads/main/cif_mag.dic',
        'name': 'Magnetic Dictionary (cif_mag.dic)',
        'description': 'Magnetic structure data'
    },
    'cif_img': {
        # 'url': 'https://github.com/COMCIFS/imgCIF/blob/master/cif_img.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/imgCIF/refs/heads/master/cif_img.dic',
        'name': 'Image Dictionary (cif_img.dic)',
        'description': 'Image and area detector data'
    },
    'cif_ed': {
        # 'url': 'https://github.com/COMCIFS/cif_ed/blob/main/cif_ed.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/cif_ed/refs/heads/main/cif_ed.dic',
        'name': 'Electron Diffraction Dictionary (cif_ed.dic)',
        'description': 'Electron diffraction data'
    },
    'cif_multiblock': {
        # 'url': 'https://github.com/COMCIFS/MultiBlock_Dictionary/blob/main/multi_block_core.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/MultiBlock_Dictionary/refs/heads/main/multi_block_core.dic',
        'name': 'Multi-Block Dictionary (multi_block_core.dic)',
        'description': 'Multi-container data'
    },
    'cif_ms': {
        # 'url': 'https://github.com/COMCIFS/Modulated_Structures/blob/main/cif_ms.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/Modulated_Structures/refs/heads/main/cif_ms.dic',
        'name': 'Modulated Structures Dictionary (cif_ms.dic)',
        'description': 'Modulated structure data'
    },
    'cif_rho': {
        # 'url': 'https://github.com/COMCIFS/Electron_Density_Dictionary/blob/main/cif_rho.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/Electron_Density_Dictionary/refs/heads/main/cif_rho.dic',
        'name': 'Electron Density Dictionary (cif_rho.dic)',
        'description': 'Electron density data'
    },
    'cif_twin': {
        # 'url': 'https://github.com/COMCIFS/Twinning_Dictionary/blob/main/cif_twin.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/Twinning_Dictionary/refs/heads/main/cif_twin.dic',
        'name': 'Twinning Dictionary (cif_twin.dic)',
        'description': 'Twinning data'
    },
    'cif_rstr': {
        # 'url': 'https://github.com/COMCIFS/Restraints_Dictionary/blob/main/cif_rstr.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/Restraints_Dictionary/refs/heads/main/cif_rstr.dic',
        'name': 'Restraints Dictionary (cif_rstr.dic)',
        'description': 'Restraints data'
    }
}


class DictionarySource:
    """Information about a dictionary source and loading status"""
    FILE = "file"
    URL = "url"
    BUNDLED = "bundled"
    UNKNOWN = "unknown"


@dataclass
class DictionaryInfo:
    """Detailed information about a loaded dictionary"""
    name: str                    # Display name (e.g., filename or dictionary title)
    path: str                   # Full path or URL
    source_type: str            # FILE, URL, BUNDLED, or UNKNOWN
    size_bytes: int = 0         # File size in bytes
    field_count: int = 0        # Number of fields provided
    loaded_time: Optional[str] = None  # When loaded (ISO format)
    version: Optional[str] = None      # Dictionary version if available
    description: Optional[str] = None  # Dictionary description
    
    def __post_init__(self):
        if self.loaded_time is None:
            self.loaded_time = datetime.now().isoformat()


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
        self.parser = CIFCoreParser(cif_core_path)
        self._loaded = False
        self._cif1_to_cif2: Optional[Dict[str, str]] = None
        self._cif2_to_cif1: Optional[Dict[str, List[str]]] = None
        
        # Multi-dictionary support with enhanced tracking
        self._additional_parsers: List[CIFCoreParser] = []
        self._dictionary_infos: List[DictionaryInfo] = []
        
        # Initialize primary dictionary info
        primary_path = getattr(self.parser, 'cif_core_path', 'dictionaries/cif_core.dic')
        source_type = DictionarySource.BUNDLED if 'dictionaries/cif_core.dic' in str(primary_path) else DictionarySource.FILE
        
        primary_info = DictionaryInfo(
            name=os.path.basename(primary_path),
            path=str(primary_path),
            source_type=source_type,
            description="CIF Core Dictionary - Primary dictionary for standard crystallographic data"
        )
        
        if source_type == DictionarySource.FILE and os.path.exists(primary_path):
            primary_info.size_bytes = os.path.getsize(primary_path)
        
        self._dictionary_infos.append(primary_info)
        
        # Auto-load essential dictionaries by default
        self._load_default_dictionaries()
        
        # Common field patterns for quick detection (fallback only)
        self._cif1_patterns = [
            r'^_[a-zA-Z][a-zA-Z0-9_\-\[\]()]*$',
            r'^_[a-zA-Z][a-zA-Z0-9_\-\[\]()]*_[a-zA-Z0-9_\-\[\]()]+$'
        ]
        
        self._cif2_patterns = [
            r'^_[a-zA-Z][a-zA-Z0-9_\-\[\]()]*\.[a-zA-Z][a-zA-Z0-9_\-\[\]()]*$'
        ]
        
    def _load_default_dictionaries(self):
        """Load essential dictionaries by default"""
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        dictionaries_dir = project_root / "dictionaries"
        
        # Load restraints dictionary by default
        restraints_dict = dictionaries_dir / "cif_rstr.dic"
        if restraints_dict.exists():
            try:
                self.add_dictionary(str(restraints_dict))
            except Exception as e:
                print(f"Warning: Could not load restraints dictionary: {e}")
        
        # Load SHELXL restraints dictionary by default  
        shelxl_dict = dictionaries_dir / "cif_shelxl.dic"
        if shelxl_dict.exists():
            try:
                self.add_dictionary(str(shelxl_dict))
            except Exception as e:
                print(f"Warning: Could not load SHELXL dictionary: {e}")
        
    def _ensure_loaded(self):
        """Ensure all dictionaries are loaded and merged (lazy loading)"""
        if not self._loaded:
            # Start with the primary dictionary
            self._cif1_to_cif2, self._cif2_to_cif1 = self.parser.parse_dictionary()
            
            # Update primary dictionary field count
            if self._dictionary_infos:
                self._dictionary_infos[0].field_count = len(self._cif1_to_cif2)
            
            # Merge additional dictionaries
            for i, additional_parser in enumerate(self._additional_parsers):
                add_cif1_to_cif2, add_cif2_to_cif1 = additional_parser.parse_dictionary()
                
                # Update field count for this dictionary
                if i + 1 < len(self._dictionary_infos):
                    self._dictionary_infos[i + 1].field_count = len(add_cif1_to_cif2)
                
                # Merge CIF1 -> CIF2 mappings
                for cif1_field, cif2_field in add_cif1_to_cif2.items():
                    if cif1_field not in self._cif1_to_cif2:
                        self._cif1_to_cif2[cif1_field] = cif2_field
                    # Note: In case of conflicts, primary dictionary takes precedence
                
                # Merge CIF2 -> CIF1 mappings
                for cif2_field, cif1_fields in add_cif2_to_cif1.items():
                    if cif2_field not in self._cif2_to_cif1:
                        self._cif2_to_cif1[cif2_field] = cif1_fields[:]
                    else:
                        # Merge alias lists, avoiding duplicates
                        existing_aliases = set(self._cif2_to_cif1[cif2_field])
                        for alias in cif1_fields:
                            if alias not in existing_aliases:
                                self._cif2_to_cif1[cif2_field].append(alias)
                                existing_aliases.add(alias)
            
            # Manual fixes for missing mappings
            self._add_missing_field_mappings()
            
            self._loaded = True
        
    def _add_missing_field_mappings(self):
        """Add manually identified missing field mappings not covered by the dictionary"""
        # Fix: _diffrn_radiation.wavelength (CIF2-style) should map to _diffrn_radiation_wavelength (CIF1-style)
        # This is a CIF2->CIF1 conversion issue
        if '_diffrn_radiation.wavelength' not in self._cif2_to_cif1:
            self._cif2_to_cif1['_diffrn_radiation.wavelength'] = ['_diffrn_radiation_wavelength']
            
        # Also ensure the reverse mapping exists for CIF1->CIF2 conversion
        if '_diffrn_radiation_wavelength' not in self._cif1_to_cif2:
            self._cif1_to_cif2['_diffrn_radiation_wavelength'] = '_diffrn_radiation_wavelength.value'
        

        
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
    
    def get_cif2_equivalent(self, field_name: str) -> Optional[str]:
        """
        Get the CIF2 equivalent of a CIF1 field name.
        
        Args:
            field_name: CIF1 field name
            
        Returns:
            CIF2 field name or None if not found
        """
        self._ensure_loaded()
        return self._cif1_to_cif2.get(field_name.lower())
    
    def get_cif1_equivalent(self, field_name: str) -> Optional[str]:
        """
        Get the CIF1 equivalent of a CIF2 field name.
        
        Args:
            field_name: CIF2 field name
            
        Returns:
            Primary CIF1 field name (without dots) or None if not found
        """
        self._ensure_loaded()
        aliases = self._cif2_to_cif1.get(field_name.lower(), [])
        
        # Find the first alias without dots (CIF1 format)
        for alias in aliases:
            if '.' not in alias:
                return alias
                
        # If no underscore-only alias found, return the first one
        return aliases[0] if aliases else None
    
    def is_known_field(self, field_name: str) -> bool:
        """
        Check if a field name is known in the CIF dictionary.
        
        Args:
            field_name: Field name to check
            
        Returns:
            True if field is in the dictionary
        """
        self._ensure_loaded()
        return (field_name in self._cif1_to_cif2 or 
                field_name in self._cif2_to_cif1)
                
    def get_canonical_name(self, field_name: str) -> str:
        """
        Get the canonical name for a field (for backward compatibility).
        
        Args:
            field_name: Field name to look up
            
        Returns:
            Canonical field name (CIF2 if available, otherwise original)
        """
        self._ensure_loaded()
        
        # If it's a CIF1 field, return the CIF2 equivalent
        cif2_equiv = self._cif1_to_cif2.get(field_name)
        if cif2_equiv:
            return cif2_equiv
            
        # If it's already a CIF2 field, return as is
        if field_name in self._cif2_to_cif1:
            return field_name
            
        # Not found in dictionary, return original
        return field_name
    
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
    
    def is_field_deprecated(self, field_name: str) -> bool:
        """Check if a field is deprecated"""
        self._ensure_loaded()
        return self.parser.is_field_deprecated(field_name)
    
    def get_non_deprecated_aliases(self, cif2_field: str) -> List[str]:
        """Get only non-deprecated aliases for a CIF2 field"""
        self._ensure_loaded()
        return self.parser.get_non_deprecated_aliases(cif2_field)
    
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
    
    def add_dictionary(self, dictionary_path: str) -> bool:
        """
        Add an additional dictionary to enhance field coverage.
        
        Args:
            dictionary_path: Path to additional dictionary file or URL
            
        Returns:
            True if dictionary was loaded successfully
            
        Raises:
            FileNotFoundError: If dictionary file doesn't exist
            ValueError: If dictionary format is invalid
        """
        try:
            # Check if it's a URL
            if dictionary_path.startswith(('http://', 'https://')):
                return self.add_dictionary_from_url(dictionary_path)
            
            # Check if file exists for local files
            if not os.path.exists(dictionary_path):
                raise FileNotFoundError(f"Dictionary file not found: {dictionary_path}")
            
            # Create parser for the additional dictionary
            additional_parser = CIFCoreParser(dictionary_path)
            
            # Test that it can be parsed and contains valid mappings
            cif1_to_cif2, cif2_to_cif1 = additional_parser.parse_dictionary()
            
            if not cif1_to_cif2 and not cif2_to_cif1:
                raise ValueError(f"Dictionary file contains no valid CIF field mappings: {dictionary_path}")
            
            # Add parser to list
            self._additional_parsers.append(additional_parser)
            
            # Create dictionary info
            dict_info = DictionaryInfo(
                name=os.path.basename(dictionary_path),
                path=dictionary_path,
                source_type=DictionarySource.FILE,
                size_bytes=os.path.getsize(dictionary_path),
                field_count=len(cif1_to_cif2),
                description=self._extract_dictionary_description(dictionary_path)
            )
            
            self._dictionary_infos.append(dict_info)
            
            # Clear loaded state to force reload with new dictionary
            self._loaded = False
            
            return True
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Dictionary file not found: {dictionary_path}")
        except Exception as e:
            raise ValueError(f"Failed to load dictionary {dictionary_path}: {str(e)}")
    
    def add_dictionary_from_url(self, url: str, timeout: int = 30) -> bool:
        """
        Download and add a dictionary from a URL.
        
        Args:
            url: URL to download dictionary from
            timeout: Request timeout in seconds
            
        Returns:
            True if dictionary was downloaded and loaded successfully
            
        Raises:
            requests.RequestException: If download fails
            ValueError: If dictionary format is invalid
        """
        try:
            # Download the dictionary
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            
            # Create a temporary file to store the dictionary
            with tempfile.NamedTemporaryFile(mode='w', suffix='.dic', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(response.text)
                temp_path = temp_file.name
            
            try:
                # Create parser for the downloaded dictionary
                additional_parser = CIFCoreParser(temp_path)
                
                # Test that it can be parsed and contains valid mappings
                cif1_to_cif2, cif2_to_cif1 = additional_parser.parse_dictionary()
                
                if not cif1_to_cif2 and not cif2_to_cif1:
                    raise ValueError(f"Downloaded dictionary contains no valid CIF field mappings: {url}")
                
                # Add parser to list
                self._additional_parsers.append(additional_parser)
                
                # Extract name from URL
                dict_name = os.path.basename(urlparse(url).path) or "downloaded_dictionary.dic"
                
                # Create dictionary info
                dict_info = DictionaryInfo(
                    name=dict_name,
                    path=url,  # Store original URL
                    source_type=DictionarySource.URL,
                    size_bytes=len(response.text.encode('utf-8')),
                    field_count=len(cif1_to_cif2),
                    description=self._extract_dictionary_description(temp_path, response.text)
                )
                
                self._dictionary_infos.append(dict_info)
                
                # Clear loaded state to force reload with new dictionary
                self._loaded = False
                
                return True
                
            except Exception as e:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise ValueError(f"Failed to parse downloaded dictionary: {str(e)}")
            
        except requests.RequestException as e:
            raise requests.RequestException(f"Failed to download dictionary from {url}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to load dictionary from URL {url}: {str(e)}")
    
    def remove_dictionary(self, dictionary_identifier: str) -> bool:
        """
        Remove a dictionary from the loaded dictionaries.
        
        Args:
            dictionary_identifier: Path, URL, or name of dictionary to remove
            
        Returns:
            True if dictionary was found and removed, False otherwise
        """
        # Find the dictionary by identifier
        dict_to_remove = None
        parser_to_remove = None
        
        for i, dict_info in enumerate(self._dictionary_infos):
            # Skip the primary dictionary (index 0)
            if i == 0:
                continue
                
            # Match by path, name, or URL
            if (dict_info.path == dictionary_identifier or 
                dict_info.name == dictionary_identifier or
                os.path.basename(dict_info.path) == dictionary_identifier):
                dict_to_remove = (i, dict_info)
                break
        
        if dict_to_remove is None:
            return False
        
        dict_index, dict_info = dict_to_remove
        
        # Remove from dictionary infos (adjust index for parsers list)
        self._dictionary_infos.pop(dict_index)
        
        # Remove corresponding parser (index adjusted for primary dictionary)
        parser_index = dict_index - 1  # Subtract 1 because parsers list doesn't include primary
        if 0 <= parser_index < len(self._additional_parsers):
            self._additional_parsers.pop(parser_index)
        
        # Clear loaded state to force reload without removed dictionary
        self._loaded = False
        
        return True
    
    def _extract_dictionary_description(self, file_path: str, content: str = None) -> str:
        """
        Extract description from dictionary file.
        
        Args:
            file_path: Path to dictionary file
            content: Pre-loaded content (optional)
            
        Returns:
            Dictionary description or default message
        """
        try:
            if content is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            # Look for common description patterns in CIF dictionaries
            lines = content.split('\n')
            for line in lines[:50]:  # Check first 50 lines
                line = line.strip()
                if line.startswith('#') and ('dictionary' in line.lower() or 'CIF' in line):
                    return line.lstrip('#').strip()
                elif '_dictionary.title' in line:
                    # Try to find the title value
                    idx = lines.index(line)
                    if idx + 1 < len(lines):
                        title_line = lines[idx + 1].strip()
                        if title_line and not title_line.startswith('_'):
                            return title_line.strip("'\"")
            
            # Default descriptions based on filename
            filename = os.path.basename(file_path).lower()
            if 'restraint' in filename or 'rstr' in filename:
                return "CIF Restraints Dictionary - Structural restraints and constraints"
            elif 'powder' in filename or 'pd' in filename:
                return "CIF Powder Dictionary - Powder diffraction data"
            elif 'modulated' in filename or 'ms' in filename:
                return "CIF Modulated Structures Dictionary - Modulated and composite structures"
            elif 'electron' in filename:
                return "CIF Electron Dictionary - Electron density and related data"
            else:
                return "Additional CIF Dictionary - Extended field definitions"
                
        except Exception:
            return "CIF Dictionary - Field definitions"
    
    def load_all_comcifs_dictionaries(self, timeout: int = 30) -> Dict[str, bool]:
        """
        Load all available COMCIFS dictionaries from their official repositories.
        
        Args:
            timeout: Request timeout in seconds for each dictionary
            
        Returns:
            Dictionary mapping dictionary names to success status
        """
        results = {}
        
        for dict_id, dict_info in COMCIFS_DICTIONARIES.items():
            try:
                # Skip if already loaded
                already_loaded = any(
                    dict_info_obj.name.lower() == f"{dict_id}.dic" or 
                    dict_info_obj.path == dict_info['url']
                    for dict_info_obj in self._dictionary_infos
                )
                
                if already_loaded:
                    results[dict_id] = True
                    continue
                
                # Attempt to load dictionary
                success = self.add_dictionary_from_url(dict_info['url'], timeout)
                results[dict_id] = success
                
            except Exception as e:
                print(f"Warning: Failed to load COMCIFS dictionary {dict_id}: {e}")
                results[dict_id] = False
        
        return results
    
    def get_available_comcifs_dictionaries(self) -> Dict[str, Dict[str, str]]:
        """
        Get information about available COMCIFS dictionaries.
        
        Returns:
            Dictionary mapping dictionary IDs to their info (name, description, url)
        """
        return COMCIFS_DICTIONARIES.copy()
    
    def get_loaded_dictionaries(self) -> List[str]:
        """
        Get list of all loaded dictionary file paths.
        
        Returns:
            List of dictionary file paths (primary + additional)
        """
        return [info.path for info in self._dictionary_infos]
    
    def get_dictionary_info(self) -> Dict[str, Any]:
        """
        Get information about all loaded dictionaries.
        
        Returns:
            Dictionary with summary information
        """
        self._ensure_loaded()
        
        return {
            'primary_dictionary': self._dictionary_infos[0].path if self._dictionary_infos else None,
            'additional_dictionaries': [info.path for info in self._dictionary_infos[1:]] if len(self._dictionary_infos) > 1 else [],
            'total_dictionaries': len(self._dictionary_infos),
            'total_cif1_mappings': len(self._cif1_to_cif2) if self._cif1_to_cif2 else 0,
            'total_cif2_mappings': len(self._cif2_to_cif1) if self._cif2_to_cif1 else 0,
            'dictionaries': [
                {
                    'name': info.name,
                    'path': info.path,
                    'source_type': info.source_type,
                    'size_bytes': info.size_bytes,
                    'field_count': info.field_count,
                    'loaded_time': info.loaded_time,
                    'description': info.description
                }
                for info in self._dictionary_infos
            ]
        }
    
    def get_detailed_dictionary_info(self) -> List[DictionaryInfo]:
        """
        Get detailed information about all loaded dictionaries.
        
        Returns:
            List of DictionaryInfo objects with full details
        """
        try:
            self._ensure_loaded()
            return self._dictionary_infos[:]
        except Exception as e:
            print(f"Error getting detailed dictionary info: {e}")
            # Return at least basic info about the primary dictionary
            return [self._dictionary_infos[0]] if self._dictionary_infos else []
    
    def detect_field_aliases_in_cif(self, cif_content: str) -> Dict[str, List[str]]:
        """
        Detect fields in CIF content that are aliases of each other (actual duplicates within the same file).
        
        Only flags cases where the SAME CIF file contains multiple aliases of the same field,
        e.g., both _diffrn_source_type and _diffrn_source_make in the same file.
        
        Args:
            cif_content: CIF file content as string
            
        Returns:
            Dictionary mapping canonical field names to lists of aliases found in the CIF
            (only returns entries where multiple aliases are actually present)
        """
        self._ensure_loaded()
        
        # Extract all field names from CIF content
        field_pattern = r'_[a-zA-Z][a-zA-Z0-9_\.\[\]()]*'
        found_fields = set(re.findall(field_pattern, cif_content))
        
        # Group fields by their canonical (CIF2) form
        canonical_to_aliases = {}
        
        for field in found_fields:
            # Skip deprecated fields - they should not participate in conflict detection
            if self.is_field_deprecated(field):
                continue
                
            # Determine canonical form for this field
            canonical = None
            
            # Check if field is in CIF1 format and has a CIF2 equivalent
            if field in self._cif1_to_cif2:
                canonical = self._cif1_to_cif2[field]
            # Check if field is already in CIF2 format
            elif field in self._cif2_to_cif1:
                canonical = field
            
            # Only process fields that have known aliases in our dictionaries
            if canonical:
                if canonical not in canonical_to_aliases:
                    canonical_to_aliases[canonical] = set()
                canonical_to_aliases[canonical].add(field)
        
        # Only return canonical fields that have multiple actual aliases present in the CIF
        actual_conflicts = {}
        for canonical, alias_set in canonical_to_aliases.items():
            if len(alias_set) > 1:
                # This canonical field has multiple different aliases present - this is a real conflict
                actual_conflicts[canonical] = list(alias_set)
        
        return actual_conflicts
    
    def detect_mixed_format_issues(self, cif_content: str) -> Dict[str, int]:
        """
        Detect if a CIF file has mixed format issues (both CIF1 and CIF2 style fields).
        
        This is different from alias conflicts - it detects when a file uses inconsistent
        naming conventions rather than having actual duplicate fields.
        
        Args:
            cif_content: CIF file content as string
            
        Returns:
            Dictionary with format statistics: {'cif1_fields': count, 'cif2_fields': count}
        """
        self._ensure_loaded()
        
        # Extract all field names from CIF content
        field_pattern = r'_[a-zA-Z][a-zA-Z0-9_\.\[\]()]*'
        found_fields = set(re.findall(field_pattern, cif_content))
        
        cif1_count = 0
        cif2_count = 0
        
        for field in found_fields:
            if field in self._cif1_to_cif2:
                cif1_count += 1
            elif field in self._cif2_to_cif1:
                cif2_count += 1
        
        return {
            'cif1_fields': cif1_count,
            'cif2_fields': cif2_count,
            'is_mixed': cif1_count > 0 and cif2_count > 0,
            'total_known_fields': cif1_count + cif2_count
        }
    
    def resolve_field_aliases(self, cif_content: str, prefer_cif2: bool = True) -> Tuple[str, List[str]]:
        """
        Resolve field aliases in CIF content by keeping only one form of each field.
        
        Args:
            cif_content: CIF file content as string
            prefer_cif2: If True, prefer CIF2 format; if False, prefer CIF1 format
            
        Returns:
            Tuple of (cleaned_cif_content, list_of_changes_made)
        """
        aliases = self.detect_field_aliases_in_cif(cif_content)
        if not aliases:
            return cif_content, []
        
        changes = []
        cleaned_content = cif_content
        
        for canonical_field, alias_list in aliases.items():
            if len(alias_list) <= 1:
                continue
                
            # Decide which field to keep
            if prefer_cif2:
                # Try to keep the CIF2 form (canonical field) if it's present in the file
                if canonical_field in alias_list:
                    preferred_field = canonical_field
                    fields_to_remove = [f for f in alias_list if f != canonical_field]
                else:
                    # Canonical field not present, convert the first alias to canonical
                    first_alias = alias_list[0]
                    preferred_field = canonical_field
                    fields_to_remove = alias_list[:]
                    # Replace the first occurrence instead of removing it
                    old_content = cleaned_content
                    cleaned_content = cleaned_content.replace(first_alias, preferred_field, 1)
                    if old_content != cleaned_content:
                        changes.append(f"Converted '{first_alias}' to '{preferred_field}'")
                    # Remove the rest
                    fields_to_remove.remove(first_alias)
            else:
                # Keep the CIF1 form (find it from aliases)
                cif1_candidates = [f for f in alias_list if f in self._cif1_to_cif2]
                if cif1_candidates:
                    preferred_field = cif1_candidates[0]  # Take first CIF1 form found
                    fields_to_remove = [f for f in alias_list if f != preferred_field]
                else:
                    # No CIF1 form found, keep canonical
                    preferred_field = canonical_field
                    fields_to_remove = [f for f in alias_list if f != canonical_field]
            
            # Remove duplicate fields and their data
            for field_to_remove in fields_to_remove:
                if field_to_remove == preferred_field:
                    continue
                    
                # Remove field from loop headers
                old_content = cleaned_content
                cleaned_content = self._remove_field_from_cif(cleaned_content, field_to_remove)
                
                if old_content != cleaned_content:
                    changes.append(f"Removed duplicate field '{field_to_remove}' (alias of '{preferred_field}')")
        
        return cleaned_content, changes
    
    def _remove_field_from_cif(self, cif_content: str, field_to_remove: str) -> str:
        """
        Remove a specific field and its data from CIF content.
        
        Args:
            cif_content: CIF file content
            field_to_remove: Field name to remove
            
        Returns:
            CIF content with field removed
        """
        lines = cif_content.split('\n')
        result_lines = []
        in_loop = False
        loop_fields = []
        field_index = -1
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('loop_'):
                in_loop = True
                loop_fields = []
                field_index = -1
                result_lines.append(lines[i])
                
            elif in_loop and line.startswith('_'):
                loop_fields.append(line)
                if line == field_to_remove:
                    field_index = len(loop_fields) - 1
                    # Don't add this field to result
                else:
                    result_lines.append(lines[i])
                    
            elif in_loop and line and not line.startswith('_') and not line.startswith('#'):
                # Data line in loop
                if field_index >= 0:
                    # Remove the data column corresponding to the removed field
                    data_values = line.split()
                    if len(data_values) > field_index:
                        data_values.pop(field_index)
                        if data_values:  # Only add line if there's still data
                            result_lines.append(' '.join(data_values))
                    # else: line has fewer values than expected, skip it
                else:
                    result_lines.append(lines[i])
                    
            elif in_loop and (not line or line.startswith('#')):
                # End of loop data or comment
                in_loop = False
                loop_fields = []
                field_index = -1
                result_lines.append(lines[i])
                
            else:
                # Non-loop field - check if it's the one to remove
                if line.startswith(field_to_remove + ' ') or line == field_to_remove:
                    # Skip this line and potentially the next if it's a continuation
                    if i + 1 < len(lines) and not lines[i + 1].strip().startswith('_'):
                        i += 1  # Skip the data line too
                else:
                    result_lines.append(lines[i])
                    
            i += 1
        
        return '\n'.join(result_lines)
    
    def get_deprecated_fields(self, field_list: List[str]) -> Dict[str, str]:
        """
        Identify deprecated fields and suggest their modern equivalents.
        
        Args:
            field_list: List of field names to check
            
        Returns:
            Dictionary mapping deprecated fields to their modern equivalents
        """
        self._ensure_loaded()
        
        deprecated_mappings = {}
        
        for field in field_list:
            # Check if this is a CIF1 field with a CIF2 equivalent
            if field in self._cif1_to_cif2:
                modern_field = self._cif1_to_cif2[field]
                if modern_field != field:  # Only if they're different
                    deprecated_mappings[field] = modern_field
        
        return deprecated_mappings
    
    def standardize_cif_fields(self, cif_content: str) -> Tuple[str, List[str]]:
        """
        Standardize CIF content by resolving actual alias conflicts only.
        
        Only makes changes when there are real conflicts (same field appears in multiple forms).
        Does NOT convert well-formed CIF1 or CIF2 files just because they use one format.
        
        Args:
            cif_content: CIF file content as string
            
        Returns:
            Tuple of (standardized_cif_content, list_of_changes_made)
        """
        all_changes = []
        
        # Step 1: Resolve field aliases (only actual conflicts, prefer CIF2 format)
        cleaned_content, alias_changes = self.resolve_field_aliases(cif_content, prefer_cif2=True)
        all_changes.extend(alias_changes)
        
        # Only return the content with conflicts resolved
        # Do NOT mass-convert deprecated fields unless specifically requested
        return cleaned_content, all_changes
    
    def convert_cif_format(self, cif_content: str, target_format: str = 'CIF2') -> Tuple[str, List[str]]:
        """
        Convert CIF content to a specific format (CIF1 or CIF2).
        
        This is different from standardize_cif_fields - this method will convert
        ALL fields to the target format, not just resolve conflicts.
        
        Args:
            cif_content: CIF file content as string
            target_format: 'CIF1' or 'CIF2'
            
        Returns:
            Tuple of (converted_cif_content, list_of_changes_made)
        """
        self._ensure_loaded()
        
        all_changes = []
        converted_content = cif_content
        
        # Extract all field names from CIF content
        field_pattern = r'_[a-zA-Z][a-zA-Z0-9_\.\[\]()]*'
        found_fields = list(set(re.findall(field_pattern, cif_content)))
        
        if target_format.upper() == 'CIF2':
            # Convert all CIF1 fields to CIF2
            for field in found_fields:
                if field in self._cif1_to_cif2:
                    cif2_field = self._cif1_to_cif2[field]
                    old_content = converted_content
                    converted_content = converted_content.replace(field, cif2_field)
                    if old_content != converted_content:
                        all_changes.append(f"Converted '{field}' to '{cif2_field}'")
        
        elif target_format.upper() == 'CIF1':
            # Convert all CIF2 fields to CIF1 (use first CIF1 alternative)
            for field in found_fields:
                if field in self._cif2_to_cif1:
                    cif1_alternatives = self._cif2_to_cif1[field]
                    if cif1_alternatives:
                        cif1_field = cif1_alternatives[0]  # Use first alternative
                        old_content = converted_content
                        converted_content = converted_content.replace(field, cif1_field)
                        if old_content != converted_content:
                            all_changes.append(f"Converted '{field}' to '{cif1_field}'")
        
        return converted_content, all_changes
    
    def apply_field_conflict_resolutions(self, cif_content: str, resolutions: Dict[str, Tuple[str, str]]) -> Tuple[str, List[str]]:
        """
        Apply user-specified resolutions for field conflicts.
        
        Args:
            cif_content: CIF file content as string
            resolutions: Dict mapping canonical_field -> (chosen_field_name, chosen_value)
            
        Returns:
            Tuple of (resolved_cif_content, list_of_changes_made)
        """
        changes = []
        resolved_content = cif_content
        
        # Get current conflicts to know which fields to remove
        current_conflicts = self.detect_field_aliases_in_cif(cif_content)
        
        for canonical_field, (chosen_field, chosen_value) in resolutions.items():
            if canonical_field not in current_conflicts:
                continue
                
            alias_list = current_conflicts[canonical_field]
            
            # Check if any of the aliases are in loops
            field_in_loop = self._is_field_in_loop(resolved_content, alias_list)
            
            if field_in_loop:
                # Handle loop fields differently - rename instead of remove/add
                resolved_content, loop_changes = self._resolve_loop_field_conflict(
                    resolved_content, alias_list, chosen_field
                )
                changes.extend(loop_changes)
            else:
                # Handle simple fields - remove conflicts and add chosen one
                for alias in alias_list:
                    old_content = resolved_content
                    resolved_content = self._remove_field_from_cif(resolved_content, alias)
                    if old_content != resolved_content:
                        changes.append(f"Removed conflicting field '{alias}'")
                
                # Add the chosen field with the chosen value (only for non-loop fields)
                if chosen_value and chosen_value.strip() and chosen_value != "(loop data)":
                    resolved_content = self._add_field_to_cif(resolved_content, chosen_field, chosen_value)
                    changes.append(f"Added resolved field '{chosen_field}' with value '{chosen_value}'")
        
        return resolved_content, changes
    
    def _is_field_in_loop(self, cif_content: str, field_list: List[str]) -> bool:
        """Check if any of the fields in the list are part of a loop"""
        lines = cif_content.split('\n')
        in_loop = False
        
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith('loop_'):
                in_loop = True
            elif in_loop and line_stripped.startswith('_'):
                # Field in loop header
                if any(field in line_stripped for field in field_list):
                    return True
            elif in_loop and line_stripped and not line_stripped.startswith('_') and not line_stripped.startswith('#'):
                # Data line - end of loop header
                in_loop = False
            elif not line_stripped or line_stripped.startswith('#'):
                # Empty line or comment - might end loop
                in_loop = False
        
        return False
    
    def _resolve_loop_field_conflict(self, cif_content: str, alias_list: List[str], chosen_field: str) -> Tuple[str, List[str]]:
        """Resolve conflicts for fields that are in loops by renaming and removing duplicates"""
        changes = []
        lines = cif_content.split('\n')
        result_lines = []
        i = 0
        
        fields_to_rename = [field for field in alias_list if field != chosen_field]
        
        while i < len(lines):
            line = lines[i]
            line_stripped = line.strip()
            
            if line_stripped.startswith('loop_'):
                # Found a loop - process it
                result_lines.append(line)
                i += 1
                
                # Collect loop header lines (all lines starting with _)
                loop_header = []
                while i < len(lines):
                    loop_line = lines[i]
                    loop_line_stripped = loop_line.strip()
                    
                    if loop_line_stripped.startswith('_'):
                        loop_header.append(loop_line)
                        i += 1
                    else:
                        break
                
                # Process loop header - handle conflicts
                processed_header = []
                found_chosen_field = False
                conflicts_in_this_loop = False
                
                for header_line in loop_header:
                    header_stripped = header_line.strip()
                    
                    if header_stripped in alias_list:
                        conflicts_in_this_loop = True
                        
                        if header_stripped == chosen_field:
                            # This is the chosen field - keep it if we haven't found it yet
                            if not found_chosen_field:
                                processed_header.append(header_line)
                                found_chosen_field = True
                            else:
                                # Skip this duplicate of the chosen field
                                changes.append(f"Removed duplicate loop field '{header_stripped}'")
                        else:
                            # This is a field to be renamed to chosen field
                            if not found_chosen_field:
                                # Replace with chosen field, maintaining formatting
                                indent = header_line[:len(header_line) - len(header_line.lstrip())]
                                processed_header.append(f"{indent}{chosen_field}\n")
                                found_chosen_field = True
                                changes.append(f"Renamed loop field '{header_stripped}' to '{chosen_field}'")
                            else:
                                # Skip this duplicate - we already have the chosen field
                                changes.append(f"Removed duplicate loop field '{header_stripped}'")
                        
                    else:
                        # Keep other fields unchanged
                        processed_header.append(header_line)
                
                # Only process this loop if it actually contains conflicts
                if conflicts_in_this_loop:
                    result_lines.extend(processed_header)
                else:
                    # No conflicts in this loop, keep original header
                    result_lines.extend(loop_header)
                
                # Copy the loop data unchanged
                while i < len(lines):
                    data_line = lines[i]
                    data_stripped = data_line.strip()
                    
                    # Stop at next loop, next field, or empty lines that might end the loop
                    if (data_stripped.startswith('loop_') or 
                        data_stripped.startswith('_') or
                        (not data_stripped and i + 1 < len(lines) and 
                         len(lines) > i + 1 and lines[i + 1].strip().startswith('_'))):
                        break
                    
                    result_lines.append(data_line)
                    i += 1
            else:
                result_lines.append(line)
                i += 1
        
        resolved_content = '\n'.join(result_lines)
        return resolved_content, changes
    
    def _add_field_to_cif(self, cif_content: str, field_name: str, field_value: str) -> str:
        """
        Add a field and its value to CIF content.
        
        Args:
            cif_content: CIF file content
            field_name: Field name to add
            field_value: Field value to add
            
        Returns:
            CIF content with field added
        """
        lines = cif_content.split('\n')
        
        # Find a good place to insert the field
        # Look for the data_ block and add after it
        insert_index = len(lines)
        
        for i, line in enumerate(lines):
            if line.strip().startswith('data_'):
                # Look for the end of any existing single fields before loops
                for j in range(i + 1, len(lines)):
                    line_j = lines[j].strip()
                    if line_j.startswith('loop_') or not line_j or line_j.startswith('#'):
                        insert_index = j
                        break
                break
        
        # Format the field value
        if ' ' in field_value or ',' in field_value or field_value.startswith("'"):
            if not (field_value.startswith("'") and field_value.endswith("'")):
                formatted_value = f"'{field_value}'"
            else:
                formatted_value = field_value
        else:
            formatted_value = field_value
        
        # Insert the field
        field_line = f"{field_name} {formatted_value}"
        lines.insert(insert_index, field_line)
        
        return '\n'.join(lines)


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