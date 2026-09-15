"""Tests for utils.cif_block_rename.rename_data_block."""

import pytest

from utils.cif_block_rename import rename_data_block, validate_new_block_name


def test_renames_header_line():
    content = "data_old_name\n_cell_length_a 5.0\n"
    result = rename_data_block(content, "old_name", "new_name")
    assert "data_new_name" in result.content
    assert "data_old_name" not in result.content
    assert any("Renamed data_old_name to data_new_name" in c for c in result.changes)


def test_renames_vrf_field_names():
    content = (
        "data_2025NCS0255_aP0\n"
        "_cell_length_a 5.0\n"
        "_vrf_PLAT020_2025NCS0255_aP0\n"
        ";\n"
        "PROBLEM: something\n"
        "RESPONSE: something else\n"
        ";\n"
        "_vrf_PLAT911_2025NCS0255_aP0\n"
        ";\n"
        "PROBLEM: another\n"
        "RESPONSE: reply\n"
        ";\n"
    )
    result = rename_data_block(content, "2025NCS0255_aP0", "final_name")
    assert "_vrf_PLAT020_final_name" in result.content
    assert "_vrf_PLAT911_final_name" in result.content
    assert "2025NCS0255_aP0" not in result.content
    assert any("2 VRF field names" in c for c in result.changes)


def test_updates_audit_block_code_when_matching():
    content = (
        "data_old_name\n"
        "_audit.block_code old_name\n"
        "_cell_length_a 5.0\n"
    )
    result = rename_data_block(content, "old_name", "new_name")
    assert "_audit.block_code new_name" in result.content


def test_does_not_touch_audit_block_code_when_different():
    content = (
        "data_old_name\n"
        "_audit.block_code some_other_code\n"
    )
    result = rename_data_block(content, "old_name", "new_name")
    assert "_audit.block_code some_other_code" in result.content


def test_updates_legacy_audit_block_code_alias_with_quotes():
    content = (
        "data_old_name\n"
        "_audit_block_code   'old_name'\n"
    )
    result = rename_data_block(content, "old_name", "new_name")
    assert "_audit_block_code   'new_name'" in result.content


def test_renames_fcf_echo_header():
    content = (
        "data_old_name\n"
        "_iucr_refine_fcf_details\n"
        ";\n"
        "data_old_name\n"
        "_shelx_refln_list_code 4\n"
        ";\n"
    )
    result = rename_data_block(content, "old_name", "new_name")
    lines = result.content.splitlines()
    assert lines[3] == "data_new_name"
    assert any("_iucr_refine_fcf_details" in c for c in result.changes)


def test_fcf_echo_untouched_when_it_does_not_match_old_name():
    content = (
        "data_old_name\n"
        "_iucr_refine_fcf_details\n"
        ";\n"
        "data_something_unrelated\n"
        ";\n"
    )
    result = rename_data_block(content, "old_name", "new_name")
    assert "data_something_unrelated" in result.content


def test_updates_cross_block_audit_link_simple_field():
    content = (
        "data_block_a\n"
        "_audit_link.block_code block_b\n"
        "data_block_b\n"
        "_cell_length_a 5.0\n"
    )
    result = rename_data_block(content, "block_b", "block_c")
    assert "_audit_link.block_code block_c" in result.content
    assert "data_block_c" in result.content


def test_updates_cross_block_audit_link_in_loop():
    content = (
        "data_block_a\n"
        "loop_\n"
        "_audit_link.id\n"
        "_audit_link.block_code\n"
        "1 block_b\n"
        "2 .\n"
        "data_block_b\n"
        "_cell_length_a 5.0\n"
    )
    result = rename_data_block(content, "block_b", "block_c")
    assert "block_c" in result.content
    lines = result.content.splitlines()
    loop_lines = "\n".join(lines)
    assert "1 block_c" in loop_lines or "block_c" in loop_lines
    # The self-reference '.' must be left alone.
    assert "2 ." in loop_lines


def test_does_not_touch_unrelated_text_matching_old_name():
    content = (
        "data_old_name\n"
        "_chemical_name_common 'old_name'\n"
    )
    result = rename_data_block(content, "old_name", "new_name")
    assert "_chemical_name_common 'old_name'" in result.content
    assert not any("_chemical_name_common" in c for c in result.changes)


def test_no_op_when_new_name_equals_old_name():
    content = "data_old_name\n_cell_length_a 5.0\n"
    result = rename_data_block(content, "old_name", "old_name")
    assert result.content == content
    assert result.changes == []
    assert result.changed is False


def test_raises_when_block_not_found():
    content = "data_old_name\n"
    with pytest.raises(ValueError):
        rename_data_block(content, "missing_block", "new_name")


def test_raises_on_duplicate_block_name():
    content = "data_a\n_x 1\ndata_b\n_x 2\n"
    with pytest.raises(ValueError):
        rename_data_block(content, "a", "b")


@pytest.mark.parametrize("new_name", ["", "  ", "has space", "bad#name", "bad'name"])
def test_validate_rejects_bad_names(new_name):
    assert validate_new_block_name(new_name, ["old_name"], "old_name") is not None


def test_validate_allows_same_name_noop():
    assert validate_new_block_name("old_name", ["old_name"], "old_name") is None


def test_validate_allows_unique_new_name():
    assert validate_new_block_name("brand_new", ["old_name"], "old_name") is None
