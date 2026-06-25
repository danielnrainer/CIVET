"""Tests for CIF parsing behavior (fields, loops, CIF2 values)."""

from utils.CIF_parser import CIFParser, CIFField


def test_parse_simple_field_with_value():
    parser = CIFParser()
    fields = parser.parse_file("_cell_length_a 5.0")

    assert "_cell_length_a" in fields
    assert fields["_cell_length_a"].value == "5.0"
    assert fields["_cell_length_a"].line_number == 1


def test_parse_quoted_value_strips_outer_quotes():
    parser = CIFParser()
    fields = parser.parse_file("_chemical_name_common 'copper sulfate'")

    assert fields["_chemical_name_common"].value == "copper sulfate"


def test_parse_multiline_semicolon_value_content_on_same_line():
    parser = CIFParser()
    content = "_publ_section_comment\n;first line\nsecond line\n;"
    fields = parser.parse_file(content)

    assert fields["_publ_section_comment"].is_multiline is True
    assert "first line" in fields["_publ_section_comment"].value
    assert "second line" in fields["_publ_section_comment"].value


def test_parse_multiline_triple_quoted_value():
    parser = CIFParser()
    content = "_field\n\"\"\"line1\nline2\"\"\""
    fields = parser.parse_file(content)

    assert fields["_field"].is_multiline is True
    assert fields["_field"].value == "line1\nline2"


def test_parse_simple_loop_rows_and_columns():
    parser = CIFParser()
    content = "\n".join(
        [
            "loop_",
            "_atom_site_label",
            "_atom_site_fract_x",
            "_atom_site_fract_y",
            "C1 0.123 0.456",
            "C2 0.789 0.012",
        ]
    )
    parser.parse_file(content)

    assert len(parser.loops) == 1
    loop = parser.loops[0]
    assert loop.field_names == ["_atom_site_label", "_atom_site_fract_x", "_atom_site_fract_y"]
    assert loop.data_rows[0] == ["C1", "0.123", "0.456"]
    assert loop.data_rows[1] == ["C2", "0.789", "0.012"]


def test_parse_loop_marks_incomplete_last_row():
    parser = CIFParser()
    content = "\n".join(
        [
            "loop_",
            "_a",
            "_b",
            "1",
        ]
    )
    parser.parse_file(content)

    loop = parser.loops[0]
    assert loop.has_incomplete_last_row is True
    assert loop.incomplete_row_actual_count == 1
    assert loop.data_rows[0] == ["1", ""]


def test_parse_cif2_list_and_table_value_types():
    parser = CIFParser()
    content = "\n".join(
        [
            "_list_field [1 2 3]",
            '_table_field {"k": 1}',
        ]
    )
    fields = parser.parse_file(content)

    assert fields["_list_field"].value_type == CIFField.TYPE_LIST
    assert fields["_list_field"].is_list is True
    assert fields["_table_field"].value_type == CIFField.TYPE_TABLE
    assert fields["_table_field"].is_table is True
