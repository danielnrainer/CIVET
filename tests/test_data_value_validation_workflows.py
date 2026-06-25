"""Behavior-focused tests for CIF data-value validation workflows."""

import pytest

from utils.CIF_parser import CIFParser
from utils.cif_data_validator import CIFDataValidator
from utils.cif_dictionary_manager import CIFDictionaryManager


def _manager() -> CIFDictionaryManager:
    manager = CIFDictionaryManager()
    manager._ensure_loaded()
    return manager


def _validate(content: str):
    parser = CIFParser()
    parser.parse_file(content)
    validator = CIFDataValidator()
    manager = _manager()
    return validator.validate(parser, manager)


def test_numeric_type_mismatch_yields_warning():
    manager = _manager()
    numeric_candidate = None
    for metadata in manager.parser._field_metadata.values():
        type_name = (metadata.type_contents or "").strip().lower()
        if type_name in {"real", "float", "integer", "int", "count", "index", "numb"}:
            numeric_candidate = metadata.definition_id
            break

    if numeric_candidate is None:
        pytest.skip("No numeric-typed dictionary field found")

    parser = CIFParser()
    parser.parse_file(f"{numeric_candidate} not_a_number\\n")
    issues = CIFDataValidator().validate(parser, manager)

    assert any(i.issue_type == "type_mismatch" and i.severity == "warning" for i in issues)


def test_special_missing_values_are_accepted_for_typed_fields():
    issues = _validate("_cell.length_a ?\n")

    assert all(i.issue_type != "type_mismatch" for i in issues)


def test_incomplete_loop_row_reports_structural_error():
    content = "\n".join(
        [
            "loop_",
            "_cell.length_a",
            "_cell.length_b",
            "1",
        ]
    )
    issues = _validate(content)

    assert any(i.issue_type == "loop_incomplete" and i.severity == "error" for i in issues)


def test_unknown_field_is_not_flagged_as_type_or_enum_violation_without_metadata():
    issues = _validate("_this_field_does_not_exist 123\n")

    assert issues == []


def test_enumeration_violation_detected_for_dictionary_enum_field():
    manager = _manager()
    candidate = None
    for metadata in manager.parser._field_metadata.values():
        if metadata.enumeration_values:
            candidate = metadata.definition_id
            break

    if candidate is None:
        pytest.skip("No dictionary field with enumeration values found")

    parser = CIFParser()
    parser.parse_file(f"{candidate} __definitely_invalid_enum_value__\n")
    issues = CIFDataValidator().validate(parser, manager)

    assert any(i.issue_type == "enum_violation" and i.severity == "error" for i in issues)
