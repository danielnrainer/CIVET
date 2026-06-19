"""Data-name integrity checks for CIF content.

This module identifies integrity conflicts that should be resolved before save:
- Direct duplicate data names (same field repeated)
- Alias groups where aliases carry different data values

Alias groups with identical values are treated as valid and are not flagged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from .CIF_parser import CIFParser


@dataclass
class AliasValueMismatch:
    """Represents an alias group whose values are not identical."""

    canonical_name: str
    aliases: List[str]
    alias_signatures: Dict[str, Tuple[str, ...]]


def _signature_sort_key(signature: Tuple[str, ...]) -> str:
    """Sort key for deterministic comparison of value signatures."""
    return "\u241f".join(signature)


def _build_field_value_signatures(cif_content: str) -> Dict[str, List[Tuple[str, ...]]]:
    """Build comparable value signatures for each field name in a CIF.

    Signatures are extracted for both scalar fields and loop columns.
    """
    parser = CIFParser()
    parser.parse_file(cif_content)

    signatures: Dict[str, List[Tuple[str, ...]]] = {}

    # Scalar (non-loop) fields
    for field_name, field_obj in parser.fields.items():
        if field_obj.value == "(in loop)":
            continue
        value = "" if field_obj.value is None else str(field_obj.value)
        signatures.setdefault(field_name, []).append(("scalar", value))

    # Loop columns (signature is all values in the column)
    for loop in parser.loops:
        for col_idx, field_name in enumerate(loop.field_names):
            col_values: List[str] = []
            for row in loop.data_rows:
                col_values.append(row[col_idx] if col_idx < len(row) else "")
            signatures.setdefault(field_name, []).append(("loop", *col_values))

    return signatures


def find_alias_value_mismatches(cif_content: str, dict_manager) -> List[AliasValueMismatch]:
    """Find alias groups where aliases do not carry exactly the same value signature."""
    # Include duplicates from the source extraction for reliable field presence.
    all_found_fields: List[str] = dict_manager._extract_fields_excluding_text_blocks(cif_content)
    unique_fields = set(all_found_fields)

    canonical_to_aliases: Dict[str, set[str]] = {}
    for field_name in unique_fields:
        canonical = dict_manager.map_to_modern(field_name) or field_name
        canonical_to_aliases.setdefault(canonical, set()).add(field_name)

    field_signatures = _build_field_value_signatures(cif_content)

    mismatches: List[AliasValueMismatch] = []
    for canonical, alias_set in canonical_to_aliases.items():
        if len(alias_set) <= 1:
            continue

        aliases = sorted(alias_set)
        alias_signatures: Dict[str, Tuple[str, ...]] = {}
        for alias in aliases:
            sig_list = sorted(field_signatures.get(alias, []), key=_signature_sort_key)
            flattened: List[str] = []
            for sig in sig_list:
                flattened.extend(sig)
                flattened.append("<occ>")
            alias_signatures[alias] = tuple(flattened)

        baseline_alias = aliases[0]
        baseline_signature = alias_signatures[baseline_alias]
        if any(alias_signatures[a] != baseline_signature for a in aliases[1:]):
            mismatches.append(
                AliasValueMismatch(
                    canonical_name=canonical,
                    aliases=aliases,
                    alias_signatures=alias_signatures,
                )
            )

    return mismatches


def _field_occurrence_counts(cif_content: str, dict_manager) -> Dict[str, int]:
    """Count field-name occurrences outside semicolon text blocks."""
    counts: Dict[str, int] = {}
    for field_name in dict_manager._extract_fields_excluding_text_blocks(cif_content):
        counts[field_name] = counts.get(field_name, 0) + 1
    return counts


def get_data_name_conflicts_requiring_resolution(
    cif_content: str,
    dict_manager,
) -> Tuple[Dict[str, List[str]], List[AliasValueMismatch]]:
    """Return only actionable conflicts: duplicates or alias value mismatches.

    Returns:
        Tuple of:
          - conflicts map compatible with FieldConflictDialog workflow
          - alias mismatch details for reporting
    """
    raw_conflicts = dict_manager.detect_field_aliases_in_cif(cif_content)
    mismatches = find_alias_value_mismatches(cif_content, dict_manager)
    mismatch_canonicals = {m.canonical_name for m in mismatches}
    counts = _field_occurrence_counts(cif_content, dict_manager)

    filtered_conflicts: Dict[str, List[str]] = {}
    for canonical, alias_list in raw_conflicts.items():
        unique_aliases = set(alias_list)
        has_duplicate_names = any(counts.get(alias, 0) > 1 for alias in unique_aliases)

        # Keep conflict when duplicate names exist OR alias values differ.
        if has_duplicate_names or canonical in mismatch_canonicals:
            filtered_conflicts[canonical] = alias_list

    return filtered_conflicts, mismatches
