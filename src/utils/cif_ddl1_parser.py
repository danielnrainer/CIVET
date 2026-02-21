"""
CIF DDL1 Dictionary Parser
===========================

Parses CIF dictionary files written in DDL1 format (e.g., cif_pd.dic from IUCr).

DDL1 Format Overview:
- Dictionary metadata in `data_on_this_dictionary` block with `_dictionary_name`,
  `_dictionary_version`, `_dictionary_update`
- Field definitions in `data_<block_name>` blocks (not `save_` frames)
- Key tags:
  - `_name` - field name(s), may be looped for multiple related names
  - `_category` - category name
  - `_type` - data type (char, numb, null)
  - `_definition` - semicolon-delimited description
  - `_enumeration` / `_enumeration_range` - allowed values
  - `_related_item` / `_related_function` - related items (alternate, replace, etc.)
  - `_units` / `_units_detail` - units
  - `_list` - whether field can be looped (yes, no, both)
"""

import re
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field as dataclass_field

from .cif_dictionary_parser import FieldAlias, FieldMetadata


# Mapping from DDL1 _type values to DDLm _type.contents equivalents
DDL1_TYPE_MAP = {
    'char': 'Text',
    'numb': 'Real',
    'null': None,  # null type in DDL1 means category overview, no actual type
}


@dataclass
class DDL1BlockData:
    """Raw parsed data from a DDL1 data_ block"""
    block_name: str
    names: List[str]  # _name field(s) - can be multiple if looped
    category: Optional[str] = None
    type_code: Optional[str] = None  # char, numb, null
    type_conditions: Optional[str] = None  # esd, su, etc.
    definition: Optional[str] = None  # Semicolon-block description
    list_flag: Optional[str] = None  # yes, no, both
    list_reference: Optional[str] = None
    list_link_parent: Optional[str] = None
    list_link_child: Optional[str] = None
    enumeration_values: List[str] = dataclass_field(default_factory=list)
    enumeration_range: Optional[str] = None
    units: Optional[str] = None
    units_detail: Optional[str] = None
    examples: List[str] = dataclass_field(default_factory=list)
    related_items: List[Tuple[str, str]] = dataclass_field(default_factory=list)  # (item, function) pairs
    raw_content: str = ""


class DDL1DictionaryParser:
    """
    Parser for CIF dictionary files in DDL1 format.
    
    DDL1 dictionaries use `data_` blocks instead of `save_` frames.
    Each block defines one or more field names with their metadata.
    
    The parser produces the same output data structures as CIFDictionaryParser
    (FieldAlias, FieldMetadata) to enable seamless integration.
    """
    
    def __init__(self, dictionary_path: Optional[str] = None):
        self.dictionary_path = dictionary_path
        
        # Primary output - mirrors CIFDictionaryParser interface
        self._cif1_to_cif2: Optional[Dict[str, str]] = None
        self._cif2_to_cif1: Optional[Dict[str, List[str]]] = None
        self._deprecated_fields: Set[str] = set()
        self._replaced_fields: Set[str] = set()
        self._field_aliases: Dict[str, List[FieldAlias]] = {}
        
        # Comprehensive tracking - mirrors CIFDictionaryParser
        self._all_known_fields: Set[str] = set()
        self._all_known_fields_lower: Set[str] = set()
        self._field_metadata: Dict[str, FieldMetadata] = {}
        self._alias_to_definition: Dict[str, str] = {}
        
        # DDL1-specific: dictionary metadata
        self._dictionary_name: Optional[str] = None
        self._dictionary_version: Optional[str] = None
        self._dictionary_update: Optional[str] = None
        
        self._parsed = False
    
    def parse_dictionary(self) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        """
        Parse a DDL1 dictionary file and extract field mappings.
        
        Returns:
            Tuple of (cif1_to_cif2_mapping, cif2_to_cif1_mapping)
            Note: For DDL1 dictionaries, these are mostly identity mappings
            since DDL1 fields are typically legacy format only.
        """
        if self._parsed:
            return self._cif1_to_cif2, self._cif2_to_cif1
        
        print(f"Parsing DDL1 dictionary: {self.dictionary_path}")
        
        if not self.dictionary_path:
            raise ValueError("No dictionary path specified")
        
        self._cif1_to_cif2 = {}
        self._cif2_to_cif1 = {}
        self._deprecated_fields = set()
        self._replaced_fields = set()
        self._field_aliases = {}
        
        with open(self.dictionary_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse data blocks
        blocks = self._extract_data_blocks(content)
        
        for block in blocks:
            if block.block_name.lower() == 'on_this_dictionary':
                self._parse_dictionary_metadata(block)
            elif block.category and block.category.lower() == 'category_overview':
                # Category overview blocks don't define actual fields
                continue
            else:
                self._process_field_block(block)
        
        self._parsed = True
        print(f"Parsed {len(self._all_known_fields)} field definitions from DDL1 dictionary")
        if self._cif1_to_cif2:
            print(f"Found {len(self._cif1_to_cif2)} field alias mappings")
        
        return self._cif1_to_cif2, self._cif2_to_cif1
    
    def _extract_data_blocks(self, content: str) -> List[DDL1BlockData]:
        """
        Extract all data_ blocks from DDL1 dictionary content.
        
        DDL1 dictionaries use `data_blockname` to start each block.
        Blocks end when the next `data_` is encountered or at EOF.
        """
        blocks = []
        
        # Split content by data_ markers
        # Pattern: data_ followed by block name, capturing content until next data_ or EOF
        block_pattern = re.compile(r'^data_(\S+)\s*$', re.MULTILINE)
        
        matches = list(block_pattern.finditer(content))
        
        for i, match in enumerate(matches):
            block_name = match.group(1)
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            block_content = content[start:end].strip()
            
            # Parse the block content
            block_data = self._parse_block_content(block_name, block_content)
            if block_data:
                blocks.append(block_data)
        
        return blocks
    
    def _parse_block_content(self, block_name: str, content: str) -> Optional[DDL1BlockData]:
        """Parse the content of a single data_ block into structured data."""
        
        block = DDL1BlockData(block_name=block_name, names=[], raw_content=content)
        
        # Extract _name (may be single value or looped)
        block.names = self._extract_names(content)
        if not block.names and block_name.lower() != 'on_this_dictionary':
            return None  # No field names defined
        
        # Extract category
        block.category = self._extract_single_value(content, '_category')
        
        # Extract type
        block.type_code = self._extract_single_value(content, '_type')
        
        # Extract type_conditions
        block.type_conditions = self._extract_single_value(content, '_type_conditions')
        
        # Extract definition (semicolon-delimited text)
        block.definition = self._extract_semicolon_text(content, '_definition')
        
        # Extract list flag
        block.list_flag = self._extract_single_value(content, '_list')
        
        # Extract list_reference
        block.list_reference = self._extract_single_value(content, '_list_reference')
        
        # Extract list_link_parent and list_link_child
        block.list_link_parent = self._extract_single_value(content, '_list_link_parent')
        block.list_link_child = self._extract_single_value(content, '_list_link_child')
        
        # Extract enumeration values
        block.enumeration_values = self._extract_enumerations(content)
        
        # Extract enumeration range
        block.enumeration_range = self._extract_single_value(content, '_enumeration_range')
        
        # Extract units
        block.units = self._extract_single_value(content, '_units')
        block.units_detail = self._extract_single_value(content, '_units_detail')
        
        # Extract examples
        block.examples = self._extract_examples(content)
        
        # Extract related items and functions
        block.related_items = self._extract_related_items(content)
        
        return block
    
    def _extract_names(self, content: str) -> List[str]:
        """
        Extract field name(s) from DDL1 block.
        
        Can be:
        1. Single: _name  '_field_name'
        2. Looped: loop_ _name  '_field1' '_field2' ...
        """
        names = []
        
        # Check for looped names first
        loop_pattern = r'loop_\s+_name\s+(.*?)(?=\n\s*_[a-zA-Z]|\n\s*loop_|\Z)'
        loop_match = re.search(loop_pattern, content, re.DOTALL)
        
        if loop_match:
            name_data = loop_match.group(1).strip()
            for line in name_data.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Extract quoted names from the line
                quoted = re.findall(r"'([^']+)'", line)
                if quoted:
                    names.extend(quoted)
                else:
                    # Try unquoted
                    parts = line.split()
                    for part in parts:
                        if part.startswith('_'):
                            names.append(part)
        else:
            # Single name
            single_pattern = r"(?:^|\n)\s*_name\s+['\"]?([^'\"\n]+)['\"]?"
            match = re.search(single_pattern, content)
            if match:
                name = match.group(1).strip()
                # Remove quotes if present
                if name.startswith("'") and name.endswith("'"):
                    name = name[1:-1]
                names.append(name)
        
        return names
    
    def _extract_single_value(self, content: str, tag: str) -> Optional[str]:
        """
        Extract a single-line value for a DDL1 tag.
        
        Handles both quoted and unquoted values.
        Skips values that are part of a loop.
        """
        # Make sure we're not inside a loop_ for this tag
        # Look for the tag NOT preceded by loop_ context
        escaped_tag = re.escape(tag)
        
        # Pattern: tag at start of line (possibly with whitespace), followed by value
        pattern = rf"(?:^|\n)\s*{escaped_tag}\s+['\"]?([^'\"\n;]+)['\"]?"
        match = re.search(pattern, content)
        if match:
            value = match.group(1).strip()
            # Skip if this looks like it's actually a different tag name
            if value.startswith('_'):
                return None
            return value if value and value != '?' else None
        return None
    
    def _extract_semicolon_text(self, content: str, tag: str) -> Optional[str]:
        """Extract semicolon-delimited text block following a tag in DDL1 format."""
        escaped_tag = re.escape(tag)
        # In DDL1, the semicolon block comes on the next line after the tag
        pattern = rf"(?:^|\n)\s*{escaped_tag}\s*\n;\s*(.*?)\n;"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            text = match.group(1).strip()
            return text if text else None
        return None
    
    def _extract_enumerations(self, content: str) -> List[str]:
        """Extract enumeration values from DDL1 block."""
        values = []
        
        # Check for looped enumerations
        loop_pattern = r'loop_\s+_enumeration\s+(.*?)(?=\n\s*_[a-zA-Z]|\n\s*loop_|\Z)'
        loop_match = re.search(loop_pattern, content, re.DOTALL)
        
        if loop_match:
            enum_data = loop_match.group(1).strip()
            for line in enum_data.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Also check for _enumeration_detail which may follow in the loop
                if line.startswith('_'):
                    break
                parts = line.split()
                if parts:
                    value = parts[0]
                    if value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    values.append(value)
        
        # Also check for looped enumerations with _enumeration_detail
        if not values:
            loop_pattern2 = r'loop_\s+_enumeration\s+_enumeration_detail\s+(.*?)(?=\n\s*_[a-zA-Z]|\n\s*loop_|\Z)'
            loop_match2 = re.search(loop_pattern2, content, re.DOTALL)
            if loop_match2:
                enum_data = loop_match2.group(1).strip()
                for line in enum_data.split('\n'):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line.startswith('_'):
                        break
                    parts = line.split()
                    if parts:
                        value = parts[0]
                        if value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        values.append(value)
        
        # Single enumeration value
        if not values:
            single_pattern = r'(?:^|\n)\s*_enumeration\s+(\S+)'
            for match in re.finditer(single_pattern, content):
                value = match.group(1).strip()
                if not value.startswith('_'):
                    if value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    values.append(value)
        
        return values
    
    def _extract_examples(self, content: str) -> List[str]:
        """Extract example values from DDL1 block."""
        examples = []
        
        # Check for looped examples
        loop_pattern = r'loop_\s+_example\s+(.*?)(?=\n\s*_[a-zA-Z]|\n\s*loop_|\Z)'
        loop_match = re.search(loop_pattern, content, re.DOTALL)
        
        if loop_match:
            ex_data = loop_match.group(1).strip()
            for line in ex_data.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('_'):
                    break
                examples.append(line)
        
        # Single example
        if not examples:
            single_match = re.search(r'(?:^|\n)\s*_example\s+(.+)', content)
            if single_match:
                examples.append(single_match.group(1).strip())
        
        return examples
    
    def _extract_related_items(self, content: str) -> List[Tuple[str, str]]:
        """
        Extract _related_item / _related_function pairs from DDL1 block.
        
        Can be single or looped:
          _related_item  '_field_name'
          _related_function  alternate
        
        Or looped:
          loop_ _related_item _related_function
            '_field1'  alternate
            '_field2'  replace
        """
        pairs = []
        
        # Check for looped related items
        loop_pattern = r'loop_\s+_related_item\s+_related_function\s+(.*?)(?=\n\s*_[a-zA-Z]|\n\s*loop_|\Z)'
        loop_match = re.search(loop_pattern, content, re.DOTALL)
        
        if loop_match:
            data = loop_match.group(1).strip()
            for line in data.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('_'):
                    break
                parts = line.split()
                if len(parts) >= 2:
                    item = parts[0]
                    func = parts[1]
                    if item.startswith("'") and item.endswith("'"):
                        item = item[1:-1]
                    pairs.append((item, func))
        else:
            # Try single values
            item_match = re.search(r"(?:^|\n)\s*_related_item\s+['\"]?([^'\"\n]+)['\"]?", content)
            func_match = re.search(r"(?:^|\n)\s*_related_function\s+(\S+)", content)
            
            if item_match and func_match:
                item = item_match.group(1).strip()
                if item.startswith("'") and item.endswith("'"):
                    item = item[1:-1]
                func = func_match.group(1).strip()
                pairs.append((item, func))
        
        return pairs
    
    def _parse_dictionary_metadata(self, block: DDL1BlockData) -> None:
        """Extract dictionary-level metadata from the data_on_this_dictionary block."""
        content = block.raw_content
        
        # _dictionary_name
        match = re.search(r"_dictionary_name\s+(\S+)", content)
        if match:
            self._dictionary_name = match.group(1).strip()
        
        # _dictionary_version
        match = re.search(r"_dictionary_version\s+(\S+)", content)
        if match:
            self._dictionary_version = match.group(1).strip()
        
        # _dictionary_update
        match = re.search(r"_dictionary_update\s+(\S+)", content)
        if match:
            self._dictionary_update = match.group(1).strip()
    
    def _process_field_block(self, block: DDL1BlockData) -> None:
        """
        Process a parsed DDL1 block to populate field indexes.
        
        In DDL1, there's no separate CIF2 definition_id - the _name values ARE
        the field names. We treat the first (or only) name as the canonical name,
        and any additional names or _related_item entries as aliases.
        """
        if not block.names:
            return
        
        # For DDL1, all names are underscore-only (legacy format)
        # The canonical name is the first name
        canonical_name = block.names[0].lower()
        
        # Collect aliases: additional names from the same block + related items
        aliases = []
        
        # Additional names in the block (when loop_ _name has multiple entries)
        for name in block.names[1:]:
            aliases.append(FieldAlias(name=name.lower()))
        
        # Process _related_item entries
        is_replaced = False
        replacement_by = None
        for related_item, related_function in block.related_items:
            func_lower = related_function.lower()
            if func_lower == 'alternate':
                # Alternate name = alias
                aliases.append(FieldAlias(name=related_item.lower()))
            elif func_lower == 'replace':
                # In DDL1, _related_function 'replace' means THIS field
                # has been replaced by _related_item (i.e., this field is deprecated)
                is_replaced = True
                replacement_by = related_item.lower()
                self._deprecated_fields.add(canonical_name)
                self._replaced_fields.add(canonical_name)
        
        # Map DDL1 type to DDLm equivalent
        type_contents = DDL1_TYPE_MAP.get(block.type_code, None) if block.type_code else None
        
        # For numeric fields with esd condition, they're typically Real
        if type_contents == 'Real' and block.type_conditions in ('esd', 'su'):
            type_contents = 'Real'  # Same, but noting it has uncertainty
        
        # Create FieldMetadata compatible with CIFDictionaryParser output
        metadata = FieldMetadata(
            definition_id=canonical_name,
            aliases=aliases,
            type_contents=type_contents,
            type_purpose=None,  # DDL1 doesn't have type.purpose
            type_container=None,  # DDL1 doesn't have type.container
            type_source=None,  # DDL1 doesn't have type.source
            description=block.definition,
            category_id=block.category,
            is_replaced=is_replaced,
            replacement_by=replacement_by,
            enumeration_values=block.enumeration_values if block.enumeration_values else None,
            units=block.units,
            ddl_format='DDL1',
            source_dictionary=self._dictionary_name
        )
        
        # Store metadata
        self._field_metadata[canonical_name] = metadata
        self._field_aliases[canonical_name] = aliases
        
        # Index all names from this block
        for name in block.names:
            name_lower = name.lower()
            self._all_known_fields.add(name_lower)
            self._all_known_fields_lower.add(name_lower)
            self._alias_to_definition[name_lower] = canonical_name
        
        # Index related alternate names
        for alias in aliases:
            if alias.name:
                self._all_known_fields.add(alias.name)
                self._all_known_fields_lower.add(alias.name.lower())
                self._alias_to_definition[alias.name.lower()] = canonical_name
        
        # Build CIF1<->CIF2 mappings
        # In DDL1, there are no CIF2 equivalents, so we create identity mappings
        # and aliasing between alternate names
        if len(block.names) > 1:
            # Multiple names: first is canonical, others are aliases
            for name in block.names[1:]:
                alias_lower = name.lower()
                self._cif1_to_cif2[alias_lower] = canonical_name
                if canonical_name not in self._cif2_to_cif1:
                    self._cif2_to_cif1[canonical_name] = []
                if alias_lower not in self._cif2_to_cif1[canonical_name]:
                    self._cif2_to_cif1[canonical_name].append(alias_lower)
        
        # Add related alternate aliases to mappings
        for related_item, related_function in block.related_items:
            if related_function.lower() == 'alternate':
                alias_lower = related_item.lower()
                if alias_lower != canonical_name:
                    self._cif1_to_cif2[alias_lower] = canonical_name
                    if canonical_name not in self._cif2_to_cif1:
                        self._cif2_to_cif1[canonical_name] = []
                    if alias_lower not in self._cif2_to_cif1[canonical_name]:
                        self._cif2_to_cif1[canonical_name].append(alias_lower)
    
    # ---- Public API methods (mirrors CIFDictionaryParser interface) ----
    
    def is_known_field(self, field_name: str) -> bool:
        """Check if a field is known in this dictionary (case-insensitive)."""
        if not self._parsed:
            self.parse_dictionary()
        return field_name.lower() in self._all_known_fields_lower
    
    def get_definition_id(self, field_name: str) -> Optional[str]:
        """Get the canonical definition_id for any field name."""
        if not self._parsed:
            self.parse_dictionary()
        return self._alias_to_definition.get(field_name.lower())
    
    def get_field_metadata(self, field_name: str) -> Optional[FieldMetadata]:
        """Get complete metadata for a field."""
        if not self._parsed:
            self.parse_dictionary()
        definition_id = self.get_definition_id(field_name)
        if definition_id:
            return self._field_metadata.get(definition_id)
        return None
    
    def is_field_deprecated(self, field_name: str) -> bool:
        """Check if a field is deprecated or replaced."""
        if not self._parsed:
            self.parse_dictionary()
        field_lower = field_name.lower()
        deprecated_lower = {f.lower() for f in self._deprecated_fields}
        replaced_lower = {f.lower() for f in self._replaced_fields}
        return field_lower in deprecated_lower or field_lower in replaced_lower
    
    def get_all_aliases(self, field_name: str, include_deprecated: bool = True) -> List[str]:
        """Get all aliases for a field."""
        metadata = self.get_field_metadata(field_name)
        if not metadata:
            return []
        
        if include_deprecated:
            aliases = metadata.get_all_aliases_names()
        else:
            aliases = metadata.get_non_deprecated_aliases()
        
        if metadata.definition_id not in aliases:
            aliases.insert(0, metadata.definition_id)
        
        return aliases
    
    def get_replacement_field(self, field_name: str) -> Optional[str]:
        """Get the replacement field for a deprecated/replaced field."""
        metadata = self.get_field_metadata(field_name)
        if metadata and metadata.is_replaced:
            return metadata.replacement_by
        return None
    
    def get_field_type_contents(self, field_name: str) -> Optional[str]:
        """Get the type contents for a field."""
        metadata = self.get_field_metadata(field_name)
        return metadata.type_contents if metadata else None
