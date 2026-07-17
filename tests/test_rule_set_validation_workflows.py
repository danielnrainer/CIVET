"""Behavior-focused tests for rule-set validation workflows."""

import pytest

from utils.cif_dictionary_manager import CIFDictionaryManager
from utils.field_rules_validator import (
    AutoFixType,
    CIFFormatAnalyzer,
    FieldRulesValidator,
    IssueType,
)


def _manager() -> CIFDictionaryManager:
    manager = CIFDictionaryManager()
    manager._ensure_loaded()
    return manager


def test_rule_content_format_analyzer_detects_legacy_modern_and_mixed():
    legacy = "_cell_length_a 1\n_cell_length_b 2\n_cell_length_c 3\n"
    modern = "_cell.length_a 1\n_cell.length_b 2\n_cell.length_c 3\n"
    mixed = "_cell_length_a 1\n_cell.length_b 2\n"

    assert CIFFormatAnalyzer.analyze_cif_format(legacy) == "legacy"
    assert CIFFormatAnalyzer.analyze_cif_format(modern) == "modern"
    assert CIFFormatAnalyzer.analyze_cif_format(mixed) == "Mixed"


def test_validator_auto_switches_target_to_legacy_for_mixed_rules_when_requested_modern():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    rules = "_cell_length_a 1\n_cell.length_b 2\n"

    result = validator.validate_field_rules(rules, target_format="modern")

    assert result.target_format_used == "legacy"


def test_truly_unknown_field_is_reported_with_manual_verification_guidance():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    rules = "_definitely_not_a_known_field 5.0\n"

    result = validator.validate_field_rules(rules, target_format="modern")
    unknown_issues = [i for i in result.issues if i.issue_type == IssueType.UNKNOWN_FIELD]

    assert len(unknown_issues) == 1
    issue = unknown_issues[0]
    assert "Verify field name" in issue.suggested_fix
    assert issue.auto_fix_type == AutoFixType.NO


def test_deprecated_field_issue_reported_when_not_in_checkcif_compat_list():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    compat_fields = validator._load_checkcif_compatibility_fields()

    candidate = None
    for metadata in manager.parser._field_metadata.values():
        field_name = metadata.definition_id
        if manager.is_field_deprecated(field_name) and field_name not in compat_fields:
            candidate = field_name
            break

    if candidate is None:
        pytest.skip("No deprecated non-compatibility field available in loaded dictionaries")

    rules = f"{candidate} 1\n"
    result = validator.validate_field_rules(rules, target_format="modern")
    deprecated_issues = [i for i in result.issues if i.issue_type == IssueType.DEPRECATED_FIELD]

    assert len(deprecated_issues) >= 1


def test_convert_field_rules_notation_converts_known_fields_in_action_lines():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    rules = (
        "_cell_length_a 1\n"
        "RENAME: _cell_length_b _cell_length_c\n"
        "CALCULATE: _cell_volume = _cell_length_a * _cell_length_b * _cell_length_c\n"
    )

    converted, changes = validator.convert_field_rules_notation(rules, target_notation="modern")

    assert "_cell.length_a 1" in converted
    assert "RENAME: _cell.length_b _cell.length_c" in converted
    assert "CALCULATE: _cell.volume = _cell.length_a * _cell.length_b * _cell.length_c" in converted
    assert any("Converted _cell_length_a -> _cell.length_a" in c for c in changes)


def test_convert_field_rules_notation_to_legacy_preserves_modern_only_fields():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    rules = "_diffrn.flux_density 123\n"

    converted, changes = validator.convert_field_rules_notation(rules, target_notation="legacy")

    assert converted == rules
    assert any("no direct legacy alias" in c for c in changes)


def test_format_analyzer_counts_fields_inside_if_blocks():
    # A field embedded only in an IF condition / nested body must still count
    # towards format detection, otherwise a rules file whose top-level lines
    # happen to be legacy but whose IF blocks are all modern would be
    # misclassified.
    modern_via_if_blocks = (
        "IF: _diffrn_radiation.probe electron\n"
        "    CHECK: _diffrn.ambient_temperature 293\n"
        "ENDIF\n"
        "IF NOT: _cell.measurement_temperature\n"
        "    CHECK: _cell.measurement_temperature 293\n"
        "ENDIF\n"
    )

    assert CIFFormatAnalyzer.analyze_cif_format(modern_via_if_blocks) == "modern"


def test_unknown_field_used_only_in_if_condition_is_reported():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    rules = (
        "IF: _definitely_not_a_known_field electron\n"
        "    CHECK: _diffrn.ambient_temperature 293\n"
        "ENDIF\n"
    )

    result = validator.validate_field_rules(rules, target_format="modern")
    unknown_fields = {i.field_names[0] for i in result.issues if i.issue_type == IssueType.UNKNOWN_FIELD}

    assert "_definitely_not_a_known_field" in unknown_fields


def test_unknown_field_used_only_in_nested_check_inside_if_block_is_reported():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    rules = (
        "IF: _diffrn_radiation.probe electron\n"
        "    IF: _diffrn_measurement.method exists_but_this_is_just_a_value\n"
        "        CHECK: _definitely_not_a_known_field 5.0\n"
        "    ENDIF\n"
        "ENDIF\n"
    )

    result = validator.validate_field_rules(rules, target_format="modern")
    unknown_fields = {i.field_names[0] for i in result.issues if i.issue_type == IssueType.UNKNOWN_FIELD}

    assert "_definitely_not_a_known_field" in unknown_fields


def test_deprecated_field_used_as_if_condition_is_reported():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    compat_fields = validator._load_checkcif_compatibility_fields()

    candidate = None
    for metadata in manager.parser._field_metadata.values():
        field_name = metadata.definition_id
        if manager.is_field_deprecated(field_name) and field_name not in compat_fields:
            candidate = field_name
            break

    if candidate is None:
        pytest.skip("No deprecated non-compatibility field available in loaded dictionaries")

    rules = f"IF: {candidate}\n    CHECK: _diffrn.ambient_temperature 293\nENDIF\n"
    result = validator.validate_field_rules(rules, target_format="modern")
    deprecated_fields = {i.field_names[0] for i in result.issues if i.issue_type == IssueType.DEPRECATED_FIELD}

    assert candidate in deprecated_fields


def test_convert_field_rules_notation_converts_fields_inside_nested_if_blocks():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    rules = (
        "IF: _cell_length_a 1\n"
        "    CHECK: _cell_length_b 2\n"
        "    IF NOT: _cell_length_c\n"
        "        EDIT: _cell_length_c 3\n"
        "        RENAME: _cell_length_a _cell_angle_alpha\n"
        "    ENDIF\n"
        "ENDIF\n"
    )

    converted, changes = validator.convert_field_rules_notation(rules, target_notation="modern")

    # Structure (keywords, nesting, indentation-independent) must survive untouched.
    assert "IF: _cell.length_a 1" in converted
    assert "CHECK: _cell.length_b 2" in converted
    assert "IF NOT: _cell.length_c" in converted
    assert "EDIT: _cell.length_c 3" in converted
    assert "RENAME: _cell.length_a _cell.angle_alpha" in converted
    assert converted.count("ENDIF") == 2
    assert any("Converted _cell_length_a -> _cell.length_a" in c for c in changes)
    assert any("Converted _cell_length_b -> _cell.length_b" in c for c in changes)
    assert any("Converted _cell_length_c -> _cell.length_c" in c for c in changes)
    assert any("Converted _cell_angle_alpha -> _cell.angle_alpha" in c for c in changes)


def test_apply_automatic_fixes_rewrites_mixed_format_field_inside_if_condition():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    # Predominantly modern rules file (so target_format="modern" isn't
    # auto-switched to legacy) with one legacy-notation field used only
    # inside an IF condition.
    rules = (
        "_cell.length_a 1\n"
        "_cell.length_b 2\n"
        "_cell.length_c 3\n"
        "IF: _cell_angle_alpha 1\n"
        "    CHECK: _cell.length_a 1\n"
        "ENDIF\n"
    )

    result = validator.validate_field_rules(rules, target_format="modern")
    assert result.target_format_used == "modern"
    mixed_issues = [i for i in result.issues if i.issue_type == IssueType.MIXED_FORMAT]
    assert any(i.field_names == ["_cell_angle_alpha"] for i in mixed_issues)

    fixed_content, changes = validator.apply_automatic_fixes(rules, result.issues, target_format="modern")

    assert "IF: _cell.angle_alpha 1" in fixed_content
    assert changes


def test_validator_flags_user_reported_missing_endif_instead_of_reporting_no_errors():
    """Regression test for a real user report: a hand-written IF block with a
    nested CHECK and no ENDIF validated as "no errors found", even though the
    rules loader silently drops the entire block (both fields are individually
    known, so the old regex-only field extraction saw nothing wrong)."""
    manager = _manager()
    validator = FieldRulesValidator(manager)
    rules = (
        "IF: _chemical_formula_moiety           'C28 H48 N2 O4'\n"
        "  CHECK: _chemical_formula_weight           476.702\n"
    )

    result = validator.validate_field_rules(rules, target_format="modern")

    assert result.has_issues
    malformed = [i for i in result.issues if i.issue_type == IssueType.MALFORMED_RULE]
    assert len(malformed) == 1
    assert "no matching ENDIF" in malformed[0].description
    assert malformed[0].field_names == ["_chemical_formula_moiety"]
    assert malformed[0].auto_fix_type == AutoFixType.NO


def test_validator_flags_malformed_condition_that_would_otherwise_run_unconditionally():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    rules = "IF: not_a_field electron\n    CHECK: _cell.length_a 1\nENDIF\n"

    result = validator.validate_field_rules(rules, target_format="modern")

    malformed = [i for i in result.issues if i.issue_type == IssueType.MALFORMED_RULE]
    assert len(malformed) == 1
    assert "Malformed condition" in malformed[0].description


def test_validator_flags_malformed_rename_and_calculate_lines():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    rules = "RENAME: _only_one_name\nCALCULATE: _no_expression =\n"

    result = validator.validate_field_rules(rules, target_format="modern")

    malformed_messages = [
        i.description for i in result.issues if i.issue_type == IssueType.MALFORMED_RULE
    ]
    assert len(malformed_messages) == 2
    assert any("Malformed RENAME" in m for m in malformed_messages)
    assert any("Malformed CALCULATE" in m for m in malformed_messages)


def test_validator_reports_no_malformed_issues_for_well_formed_rules():
    manager = _manager()
    validator = FieldRulesValidator(manager)
    rules = (
        "_cell.length_a 1\n"
        "IF: _cell.length_a 1\n"
        "    CHECK: _cell.length_b 2\n"
        "ENDIF\n"
    )

    result = validator.validate_field_rules(rules, target_format="modern")

    malformed = [i for i in result.issues if i.issue_type == IssueType.MALFORMED_RULE]
    assert malformed == []


def test_convert_field_rules_notation_replaces_deprecated_with_successor():
    manager = _manager()
    validator = FieldRulesValidator(manager)

    deprecated_field = None
    successor_field = None
    for metadata in manager.parser._field_metadata.values():
        candidate = metadata.definition_id
        if not manager.is_field_deprecated(candidate):
            continue
        successor = manager.get_modern_equivalent(candidate, prefer_format="modern")
        if successor and successor != candidate:
            deprecated_field = candidate
            successor_field = successor
            break

    if deprecated_field is None or successor_field is None:
        pytest.skip("No deprecated field with successor mapping available")

    rules = f"{deprecated_field} 1\n"
    converted, _ = validator.convert_field_rules_notation(rules, target_notation="modern")

    assert deprecated_field not in converted
    assert successor_field in converted
