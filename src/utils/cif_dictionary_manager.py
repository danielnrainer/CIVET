"""
CIF Dictionary Manager with Lazy Loading
========================================

Efficient manager for CIF core dictionary that provides:
- Lazy loading of field definitions from cif_core.dic
- Field alias resolution (legacy <-> modern)
- CIF format version detection
- Field validation and compliance checking

Uses the actual cif_core.dic file for accurate field mappings.
"""

import os
import re
import json
import requests
import sys
import tempfile
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from urllib.parse import urlparse
from .cif_dictionary_parser import CIFDictionaryParser
from .dictionary_suggestion_manager import DictionarySuggestionManager, DictionarySuggestion


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


# COMCIFS Dictionary URLs - Development versions from GitHub
COMCIFS_DICTIONARIES = {
    'cif_core': {
        # 'url': 'https://github.com/COMCIFS/cif_core/blob/master/cif_core.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/cif_core/refs/heads/master/cif_core.dic',
        'name': 'Core Dictionary (cif_core.dic)',
        'description': 'Standard crystallographic data',
        'source': 'COMCIF',
        'status': 'development'
    },
    'cif_pow': {
        # 'url': 'https://github.com/COMCIFS/Powder_Dictionary/blob/master/cif_pow.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/Powder_Dictionary/refs/heads/master/cif_pow.dic',
        'name': 'Powder Dictionary (cif_pow.dic)', 
        'description': 'Powder diffraction data',
        'source': 'COMCIF',
        'status': 'development'
    },
    'cif_topo': {
        # 'url': 'https://github.com/COMCIFS/TopoCif/blob/main/cif_topo.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/TopoCif/refs/heads/main/cif_topo.dic',
        'name': 'Topology Dictionary (cif_topo.dic)',
        'description': 'Topology descriptions',
        'source': 'COMCIF',
        'status': 'development'
    },
    'cif_mag': {
        # 'url': 'https://github.com/COMCIFS/magnetic_dic/blob/main/cif_mag.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/magnetic_dic/refs/heads/main/cif_mag.dic',
        'name': 'Magnetic Dictionary (cif_mag.dic)',
        'description': 'Magnetic structure data',
        'source': 'COMCIF',
        'status': 'development'
    },
    'cif_img': {
        # 'url': 'https://github.com/COMCIFS/imgCIF/blob/master/cif_img.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/imgCIF/refs/heads/master/cif_img.dic',
        'name': 'Image Dictionary (cif_img.dic)',
        'description': 'Image and area detector data',
        'source': 'COMCIF',
        'status': 'development'
    },
    'cif_ed': {
        # 'url': 'https://github.com/COMCIFS/cif_ed/blob/main/cif_ed.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/cif_ed/refs/heads/main/cif_ed.dic',
        'name': 'Electron Diffraction Dictionary (cif_ed.dic)',
        'description': 'Electron diffraction data',
        'source': 'COMCIF',
        'status': 'development'
    },
    'cif_multiblock': {
        # 'url': 'https://github.com/COMCIFS/MultiBlock_Dictionary/blob/main/multi_block_core.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/MultiBlock_Dictionary/refs/heads/main/multi_block_core.dic',
        'name': 'Multi-Block Dictionary (multi_block_core.dic)',
        'description': 'Multi-container data',
        'source': 'COMCIF',
        'status': 'development'
    },
    'cif_ms': {
        # 'url': 'https://github.com/COMCIFS/Modulated_Structures/blob/main/cif_ms.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/Modulated_Structures/refs/heads/main/cif_ms.dic',
        'name': 'Modulated Structures Dictionary (cif_ms.dic)',
        'description': 'Modulated structure data',
        'source': 'COMCIF',
        'status': 'development'
    },
    'cif_rho': {
        # 'url': 'https://github.com/COMCIFS/Electron_Density_Dictionary/blob/main/cif_rho.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/Electron_Density_Dictionary/refs/heads/main/cif_rho.dic',
        'name': 'Electron Density Dictionary (cif_rho.dic)',
        'description': 'Electron density data',
        'source': 'COMCIF',
        'status': 'development'
    },
    'cif_twin': {
        # 'url': 'https://github.com/COMCIFS/Twinning_Dictionary/blob/main/cif_twin.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/Twinning_Dictionary/refs/heads/main/cif_twin.dic',
        'name': 'Twinning Dictionary (cif_twin.dic)',
        'description': 'Twinning data',
        'source': 'COMCIF',
        'status': 'development'
    },
    'cif_rstr': {
        # 'url': 'https://github.com/COMCIFS/Restraints_Dictionary/blob/main/cif_rstr.dic',
        'url': 'https://raw.githubusercontent.com/COMCIFS/Restraints_Dictionary/refs/heads/main/cif_rstr.dic',
        'name': 'Restraints Dictionary (cif_rstr.dic)',
        'description': 'Restraints data',
        'source': 'COMCIF',
        'status': 'development'
    }
}

# IUCr Dictionary URLs - Official release versions
# Reference: https://www.iucr.org/resources/cif/dictionaries
IUCR_DICTIONARIES = {
    'cif_core': {
        'url': 'https://www.iucr.org/__data/iucr/cif/dictionaries/cif_core_3.2.0.dic',
        # !!! be mindufl here, this doesn't resolve permanently and links to a specific version!
        # almost certainly an oversight
        'name': 'Core Dictionary (cif_core.dic) - IUCr Release',
        'description': 'Standard crystallographic data - Official IUCr release version',
        'source': 'IUCr',
        'status': 'release'
    },
    'cif_pow': {
        'url': 'https://www.iucr.org/__data/iucr/cif/dictionaries/cif_pd.dic',
        'name': 'Powder Dictionary (cif_pow.dic) - IUCr Release',
        'description': 'Powder diffraction data - Official IUCr release version',
        'source': 'IUCr',
        'status': 'release'
    },
    'cif_multiblock': {
        'url': 'https://www.iucr.org/__data/iucr/cif/dictionaries/cif_core_multiblock_1.0.0.dic',
        'name': 'Multi-Block Dictionary (multi_block_core.dic) - IUCr Release',
        'description': 'Multi-container data - Official IUCr release version',
        'source': 'IUCr',
        'status': 'release'
    },
    'cif_img': {
        'url': 'https://www.iucr.org/__data/iucr/cif/dictionaries/cif_img.dic',
        'name': 'Image Dictionary (cif_img.dic) - IUCr Release',
        'description': 'Image and area detector data - Official IUCr release version',
        'source': 'IUCr',
        'status': 'release'
    },
    'cif_rstr': {
        'url': 'https://www.iucr.org/__data/iucr/cif/dictionaries/cif_core_restraints.dic',
        'name': 'Restraints Dictionary (cif_rstr.dic) - IUCr Release',
        'description': 'Restraints data - Official IUCr release version',
        'source': 'IUCr',
        'status': 'release'
    },
    'cif_ms': {
        'url': 'https://www.iucr.org/__data/iucr/cif/dictionaries/cif_ms.dic',
        'name': 'Modulated Structures Dictionary (cif_ms.dic) - IUCr Release',
        'description': 'Modulated structure data - Official IUCr release version',
        'source': 'IUCr',
        'status': 'release'
    },
    'cif_mag': {
        'url': 'https://www.iucr.org/__data/iucr/cif/dictionaries/cif_mag.dic',
        'name': 'Magnetic Structures Dictionary (cif_mag.dic) - IUCr Release',
        'description': 'Magnetic structure data - Official IUCr release version',
        'source': 'IUCr',
        'status': 'release'
    },
    'cif_topo': {
        'url': 'https://www.iucr.org/__data/iucr/cif/dictionaries/cif_topology.dic',
        'name': 'Topology Dictionary (cif_topology.dic) - IUCr Release',
        'description': 'Topology data - Official IUCr release version',
        'source': 'IUCr',
        'status': 'release'
    },
    'cif_rho': {
        'url': 'https://www.iucr.org/__data/iucr/cif/dictionaries/cif_rho.dic',
        'name': 'Electron Density Dictionary (cif_rho.dic) - IUCr Release',
        'description': 'Electron density data - Official IUCr release version',
        'source': 'IUCr',
        'status': 'release'
    },
    'cif_twin': {
        'url': 'https://www.iucr.org/__data/iucr/cif/dictionaries/cif_twinning.dic',
        'name': 'Twinning Dictionary (cif_twin.dic) - IUCr Release',
        'description': 'Twinning data - Official IUCr release version',
        'source': 'IUCr',
        'status': 'release'
    },
    'cif_sym': {
        'url': 'https://www.iucr.org/__data/iucr/cif/dictionaries/cif_sym.dic',
        'name': 'Symmetry Dictionary (cif_sym.dic) - IUCr Release',
        'description': 'Symmetry extensions - Official IUCr release version',
        'source': 'IUCr',
        'status': 'release'
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
    source: Optional[str] = None       # Source: 'COMCIF', 'IUCr', 'Local', 'Custom'
    status: Optional[str] = None       # Status: 'release', 'development', 'unknown'
    dict_type: Optional[str] = None    # Dictionary type: 'core', 'powder', 'img', etc.
    is_active: bool = True             # Whether this dictionary is active for its type
    dict_title: Optional[str] = None   # Official dictionary title from _dictionary.title
    dict_date: Optional[str] = None    # Dictionary date from _dictionary.date
    
    def __post_init__(self):
        if self.loaded_time is None:
            self.loaded_time = datetime.now().isoformat()
        if self.dict_type is None:
            # Try to extract type from name (e.g., "cif_core.dic" -> "core")
            self.dict_type = self._extract_dict_type()
    
    def _extract_dict_type(self) -> str:
        """Extract dictionary type from filename"""
        name_lower = self.name.lower()
        # Match patterns like cif_core, cif_pow, cif_img, etc.
        match = re.match(r'cif[_-](\w+)\.dic', name_lower)
        if match:
            return match.group(1)
        # Fallback to using the filename without extension
        return os.path.splitext(self.name)[0].replace('cif_', '').replace('cif-', '')


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
            # Use resource path function to find bundled dictionary
            cif_core_path = get_resource_path('dictionaries/cif_core.dic')
            
        self.parser = CIFDictionaryParser(cif_core_path)
        self._loaded = False
        self._cif1_to_cif2: Optional[Dict[str, str]] = None
        self._cif2_to_cif1: Optional[Dict[str, List[str]]] = None
        
        # Multi-dictionary support with enhanced tracking
        self._additional_parsers: List[CIFDictionaryParser] = []
        self._dictionary_infos: List[DictionaryInfo] = []
        # Map dictionary info index to parser (0 = primary, 1+ = additional)
        # This allows us to track inactive dictionaries that don't have parsers loaded
        self._info_to_parser_map: Dict[int, int] = {0: -1}  # -1 = primary parser
        
        # Dictionary suggestion system
        self._suggestion_manager = DictionarySuggestionManager()
        
        # Initialize primary dictionary info
        primary_path = getattr(self.parser, 'cif_core_path', 'dictionaries/cif_core.dic')
        source_type = DictionarySource.BUNDLED if 'dictionaries/cif_core.dic' in str(primary_path) else DictionarySource.FILE
        
        # Read the primary dictionary file to extract metadata
        version = None
        dict_title = None
        dict_date = None
        if os.path.exists(primary_path):
            try:
                with open(primary_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                version = self._extract_dictionary_version(content)
                dict_title = self._extract_dictionary_title(content)
                dict_date = self._extract_dictionary_date(content)
            except Exception as e:
                print(f"Warning: Could not read primary dictionary metadata: {e}")
        
        # Create a descriptive name for the bundled dictionary
        base_name = os.path.basename(primary_path)
        if source_type == DictionarySource.BUNDLED:
            # Add identifier for bundled version
            base_without_ext = os.path.splitext(base_name)[0]
            display_name = f"{base_without_ext} (Built-in).dic"
        else:
            display_name = base_name
        
        primary_info = DictionaryInfo(
            name=display_name,
            path=str(primary_path),
            source_type=source_type,
            description="CIF Core Dictionary - Primary dictionary for standard crystallographic data",
            version=version,
            dict_title=dict_title,
            dict_date=dict_date
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
        # Use resource path function to find bundled dictionaries
        dictionaries_dir = get_resource_path("dictionaries")
        
        # Load restraints dictionary by default
        restraints_dict = os.path.join(dictionaries_dir, "cif_rstr.dic")
        if os.path.exists(restraints_dict):
            try:
                self.add_dictionary(restraints_dict)
            except Exception as e:
                print(f"Warning: Could not load restraints dictionary: {e}")
        
        # Load SHELXL restraints dictionary by default  
        shelxl_dict = os.path.join(dictionaries_dir, "cif_shelxl.dic")
        if os.path.exists(shelxl_dict):
            try:
                self.add_dictionary(shelxl_dict)
            except Exception as e:
                print(f"Warning: Could not load SHELXL dictionary: {e}")
        
        # Load twinning dictionary by default
        twinning_dict = os.path.join(dictionaries_dir, "cif_twin.dic")
        if os.path.exists(twinning_dict):
            try:
                self.add_dictionary(twinning_dict)
            except Exception as e:
                print(f"Warning: Could not load twinning dictionary: {e}")
        
    def _ensure_loaded(self):
        """Ensure all active dictionaries are loaded and merged (lazy loading)"""
        if not self._loaded:
            # Initialize caches
            self._field_cache = {}
            self._alias_map = {}
            
            # Start with the primary dictionary if it's active
            if self._dictionary_infos and self._dictionary_infos[0].is_active:
                self._cif1_to_cif2, self._cif2_to_cif1 = self.parser.parse_dictionary()
                # Update primary dictionary field count
                self._dictionary_infos[0].field_count = len(self._cif1_to_cif2)
            else:
                # If primary is inactive, start with empty mappings
                self._cif1_to_cif2 = {}
                self._cif2_to_cif1 = {}
            
            # Merge active additional dictionaries only
            for i, additional_parser in enumerate(self._additional_parsers):
                # Check if this dictionary is active (i+1 because 0 is primary)
                dict_info_index = i + 1
                if dict_info_index < len(self._dictionary_infos):
                    dict_info = self._dictionary_infos[dict_info_index]
                    
                    # Skip inactive dictionaries
                    if not dict_info.is_active:
                        continue
                    
                    add_cif1_to_cif2, add_cif2_to_cif1 = additional_parser.parse_dictionary()
                    
                    # Update field count for this dictionary
                    dict_info.field_count = len(add_cif1_to_cif2)
                    
                    # Merge CIF1 -> CIF2 mappings
                    for cif1_field, cif2_field in add_cif1_to_cif2.items():
                        if cif1_field not in self._cif1_to_cif2:
                            self._cif1_to_cif2[cif1_field] = cif2_field
                        # Note: In case of conflicts, earlier dictionaries take precedence
                    
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
        field_pattern = re.compile(r'^(\s*)(_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*)', re.MULTILINE)
        
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
        
        # First try to get the correctly-cased definition_id from the parser
        # This preserves proper case like "IT_number" instead of "it_number"
        definition_id = self.parser._alias_to_definition.get(field_name.lower())
        if definition_id:
            return definition_id
        
        # Fall back to the legacy mapping (may have incorrect case)
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
        
        # Check field cache first (main dictionary)
        field_name_lower = field_name.lower().strip()
        if hasattr(self, '_field_cache') and field_name_lower in self._field_cache:
            return True
            
        # Check alias mappings
        if hasattr(self, '_alias_map') and field_name_lower in self._alias_map:
            return True
            
        # Check CIF format conversion mappings (case-insensitive)
        if (field_name.lower() in self._cif1_to_cif2 or 
            field_name.lower() in self._cif2_to_cif1):
            return True
        
        # Also check exact case match for backwards compatibility
        if (field_name in self._cif1_to_cif2 or 
            field_name in self._cif2_to_cif1):
            return True
        
        # For CIF2 format fields (with dots), also check if the CIF1 equivalent exists
        if '.' in field_name:
            cif1_equivalent = field_name.replace('.', '_')
            if (cif1_equivalent.lower() in self._cif1_to_cif2 or 
                cif1_equivalent.lower() in self._cif2_to_cif1 or
                cif1_equivalent in self._cif1_to_cif2 or 
                cif1_equivalent in self._cif2_to_cif1):
                return True
        
        # For CIF1 format fields (with underscores), check if CIF2 equivalent exists
        elif '_' in field_name[1:]:  # Skip first underscore
            parts = field_name[1:].split('_')
            if len(parts) >= 2:
                cif2_equivalent = f"_{parts[0]}.{'_'.join(parts[1:])}"
                if (cif2_equivalent.lower() in self._cif1_to_cif2 or 
                    cif2_equivalent.lower() in self._cif2_to_cif1 or
                    cif2_equivalent in self._cif1_to_cif2 or 
                    cif2_equivalent in self._cif2_to_cif1):
                    return True
        
        # As a fallback, directly search the dictionary file
        # This handles cases where fields exist but aren't in the parsed mappings
        return self._search_field_in_dictionary_file(field_name)
    
    def _search_field_in_dictionary_file(self, field_name: str) -> bool:
        """
        Search for a field name directly in the CIF core dictionary file.
        This is a fallback when the field isn't in the parsed mappings.
        """
        cif_core_path = getattr(self.parser, 'cif_core_path', None)
        if not cif_core_path or not os.path.exists(cif_core_path):
            return False
        
        try:
            with open(cif_core_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Search for the field definition pattern
            import re
            # Look for _definition.id lines containing our field
            pattern = rf"_definition\.id\s+['\"]?{re.escape(field_name)}['\"]?"
            if re.search(pattern, content, re.IGNORECASE):
                return True
                
            # Also check for save frames with the field name
            # Build pattern outside f-string to avoid backslash issues
            escaped_field = re.escape(field_name.replace('.', r'\.'))
            pattern_str = escaped_field.replace('_', r'[_\.]')
            pattern = rf"save_{pattern_str}"
            if re.search(pattern, content, re.IGNORECASE):
                return True
                
            return False
            
        except Exception as e:
            # If file search fails, return False
            return False
                
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
        
        # Fields that should NOT be considered deprecated despite what the dictionary says
        non_deprecated_whitelist = {
            '_diffrn_source',  # Has valid CIF2 equivalent, not deprecated
        }
        
        if field_name in non_deprecated_whitelist:
            return False
        
        return self.parser.is_field_deprecated(field_name)
    
    def get_modern_replacement(self, deprecated_field: str) -> Optional[str]:
        """
        Get the modern (non-deprecated) replacement for a deprecated field.
        
        Args:
            deprecated_field: Deprecated field name
            
        Returns:
            Modern replacement field name, or None if no replacement exists
        """
        self._ensure_loaded()
        
        # First, check if this field has a direct replacement_by value
        # Note: _alias_to_definition uses lowercase keys
        definition_id = self.parser._alias_to_definition.get(deprecated_field.lower())
        if definition_id:
            metadata = self.parser._field_metadata.get(definition_id)
            if metadata and metadata.replacement_by:
                return metadata.replacement_by
            
            # If no explicit replacement_by, but the field is deprecated,
            # return the canonical (definition_id) if it's not deprecated
            if metadata and not self.is_field_deprecated(metadata.definition_id):
                return metadata.definition_id
        
        # Try getting CIF2 equivalent if this is a CIF1 field
        cif2_equiv = self.get_cif2_equivalent(deprecated_field)
        if cif2_equiv and not self.is_field_deprecated(cif2_equiv):
            return cif2_equiv
        
        return None
    
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
    
    def _normalize_field_variations(self, field_name: str) -> List[str]:
        """
        Generate possible variations of a field name to handle case sensitivity
        and format differences between user input and dictionary parsing.
        
        Args:
            field_name: Original field name
            
        Returns:
            List of possible field name variations to try
        """
        variations = [field_name]  # Always include original
        
        # Handle the specific pattern where CIF parsing might normalize:
        # _symmetry_space_group_name_Hall -> _symmetry.space_group_name_hall
        # _symmetry_Int_Tables_number -> _symmetry.int_tables_number
        if field_name.startswith('_symmetry_'):
            # Convert underscore format to dot format with lowercase
            dot_format = field_name.replace('_symmetry_', '_symmetry.', 1).lower()
            variations.append(dot_format)
            
            # Also try the exact case but with dot
            dot_format_case = field_name.replace('_symmetry_', '_symmetry.', 1)
            variations.append(dot_format_case)
        
        # Handle the reverse: if it starts with _symmetry., try underscore versions
        elif field_name.startswith('_symmetry.'):
            # Convert dot format to underscore format
            underscore_format = field_name.replace('_symmetry.', '_symmetry_', 1)
            variations.append(underscore_format)
            
            # Try different case variations
            variations.append(underscore_format.lower())
            variations.append(underscore_format.upper())
        
        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for var in variations:
            if var not in seen:
                seen.add(var)
                unique_variations.append(var)
        
        return unique_variations

    def get_modern_equivalent(self, old_field_name: str, prefer_format: str = "legacy") -> Optional[str]:
        """
        Get the modern equivalent of a deprecated/replaced field name.
        
        Args:
            old_field_name: Old/deprecated field name
            prefer_format: Preferred format for the result ("legacy" or "modern")
            
        Returns:
            Modern field name or None if no equivalent exists
        """
        self._ensure_loaded()
        
        # Generate field name variations to handle case sensitivity and format differences
        field_variations = self._normalize_field_variations(old_field_name)
        
        # Try each variation to find a working mapping
        for field_variant in field_variations:
            if prefer_format == "legacy":
                # Try to get CIF2 equivalent first, then find its CIF1 alias
                cif2_equiv = self.get_cif2_equivalent(field_variant)
                if cif2_equiv:
                    # Find the CIF1 alias for this CIF2 field
                    cif1_alias = self.get_cif1_equivalent(cif2_equiv)
                    if cif1_alias and cif1_alias != old_field_name:
                        # Make sure the CIF1 alias is not deprecated
                        if not self.is_field_deprecated(cif1_alias):
                            return cif1_alias
                    # If no CIF1 alias, return the CIF2 field if it's not deprecated
                    if not self.is_field_deprecated(cif2_equiv):
                        return cif2_equiv
            else:
                # Prefer CIF2 format
                cif2_equiv = self.get_cif2_equivalent(field_variant)
                if cif2_equiv and not self.is_field_deprecated(cif2_equiv):
                    return cif2_equiv
        
        # Fallback: look for non-deprecated aliases within the same field definition
        field_info = self.get_field_info(old_field_name)
        if field_info and field_info.deprecated:
            for alias in field_info.aliases:
                alias_info = self.get_field_info(alias)
                if alias_info and not alias_info.deprecated:
                    return alias_info.name
        
        # If field is not deprecated, return itself
        if field_info and not field_info.deprecated:
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
        cif_core_path = getattr(self.parser, 'cif_core_path', None)
        if not cif_core_path or not os.path.exists(cif_core_path):
            return None
        
        try:
            with open(cif_core_path, 'r', encoding='utf-8') as f:
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
            field_pattern = re.compile(r'^(\s*)(_[a-zA-Z][a-zA-Z0-9_.\-\[\]()/]*)', re.MULTILINE)
            
            cif1_fields = []
            cif2_fields = []
            
            for match in field_pattern.finditer(content):
                field_name = match.group(2)
                if '.' in field_name:
                    cif2_fields.append(field_name)
                else:
                    cif1_fields.append(field_name)
            
            issues.append(f"Mixed legacy/modern format detected")
            issues.append(f"Found {len(cif1_fields)} CIF1-style fields and {len(cif2_fields)} CIF2-style fields")
            
            suggestions.append("Convert to consistent CIF2 format")
            suggestions.append("Update deprecated field names to modern equivalents")
        
        return {
            'version': version,
            'issues': issues,
            'suggestions': suggestions,
            'is_valid': version in [CIFVersion.CIF1, CIFVersion.CIF2]
        }
    
    @staticmethod
    def _extract_dictionary_version(content: str) -> Optional[str]:
        """
        Extract version information from dictionary content.
        Looks for _dictionary.version field.
        
        Args:
            content: Dictionary file content
            
        Returns:
            Version string or None if not found
        """
        try:
            # Look for _dictionary.version in the content
            version_pattern = r'_dictionary\.version\s+([^\s\n]+)'
            match = re.search(version_pattern, content)
            if match:
                version = match.group(1).strip("'\"")
                return version
            
            # Alternative pattern: look in data_ block
            data_pattern = r'data_\w+.*?_dictionary\.version\s+([^\s\n]+)'
            match = re.search(data_pattern, content, re.DOTALL)
            if match:
                version = match.group(1).strip("'\"")
                return version
                
        except Exception as e:
            print(f"Warning: Could not extract dictionary version: {e}")
        
        return None
    
    @staticmethod
    def _extract_dictionary_title(content: str) -> Optional[str]:
        """
        Extract title information from dictionary content.
        Looks for _dictionary.title field.
        
        Args:
            content: Dictionary file content
            
        Returns:
            Title string or None if not found
        """
        try:
            # Look for _dictionary.title in the content
            # Title can be single or multi-line, possibly with quotes or semicolons
            title_pattern = r'_dictionary\.title\s+[;\n]?\s*([^\n]+(?:\n(?!_)[^\n]+)*)'
            match = re.search(title_pattern, content)
            if match:
                title = match.group(1).strip()
                # Clean up semicolon delimiters and quotes
                title = title.strip(';').strip("'\"").strip()
                # Remove extra whitespace
                title = ' '.join(title.split())
                return title
            
            # Alternative: look for single-line title
            simple_pattern = r'_dictionary\.title\s+(.+?)(?=\n_|\n\n|\Z)'
            match = re.search(simple_pattern, content, re.DOTALL)
            if match:
                title = match.group(1).strip().strip(';').strip("'\"").strip()
                title = ' '.join(title.split())
                return title
                
        except Exception as e:
            print(f"Warning: Could not extract dictionary title: {e}")
        
        return None
    
    @staticmethod
    def _extract_dictionary_date(content: str) -> Optional[str]:
        """
        Extract date information from dictionary content.
        Looks for _dictionary.date field.
        
        Args:
            content: Dictionary file content
            
        Returns:
            Date string or None if not found
        """
        try:
            # Look for _dictionary.date in the content
            date_pattern = r'_dictionary\.date\s+([^\s\n]+)'
            match = re.search(date_pattern, content)
            if match:
                date = match.group(1).strip("'\"")
                return date
            
            # Alternative pattern: look in data_ block
            data_pattern = r'data_\w+.*?_dictionary\.date\s+([^\s\n]+)'
            match = re.search(data_pattern, content, re.DOTALL)
            if match:
                date = match.group(1).strip("'\"")
                return date
                
        except Exception as e:
            print(f"Warning: Could not extract dictionary date: {e}")
        
        return None
    
    @staticmethod
    def _determine_dict_source_and_status(url_or_path: str, content: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Determine the source and status of a dictionary based on URL/path.
        
        Args:
            url_or_path: URL or file path of the dictionary
            content: Optional dictionary content for version extraction
            
        Returns:
            Tuple of (source, status) where:
                source: 'COMCIF', 'IUCr', 'Local', or 'Custom'
                status: 'release', 'development', or 'unknown'
        """
        url_lower = url_or_path.lower()
        
        # Check for IUCr official source
        if 'iucr.org' in url_lower:
            return 'IUCr', 'release'
        
        # Check for COMCIF GitHub (development versions)
        if 'github.com/comcifs' in url_lower or 'raw.githubusercontent.com/comcifs' in url_lower:
            return 'COMCIF', 'development'
        
        # Local file
        if os.path.isfile(url_or_path):
            return 'Local', 'unknown'
        
        # Custom/unknown source
        return 'Custom', 'unknown'
    
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
            additional_parser = CIFDictionaryParser(dictionary_path)
            
            # Test that it can be parsed and contains valid mappings
            cif1_to_cif2, cif2_to_cif1 = additional_parser.parse_dictionary()
            
            if not cif1_to_cif2 and not cif2_to_cif1:
                raise ValueError(f"Dictionary file contains no valid CIF field mappings: {dictionary_path}")
            
            # Add parser to list
            self._additional_parsers.append(additional_parser)
            
            # Read content for version extraction
            with open(dictionary_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract metadata from dictionary
            version = self._extract_dictionary_version(content)
            dict_title = self._extract_dictionary_title(content)
            dict_date = self._extract_dictionary_date(content)
            source, status = self._determine_dict_source_and_status(dictionary_path, content)
            
            # Create dictionary info
            dict_info = DictionaryInfo(
                name=os.path.basename(dictionary_path),
                path=dictionary_path,
                source_type=DictionarySource.FILE,
                size_bytes=os.path.getsize(dictionary_path),
                field_count=len(cif1_to_cif2),
                description=self._extract_dictionary_description(dictionary_path),
                version=version,
                dict_title=dict_title,
                dict_date=dict_date,
                source=source,
                status=status
            )
            
            # Check if there's already an active dictionary of this type
            # If so, mark this new one as inactive by default
            existing_active = any(
                info.dict_type == dict_info.dict_type and info.is_active 
                for info in self._dictionary_infos
            )
            dict_info.is_active = not existing_active
            
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
                additional_parser = CIFDictionaryParser(temp_path)
                
                # Test that it can be parsed and contains valid mappings
                cif1_to_cif2, cif2_to_cif1 = additional_parser.parse_dictionary()
                
                if not cif1_to_cif2 and not cif2_to_cif1:
                    raise ValueError(f"Downloaded dictionary contains no valid CIF field mappings: {url}")
                
                # Add parser to list
                self._additional_parsers.append(additional_parser)
                
                # Extract name from URL
                base_name = os.path.basename(urlparse(url).path) or "downloaded_dictionary.dic"
                
                # Extract metadata from dictionary
                version = self._extract_dictionary_version(response.text)
                dict_title = self._extract_dictionary_title(response.text)
                dict_date = self._extract_dictionary_date(response.text)
                source, status = self._determine_dict_source_and_status(url, response.text)
                
                # Create a unique name that includes source and version info
                # This allows multiple versions of the same dictionary to coexist
                name_parts = [base_name]
                if source and source != 'Custom':
                    # Remove the .dic extension temporarily
                    base_without_ext = os.path.splitext(base_name)[0]
                    # Add source identifier
                    if source == 'IUCr':
                        dict_name = f"{base_name} (IUCr Release)"
                    elif source == 'COMCIF':
                        dict_name = f"{base_name} (COMCIF GitHub Dev)"
                    else:
                        dict_name = f"{base_without_ext} ({source}).dic"
                else:
                    dict_name = base_name
                
                # Create dictionary info
                dict_info = DictionaryInfo(
                    name=dict_name,
                    path=url,  # Store original URL
                    source_type=DictionarySource.URL,
                    size_bytes=len(response.text.encode('utf-8')),
                    field_count=len(cif1_to_cif2),
                    description=self._extract_dictionary_description(temp_path, response.text),
                    version=version,
                    dict_title=dict_title,
                    dict_date=dict_date,
                    source=source,
                    status=status
                )
                
                # Check if there's already an active dictionary of this type
                # If so, mark this new one as inactive by default
                existing_active = any(
                    info.dict_type == dict_info.dict_type and info.is_active 
                    for info in self._dictionary_infos
                )
                dict_info.is_active = not existing_active
                
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
                # Check if this exact URL is already loaded
                already_loaded = any(
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
    
    def load_all_iucr_dictionaries(self, timeout: int = 30) -> Dict[str, bool]:
        """
        Load all available IUCr dictionaries from their official repositories.
        
        Args:
            timeout: Request timeout in seconds for each dictionary
            
        Returns:
            Dictionary mapping dictionary names to success status
        """
        results = {}
        
        for dict_id, dict_info in IUCR_DICTIONARIES.items():
            try:
                # Check if this exact URL is already loaded
                already_loaded = any(
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
                print(f"Warning: Failed to load IUCr dictionary {dict_id}: {e}")
                results[dict_id] = False
        
        return results
    
    def get_available_comcifs_dictionaries(self) -> Dict[str, Dict[str, str]]:
        """
        Get information about available COMCIFS dictionaries (development versions).
        
        Returns:
            Dictionary mapping dictionary IDs to their info (name, description, url, source, status)
        """
        return COMCIFS_DICTIONARIES.copy()
    
    def get_available_iucr_dictionaries(self) -> Dict[str, Dict[str, str]]:
        """
        Get information about available IUCr dictionaries (official release versions).
        
        Returns:
            Dictionary mapping dictionary IDs to their info (name, description, url, source, status)
        """
        return IUCR_DICTIONARIES.copy()
    
    def get_all_available_dictionaries(self) -> Dict[str, Dict[str, str]]:
        """
        Get information about all available dictionaries (both COMCIF and IUCr).
        
        Returns:
            Dictionary with 'comcif' and 'iucr' keys, each containing their respective dictionaries
        """
        return {
            'comcif': COMCIFS_DICTIONARIES.copy(),
            'iucr': IUCR_DICTIONARIES.copy()
        }
    
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
    
    def set_dictionary_active(self, dict_name: str, active: bool = True) -> bool:
        """
        Set a dictionary as active or inactive for its type.
        When setting a dictionary active, all other dictionaries of the same type are deactivated.
        When trying to deactivate the only active dictionary of a type, the operation is allowed.
        
        Args:
            dict_name: Name of the dictionary to activate/deactivate
            active: True to activate, False to deactivate
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the dictionary
            dict_index = None
            dict_info = None
            for i, info in enumerate(self._dictionary_infos):
                if info.name == dict_name:
                    dict_index = i
                    dict_info = info
                    break
            
            if dict_info is None:
                print(f"Dictionary not found: {dict_name}")
                return False
            
            # If already in the desired state, nothing to do
            if dict_info.is_active == active:
                return True
            
            # If activating, deactivate all other dictionaries of the same type
            if active:
                dict_type = dict_info.dict_type
                for i, info in enumerate(self._dictionary_infos):
                    if info.dict_type == dict_type and i != dict_index:
                        info.is_active = False
                
                # Set the active state
                dict_info.is_active = True
            else:
                # Deactivating - just set it to inactive
                # Note: This means it's possible to have no active dictionary of a type
                dict_info.is_active = False
            
            # Force reload to rebuild mappings with new active state
            self._loaded = False
            
            return True
            
        except Exception as e:
            print(f"Error setting dictionary active state: {e}")
            return False
    
    def get_active_dictionaries(self) -> List[DictionaryInfo]:
        """
        Get list of currently active dictionaries.
        
        Returns:
            List of active DictionaryInfo objects
        """
        return [info for info in self._dictionary_infos if info.is_active]
    
    def get_dictionaries_by_type(self, dict_type: str) -> List[DictionaryInfo]:
        """
        Get all dictionaries of a specific type.
        
        Args:
            dict_type: Dictionary type (e.g., 'core', 'powder', 'img')
            
        Returns:
            List of DictionaryInfo objects of the specified type
        """
        return [info for info in self._dictionary_infos if info.dict_type == dict_type]
    
    def suggest_dictionaries_for_cif(self, cif_content: str) -> List[DictionarySuggestion]:
        """
        Analyze CIF content and suggest relevant COMCIFS dictionaries to load.
        
        Args:
            cif_content: CIF file content as string
            
        Returns:
            List of DictionarySuggestion objects for specialized dictionaries
        """
        return self._suggestion_manager.analyze_cif_content(cif_content)
    
    def get_suggestion_summary(self, cif_content: str) -> str:
        """
        Get a human-readable summary of dictionary suggestions for CIF content.
        
        Args:
            cif_content: CIF file content as string
            
        Returns:
            Formatted string summary of suggested dictionaries
        """
        suggestions = self.suggest_dictionaries_for_cif(cif_content)
        return self._suggestion_manager.get_suggestion_summary(suggestions)
    
    def detect_cif_format(self, cif_content: str) -> str:
        """
        Detect whether CIF content is in legacy or modern format.
        
        Args:
            cif_content: CIF file content as string
            
        Returns:
            'legacy' or 'modern' based on field naming patterns
        """
        return self._suggestion_manager.detect_cif_format(cif_content)
    
    def detect_field_aliases_in_cif(self, cif_content: str) -> Dict[str, List[str]]:
        """
        Detect fields in CIF content that are aliases of each other OR direct duplicates.
        
        Flags cases where:
        1. The SAME CIF file contains multiple aliases of the same field (e.g., _cell_length_a and _cell.length_a)
        2. The same exact field appears multiple times (e.g., _diffrn.ambient_temperature appears twice)
        
        Args:
            cif_content: CIF file content as string
            
        Returns:
            Dictionary mapping canonical field names to lists of aliases/duplicates found in the CIF
            (only returns entries where multiple instances are actually present)
        """
        self._ensure_loaded()
        
        # Extract all field names from CIF content (including duplicates) 
        # Exclude field references within multi-line text blocks
        all_found_fields = self._extract_fields_excluding_text_blocks(cif_content)
        
        # First check for direct duplicates (same field appearing multiple times)
        field_counts = {}
        for field in all_found_fields:
            field_counts[field] = field_counts.get(field, 0) + 1
        
        # Find unique fields for alias detection
        unique_fields = set(all_found_fields)
        
        # Group fields by their canonical (CIF2) form
        canonical_to_aliases = {}
        
        # Handle direct duplicates first
        for field, count in field_counts.items():
            if count > 1:
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
                # For unknown fields, use the field itself as canonical
                else:
                    canonical = field
                
                if canonical not in canonical_to_aliases:
                    canonical_to_aliases[canonical] = set()
                canonical_to_aliases[canonical].add(field)
        
        # Then handle alias conflicts
        for field in unique_fields:
            # Skip deprecated fields - they should not participate in conflict detection
            if self.is_field_deprecated(field):
                continue
                
            # Skip fields already handled as direct duplicates
            if field_counts.get(field, 0) > 1:
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
        
        # Only return canonical fields that have multiple actual aliases/duplicates present in the CIF
        actual_conflicts = {}
        for canonical, alias_set in canonical_to_aliases.items():
            if len(alias_set) > 1:
                # This canonical field has multiple different aliases/duplicates present - this is a real conflict
                actual_conflicts[canonical] = list(alias_set)
            elif len(alias_set) == 1:
                # Check if this single field appears multiple times
                single_field = list(alias_set)[0]
                if field_counts.get(single_field, 0) > 1:
                    actual_conflicts[canonical] = [single_field] * field_counts[single_field]
        
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
        # Exclude field references within multi-line text blocks
        found_fields = set(self._extract_fields_excluding_text_blocks(cif_content))
        
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
        Resolve field aliases and direct duplicates in CIF content by keeping only one form of each field.
        
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
                
            # Check if this is a direct duplicate (same field name multiple times)
            unique_fields = set(alias_list)
            if len(unique_fields) == 1:
                # Direct duplicate - same field appearing multiple times
                duplicate_field = list(unique_fields)[0]
                duplicate_count = len(alias_list)
                
                # Remove all but the first occurrence of the duplicate field
                cleaned_content = self._remove_duplicate_field_occurrences(cleaned_content, duplicate_field, keep_first=True)
                changes.append(f"Removed {duplicate_count-1} duplicate occurrence(s) of '{duplicate_field}'")
                continue
                
            # Handle alias conflicts (different field names that mean the same thing)
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
                    # Replace the first occurrence with text-block awareness instead of removing it
                    old_content = cleaned_content
                    cleaned_content = self._replace_field_text_block_aware(cleaned_content, first_alias, preferred_field, 1)
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
    
    def _extract_fields_excluding_text_blocks(self, cif_content: str) -> List[str]:
        """
        Extract CIF field names from content while excluding field references
        within semicolon-delimited multi-line text blocks.
        
        Args:
            cif_content: CIF file content as string
            
        Returns:
            List of field names that are actual CIF fields, not text references
        """
        lines = cif_content.split('\n')
        field_matches = []
        in_text_block = False
        
        field_pattern = re.compile(r'^\s*(_[a-zA-Z][a-zA-Z0-9_\.\[\]()/]*)')
        
        for line in lines:
            stripped = line.strip()
            
            # Check for start/end of multi-line text block
            if stripped == ';':
                in_text_block = not in_text_block
                continue
            
            # Skip field detection inside text blocks
            if in_text_block:
                continue
            
            # Look for fields in non-text-block lines
            match = field_pattern.match(line)
            if match:
                field_matches.append(match.group(1))
        
        return field_matches
    
    def _replace_field_text_block_aware(self, cif_content: str, old_field: str, new_field: str, max_replacements: int = -1) -> str:
        """
        Replace field names in CIF content while avoiding replacements inside 
        semicolon-delimited multi-line text blocks.
        
        CRITICAL: This method was created to fix a major bug where simple string.replace()
        was inserting field names into text blocks during CIF format conversion.
        Always use this method instead of string.replace() for field name replacements.
        
        Args:
            cif_content: CIF file content as string
            old_field: Field name to replace
            new_field: New field name
            max_replacements: Maximum number of replacements to make (-1 for all)
            
        Returns:
            CIF content with field names replaced (outside text blocks only)
            
        Example problem this fixes:
            _publ_section.references
            ;
            Crystal structure at _diffrn_ambient_temperature
            ;
            # Without this method, the field name in the text would be replaced!
        """
        lines = cif_content.split('\n')
        result_lines = []
        in_text_block = False
        replacements_made = 0
        
        for line in lines:
            stripped = line.strip()
            
            # Check for start/end of multi-line text block
            if stripped == ';':
                in_text_block = not in_text_block
                result_lines.append(line)
                continue
            
            # Skip replacement inside text blocks
            if in_text_block:
                result_lines.append(line)
                continue
            
            # Replace field names outside text blocks
            if max_replacements == -1 or replacements_made < max_replacements:
                if old_field in line:
                    # Check if it's actually a field definition (starts with the field name)
                    if line.strip().startswith(old_field + ' ') or line.strip() == old_field:
                        line = line.replace(old_field, new_field, 1)
                        replacements_made += 1
                    elif line.strip().startswith(old_field):
                        # Handle cases where field name is at start of line
                        line = line.replace(old_field, new_field, 1)
                        replacements_made += 1
            
            result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _convert_fields_within_text_blocks(self, cif_content: str, target_format: str) -> Tuple[str, List[str]]:
        """
        Convert field references within semicolon-delimited text blocks to target format.
        This handles field name conversions within text without treating them as duplicates.
        
        Args:
            cif_content: CIF file content
            target_format: 'CIF1' or 'CIF2'
            
        Returns:
            Tuple of (updated_content, list_of_changes)
        """
        lines = cif_content.split('\n')
        updated_lines = []
        changes = []
        in_text_block = False
        
        # Pattern to find field references in text
        field_reference_pattern = re.compile(r'(_[a-zA-Z][a-zA-Z0-9_\.\[\]()/]*)')
        
        for line in lines:
            stripped = line.strip()
            
            # Track text block boundaries
            if stripped == ';':
                in_text_block = not in_text_block
                updated_lines.append(line)
                continue
            
            # Process field references within text blocks
            if in_text_block:
                original_line = line
                updated_line = line
                
                # Find all field references in this line
                for match in field_reference_pattern.finditer(line):
                    field_ref = match.group(1)
                    converted_field = self._convert_single_field(field_ref, target_format)
                    
                    if converted_field != field_ref:
                        updated_line = updated_line.replace(field_ref, converted_field, 1)
                        changes.append(f"Text block reference: '{field_ref}' -> '{converted_field}'")
                
                updated_lines.append(updated_line)
            else:
                updated_lines.append(line)
        
        return '\n'.join(updated_lines), changes
    
    def _convert_single_field(self, field_name: str, target_format: str) -> str:
        """
        Convert a single field name to target format.
        
        Args:
            field_name: Field name to convert
            target_format: 'CIF1' or 'CIF2'
            
        Returns:
            Converted field name
        """
        self._ensure_loaded()
        
        if target_format.upper() == 'CIF2':
            # Convert CIF1 to CIF2
            if field_name in self._cif1_to_cif2:
                return self._cif1_to_cif2[field_name]
        else:
            # Convert CIF2 to CIF1  
            if field_name in self._cif2_to_cif1:
                return self._cif2_to_cif1[field_name]
        
        return field_name  # No conversion needed
    
    def _remove_duplicate_field_occurrences(self, cif_content: str, field_name: str, keep_first: bool = True) -> str:
        """
        Remove duplicate occurrences of the same field name from CIF content.
        
        Args:
            cif_content: CIF file content
            field_name: Field name to deduplicate
            keep_first: If True, keep first occurrence; if False, keep last
            
        Returns:
            CIF content with duplicates removed
        """
        lines = cif_content.split('\n')
        result_lines = []
        in_loop = False
        loop_fields = []
        field_positions = []
        
        # First pass: identify all occurrences of the field
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            if line_stripped.startswith('loop_'):
                in_loop = True
                loop_fields = []
                result_lines.append(line)
                continue
            
            if in_loop:
                if line_stripped.startswith('_') and not line_stripped.startswith('#'):
                    loop_fields.append(line_stripped)
                    if line_stripped == field_name:
                        field_positions.append((i, 'loop', len(loop_fields) - 1))
                    result_lines.append(line)
                elif line_stripped == '' or line_stripped.startswith('#'):
                    result_lines.append(line)
                elif loop_fields:  # Data line in loop
                    result_lines.append(line)
                else:
                    in_loop = False
                    result_lines.append(line)
            else:
                if line_stripped.startswith(field_name + ' ') or line_stripped == field_name:
                    field_positions.append((i, 'single', -1))
                result_lines.append(line)
        
        # If only one or no occurrences, return unchanged
        if len(field_positions) <= 1:
            return cif_content
        
        # Determine which occurrences to remove
        if keep_first:
            positions_to_remove = field_positions[1:]  # Remove all but first
        else:
            positions_to_remove = field_positions[:-1]  # Remove all but last
        
        # Second pass: remove the unwanted occurrences
        for line_idx, occurrence_type, field_idx in reversed(positions_to_remove):
            if occurrence_type == 'single':
                # Remove single field line (and potentially its value on next line)
                if line_idx < len(result_lines):
                    del result_lines[line_idx]
                    # Check if next line is a value line (not starting with _ or loop_ or #)
                    if (line_idx < len(result_lines) and 
                        not result_lines[line_idx].strip().startswith('_') and
                        not result_lines[line_idx].strip().startswith('loop_') and
                        not result_lines[line_idx].strip().startswith('#') and
                        result_lines[line_idx].strip() != ''):
                        del result_lines[line_idx]
            # Note: Loop field removal is more complex and would require restructuring the entire loop
            # For now, we'll focus on single field occurrences
        
        return '\n'.join(result_lines)
    
    
    def _remove_field_from_cif(self, cif_content: str, field_to_remove: str) -> str:
        """
        Remove a specific field and its data from CIF content.
        
        Important: This method respects text blocks (semicolon-delimited) and will NOT
        remove field-like text within blocks such as _iucr_refine_fcf_details.
        
        Args:
            cif_content: CIF file content
            field_to_remove: Field name to remove
            
        Returns:
            CIF content with field removed
        """
        lines = cif_content.split('\n')
        result_lines = []
        in_loop = False
        in_text_block = False
        loop_fields = []
        field_index = -1
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Track text block boundaries (e.g., _iucr_refine_fcf_details blocks)
            if line == ';':
                in_text_block = not in_text_block
                result_lines.append(lines[i])
                i += 1
                continue
            
            # Don't remove anything inside text blocks
            if in_text_block:
                result_lines.append(lines[i])
                i += 1
                continue
            
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
        
        # 1. Convert actual CIF fields (excluding text blocks)
        found_fields = list(set(self._extract_fields_excluding_text_blocks(cif_content)))
        
        if target_format.upper() == 'CIF2':
            # Convert all CIF1 fields to CIF2
            for field in found_fields:
                if field in self._cif1_to_cif2:
                    cif2_field = self._cif1_to_cif2[field]
                    old_content = converted_content
                    converted_content = self._replace_field_text_block_aware(converted_content, field, cif2_field)
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
                        converted_content = self._replace_field_text_block_aware(converted_content, field, cif1_field)
                        if old_content != converted_content:
                            all_changes.append(f"Converted '{field}' to '{cif1_field}'")
        
        # 2. Convert field references within text blocks  
        text_block_content, text_block_changes = self._convert_fields_within_text_blocks(converted_content, target_format)
        converted_content = text_block_content
        all_changes.extend(text_block_changes)
        
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
                # Handle simple fields - replace in-place instead of remove and add
                resolved_content, field_changes = self._resolve_simple_field_conflict(
                    resolved_content, alias_list, chosen_field, chosen_value
                )
                changes.extend(field_changes)
        
        return resolved_content, changes
    
    def _resolve_simple_field_conflict(self, cif_content: str, alias_list: List[str], 
                                       chosen_field: str, chosen_value: str) -> Tuple[str, List[str]]:
        """
        Resolve conflicts for simple (non-loop) fields by replacing in-place.
        
        Finds the first occurrence of any alias field and replaces it with the chosen field,
        then removes all other occurrences.
        
        Important: This method respects text blocks (semicolon-delimited) and will NOT
        remove or modify field-like text within blocks such as _iucr_refine_fcf_details.
        
        Args:
            cif_content: CIF file content
            alias_list: List of conflicting field names (aliases)
            chosen_field: The field name to use for resolution
            chosen_value: The value to use
            
        Returns:
            Tuple of (resolved_content, list_of_changes)
        """
        changes = []
        lines = cif_content.split('\n')
        result_lines = []
        first_occurrence_replaced = False
        fields_to_remove = set(alias_list)  # Track which fields to remove
        in_text_block = False
        
        # Format the chosen value properly
        if chosen_value and chosen_value.strip() and chosen_value != "(loop data)":
            if ' ' in chosen_value or ',' in chosen_value or '[' in chosen_value or ']' in chosen_value or '{' in chosen_value or '}' in chosen_value:
                if not (chosen_value.startswith("'") and chosen_value.endswith("'")):
                    formatted_value = f"'{chosen_value}'"
                else:
                    formatted_value = chosen_value
            else:
                formatted_value = chosen_value
        else:
            formatted_value = "?"
        
        i = 0
        while i < len(lines):
            line = lines[i]
            line_stripped = line.strip()
            
            # Track text block boundaries (e.g., _iucr_refine_fcf_details blocks)
            if line_stripped == ';':
                in_text_block = not in_text_block
                result_lines.append(line)
                i += 1
                continue
            
            # Don't modify anything inside text blocks
            if in_text_block:
                result_lines.append(line)
                i += 1
                continue
            
            # Check if this line contains any of the conflicting fields
            found_conflict = False
            for alias in fields_to_remove:
                if line_stripped.startswith(alias + ' ') or line_stripped == alias:
                    found_conflict = True
                    
                    if not first_occurrence_replaced:
                        # Replace the first occurrence in-place
                        indent = line[:len(line) - len(line.lstrip())]
                        result_lines.append(f"{indent}{chosen_field} {formatted_value}")
                        first_occurrence_replaced = True
                        changes.append(f"Replaced '{alias}' with '{chosen_field}' (value: '{formatted_value}')")
                        
                        # Skip multiline value if present
                        if i + 1 < len(lines) and not lines[i + 1].strip().startswith('_'):
                            i += 1  # Skip the value line
                    else:
                        # Remove subsequent occurrences
                        changes.append(f"Removed duplicate field '{alias}'")
                        
                        # Skip multiline value if present
                        if i + 1 < len(lines) and not lines[i + 1].strip().startswith('_'):
                            i += 1  # Skip the value line
                    
                    break  # Found and processed the conflict, move to next line
            
            if not found_conflict:
                # Keep lines that are not conflicting fields
                result_lines.append(line)
            
            i += 1
        
        resolved_content = '\n'.join(result_lines)
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
        """
        Resolve conflicts for fields that are in loops by renaming and removing duplicates.
        
        Note: Loops cannot appear inside text blocks in CIF format, so text block
        protection is not needed for this method.
        """
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
        Ensures fields are not inserted into multi-line text blocks.
        
        Args:
            cif_content: CIF file content
            field_name: Field name to add
            field_value: Field value to add
            
        Returns:
            CIF content with field added
        """
        lines = cif_content.split('\n')
        
        # Find a good place to insert the field
        # Look for the data_ block and add after it, avoiding text blocks
        insert_index = len(lines)
        in_text_block = False
        found_data_block = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Track text block boundaries
            if stripped == ';':
                in_text_block = not in_text_block
                continue
                
            # Skip insertion points inside text blocks
            if in_text_block:
                continue
                
            if line.strip().startswith('data_'):
                found_data_block = True
                continue
                
            if found_data_block:
                # Look for the end of any existing single fields before loops/blocks
                if (stripped.startswith('loop_') or 
                    stripped.startswith('_') or
                    not stripped or 
                    stripped.startswith('#')):
                    # This is a safe insertion point (not in text block)
                    if stripped.startswith('loop_') or not stripped or stripped.startswith('#'):
                        insert_index = i
                        break
                    # If it's a field line, continue looking
                    continue
        
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