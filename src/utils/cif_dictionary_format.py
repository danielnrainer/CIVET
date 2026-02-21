"""
CIF Dictionary Format Detection
================================

Provides automatic detection of CIF dictionary formats (DDLm, DDL1, DDL2)
and a unified factory function to create the appropriate parser.

Dictionary Format Indicators:
- DDLm: Uses `save_` frames with `_definition.id`, `_dictionary.title`
- DDL1: Uses `data_` blocks with `_name`, `_category`, `_dictionary_name`
- DDL2: Uses `save_` frames with `_item.name`, `_item.category_id`

Usage:
    from .cif_dictionary_format import detect_dictionary_format, create_dictionary_parser
    
    fmt = detect_dictionary_format('/path/to/dictionary.dic')
    parser = create_dictionary_parser('/path/to/dictionary.dic')
    parser.parse_dictionary()
"""

import re
import os
from enum import Enum
from typing import Optional, Union


class DictionaryFormat(Enum):
    """Enum representing CIF dictionary DDL formats"""
    DDLm = "DDLm"    # Modern format (CIF2-era dictionaries)
    DDL1 = "DDL1"    # Legacy format (CIF1-era dictionaries) 
    DDL2 = "DDL2"    # Intermediate format (mmCIF-era dictionaries)
    UNKNOWN = "unknown"


def detect_dictionary_format(path_or_content: str, is_content: bool = False) -> DictionaryFormat:
    """
    Detect the DDL format of a CIF dictionary.
    
    Examines the content of a dictionary file to determine whether it uses
    DDLm, DDL1, or DDL2 conventions.
    
    Args:
        path_or_content: Either a file path to a dictionary, or dictionary content string
        is_content: If True, path_or_content is treated as content string, not a file path
        
    Returns:
        DictionaryFormat enum value
    """
    if is_content:
        content = path_or_content
    else:
        if not os.path.exists(path_or_content):
            raise FileNotFoundError(f"Dictionary file not found: {path_or_content}")
        with open(path_or_content, 'r', encoding='utf-8') as f:
            content = f.read()
    
    # Use a scoring system - the format with the highest score wins
    scores = {
        DictionaryFormat.DDLm: 0,
        DictionaryFormat.DDL1: 0,
        DictionaryFormat.DDL2: 0,
    }
    
    # --- DDLm indicators ---
    
    # DDLm dictionary header
    if re.search(r'_dictionary\.title\b', content):
        scores[DictionaryFormat.DDLm] += 3
    
    # DDLm field definition marker
    if re.search(r'_definition\.id\b', content):
        scores[DictionaryFormat.DDLm] += 5
    
    # DDLm-specific tags
    if re.search(r'_name\.category_id\b', content):
        scores[DictionaryFormat.DDLm] += 2
    
    if re.search(r'_description\.text\b', content):
        scores[DictionaryFormat.DDLm] += 2
    
    if re.search(r'_type\.contents\b', content):
        scores[DictionaryFormat.DDLm] += 2
    
    if re.search(r'_alias\.definition_id\b', content):
        scores[DictionaryFormat.DDLm] += 2
    
    # DDLm DDL conformance declaration
    if re.search(r'_dictionary\.ddl_conformance\b', content):
        scores[DictionaryFormat.DDLm] += 3
    
    # --- DDL1 indicators ---
    
    # DDL1 dictionary metadata block
    if re.search(r'^data_on_this_dictionary\s*$', content, re.MULTILINE):
        scores[DictionaryFormat.DDL1] += 5
    
    # DDL1-only tags (not DDLm or DDL2)
    if re.search(r'_dictionary_name\b', content):
        scores[DictionaryFormat.DDL1] += 3
    
    if re.search(r'_dictionary_version\b', content):
        scores[DictionaryFormat.DDL1] += 1
    
    if re.search(r'_dictionary_update\b', content):
        scores[DictionaryFormat.DDL1] += 1
    
    # DDL1 uses data_ blocks without save_ frames
    has_save_blocks = bool(re.search(r'^save_\S+', content, re.MULTILINE))
    has_data_blocks = bool(re.search(r'^data_\S+', content, re.MULTILINE))
    
    if has_data_blocks and not has_save_blocks:
        scores[DictionaryFormat.DDL1] += 5
    
    # DDL1-specific: _name as a simple tag (not _name.category_id)
    # Count standalone _name tags (not _name.something)
    ddl1_name_count = len(re.findall(r'(?:^|\n)\s*_name\s+', content))
    if ddl1_name_count > 5:
        scores[DictionaryFormat.DDL1] += 3
    
    # DDL1 type values are char/numb/null
    ddl1_type_count = len(re.findall(r'(?:^|\n)\s*_type\s+(char|numb|null)\s*$', content, re.MULTILINE))
    if ddl1_type_count > 5:
        scores[DictionaryFormat.DDL1] += 3
    
    # DDL1 _related_item / _related_function
    if re.search(r'_related_item\b', content) and re.search(r'_related_function\b', content):
        scores[DictionaryFormat.DDL1] += 2
    
    # --- DDL2 indicators ---
    
    # DDL2 uses save_ frames like DDLm, but with different internal tags
    if has_save_blocks:
        # DDL2 save frames often start with double underscore: save__category.item
        ddl2_saves = re.findall(r'^save__\S+', content, re.MULTILINE)
        if len(ddl2_saves) > 5:
            scores[DictionaryFormat.DDL2] += 5
    
    # DDL2-specific tags
    if re.search(r'_item\.name\b', content):
        scores[DictionaryFormat.DDL2] += 4
    
    if re.search(r'_item\.category_id\b', content):
        scores[DictionaryFormat.DDL2] += 3
    
    if re.search(r'_item_description\.description\b', content):
        scores[DictionaryFormat.DDL2] += 3
    
    if re.search(r'_item_type\.code\b', content):
        scores[DictionaryFormat.DDL2] += 3
    
    if re.search(r'_item_aliases\.alias_name\b', content):
        scores[DictionaryFormat.DDL2] += 2
    
    # DDL2 datablock_id
    if re.search(r'_datablock\.id\b', content):
        scores[DictionaryFormat.DDL2] += 2
    
    # Determine winner
    max_score = max(scores.values())
    
    if max_score == 0:
        return DictionaryFormat.UNKNOWN
    
    # Get format with highest score
    winner = max(scores, key=scores.get)
    
    # Verify there's a clear winner (at least 2x the runner-up)
    runner_up_score = sorted(scores.values(), reverse=True)[1]
    if runner_up_score > 0 and max_score < runner_up_score * 1.5:
        # Ambiguous - check a few more definitive markers
        if re.search(r'_definition\.id\b', content):
            return DictionaryFormat.DDLm
        if re.search(r'_item\.name\b', content):
            return DictionaryFormat.DDL2
        if re.search(r'^data_on_this_dictionary\s*$', content, re.MULTILINE):
            return DictionaryFormat.DDL1
    
    return winner


def create_dictionary_parser(dictionary_path: str, format_hint: Optional[DictionaryFormat] = None):
    """
    Factory function to create the appropriate parser for a dictionary file.
    
    Auto-detects the dictionary format and returns the corresponding parser instance.
    
    Args:
        dictionary_path: Path to the dictionary file
        format_hint: Optional hint for the format (skips auto-detection if provided)
        
    Returns:
        Parser instance (CIFDictionaryParser or DDL1DictionaryParser)
        
    Raises:
        ValueError: If the format cannot be detected or is unsupported
        FileNotFoundError: If the dictionary file doesn't exist
    """
    if not os.path.exists(dictionary_path):
        raise FileNotFoundError(f"Dictionary file not found: {dictionary_path}")
    
    if format_hint is None:
        fmt = detect_dictionary_format(dictionary_path)
    else:
        fmt = format_hint
    
    if fmt == DictionaryFormat.DDLm:
        from .cif_dictionary_parser import CIFDictionaryParser
        return CIFDictionaryParser(dictionary_path)
    
    elif fmt == DictionaryFormat.DDL1:
        from .cif_ddl1_parser import DDL1DictionaryParser
        return DDL1DictionaryParser(dictionary_path)
    
    elif fmt == DictionaryFormat.DDL2:
        # DDL2 not yet implemented - raise informative error
        raise ValueError(
            f"DDL2 dictionary format detected for '{os.path.basename(dictionary_path)}'. "
            f"DDL2 parsing is not yet supported. "
            f"Consider using a DDLm version of this dictionary from COMCIFS GitHub."
        )
    
    else:
        raise ValueError(
            f"Cannot determine dictionary format for '{os.path.basename(dictionary_path)}'. "
            f"Only DDLm and DDL1 formats are currently supported."
        )


def get_format_description(fmt: DictionaryFormat) -> str:
    """Get a human-readable description of a dictionary format."""
    descriptions = {
        DictionaryFormat.DDLm: "DDLm (modern, CIF2-era)",
        DictionaryFormat.DDL1: "DDL1 (legacy, CIF1-era)",
        DictionaryFormat.DDL2: "DDL2 (intermediate, mmCIF-era)",
        DictionaryFormat.UNKNOWN: "Unknown format",
    }
    return descriptions.get(fmt, "Unknown format")
