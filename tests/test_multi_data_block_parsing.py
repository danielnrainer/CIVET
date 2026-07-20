"""Tests for the per-data-block parse view (CIFDataBlock, CIFParser.blocks).

Phase 1 of multi-data-block support (.github/multi_data_block_plan.md):
the parser exposes each data_ block individually while the flat
fields/loops view keeps its historical whole-file (last block wins)
behaviour for existing callers.
"""

from utils.CIF_parser import CIFParser, count_data_blocks, list_data_block_names


MULTI_BLOCK_CIF = "\n".join(
    [
        "#\\#CIF_2.0",
        "# a leading comment",
        "data_xtal_100K",
        "_diffrn.ambient_temperature 100",
        "_diffrn_source 'sealed tube'",
        "loop_",
        "_atom_site_label",
        "_atom_site_fract_x",
        "C1 0.1",
        "",
        "data_xtal_200K",
        "_diffrn.ambient_temperature 200",
        "_diffrn_source 'sealed tube'",
    ]
)


def test_single_block_file_has_one_block():
    parser = CIFParser()
    parser.parse_file("data_test\n_cell_length_a 5.0")

    assert len(parser.blocks) == 1
    assert parser.has_multiple_blocks() is False
    block = parser.blocks[0]
    assert block.name == "test"
    assert block.header_line == "data_test"
    assert block.is_preamble is False
    assert block.get_field_value("_cell_length_a") == "5.0"


def test_preamble_collects_content_before_first_data_block():
    parser = CIFParser()
    parser.parse_file(MULTI_BLOCK_CIF)

    assert parser.preamble.is_preamble is True
    preamble_lines = [entry["content"] for entry in parser.preamble.content_blocks]
    assert "#\\#CIF_2.0" in preamble_lines
    assert "# a leading comment" in preamble_lines
    assert parser.preamble.fields == {}


def test_fields_are_scoped_to_their_block():
    parser = CIFParser()
    parser.parse_file(MULTI_BLOCK_CIF)

    assert parser.has_multiple_blocks() is True
    assert parser.get_block_names() == ["xtal_100K", "xtal_200K"]
    assert parser.get_block_field_value("xtal_100K", "_diffrn.ambient_temperature") == "100"
    assert parser.get_block_field_value("xtal_200K", "_diffrn.ambient_temperature") == "200"
    # The loop only exists in the first block
    assert len(parser.blocks[0].loops) == 1
    assert parser.blocks[1].loops == []
    assert parser.blocks[0].get_field_value("_atom_site_label") == "(in loop)"
    assert parser.blocks[1].has_field("_atom_site_label") is False


def test_flat_view_keeps_last_block_wins_compatibility():
    parser = CIFParser()
    fields = parser.parse_file(MULTI_BLOCK_CIF)

    # Historical behaviour relied upon by single-block callers
    assert fields["_diffrn.ambient_temperature"].value == "200"
    assert parser.get_field_value("_diffrn_source") == "sealed tube"


def test_get_block_accepts_prefix_and_is_case_insensitive():
    parser = CIFParser()
    parser.parse_file(MULTI_BLOCK_CIF)

    assert parser.get_block("data_xtal_100K").name == "xtal_100K"
    assert parser.get_block("XTAL_100K").name == "xtal_100K"
    assert parser.get_block("DATA_XTAL_200K").name == "xtal_200K"
    assert parser.get_block("missing") is None


def test_get_field_values_by_block_reports_divergence():
    parser = CIFParser()
    parser.parse_file(MULTI_BLOCK_CIF)

    temperatures = parser.get_field_values_by_block("_diffrn.ambient_temperature")
    assert temperatures == {"xtal_100K": "100", "xtal_200K": "200"}

    sources = parser.get_field_values_by_block("_diffrn_source")
    assert set(sources.values()) == {"sealed tube"}

    missing = parser.get_field_values_by_block("_not_present")
    assert missing == {"xtal_100K": None, "xtal_200K": None}


def test_data_inside_text_block_does_not_start_a_block():
    content = "\n".join(
        [
            "data_real",
            "_iucr_refine_fcf_details",
            ";",
            "data_fake_inside_text",
            "_cell_length_a 9.9",
            ";",
            "_cell_length_a 5.0",
        ]
    )
    parser = CIFParser()
    parser.parse_file(content)

    assert parser.get_block_names() == ["real"]
    assert parser.get_block_field_value("real", "_cell_length_a") == "5.0"
    assert count_data_blocks(content) == 1


def test_count_data_blocks():
    assert count_data_blocks("") == 0
    assert count_data_blocks("_cell_length_a 5.0") == 0
    assert count_data_blocks("data_one\n_a 1") == 1
    assert count_data_blocks(MULTI_BLOCK_CIF) == 2
    # data_ in a comment line is not a block
    assert count_data_blocks("# data_commented\ndata_real\n_a 1") == 1


def test_list_data_block_names():
    assert list_data_block_names("") == []
    assert list_data_block_names(MULTI_BLOCK_CIF) == ["xtal_100K", "xtal_200K"]
    assert list_data_block_names("# data_commented\ndata_real\n_a 1") == ["real"]


def test_generate_cif_content_round_trips_all_blocks():
    parser = CIFParser()
    parser.parse_file(MULTI_BLOCK_CIF)
    regenerated = parser.generate_cif_content()

    assert "data_xtal_100K" in regenerated
    assert "data_xtal_200K" in regenerated
    # Both temperature values survive regeneration
    assert "100" in regenerated
    assert "200" in regenerated

    # Reparsing the regenerated content yields the same block structure
    reparsed = CIFParser()
    reparsed.parse_file(regenerated)
    assert reparsed.get_block_names() == ["xtal_100K", "xtal_200K"]
    assert reparsed.get_block_field_value("xtal_100K", "_diffrn.ambient_temperature") == "100"
    assert reparsed.get_block_field_value("xtal_200K", "_diffrn.ambient_temperature") == "200"


def test_reparse_resets_block_state():
    parser = CIFParser()
    parser.parse_file(MULTI_BLOCK_CIF)
    parser.parse_file("data_only\n_cell_length_a 1.0")

    assert parser.get_block_names() == ["only"]
    assert parser.preamble.content_blocks == []
