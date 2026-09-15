"""Regression tests for DataNameValidator loop-column detection.

A loop_'s header field names are columns of a table, not standalone fields:
deleting one requires removing its value from every row too. The validator
flags this via FieldValidationResult.in_loop so the Data Name Validation
dialog can warn before treating a loop column like an ordinary field.
"""

from utils.cif_dictionary_manager import CIFDictionaryManager
from utils.data_name_validator import DataNameValidator


def _validator() -> DataNameValidator:
    manager = CIFDictionaryManager()
    manager._ensure_loaded()
    return DataNameValidator(manager)


def _result_for(report, field_name):
    for bucket in (
        report.valid_fields,
        report.registered_local_fields,
        report.user_allowed_fields,
        report.unknown_fields,
        report.deprecated_fields,
        report.malformed_fields,
        report.malformed_user_allowed_fields,
    ):
        for result in bucket:
            if result.field_name.lower() == field_name.lower():
                return result
    return None


def test_standalone_field_is_not_flagged_as_in_loop():
    validator = _validator()
    content = "data_test\n_unknown_standalone value\n"
    report = validator.validate_cif_content(content)
    result = _result_for(report, "_unknown_standalone")
    assert result is not None
    assert result.in_loop is False


def test_loop_column_is_flagged_as_in_loop():
    validator = _validator()
    content = (
        "data_test\n"
        "loop_\n"
        "_unknown_col_a\n"
        "_unknown_col_b\n"
        "1 2\n"
        "3 4\n"
    )
    report = validator.validate_cif_content(content)
    result_a = _result_for(report, "_unknown_col_a")
    result_b = _result_for(report, "_unknown_col_b")
    assert result_a is not None and result_a.in_loop is True
    assert result_b is not None and result_b.in_loop is True


def test_field_after_loop_data_rows_is_not_in_loop():
    validator = _validator()
    content = (
        "data_test\n"
        "loop_\n"
        "_unknown_col_a\n"
        "1\n"
        "2\n"
        "\n"
        "_unknown_after_loop value\n"
    )
    report = validator.validate_cif_content(content)
    in_loop_result = _result_for(report, "_unknown_col_a")
    after_result = _result_for(report, "_unknown_after_loop")
    assert in_loop_result.in_loop is True
    assert after_result.in_loop is False


def test_loop_field_name_with_inline_data_value_is_still_flagged():
    """The last header line of a loop_ may carry an inline value that starts
    the data section on the same line - the field name itself is still a
    loop column."""
    validator = _validator()
    content = (
        "data_test\n"
        "loop_\n"
        "_unknown_col_a\n"
        "_unknown_col_b  1 2\n"
        "3 4\n"
    )
    report = validator.validate_cif_content(content)
    result_b = _result_for(report, "_unknown_col_b")
    assert result_b is not None
    assert result_b.in_loop is True


def test_loop_detection_resets_across_data_blocks():
    validator = _validator()
    content = (
        "data_a\n"
        "loop_\n"
        "_unknown_col_a\n"
        "1\n"
        "2\n"
        "\n"
        "data_b\n"
        "_unknown_standalone value\n"
    )
    report = validator.validate_cif_content(content)
    loop_result = _result_for(report, "_unknown_col_a")
    standalone_result = _result_for(report, "_unknown_standalone")
    assert loop_result.in_loop is True
    assert standalone_result.in_loop is False
