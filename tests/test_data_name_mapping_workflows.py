"""Tests for CIFDictionaryManager detection, mapping, and conversion helpers."""

from utils.cif_dictionary_manager import (
    CIFDictionaryManager,
    FieldNotation,
    CIFSyntaxVersion,
)


def _manager() -> CIFDictionaryManager:
    manager = CIFDictionaryManager()
    manager._ensure_loaded()
    return manager


def test_detect_notation_legacy():
    manager = _manager()
    content = "_cell_length_a 5.0\n_cell_length_b 6.0\n"

    assert manager.detect_notation(content) == FieldNotation.LEGACY


def test_detect_notation_modern():
    manager = _manager()
    content = "_cell.length_a 5.0\n_cell.length_b 6.0\n"

    assert manager.detect_notation(content) == FieldNotation.MODERN


def test_detect_notation_mixed():
    manager = _manager()
    content = "_cell_length_a 5.0\n_cell.length_b 6.0\n"

    assert manager.detect_notation(content) == FieldNotation.MIXED


def test_detect_syntax_version_by_header_and_headerless_unknown():
    manager = _manager()

    assert manager.detect_syntax_version("#\\#CIF_2.0\ndata_t\n") == CIFSyntaxVersion.CIF2
    assert manager.detect_syntax_version("#\\#CIF_1.1\ndata_t\n") == CIFSyntaxVersion.CIF1
    assert manager.detect_syntax_version("data_t\n_cell.length_a 1\n") == CIFSyntaxVersion.UNKNOWN


def test_detect_syntax_version_cif2_construct_without_header():
    manager = _manager()

    assert manager.detect_syntax_version("data_t\n_field [1 2 3]\n") == CIFSyntaxVersion.CIF2


def test_map_to_modern_and_legacy_for_common_field():
    manager = _manager()

    modern = manager.map_to_modern("_cell_length_a")
    legacy = manager.map_to_legacy("_cell.length_a")

    assert modern == "_cell.length_a"
    assert legacy == "_cell_length_a"


def test_map_to_legacy_resolves_modern_alias_name():
    manager = _manager()

    assert manager.map_to_legacy("_diffrn_detector.type") == "_diffrn_detector_type"


def test_is_known_field_true_for_core_field_false_for_unknown_field():
    manager = _manager()

    assert manager.is_known_field("_cell_length_a") is True
    assert manager.is_known_field("_definitely_not_a_real_cif_field_name") is False


def test_is_known_field_rejects_wrong_dot_position_false_positive():
    manager = _manager()

    # This looks similar to valid audit-contact names but resolves to a different
    # canonical field family and must not be accepted as known.
    assert manager.is_known_field("_audit_contact.author_address") is False


def test_guess_modern_equivalent_detects_misplaced_dot_name():
    manager = _manager()

    suggested = manager.guess_modern_equivalent("_audit_contact.author_address")

    assert suggested == "_audit_contact_author.address"


def test_find_malformed_fields_detects_misplaced_dot_name():
    manager = _manager()
    content = "data_t\n_audit_contact.author_address ;Street\n;\n"

    malformed = manager.find_malformed_fields(content)

    assert len(malformed) == 1
    assert malformed[0]["original"] == "_audit_contact.author_address"
    assert malformed[0]["suggested"] == "_audit_contact_author.address"


def test_find_malformed_fields_prefers_legacy_suggestion_for_legacy_notation_file():
    manager = _manager()
    content = "data_t\n_cell_length_a 5.0\n_audit_contact.author_address ;Street\n;\n"

    malformed = manager.find_malformed_fields(content)

    assert len(malformed) == 1
    assert malformed[0]["original"] == "_audit_contact.author_address"
    assert malformed[0]["suggested"] == "_audit_contact_author_address"


def test_find_malformed_fields_prefers_legacy_suggestion_for_mixed_notation_file():
    manager = _manager()
    content = "data_t\n_cell_length_a 5.0\n_cell.length_b 6.0\n_audit_contact.author_address ;Street\n;\n"

    malformed = manager.find_malformed_fields(content)

    assert len(malformed) == 1
    assert malformed[0]["original"] == "_audit_contact.author_address"
    assert malformed[0]["suggested"] == "_audit_contact_author_address"


def test_get_modern_replacement_for_deprecated_field_with_explicit_replacement():
    manager = _manager()

    # Pick a deprecated field that explicitly declares replacement_by in the
    # loaded dictionary metadata, then verify manager-level lookup resolves it.
    candidate = None
    for metadata in manager.parser._field_metadata.values():
        if metadata.replacement_by:
            candidate = metadata.definition_id
            break

    assert candidate is not None
    replacement = manager.get_modern_replacement(candidate)
    assert replacement is not None
    assert replacement != candidate


def test_convert_cif_format_legacy_to_modern_changes_field_names():
    manager = _manager()
    content = "data_t\n_cell_length_a 5.0\n"

    converted, changes = manager.convert_cif_format(content, "MODERN")

    assert "_cell.length_a 5.0" in converted
    assert any("Converted '_cell_length_a'" in change for change in changes)
