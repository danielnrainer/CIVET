"""
CIF Data Name Validator for CIVET
=================================

This module provides validation of CIF data names against loaded dictionaries
and registered IUCr prefixes. It categorizes fields into:
- Valid: Known in loaded dictionaries
- Registered Local: Uses a registered IUCr prefix
- User Allowed: User has explicitly allowed this prefix/field
- Unknown: Not recognized in any dictionary
- Deprecated: Field is deprecated with modern replacement

The validator maintains user preferences in QSettings for persistence and
provides caching for performance optimization.
"""

from enum import Enum
import copy
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from PyQt6.QtCore import QSettings

from utils.CIF_parser import TextBlockTracker
from utils.registered_prefixes import (
    is_registered_prefix,
    get_prefix_from_field,
    suggest_dictionary_for_prefix,
    get_prefix_info,
    get_registered_prefixes_lower
)

if TYPE_CHECKING:
    from utils.cif_dictionary_manager import CIFDictionaryManager


class FieldCategory(Enum):
    """Categories for CIF field validation results."""
    VALID = "valid"                    # Known in loaded dictionaries
    REGISTERED_LOCAL = "registered"    # Uses registered IUCr prefix
    USER_ALLOWED = "user_allowed"      # User has allowed this prefix/field
    UNKNOWN = "unknown"                # Not recognized
    DEPRECATED = "deprecated"          # Deprecated field
    MALFORMED = "malformed"            # Malformed name matchable to a known field


class FieldAction(Enum):
    """Actions that can be taken on a field."""
    KEEP = "keep"                      # Keep field as-is
    DELETE = "delete"                  # Remove from CIF
    ALLOW_PREFIX = "allow_prefix"      # Add prefix to user allowed list
    ALLOW_FIELD = "allow_field"        # Add specific field to allowed list
    IGNORE_SESSION = "ignore_session"  # Ignore for this session only
    CORRECT_FORMAT = "correct_format"  # Apply suggested format correction
    DEPRECATION_UPDATE = "deprecation_update"  # Add modern equivalent alongside deprecated field
    DEPRECATION_REPLACE = "deprecation_replace"  # Replace deprecated field name with successor
    FIX_MALFORMED = "fix_malformed"    # Rename malformed field to correct name


@dataclass
class FieldValidationResult:
    """Result of validating a single CIF field."""
    field_name: str
    category: FieldCategory
    line_number: int
    description: str = ""              # Why this category
    suggested_dictionary: str = ""     # If unknown, suggest a dict
    modern_equivalent: str = ""        # If deprecated, the modern (dot-notation) replacement
    successor_name: str = ""           # Format-aware successor (legacy or modern, depending on file)
    successor_already_exists: bool = False  # True when successor (or alias-equivalent) is already present
    checkcif_retain_required: bool = False  # True when checkCIF needs this deprecated field kept (see checkcif_compatibility.cif_rules)
    prefix: str = ""                   # Extracted prefix if applicable
    suggested_format: str = ""         # Suggested correct format (for embedded local prefixes)
    embedded_prefix: str = ""          # If local prefix is embedded in category extension


@dataclass
class ValidationReport:
    """Complete validation report for CIF content."""
    valid_fields: List[FieldValidationResult] = field(default_factory=list)
    registered_local_fields: List[FieldValidationResult] = field(default_factory=list)
    user_allowed_fields: List[FieldValidationResult] = field(default_factory=list)
    unknown_fields: List[FieldValidationResult] = field(default_factory=list)
    deprecated_fields: List[FieldValidationResult] = field(default_factory=list)
    malformed_fields: List[FieldValidationResult] = field(default_factory=list)
    total_fields: int = 0


class DataNameValidator:
    """
    Validates CIF data names against dictionaries and registered prefixes.
    
    This class provides comprehensive validation of CIF field names, categorizing
    them based on dictionary presence, registered prefixes, user preferences,
    and deprecation status.
    
    Attributes:
        dict_manager: CIFDictionaryManager for checking field validity
        _user_allowed_prefixes: Set of prefixes user has explicitly allowed
        _user_allowed_fields: Set of specific fields user has allowed
        _session_ignored: Fields to ignore for current session only
        _validation_cache: Cache of validation results for performance
    """
    
    # QSettings keys for persistence
    SETTINGS_KEY_PREFIXES = "CIVET/allowed_prefixes"
    SETTINGS_KEY_FIELDS = "CIVET/allowed_fields"
    MAX_FIELD_CACHE_ENTRIES = 4096
    MAX_REPORT_CACHE_ENTRIES = 16
    MAX_EQUIVALENT_CACHE_ENTRIES = 1024
    
    def __init__(self, dict_manager: 'CIFDictionaryManager'):
        """
        Initialize the DataNameValidator.
        
        Args:
            dict_manager: CIFDictionaryManager instance for field validation
        """
        self.dict_manager = dict_manager
        self._user_allowed_prefixes: Set[str] = set()
        self._user_allowed_fields: Set[str] = set()
        self._session_ignored: Set[str] = set()
        self._validation_cache: Dict[str, FieldValidationResult] = {}
        self._report_cache: Dict[str, ValidationReport] = {}
        self._equivalent_names_cache: Dict[str, Set[str]] = {}
        
        # Load persisted user preferences
        self._load_user_preferences()
    
    def validate_field(self, field_name: str, line_number: int = 0) -> FieldValidationResult:
        """
        Validate a single CIF field name.
        
        Args:
            field_name: The CIF field name to validate (with leading underscore)
            line_number: Line number in CIF file (for reporting)
            
        Returns:
            FieldValidationResult with category and details
        """
        # Normalize field name
        field_name_lower = field_name.lower().strip()
        
        # Check cache first (use normalized name + line number as key since
        # line number may differ for same field name in different contexts)
        cache_key = field_name_lower
        if cache_key in self._validation_cache:
            # Return cached result but update line number
            cached = self._validation_cache[cache_key]
            return FieldValidationResult(
                field_name=field_name,
                category=cached.category,
                line_number=line_number,
                description=cached.description,
                suggested_dictionary=cached.suggested_dictionary,
                modern_equivalent=cached.modern_equivalent,
                successor_name=cached.successor_name,
                successor_already_exists=cached.successor_already_exists,
                checkcif_retain_required=cached.checkcif_retain_required,
                prefix=cached.prefix
            )
        
        # Extract prefix for later use
        prefix = get_prefix_from_field(field_name) or ""
        
        # Check if field is in session ignored list
        if field_name_lower in self._session_ignored:
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.USER_ALLOWED,
                line_number=line_number,
                description="Ignored for this session",
                prefix=prefix
            )
            self._validation_cache[cache_key] = result
            self._trim_cache(self._validation_cache, self.MAX_FIELD_CACHE_ENTRIES)
            return result
        
        # Check if specific field is user allowed
        if field_name_lower in self._user_allowed_fields:
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.USER_ALLOWED,
                line_number=line_number,
                description="Field allowed by user",
                prefix=prefix
            )
            self._validation_cache[cache_key] = result
            self._trim_cache(self._validation_cache, self.MAX_FIELD_CACHE_ENTRIES)
            return result
        
        # Check if prefix is user allowed
        if prefix and prefix.lower() in {p.lower() for p in self._user_allowed_prefixes}:
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.USER_ALLOWED,
                line_number=line_number,
                description=f"Prefix '{prefix}' allowed by user",
                prefix=prefix
            )
            self._validation_cache[cache_key] = result
            self._trim_cache(self._validation_cache, self.MAX_FIELD_CACHE_ENTRIES)
            return result
        
        # Check if field is deprecated (before checking if known, as deprecated fields are "known")
        if self.dict_manager.is_field_deprecated(field_name):
            modern_replacement = self.dict_manager.get_modern_replacement(field_name) or ""
            checkcif_retain_required = self.dict_manager.is_checkcif_deprecation_field(field_name)
            description = "Field is deprecated"
            if checkcif_retain_required:
                description += " (retained for checkCIF compatibility - see README)"
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.DEPRECATED,
                line_number=line_number,
                description=description,
                modern_equivalent=modern_replacement,
                checkcif_retain_required=checkcif_retain_required,
                prefix=prefix
            )
            self._validation_cache[cache_key] = result
            self._trim_cache(self._validation_cache, self.MAX_FIELD_CACHE_ENTRIES)
            return result
        
        # Check if field is known in dictionary
        if self.dict_manager.is_known_field(field_name):
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.VALID,
                line_number=line_number,
                description="Known in dictionary",
                prefix=prefix
            )
            self._validation_cache[cache_key] = result
            self._trim_cache(self._validation_cache, self.MAX_FIELD_CACHE_ENTRIES)
            return result
        
        # Check if field is a malformed version of a known field.
        # Examples:
        # - _diffrn_flux_density -> _diffrn.flux_density
        # - _audit_contact.author_address -> _audit_contact_author.address
        modern_equiv = self.dict_manager.guess_modern_equivalent(field_name)
        if modern_equiv:
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.MALFORMED,
                line_number=line_number,
                description=f"Should be {modern_equiv}",
                suggested_format=modern_equiv,
                prefix=prefix
            )
            self._validation_cache[cache_key] = result
            self._trim_cache(self._validation_cache, self.MAX_FIELD_CACHE_ENTRIES)
            return result
        
        # Check if field uses a registered IUCr prefix
        if is_registered_prefix(field_name):
            prefix_info = get_prefix_info(prefix) or ""
            suggested_dict = suggest_dictionary_for_prefix(prefix) or ""
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.REGISTERED_LOCAL,
                line_number=line_number,
                description=f"Uses registered prefix '{prefix}'" + (f": {prefix_info}" if prefix_info else ""),
                suggested_dictionary=suggested_dict,
                prefix=prefix
            )
            self._validation_cache[cache_key] = result
            self._trim_cache(self._validation_cache, self.MAX_FIELD_CACHE_ENTRIES)
            return result
        
        # Field is unknown - check for embedded local prefix in category extension
        embedded_prefix, suggested_format = self._detect_embedded_local_prefix(field_name)
        
        # Check if embedded local prefix is user allowed
        if embedded_prefix and embedded_prefix.lower() in {p.lower() for p in self._user_allowed_prefixes}:
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.USER_ALLOWED,
                line_number=line_number,
                description=f"Embedded prefix '{embedded_prefix}' allowed by user",
                prefix=prefix,
                embedded_prefix=embedded_prefix,
                suggested_format=suggested_format or ""
            )
            self._validation_cache[cache_key] = result
            self._trim_cache(self._validation_cache, self.MAX_FIELD_CACHE_ENTRIES)
            return result
        
        # Check if embedded local prefix is a registered IUCr prefix
        if embedded_prefix and embedded_prefix.lower() in get_registered_prefixes_lower():
            from utils.registered_prefixes import get_prefix_info as get_info
            prefix_info = get_info(embedded_prefix) or ""
            suggested_dict = suggest_dictionary_for_prefix(embedded_prefix) or ""
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.REGISTERED_LOCAL,
                line_number=line_number,
                description=f"Uses registered embedded prefix '{embedded_prefix}'" + (f": {prefix_info}" if prefix_info else ""),
                suggested_dictionary=suggested_dict,
                prefix=prefix,
                embedded_prefix=embedded_prefix,
                suggested_format=suggested_format or ""
            )
            self._validation_cache[cache_key] = result
            self._trim_cache(self._validation_cache, self.MAX_FIELD_CACHE_ENTRIES)
            return result
        
        suggested_dict = suggest_dictionary_for_prefix(prefix) if prefix else ""
        
        if embedded_prefix:
            # This appears to be a category extension with embedded local prefix
            description = (
                f"Unknown field with embedded local prefix '{embedded_prefix}'. "
                # f"Consider using proper format: {suggested_format}"
            )
        else:
            description = "Not found in loaded dictionaries"
        
        result = FieldValidationResult(
            field_name=field_name,
            category=FieldCategory.UNKNOWN,
            line_number=line_number,
            description=description,
            suggested_dictionary=suggested_dict or "",
            prefix=prefix,
            suggested_format=suggested_format or "",
            embedded_prefix=embedded_prefix or ""
        )
        self._validation_cache[cache_key] = result
        self._trim_cache(self._validation_cache, self.MAX_FIELD_CACHE_ENTRIES)
        return result
    
    def validate_cif_content(self, content: str) -> ValidationReport:
        """
        Validate all field names in CIF content.
        
        Args:
            content: CIF file content as string
            
        Returns:
            ValidationReport with categorized fields
        """
        report_cache_key = self._content_cache_key(content)
        if report_cache_key in self._report_cache:
            return copy.deepcopy(self._report_cache[report_cache_key])

        report = ValidationReport()
        seen_fields: Set[str] = set()
        parsed_fields: List[tuple[str, int]] = []
        
        # Detect file format once so we can choose the right successor name
        cif_format = self.dict_manager.detect_cif_format(content)  # "legacy"/"modern"/"mixed"
        prefer_legacy = str(cif_format).upper() in ("LEGACY", "MIXED")
        
        # Parse CIF content to extract field names and line numbers
        lines = content.split('\n')
        text_block_tracker = TextBlockTracker()

        for line_num, line in enumerate(lines, start=1):
            line_stripped = line.strip()

            # Skip field detection on text-block delimiters and interior lines
            # (e.g. _iucr_refine_fcf_details blocks) so that field-like text
            # inside a multiline value - CIF 1.1 ';' blocks or CIF 2.0
            # triple-quoted values - isn't mistaken for a real field.
            if text_block_tracker.consume(line_stripped):
                continue

            # Skip empty lines, comments, and headers
            if not line_stripped or line_stripped.startswith('#') or line_stripped.startswith('data_'):
                continue

            # Skip loop_ headers
            if line_stripped.lower() == 'loop_':
                continue

            # Match field names (start with underscore)
            # Handle both standalone field names and field name with value
            if line_stripped.startswith('_'):
                # Extract field name (first token starting with _)
                match = self._extract_field_name(line_stripped)
                if match:
                    field_name = match
                    field_name_lower = field_name.lower()
                    
                    # Skip if we've already seen this field (avoid duplicates in report)
                    if field_name_lower in seen_fields:
                        continue
                    seen_fields.add(field_name_lower)
                    parsed_fields.append((field_name, line_num))

        all_field_names = {field_name.lower() for field_name, _ in parsed_fields}

        for field_name, line_num in parsed_fields:
            # Validate the field
            result = self.validate_field(field_name, line_num)
            report.total_fields += 1

            # Add to appropriate category list
            if result.category == FieldCategory.VALID:
                report.valid_fields.append(result)
            elif result.category == FieldCategory.REGISTERED_LOCAL:
                report.registered_local_fields.append(result)
            elif result.category == FieldCategory.USER_ALLOWED:
                report.user_allowed_fields.append(result)
            elif result.category == FieldCategory.UNKNOWN:
                report.unknown_fields.append(result)
            elif result.category == FieldCategory.DEPRECATED:
                # Compute format-aware successor name
                if result.modern_equivalent:
                    successor = result.modern_equivalent
                    if prefer_legacy:
                        legacy = self.dict_manager.map_to_legacy(result.modern_equivalent)
                        if legacy:
                            successor = legacy
                    result.successor_name = successor

                    successor_equivalents = self._get_equivalent_field_names(successor)
                    current_field = field_name.lower()
                    result.successor_already_exists = any(
                        equivalent in all_field_names and equivalent != current_field
                        for equivalent in successor_equivalents
                    )

                report.deprecated_fields.append(result)
            elif result.category == FieldCategory.MALFORMED:
                if result.suggested_format and prefer_legacy:
                    legacy_suggestion = self.dict_manager.map_to_legacy(result.suggested_format)
                    if legacy_suggestion:
                        result.suggested_format = legacy_suggestion
                        result.description = f"Should be {legacy_suggestion}"
                report.malformed_fields.append(result)
        
        self._report_cache[report_cache_key] = copy.deepcopy(report)
        self._trim_cache(self._report_cache, self.MAX_REPORT_CACHE_ENTRIES)
        return report

    def _get_equivalent_field_names(self, field_name: str) -> Set[str]:
        """Return known equivalent names (legacy/modern/aliases) for duplicate checks."""
        cache_key = field_name.lower()
        cached = self._equivalent_names_cache.get(cache_key)
        if cached is not None:
            return cached.copy()

        names: Set[str] = {cache_key}

        modern_name = self.dict_manager.map_to_modern(field_name)
        if modern_name:
            names.add(modern_name.lower())
            legacy_from_modern = self.dict_manager.map_to_legacy(modern_name)
            if legacy_from_modern:
                names.add(legacy_from_modern.lower())

        legacy_name = self.dict_manager.map_to_legacy(field_name)
        if legacy_name:
            names.add(legacy_name.lower())
            modern_from_legacy = self.dict_manager.map_to_modern(legacy_name)
            if modern_from_legacy:
                names.add(modern_from_legacy.lower())

        metadata = self.dict_manager.get_field_metadata(field_name)
        if metadata:
            definition_id = getattr(metadata, 'definition_id', None)
            if definition_id:
                names.add(definition_id.lower())
            for alias in getattr(metadata, 'aliases', []):
                alias_name = getattr(alias, 'name', None)
                if alias_name:
                    names.add(alias_name.lower())

        self._equivalent_names_cache[cache_key] = names.copy()
        self._trim_cache(self._equivalent_names_cache, self.MAX_EQUIVALENT_CACHE_ENTRIES)
        return names
    
    def _extract_field_name(self, line: str) -> Optional[str]:
        """
        Extract the CIF field name from a line.
        
        Args:
            line: A line from a CIF file
            
        Returns:
            The field name if found, None otherwise
        """
        # Field name is the first token, ends at whitespace or end of line
        # Must start with underscore
        if not line.startswith('_'):
            return None
        
        # Find end of field name (first whitespace or end of string)
        parts = line.split()
        if parts:
            field_name = parts[0]
            # Validate it looks like a CIF field name
            if field_name.startswith('_') and len(field_name) > 1:
                return field_name
        
        return None
    
    def _detect_embedded_local_prefix(self, field_name: str) -> tuple:
        """
        Detect if an unknown field has an embedded local prefix in a category extension.
        
        Per IUCr Volume G Ch3.1, when adding to a pre-existing category with a local prefix,
        the prefix should come after the dot (e.g., _chemical_oxdiff.formula).
        
        This method detects patterns like _chemical_oxdiff_formula where:
        - _chemical_ is a known dictionary category
        - oxdiff is an embedded local prefix
        - formula is the attribute name
        
        Args:
            field_name: The CIF field name to analyze
            
        Returns:
            Tuple of (embedded_prefix, suggested_format) or (None, None) if not detected
        """
        from utils.registered_prefixes import REGISTERED_CIF_PREFIXES_LOWER
        
        # Only check underscore-only format (no dot already present)
        if '.' in field_name:
            return (None, None)
        
        # Remove leading underscore and split by underscore
        name_without_underscore = field_name[1:] if field_name.startswith('_') else field_name
        parts = name_without_underscore.split('_')
        
        if len(parts) < 3:
            return (None, None)
        
        # Try to find a known category at the start, followed by an embedded prefix
        # We check progressively: _cell_, _chemical_, _diffrn_, _exptl_, etc.
        for i in range(1, len(parts) - 1):
            # Build potential category (first i parts)
            potential_category = '_' + '_'.join(parts[:i]) + '_'
            
            # Check if this looks like a known dictionary category
            # We use is_known_field to check if any field with this category exists
            test_field = '_' + '_'.join(parts[:i]) + '_length_a'  # Common test pattern
            category_known = self._is_category_known(potential_category)
            
            if category_known:
                # The next part could be an embedded local prefix
                potential_embedded = parts[i].lower()
                
                # Check if it looks like a registered prefix or could be a local prefix
                # (anything that's not a known attribute of this category)
                remaining_parts = parts[i:]  # e.g., ['oxdiff', 'formula']
                
                if len(remaining_parts) >= 2:
                    embedded_prefix = remaining_parts[0]
                    attribute_parts = remaining_parts[1:]
                    
                    # Verify this isn't actually a valid field (the embedded part + rest)
                    full_check = '_' + '_'.join(parts[:i]) + '_' + '_'.join(remaining_parts)
                    if not self.dict_manager.is_known_field(full_check):
                        # Check if removing the embedded prefix would yield a known field
                        without_embedded = '_' + '_'.join(parts[:i]) + '_' + '_'.join(attribute_parts)
                        
                        # Build the suggested corrected format
                        # Per IUCr Volume G Ch3.1: local prefix goes after the dot
                        # _chemical_oxdiff_formula -> _chemical.oxdiff_formula
                        category = '_'.join(parts[:i])
                        local_attribute = '_'.join(remaining_parts)  # oxdiff_formula
                        suggested = f"_{category}.{local_attribute}"
                        
                        return (embedded_prefix, suggested)
        
        return (None, None)
    
    def _is_category_known(self, category_prefix: str) -> bool:
        """
        Check if a category prefix corresponds to known dictionary fields.
        
        Args:
            category_prefix: Category prefix like '_chemical_' or '_diffrn_'
            
        Returns:
            True if fields with this category exist in loaded dictionaries
        """
        # Common known categories in CIF dictionaries
        known_categories = {
            '_atom_', '_atom_site_', '_atom_sites_', '_atom_type_',
            '_audit_', '_cell_', '_chemical_', '_chemical_formula_',
            '_citation_', '_computing_', '_database_', '_diffrn_',
            '_diffrn_attenuator_', '_diffrn_detector_', '_diffrn_measurement_',
            '_diffrn_orient_', '_diffrn_radiation_', '_diffrn_refln_',
            '_diffrn_reflns_', '_diffrn_source_', '_diffrn_standards_',
            '_exptl_', '_exptl_absorpt_', '_exptl_crystal_',
            '_geom_', '_geom_angle_', '_geom_bond_', '_geom_contact_',
            '_geom_hbond_', '_geom_torsion_',
            '_journal_', '_publ_', '_publ_author_',
            '_refine_', '_refine_diff_', '_refine_ls_',
            '_refln_', '_reflns_', '_reflns_shell_',
            '_space_group_', '_space_group_symop_',
            '_struct_', '_symmetry_', '_twin_',
        }
        
        category_lower = category_prefix.lower()
        if category_lower in known_categories:
            return True
        
        # Also try to check against actual dictionary if available
        # This is a simplified check - a full implementation would
        # iterate through all known fields
        return False

    def add_allowed_prefix(self, prefix: str) -> None:
        """
        Add a prefix to the user-allowed list.
        
        Args:
            prefix: The prefix to allow (without underscore)
        """
        if prefix:
            self._user_allowed_prefixes.add(prefix.lower())
            self._save_user_preferences()
            self.clear_cache()
    
    def remove_allowed_prefix(self, prefix: str) -> None:
        """
        Remove a prefix from the user-allowed list.
        
        Args:
            prefix: The prefix to remove
        """
        self._user_allowed_prefixes.discard(prefix.lower())
        self._save_user_preferences()
        self.clear_cache()
    
    def add_allowed_field(self, field_name: str) -> None:
        """
        Add a specific field to the user-allowed list.
        
        Args:
            field_name: The field name to allow (with underscore)
        """
        if field_name:
            self._user_allowed_fields.add(field_name.lower().strip())
            self._save_user_preferences()
            self.clear_cache()
    
    def remove_allowed_field(self, field_name: str) -> None:
        """
        Remove a field from the user-allowed list.
        
        Args:
            field_name: The field name to remove
        """
        self._user_allowed_fields.discard(field_name.lower().strip())
        self._save_user_preferences()
        self.clear_cache()
    
    def add_session_ignored(self, field_name: str) -> None:
        """
        Add a field to the session-ignored list (not persisted).
        
        Args:
            field_name: The field name to ignore for this session
        """
        if field_name:
            self._session_ignored.add(field_name.lower().strip())
            self.clear_cache()
    
    def get_allowed_prefixes(self) -> Set[str]:
        """
        Get the set of user-allowed prefixes.
        
        Returns:
            Set of allowed prefix strings
        """
        return self._user_allowed_prefixes.copy()
    
    def get_allowed_fields(self) -> Set[str]:
        """
        Get the set of user-allowed fields.
        
        Returns:
            Set of allowed field name strings
        """
        return self._user_allowed_fields.copy()
    
    def clear_cache(self) -> None:
        """Clear the validation cache."""
        self._validation_cache.clear()
        self._report_cache.clear()
        self._equivalent_names_cache.clear()

    @staticmethod
    def _trim_cache(cache: Dict, max_entries: int) -> None:
        while len(cache) > max_entries:
            cache.pop(next(iter(cache)))

    @staticmethod
    def _content_cache_key(content: str) -> str:
        return hashlib.sha1(content.encode('utf-8')).hexdigest()
    
    def is_field_valid(self, field_name: str) -> bool:
        """
        Quick check if a field is valid (valid, registered, or user-allowed).
        
        This is a convenience method for checking if a field should be
        accepted without raising warnings.
        
        Args:
            field_name: The field name to check
            
        Returns:
            True if field is valid, registered, or user-allowed; False otherwise
        """
        result = self.validate_field(field_name)
        return result.category in {
            FieldCategory.VALID,
            FieldCategory.REGISTERED_LOCAL,
            FieldCategory.USER_ALLOWED
        }
    
    def _load_user_preferences(self) -> None:
        """Load user preferences from QSettings."""
        settings = QSettings()
        
        # Load allowed prefixes
        prefixes_str = settings.value(self.SETTINGS_KEY_PREFIXES, "")
        if prefixes_str:
            self._user_allowed_prefixes = {
                p.strip().lower() for p in prefixes_str.split(',') if p.strip()
            }
        else:
            self._user_allowed_prefixes = set()
        
        # Load allowed fields
        fields_str = settings.value(self.SETTINGS_KEY_FIELDS, "")
        if fields_str:
            self._user_allowed_fields = {
                f.strip().lower() for f in fields_str.split(',') if f.strip()
            }
        else:
            self._user_allowed_fields = set()
    
    def _save_user_preferences(self) -> None:
        """Save user preferences to QSettings."""
        settings = QSettings()
        
        # Save allowed prefixes
        prefixes_str = ','.join(sorted(self._user_allowed_prefixes))
        settings.setValue(self.SETTINGS_KEY_PREFIXES, prefixes_str)
        
        # Save allowed fields
        fields_str = ','.join(sorted(self._user_allowed_fields))
        settings.setValue(self.SETTINGS_KEY_FIELDS, fields_str)
        
        settings.sync()
