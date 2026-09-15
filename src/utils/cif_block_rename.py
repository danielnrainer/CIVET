"""Rename a CIF data block code and update the places that reference it by name.

Renaming ``data_<old>`` to ``data_<new>`` is not a plain text search/replace:
a block's code is echoed in a handful of well-defined places, and only those
should follow the rename. Everywhere else - including a coincidental
``old_name`` substring inside running or quoted text - is left untouched.

Places handled, per the COMCIFS core CIF dictionary and IUCr/checkCIF
conventions:

- The ``data_`` header line itself.
- ``_vrf_<ALERT>_<blockcode>`` validation-reply-form field names inside the
  block (checkCIF/PLATON convention: the block code is the tail of the field
  name, e.g. ``_vrf_PLAT020_2025NCS0255_aP0`` for ``data_2025NCS0255_aP0``).
- ``_audit.block_code`` (legacy alias ``_audit_block_code``) inside the
  block, when its value equals the block's own code - COMCIFS AUDIT
  category, "a unique block code identifier".
- ``_audit_link.block_code`` (legacy alias ``_audit_link_block_code``)
  anywhere else in the file - as a plain field or a loop_ column - whose
  value equals the old code, since COMCIFS AUDIT_LINK is how one block
  refers to another by its block code.
- The first line of an echoed reflection-file header inside
  ``_iucr_refine_fcf_details``, when a data-collection tool has pasted the
  block's own .fcf content (which carries a matching ``data_`` line of its
  own) into that field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .CIF_parser import CIFParser, TextBlockTracker, find_loops, list_data_block_names

AUDIT_BLOCK_CODE_NAMES = {'_audit.block_code', '_audit_block_code'}
AUDIT_LINK_BLOCK_CODE_NAMES = {'_audit_link.block_code', '_audit_link_block_code'}
FCF_DETAILS_NAMES = {'_iucr_refine_fcf_details', '_iucr_refine.fcf_details'}

# Conservative: reject whitespace and characters that are reserved elsewhere
# in the CIF grammar (comment/quote/bracket/table markers) or that would
# break a reconstructed _vrf_<code>_<name> tag.
_INVALID_NAME_CHARS_RE = re.compile(r'''[\s#$'"\[\]{}]''')

_HEADER_RE = re.compile(r'^(\s*)(data_)(\S+)(.*)$', re.IGNORECASE)
_SIMPLE_FIELD_RE = re.compile(r'^(\s*)(_\S+)(\s+)(\S.*?)(\s*)$')


@dataclass
class BlockRenameResult:
    content: str
    changes: List[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.changes)


def validate_new_block_name(new_name: str, existing_names: List[str], old_name: str) -> Optional[str]:
    """Return an error message if ``new_name`` is not usable, else None."""
    if new_name is None or not new_name.strip():
        return "The new block name cannot be empty."
    if new_name != new_name.strip():
        return "The new block name cannot have leading or trailing whitespace."
    if _INVALID_NAME_CHARS_RE.search(new_name):
        return "The new block name cannot contain whitespace or the characters # $ ' \" [ ] { }."
    if new_name.lower() == old_name.lower():
        return None
    for name in existing_names:
        if name.lower() == old_name.lower():
            continue
        if name.lower() == new_name.lower():
            return f"A data block named 'data_{new_name}' already exists in this file."
    return None


def _iter_block_spans(lines: List[str]) -> List[Tuple[Optional[str], int, int]]:
    """Return (block_name, start, end) for every data_ block, in file order.

    ``end`` is exclusive. data_ tokens inside comments or multiline text
    values are ignored, matching list_data_block_names().
    """
    tracker = TextBlockTracker()
    spans: List[Tuple[Optional[str], int, int]] = []
    current_name: Optional[str] = None
    current_start = 0
    started = False
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if tracker.consume(line):
            continue
        if line.startswith('#'):
            continue
        if line.lower().startswith('data_'):
            if started:
                spans.append((current_name, current_start, i))
            current_name = line[5:]
            current_start = i
            started = True
    if started:
        spans.append((current_name, current_start, len(lines)))
    return spans


def _rename_header_line(line: str, old_name: str, new_name: str) -> Tuple[str, bool]:
    m = _HEADER_RE.match(line)
    if not m:
        return line, False
    leading, kw, name, rest = m.groups()
    if name.lower() != old_name.lower():
        return line, False
    return f'{leading}{kw}{new_name}{rest}', True


def _rename_vrf_line(line: str, old_name: str, new_name: str) -> Tuple[str, bool]:
    """Rename a bare ``_vrf_<ALERT>_<old_name>`` tag line, if this is one."""
    stripped = line.strip()
    if not stripped.lower().startswith('_vrf_'):
        return line, False
    m = re.match(r'^(\s*)(\S+)(\s*)$', line)
    if not m:
        return line, False
    leading, token, trailing = m.groups()
    suffix = '_' + old_name
    if not token.lower().endswith(suffix.lower()):
        return line, False
    new_token = token[:len(token) - len(suffix)] + '_' + new_name
    return f'{leading}{new_token}{trailing}', True


def _rename_simple_field_value(line: str, field_names_lower: set, old_name: str, new_name: str) -> Tuple[str, bool]:
    """Rename the value of a single-line ``_name  value`` field, if it names
    one of ``field_names_lower`` and its value is exactly ``old_name``."""
    m = _SIMPLE_FIELD_RE.match(line)
    if not m:
        return line, False
    leading, name, sep, value, trailing = m.groups()
    if name.lower() not in field_names_lower:
        return line, False
    raw_value = value.strip()
    quote = None
    inner = raw_value
    if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in ('"', "'"):
        quote = raw_value[0]
        inner = raw_value[1:-1]
    if inner != old_name:
        return line, False
    new_value = f'{quote}{new_name}{quote}' if quote else new_name
    return f'{leading}{name}{sep}{new_value}{trailing}', True


def _rename_fcf_echo(lines: List[str], start: int, end: int, old_name: str, new_name: str) -> bool:
    """Rename a ``data_<old_name>`` line echoed as the start of an embedded
    reflection-file header inside _iucr_refine_fcf_details, if present."""
    for i in range(start, end):
        if lines[i].strip().lower() not in FCF_DETAILS_NAMES:
            continue
        j = i + 1
        if j >= end or not lines[j].lstrip().startswith(';'):
            continue
        k = j + 1
        if k >= end:
            continue
        new_line, changed = _rename_header_line(lines[k], old_name, new_name)
        if changed:
            lines[k] = new_line
            return True
    return False


def _rename_in_loops(lines: List[str], old_name: str, new_name: str) -> int:
    """Rename matching _audit_link.block_code values inside loop_ columns.

    Mutates ``lines`` in place and returns the number of cell values
    changed. Loops are located once on a snapshot before any edit, then
    spliced back at their original position adjusted by the running length
    change of earlier edits.
    """
    snapshot = list(lines)
    changed_cells = 0
    offset = 0
    parser = CIFParser()
    for start_idx, consumed, loop_obj in find_loops(snapshot):
        col = next(
            (i for i, name in enumerate(loop_obj.field_names)
             if name.lower() in AUDIT_LINK_BLOCK_CODE_NAMES),
            None,
        )
        if col is None:
            continue
        row_changed = False
        for row in loop_obj.data_rows:
            if col < len(row) and row[col] == old_name:
                row[col] = new_name
                changed_cells += 1
                row_changed = True
        if not row_changed:
            continue
        new_loop_lines = parser._format_loop(loop_obj)
        actual_start = start_idx + offset
        lines[actual_start:actual_start + consumed] = new_loop_lines
        offset += len(new_loop_lines) - consumed
    return changed_cells


def rename_data_block(content: str, old_name: str, new_name: str) -> BlockRenameResult:
    """Rename data block ``old_name`` to ``new_name`` in ``content``.

    Raises ValueError if the block doesn't exist or ``new_name`` is invalid
    (see validate_new_block_name).
    """
    existing = list_data_block_names(content)
    error = validate_new_block_name(new_name, existing, old_name)
    if error:
        raise ValueError(error)

    lines = content.split('\n')
    spans = _iter_block_spans(lines)
    target = next(
        (s for s in spans if s[0] is not None and s[0].lower() == old_name.lower()),
        None,
    )
    if target is None:
        raise ValueError(f"No data block named 'data_{old_name}' found in this file.")
    _, start, end = target

    changes: List[str] = []

    if new_name == old_name:
        return BlockRenameResult(content=content, changes=changes)

    new_header, ok = _rename_header_line(lines[start], old_name, new_name)
    if ok:
        lines[start] = new_header
        changes.append(f"Renamed data_{old_name} to data_{new_name}")

    vrf_count = 0
    for i in range(start, end):
        new_line, ok = _rename_vrf_line(lines[i], old_name, new_name)
        if ok:
            lines[i] = new_line
            vrf_count += 1
            continue
        new_line, ok = _rename_simple_field_value(lines[i], AUDIT_BLOCK_CODE_NAMES, old_name, new_name)
        if ok:
            lines[i] = new_line
            changes.append("Updated _audit.block_code")
    if vrf_count:
        plural = '' if vrf_count == 1 else 's'
        changes.append(f"Renamed {vrf_count} VRF field name{plural} (_vrf_...)")

    if _rename_fcf_echo(lines, start, end, old_name, new_name):
        changes.append("Updated the echoed data_ header inside _iucr_refine_fcf_details")

    link_simple_count = 0
    tracker = TextBlockTracker()
    for i, raw in enumerate(lines):
        if tracker.consume(raw.strip()):
            continue
        new_line, ok = _rename_simple_field_value(raw, AUDIT_LINK_BLOCK_CODE_NAMES, old_name, new_name)
        if ok:
            lines[i] = new_line
            link_simple_count += 1
    if link_simple_count:
        plural = '' if link_simple_count == 1 else 's'
        changes.append(f"Updated {link_simple_count} cross-block _audit_link.block_code reference{plural}")

    link_loop_count = _rename_in_loops(lines, old_name, new_name)
    if link_loop_count:
        plural = '' if link_loop_count == 1 else 's'
        changes.append(f"Updated {link_loop_count} cross-block _audit_link.block_code reference{plural} in a loop_")

    return BlockRenameResult(content='\n'.join(lines), changes=changes)
