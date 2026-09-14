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

The validator maintains user preferences (allowed prefixes/fields) in a
small CIF file in the CIVET config directory, and provides caching for
performance optimization.
"""

from enum import Enum
import copy
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from utils.CIF_parser import TextBlockTracker, CIFParser
from utils.registered_prefixes import (
    is_registered_prefix,
    get_prefix_from_field,
    get_prefix_info,
    get_registered_prefixes_lower
)
from utils.user_config import get_user_allowed_prefixes_path

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
    MALFORMED_USER_ALLOWED = "malformed_user_allowed"  # Embedded prefix is user-allowed, but the name is still not valid in any notation


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
    modern_equivalent: str = ""        # If deprecated, the modern (dot-notation) replacement
    successor_name: str = ""           # Format-aware successor (legacy or modern, depending on file)
    successor_already_exists: bool = False  # True when successor (or alias-equivalent) is already present
    checkcif_retain_required: bool = False  # True when checkCIF needs this deprecated field kept (see checkcif_compatibility.cif_rules)
    prefix: str = ""                   # Extracted prefix if applicable
    suggested_format: str = ""         # Suggested correct format (for embedded local prefixes)
    embedded_prefix: str = ""          # If local prefix is embedded in category extension
    block_name: str = ""               # data_ block the field was (first) found in ("" if single-block)
    # Every data_ block the field occurs in, as (block_code, line_number)
    # pairs in file order. Only populated for multi-block files; drives the
    # per-block action scoping in the validation dialog.
    block_occurrences: List = field(default_factory=list)


@dataclass
class ValidationReport:
    """Complete validation report for CIF content."""
    valid_fields: List[FieldValidationResult] = field(default_factory=list)
    registered_local_fields: List[FieldValidationResult] = field(default_factory=list)
    user_allowed_fields: List[FieldValidationResult] = field(default_factory=list)
    unknown_fields: List[FieldValidationResult] = field(default_factory=list)
    deprecated_fields: List[FieldValidationResult] = field(default_factory=list)
    malformed_fields: List[FieldValidationResult] = field(default_factory=list)
    malformed_user_allowed_fields: List[FieldValidationResult] = field(default_factory=list)
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

    def _cache_and_return(self, cache_key: str, result: FieldValidationResult) -> FieldValidationResult:
        """Cache *result* and return an independent copy of it.

        Must be a copy, not the same object stored in the cache -
        validate_cif_content mutates results in place for format-aware
        (legacy/modern) suggestions, and doing that to the cached object
        itself would corrupt every later lookup of this field name.
        """
        self._validation_cache[cache_key] = result
        self._trim_cache(self._validation_cache, self.MAX_FIELD_CACHE_ENTRIES)
        return copy.copy(result)

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
            # Return an independent copy with the field name/line number
            # updated for this call. Must be a copy, not the cached object
            # itself - validate_cif_content mutates results in place for
            # format-aware (legacy/modern) suggestions, and doing that to
            # the shared cached object would corrupt every later lookup
            # (e.g. a legacy-format file's suggestion leaking into a later,
            # unrelated modern-format file's validation of the same field).
            result = copy.copy(self._validation_cache[cache_key])
            result.field_name = field_name
            result.line_number = line_number
            return result

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
            return self._cache_and_return(cache_key, result)
        
        # Check if specific field is user allowed
        if field_name_lower in self._user_allowed_fields:
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.USER_ALLOWED,
                line_number=line_number,
                description="Field allowed by user",
                prefix=prefix
            )
            return self._cache_and_return(cache_key, result)
        
        # Check if prefix is user allowed. A genuine dictionary category
        # (e.g. 'refln') must never be honoured here even if it's still
        # sitting in a user's allowed-prefixes list from before this check
        # existed - that would silently wave through any unrecognized field
        # under that category (e.g. _refln_frame_id) as if it were a known
        # local extension.
        if (prefix and prefix.lower() in {p.lower() for p in self._user_allowed_prefixes}
                and not self.dict_manager.is_known_category(prefix)):
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.USER_ALLOWED,
                line_number=line_number,
                description=f"Prefix '{prefix}' allowed by user",
                prefix=prefix
            )
            return self._cache_and_return(cache_key, result)
        
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
            return self._cache_and_return(cache_key, result)
        
        # Check if field is known in dictionary
        if self.dict_manager.is_known_field(field_name):
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.VALID,
                line_number=line_number,
                description="Known in dictionary",
                prefix=prefix
            )
            return self._cache_and_return(cache_key, result)
        
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
            return self._cache_and_return(cache_key, result)
        
        # Check if field uses a registered IUCr prefix
        if is_registered_prefix(field_name):
            prefix_info = get_prefix_info(prefix) or ""
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.REGISTERED_LOCAL,
                line_number=line_number,
                description=f"Uses registered prefix '{prefix}'" + (f": {prefix_info}" if prefix_info else ""),
                prefix=prefix
            )
            return self._cache_and_return(cache_key, result)
        
        # Field is unknown - check for embedded local prefix in category extension
        embedded_prefix, suggested_format = self._detect_embedded_local_prefix(field_name)
        
        # A local prefix embedded mid-name (category_prefix_attribute) is
        # never valid as written, in any notation - legacy requires the
        # prefix first, and there's no dot to mark the category boundary
        # for modern notation either. So even once the prefix itself is
        # recognized (user-allowed or registered), the field still needs a
        # mandatory rename rather than being filed away as already fine -
        # otherwise it would keep silently passing forever.

        # Check if embedded local prefix is user allowed
        if embedded_prefix and embedded_prefix.lower() in {p.lower() for p in self._user_allowed_prefixes}:
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.MALFORMED_USER_ALLOWED,
                line_number=line_number,
                description=(
                    f"Local prefix '{embedded_prefix}' is allowed, but as written this name isn't "
                    f"valid in any notation - should be renamed to '{suggested_format}'"
                ),
                prefix=prefix,
                embedded_prefix=embedded_prefix,
                suggested_format=suggested_format or ""
            )
            return self._cache_and_return(cache_key, result)

        # Check if embedded local prefix is a registered IUCr prefix
        if embedded_prefix and embedded_prefix.lower() in get_registered_prefixes_lower():
            result = FieldValidationResult(
                field_name=field_name,
                category=FieldCategory.MALFORMED,
                line_number=line_number,
                description=(
                    f"Uses registered prefix '{embedded_prefix}', but as written this name isn't "
                    f"valid in any notation - should be renamed to '{suggested_format}'"
                ),
                prefix=prefix,
                embedded_prefix=embedded_prefix,
                suggested_format=suggested_format or ""
            )
            return self._cache_and_return(cache_key, result)
        
        if embedded_prefix:
            # This appears to be a category extension with embedded local prefix
            description = (
                f"Unknown field with embedded local prefix '{embedded_prefix}'. "
                # f"Consider using proper format: {suggested_format}"
            )
        elif prefix and self.dict_manager.is_known_category(prefix):
            # e.g. _refln_frame_id: 'refln' is a real category, but
            # 'frame_id' isn't one of its recognized attributes - this is
            # not a local-prefix situation, just an attribute name the
            # loaded dictionaries don't define.
            description = (
                f"'{prefix}' is a known category, but the rest of this name "
                f"isn't a recognized attribute of it - not found in loaded dictionaries"
            )
        else:
            description = "Not found in loaded dictionaries"

        result = FieldValidationResult(
            field_name=field_name,
            category=FieldCategory.UNKNOWN,
            line_number=line_number,
            description=description,
            prefix=prefix,
            suggested_format=suggested_format or "",
            embedded_prefix=embedded_prefix or ""
        )
        return self._cache_and_return(cache_key, result)
    
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
        parsed_fields: List[tuple[str, int, str]] = []  # (name, line, block)
        # All (block, line) occurrences per field, first line per block
        occurrences: Dict[str, List[tuple]] = {}

        # Detect file format once so we can choose the right successor name
        cif_format = self.dict_manager.detect_cif_format(content)  # "legacy"/"modern"/"mixed"
        prefer_legacy = str(cif_format).upper() in ("LEGACY", "MIXED")

        # Parse CIF content to extract field names and line numbers
        lines = content.split('\n')
        text_block_tracker = TextBlockTracker()
        current_block = ""      # data_ block currently being scanned
        block_count = 0

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
                if line_stripped.lower().startswith('data_'):
                    current_block = line_stripped[5:]
                    block_count += 1
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

                    # One report entry per field name; further occurrences in
                    # OTHER blocks are recorded so the dialog can offer
                    # per-block actions (same-block repeats are duplicate
                    # detection's job, not validation's)
                    if field_name_lower in seen_fields:
                        field_occurrences = occurrences.get(field_name_lower, [])
                        if not any(block == current_block for block, _ in field_occurrences):
                            field_occurrences.append((current_block, line_num))
                        continue
                    seen_fields.add(field_name_lower)
                    parsed_fields.append((field_name, line_num, current_block))
                    occurrences[field_name_lower] = [(current_block, line_num)]

        all_field_names = {field_name.lower() for field_name, _, _ in parsed_fields}
        multi_block = block_count > 1

        for field_name, line_num, block_name in parsed_fields:
            # Validate the field
            result = self.validate_field(field_name, line_num)
            # Only attach block context when there is more than one block -
            # single-block reports stay unchanged
            if multi_block:
                result.block_name = block_name
                result.block_occurrences = list(occurrences.get(field_name.lower(), []))
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
                if result.embedded_prefix:
                    # A confirmed-but-mid-name local prefix (see
                    # validate_field) - the "correct" form depends on
                    # notation the same way an embedded-prefix suggestion
                    # always has, not on a dictionary-defined legacy alias.
                    self._apply_legacy_preference_to_embedded_prefix(result, prefer_legacy)
                    result.description = (
                        f"Uses registered prefix '{result.embedded_prefix}', but as written "
                        f"this name isn't valid in any notation - should be renamed to "
                        f"'{result.suggested_format}'"
                    )
                elif result.suggested_format and prefer_legacy:
                    legacy_suggestion = self.dict_manager.map_to_legacy(result.suggested_format)
                    if legacy_suggestion:
                        result.suggested_format = legacy_suggestion
                        result.description = f"Should be {legacy_suggestion}"
                report.malformed_fields.append(result)
            elif result.category == FieldCategory.MALFORMED_USER_ALLOWED:
                # Same reasoning as the MALFORMED/embedded_prefix case above,
                # but for a prefix the user allowed rather than one that's
                # IUCr-registered - kept in its own category (see
                # CATEGORY_CONFIG in the dialog) since it's a personal,
                # self-declared exception rather than a globally vetted one.
                self._apply_legacy_preference_to_embedded_prefix(result, prefer_legacy)
                result.description = (
                    f"Local prefix '{result.embedded_prefix}' is allowed, but as written this "
                    f"name isn't valid in any notation - should be renamed to "
                    f"'{result.suggested_format}'"
                )
                report.malformed_user_allowed_fields.append(result)
        
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
        Detect if an unknown field has a genuine embedded local prefix in a
        category extension.

        Per IUCr Volume G Ch3.1, when adding to a pre-existing category with a
        local prefix, the prefix should come after the dot
        (e.g., _chemical_oxdiff_formula should be written _chemical.oxdiff_formula).

        This detects patterns like _chemical_oxdiff_formula where:
        - _chemical_ is a genuine category in the loaded dictionaries
          (checked dynamically, not against a hardcoded list)
        - oxdiff is an embedded local prefix - confirmed against the
          registered-prefix registry or the user's own allowed-prefix list,
          so an ordinary (if unrecognized) multi-word attribute name like
          "frame_id" in "_refln_frame_id" isn't mistaken for one
        - formula is the attribute name

        Args:
            field_name: The CIF field name to analyze

        Returns:
            Tuple of (embedded_prefix, suggested_format) or (None, None) if not detected
        """
        # Only check underscore-only format (no dot already present)
        if '.' in field_name:
            return (None, None)

        # Remove leading underscore and split by underscore
        name_without_underscore = field_name[1:] if field_name.startswith('_') else field_name
        parts = name_without_underscore.split('_')

        if len(parts) < 3:
            return (None, None)

        registered_prefixes_lower = get_registered_prefixes_lower()
        user_allowed_lower = {p.lower() for p in self._user_allowed_prefixes}

        # Prefer the longest genuine category match, so a deeper real
        # category (e.g. "diffrn_radiation") isn't mistaken for a shorter
        # one ("diffrn") plus an embedded local prefix ("radiation").
        for i in range(len(parts) - 1, 0, -1):
            potential_category = '_'.join(parts[:i])

            if not self.dict_manager.is_known_category(potential_category):
                continue

            remaining_parts = parts[i:]  # e.g., ['oxdiff', 'formula']
            if len(remaining_parts) < 2:
                continue

            embedded_prefix = remaining_parts[0]

            # Only treat the next segment as an embedded local prefix when
            # there's positive evidence it actually is one - i.e. it's a
            # registered IUCr prefix or one the user has already allowed.
            # Without that, it's most likely just part of an unrecognized
            # multi-word attribute name, not a prefix.
            if (embedded_prefix.lower() not in registered_prefixes_lower and
                    embedded_prefix.lower() not in user_allowed_lower):
                continue

            # Build the suggested corrected format
            # Per IUCr Volume G Ch3.1: local prefix goes after the dot
            # _chemical_oxdiff_formula -> _chemical.oxdiff_formula
            local_attribute = '_'.join(remaining_parts)  # oxdiff_formula
            suggested = f"_{potential_category}.{local_attribute}"

            return (embedded_prefix, suggested)

        return (None, None)

    @staticmethod
    def _legacy_format_for_embedded_prefix(embedded_prefix: str, modern_suggested_format: str) -> str:
        """
        Build the legacy-valid reordering of an embedded-local-prefix suggestion.

        A local prefix can only legitimately appear as the very first segment
        in underscore-only (legacy) CIF notation - _civet_exptl_term is a
        valid legacy tag, _exptl_civet_term is not. The modern dot-notation
        form (_exptl.civet_term) has no such restriction, since the dot marks
        the category boundary explicitly rather than relying on position.

        Args:
            embedded_prefix: The detected local prefix (e.g. 'civet')
            modern_suggested_format: The dotted suggestion from
                _detect_embedded_local_prefix (e.g. '_exptl.civet_term')

        Returns:
            The legacy-valid reordering (e.g. '_civet_exptl_term'), or "" if
            it can't be derived from the given inputs.
        """
        if not modern_suggested_format or '.' not in modern_suggested_format:
            return ""

        category, attribute = modern_suggested_format.lstrip('_').split('.', 1)
        prefix_marker = f"{embedded_prefix}_"
        if attribute.lower().startswith(prefix_marker.lower()):
            remaining_attribute = attribute[len(prefix_marker):]
        elif attribute.lower() == embedded_prefix.lower():
            remaining_attribute = ""
        else:
            return ""

        segments = [embedded_prefix, category]
        if remaining_attribute:
            segments.append(remaining_attribute)
        return "_" + "_".join(segments)

    def _apply_legacy_preference_to_embedded_prefix(
        self, result: FieldValidationResult, prefer_legacy: bool
    ) -> None:
        """
        Swap an embedded-local-prefix result's suggested_format to the
        legacy-valid reordering when the file being validated is itself in
        legacy format, since the modern dotted form isn't a legacy tag at all.
        """
        if not (result.embedded_prefix and prefer_legacy):
            return
        legacy_format = self._legacy_format_for_embedded_prefix(
            result.embedded_prefix, result.suggested_format
        )
        if legacy_format:
            result.suggested_format = legacy_format

    def is_known_category(self, category: str) -> bool:
        """
        Check if `category` is a genuine CIF category in the loaded
        dictionaries (e.g. 'refln', 'cell') rather than a local prefix.

        Args:
            category: Candidate category/prefix name, with or without
                leading/trailing underscores.

        Returns:
            True if this is a real dictionary category.
        """
        return self.dict_manager.is_known_category(category)

    def add_allowed_prefix(self, prefix: str) -> bool:
        """
        Add a prefix to the user-allowed list.

        Refuses to add a prefix that's actually a genuine dictionary
        category (e.g. 'refln') - allowing one would silently accept any
        unrecognized field under that category as a known local extension.

        Args:
            prefix: The prefix to allow (without underscore)

        Returns:
            True if the prefix was added, False if it was refused because
            it's a real dictionary category.
        """
        if not prefix:
            return False
        if self.is_known_category(prefix):
            return False
        self._user_allowed_prefixes.add(prefix.lower())
        self._save_user_preferences()
        self.clear_cache()
        return True
    
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
    
    # Loop tags used in the user_allowed_prefixes.cif file. One single-column
    # loop per list - see _load_user_preferences/_save_user_preferences.
    _ALLOWED_PREFIX_TAG = '_civet_allowed_prefix.name'
    _ALLOWED_FIELD_TAG = '_civet_allowed_field.name'

    def _load_user_preferences(self) -> None:
        """Load user-allowed prefixes/fields from the config directory's CIF file."""
        prefs_path = get_user_allowed_prefixes_path()
        self._user_allowed_prefixes = set()
        self._user_allowed_fields = set()

        if not prefs_path.exists():
            return

        try:
            with open(prefs_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except IOError as e:
            print(f"Warning: Could not read allowed prefixes/fields {prefs_path}: {e}")
            return

        parser = CIFParser()
        parser.parse_file(content)
        for loop in parser.loops:
            if len(loop.field_names) != 1:
                continue
            tag_lower = loop.field_names[0].lower()
            values = {row[0].strip().lower() for row in loop.data_rows if row and row[0].strip()}
            if tag_lower == self._ALLOWED_PREFIX_TAG.lower():
                self._user_allowed_prefixes = values
            elif tag_lower == self._ALLOWED_FIELD_TAG.lower():
                self._user_allowed_fields = values

    def _save_user_preferences(self) -> None:
        """Save user-allowed prefixes/fields to a small CIF file in the config directory."""
        prefs_path = get_user_allowed_prefixes_path()

        lines = [
            "# CIVET user-allowed CIF prefixes/fields - not officially IUCr-registered.",
            "# Managed via View Recognised Prefixes... > Add User Prefix (safe to hand-edit).",
            "data_civet_user_allowed",
        ]
        if self._user_allowed_prefixes:
            lines.append("")
            lines.append("loop_")
            lines.append(self._ALLOWED_PREFIX_TAG)
            lines.extend(f"'{p}'" for p in sorted(self._user_allowed_prefixes))
        if self._user_allowed_fields:
            lines.append("")
            lines.append("loop_")
            lines.append(self._ALLOWED_FIELD_TAG)
            lines.extend(f"'{f}'" for f in sorted(self._user_allowed_fields))
        content = "\n".join(lines) + "\n"

        try:
            prefs_path.parent.mkdir(parents=True, exist_ok=True)
            with open(prefs_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except IOError as e:
            print(f"Warning: Could not save allowed prefixes/fields {prefs_path}: {e}")
