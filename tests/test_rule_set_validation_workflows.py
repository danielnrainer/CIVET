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
