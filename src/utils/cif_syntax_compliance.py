"""
CIF Syntax Compliance Checker
==============================

Checks CIF file content for compliance with CIF 1.1 and CIF 2.0
specifications.

References
----------
- CIF 1.1 syntax:    https://www.iucr.org/resources/cif/spec/version1.1/cifsyntax
- CIF 1.1 semantics: https://www.iucr.org/resources/cif/spec/version1.1/semantics
- CIF 2.0 grammar:   CIF2-ENBF.txt (repository root)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# CIF 1.1 allowed character set:
#   HT (U+0009), LF (U+000A), CR (U+000D), printable ASCII U+0020–U+007E.
# ---------------------------------------------------------------------------
_CIF1_VALID_ORDS: frozenset = frozenset({9, 10, 13} | set(range(32, 127)))


def _is_valid_cif2_char(c: str) -> bool:
    """Return ``True`` if *c* is a permitted CIF2 ``allchars`` code point."""
    o = ord(c)
    if o <= 0x0008:
        return False
    if o in (0x000B, 0x000C):       # VT, FF
        return False
    if 0x000E <= o <= 0x001F:
        return False
    if o == 0x007F:                  # DEL
        return False
    if 0x0080 <= o <= 0x009F:        # C1 controls
        return False
    if 0xD800 <= o <= 0xDFFF:        # surrogate pairs
        return False
    if 0xFDD0 <= o <= 0xFDEF:        # Unicode non-characters
        return False
    if (o & 0xFFFF) in (0xFFFE, 0xFFFF):  # U+xFFFE / U+xFFFF
        return False
    return True


@dataclass
class ComplianceIssue:
    """A single compliance issue found in a CIF file."""

    severity: str           # "error" | "warning" | "info"
    spec: str               # "CIF1.1" | "CIF2"
    issue_type: str         # short snake_case identifier
    line_number: Optional[int]
    column: Optional[int]
    description: str
    auto_fixable: bool

    def __str__(self) -> str:
        loc = f" (line {self.line_number})" if self.line_number else ""
        fix = " [auto-fixable]" if self.auto_fixable else ""
        return f"[{self.spec}/{self.severity.upper()}]{loc} {self.description}{fix}"


# ---------------------------------------------------------------------------
# CIF 1.1 compliance checker
# ---------------------------------------------------------------------------

class CIF1ComplianceChecker:
    """Check CIF content for CIF 1.1 specification compliance."""

    def check(self, content: str) -> List[ComplianceIssue]:
        """Return all CIF 1.1 compliance issues found in *content*."""
        issues: List[ComplianceIssue] = []
        issues.extend(self._check_version_header(content))
        issues.extend(self._check_char_set(content))
        issues.extend(self._check_cif2_constructs(content))
        issues.extend(self._check_unquoted_brackets(content))
        issues.extend(self._check_line_length(content))
        issues.extend(self._check_name_lengths(content))
        issues.extend(self._check_reserved_words_as_values(content))
        return issues

    # ------------------------------------------------------------------

    def _check_version_header(self, content: str) -> List[ComplianceIssue]:
        lines = content.split('\n')
        for line in lines[:5]:
            s = line.strip()
            if s.startswith('#\\#CIF_2.0'):
                return [ComplianceIssue(
                    severity='error', spec='CIF1.1',
                    issue_type='wrong_version_header',
                    line_number=1, column=None,
                    description=(
                        'File has a CIF 2.0 header; a CIF 2.0 file is not '
                        'CIF 1.1 compliant'
                    ),
                    auto_fixable=True,
                )]
            if s.startswith('#\\#CIF_1'):
                return []  # Correct header already present
        return [ComplianceIssue(
            severity='info', spec='CIF1.1',
            issue_type='missing_version_header',
            line_number=None, column=None,
            description='No CIF version header found; #\\#CIF_1.1 is recommended (optional)',
            auto_fixable=True,
        )]

    def _check_char_set(self, content: str) -> List[ComplianceIssue]:
        """CIF 1.1 is ASCII-only: HT/LF/CR and printable U+0020–U+007E."""
        try:
            from .cif_char_encoding import CIF11_UNICODE_TO_BACKSLASH
        except ImportError:
            CIF11_UNICODE_TO_BACKSLASH = {}

        issues: List[ComplianceIssue] = []
        reported: set = set()

        for line_num, line in enumerate(content.split('\n'), 1):
            for col, ch in enumerate(line, 1):
                o = ord(ch)
                if o not in _CIF1_VALID_ORDS and ch not in reported:
                    reported.add(ch)
                    auto_fix = ch in CIF11_UNICODE_TO_BACKSLASH
                    if auto_fix:
                        fix_note = (
                            f" → CIF 1.1 encoding: '{CIF11_UNICODE_TO_BACKSLASH[ch]}'"
                        )
                    else:
                        fix_note = " (no known CIF 1.1 encoding — manual review required)"
                    issues.append(ComplianceIssue(
                        severity='error', spec='CIF1.1',
                        issue_type='non_ascii_character',
                        line_number=line_num, column=col,
                        description=(
                            f"Non-ASCII character U+{o:04X} ({repr(ch)}) "
                            f"not allowed in CIF 1.1{fix_note}"
                        ),
                        auto_fixable=auto_fix,
                    ))
        return issues

    def _check_cif2_constructs(self, content: str) -> List[ComplianceIssue]:
        """Detect CIF2-only constructs (lists, tables, triple-quoted strings)."""
        constructs = _detect_cif2_constructs(content)
        return [
            ComplianceIssue(
                severity='error', spec='CIF1.1',
                issue_type='cif2_construct',
                line_number=None, column=None,
                description=(
                    f'CIF2-only construct present: {c} — '
                    f'no CIF 1.1 equivalent (must be removed manually)'
                ),
                auto_fixable=False,
            )
            for c in constructs
        ]

    def _check_unquoted_brackets(self, content: str) -> List[ComplianceIssue]:
        """In CIF 1.1, data values must not start with an unquoted [ or ]."""
        issues: List[ComplianceIssue] = []
        in_text_block = False

        for line_num, line in enumerate(content.split('\n'), 1):
            if line.startswith(';'):
                in_text_block = not in_text_block
                continue
            if in_text_block:
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            value = _extract_value_start(stripped)
            if value and (value.startswith('[') or value.startswith(']')):
                issues.append(ComplianceIssue(
                    severity='error', spec='CIF1.1',
                    issue_type='unquoted_bracket_value',
                    line_number=line_num, column=None,
                    description=(
                        "Unquoted value starting with '[' or ']' is "
                        "reserved in CIF 1.1 and must be quoted"
                    ),
                    auto_fixable=True,
                ))
        return issues

    def _check_line_length(self, content: str) -> List[ComplianceIssue]:
        """Lines must not exceed 2048 characters."""
        issues: List[ComplianceIssue] = []
        for line_num, line in enumerate(content.split('\n'), 1):
            if len(line) > 2048:
                issues.append(ComplianceIssue(
                    severity='error', spec='CIF1.1',
                    issue_type='line_too_long',
                    line_number=line_num, column=None,
                    description=f'Line exceeds 2048 characters ({len(line)} chars)',
                    auto_fixable=False,
                ))
        return issues

    def _check_name_lengths(self, content: str) -> List[ComplianceIssue]:
        """Data names ≤ 75 chars; block/frame codes ≤ 75 chars."""
        issues: List[ComplianceIssue] = []
        for line_num, line in enumerate(content.split('\n'), 1):
            stripped = line.strip()
            m = re.match(r'^(_\S+)', stripped)
            if m:
                name = m.group(1)
                if len(name) > 75:
                    issues.append(ComplianceIssue(
                        severity='error', spec='CIF1.1',
                        issue_type='data_name_too_long',
                        line_number=line_num, column=None,
                        description=f'Data name "{name}" is {len(name)} characters (max 75)',
                        auto_fixable=False,
                    ))
            m2 = re.match(r'^(?:data_|save_)(\S+)', stripped, re.IGNORECASE)
            if m2:
                code = m2.group(1)
                if len(code) > 75:
                    issues.append(ComplianceIssue(
                        severity='error', spec='CIF1.1',
                        issue_type='block_code_too_long',
                        line_number=line_num, column=None,
                        description=f'Block/frame code "{code}" is {len(code)} characters (max 75)',
                        auto_fixable=False,
                    ))
        return issues

    def _check_reserved_words_as_values(self, content: str) -> List[ComplianceIssue]:
        """``global_`` and ``stop_`` must not appear as unquoted values."""
        issues: List[ComplianceIssue] = []
        in_text_block = False
        reserved = frozenset({'global_', 'stop_'})

        for line_num, line in enumerate(content.split('\n'), 1):
            if line.startswith(';'):
                in_text_block = not in_text_block
                continue
            if in_text_block:
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            value = _extract_value_start(stripped)
            if value:
                tokens = value.split()
                first = tokens[0] if tokens else ''
                if (first.lower() in reserved
                        and not first.startswith("'")
                        and not first.startswith('"')):
                    issues.append(ComplianceIssue(
                        severity='error', spec='CIF1.1',
                        issue_type='reserved_word_as_value',
                        line_number=line_num, column=None,
                        description=(
                            f'Reserved word "{first}" used as an unquoted '
                            f'value (must be quoted in CIF 1.1)'
                        ),
                        auto_fixable=True,
                    ))
        return issues


# ---------------------------------------------------------------------------
# CIF 2.0 compliance checker
# ---------------------------------------------------------------------------

class CIF2ComplianceChecker:
    """Check CIF content for CIF 2.0 specification compliance."""

    def check(self, content: str) -> List[ComplianceIssue]:
        """Return all CIF 2.0 compliance issues found in *content*."""
        issues: List[ComplianceIssue] = []
        issues.extend(self._check_version_header(content))
        issues.extend(self._check_invalid_unicode(content))
        issues.extend(self._check_line_length(content))
        issues.extend(self._check_unquoted_special_chars(content))
        return issues

    # ------------------------------------------------------------------

    def _check_version_header(self, content: str) -> List[ComplianceIssue]:
        """CIF 2.0 requires the ``#\\#CIF_2.0`` version header as the first line."""
        for line in content.split('\n')[:5]:
            s = line.strip()
            if s.startswith('#\\#CIF_2.0'):
                return []
            if s.startswith('#\\#CIF_'):
                return [ComplianceIssue(
                    severity='error', spec='CIF2',
                    issue_type='wrong_version_header',
                    line_number=1, column=None,
                    description=(
                        f'File has a {s[:10]} header; '
                        'CIF 2.0 requires the #\\#CIF_2.0 version header'
                    ),
                    auto_fixable=True,
                )]
        return [ComplianceIssue(
            severity='error', spec='CIF2',
            issue_type='missing_version_header',
            line_number=None, column=None,
            description='Missing required #\\#CIF_2.0 version header at the start of the file',
            auto_fixable=True,
        )]

    def _check_invalid_unicode(self, content: str) -> List[ComplianceIssue]:
        """Check for code points not permitted by the CIF2 ``allchars`` production."""
        issues: List[ComplianceIssue] = []
        reported: set = set()
        for line_num, line in enumerate(content.split('\n'), 1):
            for col, ch in enumerate(line, 1):
                if not _is_valid_cif2_char(ch) and ch not in reported:
                    reported.add(ch)
                    o = ord(ch)
                    issues.append(ComplianceIssue(
                        severity='error', spec='CIF2',
                        issue_type='invalid_unicode_char',
                        line_number=line_num, column=col,
                        description=(
                            f'Invalid Unicode code point U+{o:04X} ({repr(ch)}) '
                            f'not permitted in CIF2'
                        ),
                        auto_fixable=False,
                    ))
        return issues

    def _check_line_length(self, content: str) -> List[ComplianceIssue]:
        """Lines must not exceed 2048 characters."""
        issues: List[ComplianceIssue] = []
        for line_num, line in enumerate(content.split('\n'), 1):
            if len(line) > 2048:
                issues.append(ComplianceIssue(
                    severity='error', spec='CIF2',
                    issue_type='line_too_long',
                    line_number=line_num, column=None,
                    description=f'Line exceeds 2048 characters ({len(line)} chars)',
                    auto_fixable=False,
                ))
        return issues

    def _check_unquoted_special_chars(self, content: str) -> List[ComplianceIssue]:
        """In CIF2, ``[ ] { }`` in unquoted values must be quoted."""
        try:
            from .cif2_value_formatting import validate_cif2_content
        except ImportError:
            return []
        raw_issues = validate_cif2_content(content)
        return [
            ComplianceIssue(
                severity='error', spec='CIF2',
                issue_type='unquoted_cif2_special_char',
                line_number=line_num, column=None,
                description=(
                    f'Field {field_name}: unquoted value "{value}" contains '
                    f'CIF2 special characters ([ ] {{ }})'
                ),
                auto_fixable=True,
            )
            for line_num, field_name, value, _ in raw_issues
        ]


# ---------------------------------------------------------------------------
# Public convenience API
# ---------------------------------------------------------------------------

def check_compliance(content: str) -> Dict[str, List[ComplianceIssue]]:
    """Check CIF content against both CIF 1.1 and CIF 2.0 specifications.

    Returns
    -------
    dict
        Keys ``'cif1'`` and ``'cif2'``, each a list of
        :class:`ComplianceIssue`.
    """
    return {
        'cif1': CIF1ComplianceChecker().check(content),
        'cif2': CIF2ComplianceChecker().check(content),
    }


def is_cif1_compliant(content: str) -> bool:
    """Return ``True`` if *content* has no CIF 1.1 compliance *errors*."""
    return not any(
        i.severity == 'error'
        for i in CIF1ComplianceChecker().check(content)
    )


def is_cif2_compliant(content: str) -> bool:
    """Return ``True`` if *content* has no CIF 2.0 compliance *errors*."""
    return not any(
        i.severity == 'error'
        for i in CIF2ComplianceChecker().check(content)
    )


# ---------------------------------------------------------------------------
# Internal helpers — not part of the public API
# ---------------------------------------------------------------------------

def _detect_cif2_constructs(content: str) -> List[str]:
    """Detect CIF2-only constructs: list values, table values, triple-quoted strings.

    Self-contained implementation (no imports from ``cif_format_converter``)
    to avoid circular dependencies.

    Returns
    -------
    list of str
        Human-readable descriptions of constructs found, e.g.
        ``["list values [...]", "triple-quoted strings"]``.
    """
    found: List[str] = []
    in_text_block = False
    in_triple_double = False
    in_triple_single = False

    for line in content.split('\n'):
        stripped = line.strip()

        # Semicolon text-block boundary — semicolon MUST be at column 0.
        if line.startswith(';') and not in_triple_double and not in_triple_single:
            in_text_block = not in_text_block
            continue
        if in_text_block:
            continue

        # Track triple-quoted strings; count occurrences per line so that
        # open+close on the same line (count == 2) leaves the state unchanged.
        if '"""' in stripped:
            count = stripped.count('"""')
            if count % 2 == 1:
                in_triple_double = not in_triple_double
            if 'triple-quoted strings' not in found:
                found.append('triple-quoted strings')
        if "'''" in stripped:
            count = stripped.count("'''")
            if count % 2 == 1:
                in_triple_single = not in_triple_single
            if 'triple-quoted strings' not in found:
                found.append('triple-quoted strings')

        if in_triple_double or in_triple_single:
            continue

        if stripped.startswith('#'):
            continue

        # Determine the value portion of this line.
        value_part: Optional[str] = None
        if stripped.startswith('_'):
            parts = stripped.split(None, 1)
            if len(parts) == 2:
                value_part = _strip_inline_comment(parts[1].strip())
        elif not re.match(r'^(?:loop_|data_|save_)\b', stripped, re.IGNORECASE) and stripped:
            value_part = _strip_inline_comment(stripped)

        if value_part is not None:
            vp = value_part.lstrip()
            if vp.startswith('[') and 'list values [...]' not in found:
                if _looks_like_cif2_list(vp):
                    found.append('list values [...]')
            elif vp.startswith('{') and 'table values {...}' not in found:
                found.append('table values {...}')

    return found


def _strip_inline_comment(value_part: str) -> str:
    """Strip a trailing ``# comment`` from a value-part string.

    Only strips when ``#`` is preceded by whitespace, so it does not strip
    ``#`` that is part of a quoted or unquoted value token.
    """
    if not value_part:
        return value_part
    stripped = value_part.lstrip()
    if stripped.startswith("'") or stripped.startswith('"'):
        return value_part   # Quoted string — leave as-is
    m = re.search(r'\s#', value_part)
    if m:
        return value_part[: m.start()].rstrip()
    return value_part


def _looks_like_cif2_list(value: str) -> bool:
    """Return ``True`` if a ``[``-prefixed value looks like a CIF2 list.

    A CIF2 list has whitespace-separated items (e.g. ``[1 2 3]``), as
    opposed to a chemical formula bracket like ``[Cu(CN)2]``.
    """
    depth = 0
    for i, ch in enumerate(value):
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                inner = value[1:i]
                return bool(inner.strip()) and ' ' in inner.strip()
    return True  # Unclosed bracket — treat as CIF2 list


def _extract_value_start(stripped_line: str) -> Optional[str]:
    """Return the value portion of a stripped CIF line, or ``None``.

    For field lines (``_name value``), returns the value portion.
    For loop data lines, returns the entire line.
    Returns ``None`` for comments, ``data_`` / ``loop_`` / ``save_``.
    """
    if not stripped_line or stripped_line.startswith('#'):
        return None
    if re.match(r'^(?:loop_|data_|save_)\b', stripped_line, re.IGNORECASE):
        return None
    if stripped_line.startswith('_'):
        parts = stripped_line.split(None, 1)
        return parts[1].strip() if len(parts) == 2 else None
    return stripped_line  # Loop data line
