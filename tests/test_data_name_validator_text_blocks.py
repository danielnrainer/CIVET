"""Regression tests for DataNameValidator text-block handling.

_iucr_refine_fcf_details and similar multiline (semicolon-delimited) values can
contain echoed CIF-like text (e.g. software re-printing the refinement data
block). Lines inside such a block must never be treated as real field
definitions during data-name validation.
"""

from utils.cif_dictionary_manager import CIFDictionaryManager
from utils.data_name_validator import DataNameValidator


def _validator() -> DataNameValidator:
    manager = CIFDictionaryManager()
    manager._ensure_loaded()
    return DataNameValidator(manager)


def _all_reported_field_names(report):
    names = set()
    for bucket in (
        report.valid_fields,
        report.registered_local_fields,
        report.user_allowed_fields,
        report.unknown_fields,
        report.deprecated_fields,
        report.malformed_fields,
    ):
        names.update(result.field_name for result in bucket)
    return names


def test_deprecated_field_name_inside_text_block_is_not_reported():
    validator = _validator()
    content = (
        "data_test\n"
        "_iucr_refine_fcf_details\n"
        ";\n"
        "data_2025NCS0255_aP0\n"
        "_symmetry_space_group_name_H-M    'P -1'\n"
        "_symmetry_space_group_name_Hall   '-P 1'\n"
        ";\n"
        "_cell_length_a 5.0\n"
    )

    report = validator.validate_cif_content(content)

    reported_names = _all_reported_field_names(report)
    assert "_symmetry_space_group_name_H-M" not in reported_names
    assert "_symmetry_space_group_name_Hall" not in reported_names


def test_field_after_text_block_is_still_validated():
    validator = _validator()
    content = (
        "data_test\n"
        "_iucr_refine_fcf_details\n"
        ";\n"
        "_some_embedded_field   1\n"
        ";\n"
        "_cell_length_a 5.0\n"
    )

    report = validator.validate_cif_content(content)

    reported_names = _all_reported_field_names(report)
    assert "_some_embedded_field" not in reported_names
    assert "_cell_length_a" in reported_names


def test_text_block_with_inline_content_on_opening_line_is_tracked():
    """The opening ';' may carry content on the same line, e.g. '; asdbasdh'."""
    validator = _validator()
    content = (
        "data_test\n"
        "_dummy_data_name\n"
        "; asdbasdh\n"
        "_embedded_field_looking_line 1\n"
        ";\n"
        "_cell_length_a 5.0\n"
    )

    report = validator.validate_cif_content(content)

    reported_names = _all_reported_field_names(report)
    assert "_embedded_field_looking_line" not in reported_names
    assert "_cell_length_a" in reported_names


def test_triple_double_quoted_multiline_value_is_tracked():
    validator = _validator()
    content = (
        "data_test\n"
        "_dummy_data_name\n"
        '"""\n'
        "_embedded_field_looking_line 1\n"
        '"""\n'
        "_cell_length_a 5.0\n"
    )

    report = validator.validate_cif_content(content)

    reported_names = _all_reported_field_names(report)
    assert "_embedded_field_looking_line" not in reported_names
    assert "_cell_length_a" in reported_names


def test_triple_single_quoted_multiline_value_opened_inline_is_tracked():
    validator = _validator()
    content = (
        "data_test\n"
        "_dummy_data_name    '''some text\n"
        "_embedded_field_looking_line 1\n"
        "still going'''\n"
        "_cell_length_a 5.0\n"
    )

    report = validator.validate_cif_content(content)

    reported_names = _all_reported_field_names(report)
    assert "_embedded_field_looking_line" not in reported_names
    assert "_cell_length_a" in reported_names


def test_single_line_triple_quoted_value_does_not_open_a_block():
    validator = _validator()
    content = (
        'data_test\n'
        '_dummy_data_name """closed on one line"""\n'
        '_cell_length_a 5.0\n'
    )

    report = validator.validate_cif_content(content)

    reported_names = _all_reported_field_names(report)
    assert "_cell_length_a" in reported_names
