"""
CIF Data Value Validator
========================

Validates CIF data values against their dictionary-defined types and enumerations.
Also detects structural loop violations (wrong number of values for the number of
field names in the loop header).

Classes:
    ValidationIssue  -- a single validation finding
    CIFDataValidator -- the main validator; call validate() with a parsed CIFParser
                        and a CIFDictionaryManager

Severity levels:
    'error'   -- definite violation (loop count mismatch, enum value not allowed)
    'warning' -- likely problem (type mismatch against dictionary type)
    'info'    -- advisory (field not in any loaded dictionary)
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .CIF_parser import CIFParser, CIFLoop
    from .cif_dictionary_manager import CIFDictionaryManager

# CIF special values that are always syntactically valid regardless of type
_SPECIAL_VALUES = {'.', '?'}

# DDLm / DDL1 type codes that require a numeric value
_NUMERIC_TYPES = {'real', 'float', 'integer', 'int', 'count', 'index', 'numb'}
_INTEGER_TYPES = {'integer', 'int', 'count', 'index'}

# Regex for CIF numeric values (optionally followed by a parenthesised uncertainty)
_NUMERIC_RE = re.compile(
    r'^[+-]?'                     # optional sign
    r'(?:\d+\.?\d*|\.\d+)'        # mantissa
    r'(?:[eEdD][+-]?\d+)?'        # optional exponent
    r'(?:\(\d+\))?$'              # optional (esd) suffix
)


@dataclass
class ValidationIssue:
    """One validation finding from CIFDataValidator."""
    issue_type: str        # 'loop_incomplete', 'type_mismatch', 'enum_violation'
    severity: str          # 'error', 'warning', 'info'
    field_name: str
    message: str
    line_number: Optional[int] = None   # 1-based, if available
    value: Optional[str] = None         # the problematic value
    expected: Optional[str] = None      # expected type / allowed values summary
    row_index: Optional[int] = None     # 0-based row index within loop (if applicable)


class CIFDataValidator:
    """Validates CIF data values against dictionary type definitions.

    Usage::

        from utils.CIF_parser import CIFParser
        from utils.cif_dictionary_manager import CIFDictionaryManager
        from utils.cif_data_validator import CIFDataValidator

        parser = CIFParser()
        parser.parse_file(content)

        validator = CIFDataValidator()
        issues = validator.validate(parser, dict_manager)
    """

    def validate(
        self,
        cif_parser: 'CIFParser',
        dict_manager: 'CIFDictionaryManager',
    ) -> List[ValidationIssue]:
        """Run all checks and return the list of issues found.

        Parameters
        ----------
        cif_parser:
            A CIFParser instance whose ``parse_file()`` has already been called.
        dict_manager:
            A loaded CIFDictionaryManager used for field metadata lookup.

        Returns
        -------
        List[ValidationIssue]
            All issues found, ordered by line number where available.
        """
        issues: List[ValidationIssue] = []

        # --- Individual (non-loop) fields ---
        for field_obj in cif_parser.fields.values():
            # Skip the synthetic placeholder for loop fields
            if field_obj.value == "(in loop)":
                continue
            field_issues = self._check_value(
                field_name=field_obj.name,
                value=field_obj.value,
                line_number=field_obj.line_number,
                dict_manager=dict_manager,
            )
            issues.extend(field_issues)

        # --- Loop structures ---
        for loop in cif_parser.loops:
            issues.extend(self._check_loop(loop, dict_manager))

        # Sort by line number (issues without a line number go last)
        issues.sort(key=lambda x: (x.line_number is None, x.line_number or 0))
        return issues

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_loop(
        self,
        loop: 'CIFLoop',
        dict_manager: 'CIFDictionaryManager',
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []

        # 1. Structural check: incomplete last row
        if loop.has_incomplete_last_row:
            n_fields = len(loop.field_names)
            actual = loop.incomplete_row_actual_count
            issues.append(ValidationIssue(
                issue_type='loop_incomplete',
                severity='error',
                field_name=', '.join(loop.field_names),
                message=(
                    f"Loop starting at line {loop.line_number} has {actual} value(s) "
                    f"in its last (incomplete) row but the loop header defines "
                    f"{n_fields} field(s). "
                    f"The total number of data values must be a multiple of the number "
                    f"of field names."
                ),
                line_number=loop.line_number,
                expected=f"multiple of {n_fields}",
                value=f"{actual} (in last row)",
            ))

        # 2. Type / enumeration checks for every value in every row
        for row_idx, row in enumerate(loop.data_rows):
            for col_idx, field_name in enumerate(loop.field_names):
                if col_idx >= len(row):
                    continue
                value = row[col_idx]
                if not value:
                    continue
                # Approximate line number: loop_line + header_lines + row_idx + 1
                approx_line = (
                    (loop.line_number or 0) + len(loop.field_names) + row_idx + 1
                )
                field_issues = self._check_value(
                    field_name=field_name,
                    value=value,
                    line_number=approx_line,
                    dict_manager=dict_manager,
                    row_index=row_idx,
                )
                issues.extend(field_issues)

        return issues

    def _check_value(
        self,
        field_name: str,
        value: Any,
        line_number: Optional[int],
        dict_manager: 'CIFDictionaryManager',
        row_index: Optional[int] = None,
    ) -> List[ValidationIssue]:
        """Check one field value; return any issues found."""
        issues: List[ValidationIssue] = []

        # Normalise to string
        if value is None:
            return issues
        str_value = str(value).strip()

        # Strip multiline content to first non-empty line for type comparison
        if '\n' in str_value:
            first_line = str_value.split('\n')[0].strip()
            str_value_for_check = first_line if first_line else str_value[:80]
        else:
            str_value_for_check = str_value

        # CIF special values are always valid
        if str_value_for_check in _SPECIAL_VALUES:
            return issues

        # Look up dictionary metadata
        meta = dict_manager.get_field_metadata(field_name)
        if meta is None:
            # Field not in any loaded dictionary — no type info to check against
            return issues

        type_contents = (meta.type_contents or '').strip().lower()

        # --- Enumeration check (highest priority) ---
        if meta.enumeration_values:
            enum_lower = [v.lower() for v in meta.enumeration_values]
            if str_value_for_check.lower() not in enum_lower:
                # Show only a short preview of the allowed list to keep messages readable
                if len(meta.enumeration_values) <= 10:
                    allowed_preview = ', '.join(meta.enumeration_values)
                else:
                    allowed_preview = ', '.join(meta.enumeration_values[:10]) + f', … ({len(meta.enumeration_values)} total)'
                issues.append(ValidationIssue(
                    issue_type='enum_violation',
                    severity='error',
                    field_name=field_name,
                    message=(
                        f"Value '{str_value_for_check}' is not an allowed enumeration "
                        f"value for {field_name}."
                    ),
                    line_number=line_number,
                    value=str_value_for_check,
                    expected=f"one of: {allowed_preview}",
                    row_index=row_index,
                ))
            # Even if enum check fails, skip numeric check — enum IS the constraint
            return issues

        # --- Numeric type check ---
        if type_contents in _NUMERIC_TYPES:
            # Try integers first (strict subset of reals)
            if type_contents in _INTEGER_TYPES:
                if not self._is_integer(str_value_for_check):
                    issues.append(ValidationIssue(
                        issue_type='type_mismatch',
                        severity='warning',
                        field_name=field_name,
                        message=(
                            f"Value '{str_value_for_check}' does not look like an integer "
                            f"for {field_name} (type: {meta.type_contents})."
                        ),
                        line_number=line_number,
                        value=str_value_for_check,
                        expected=f"integer ({meta.type_contents})",
                        row_index=row_index,
                    ))
            else:
                if not _NUMERIC_RE.match(str_value_for_check):
                    issues.append(ValidationIssue(
                        issue_type='type_mismatch',
                        severity='warning',
                        field_name=field_name,
                        message=(
                            f"Value '{str_value_for_check}' does not look like a number "
                            f"for {field_name} (type: {meta.type_contents})."
                        ),
                        line_number=line_number,
                        value=str_value_for_check,
                        expected=f"numeric ({meta.type_contents})",
                        row_index=row_index,
                    ))

        # Text, Code, Name, Tag, Uri, Any, etc. — no further structural checks
        return issues

    @staticmethod
    def _is_integer(s: str) -> bool:
        """True if *s* looks like a CIF integer (optional sign, digits, optional esd)."""
        return bool(re.match(r'^[+-]?\d+(?:\(\d+\))?$', s))
