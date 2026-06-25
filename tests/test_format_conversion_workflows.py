"""Tests for CIF format conversion behavior and compliance helpers."""

import pytest

from utils.cif_format_converter import CIFFormatConverter
from utils.cif_dictionary_manager import CIFDictionaryManager, FieldNotation
from utils.CIF_parser import CIFParser


@pytest.fixture
def converter() -> CIFFormatConverter:
    return CIFFormatConverter(CIFDictionaryManager())


def test_convert_to_modern_notation_converts_known_legacy_field(converter: CIFFormatConverter):
    content = "_cell_length_a 5.0"
    converted, changes = converter.convert_to_modern_notation(content)

    assert "_cell.length_a 5.0" in converted
    assert len(changes) >= 1


def test_convert_to_legacy_notation_converts_known_modern_field(converter: CIFFormatConverter):
    content = "_cell.length_a 5.0"
    converted, changes = converter.convert_to_legacy_notation(content)

    assert "_cell_length_a 5.0" in converted
    assert len(changes) >= 1


def test_convert_to_modern_adds_cif2_header(converter: CIFFormatConverter):
    content = "data_test\n_cell_length_a 5.0\n"
    converted, _ = converter.convert_to_modern(content)

    assert converted.startswith("#\\#CIF_2.0")


def test_convert_to_legacy_replaces_cif2_header(converter: CIFFormatConverter):
    content = "#\\#CIF_2.0\ndata_test\n_cell.length_a 5.0\n"
    converted, changes = converter.convert_to_legacy(content)

    assert "#\\#CIF_1.1" in converted
    assert not converted.splitlines()[0].startswith("#\\#CIF_2.0")
    assert any("CIF 2.0 header" in change for change in changes)


def test_fix_mixed_format_to_modern(converter: CIFFormatConverter):
    content = "_cell_length_a 5.0\n_cell.length_b 6.0\n"
    converted, _ = converter.fix_mixed_format(content, FieldNotation.MODERN)

    assert "_cell.length_a 5.0" in converted
    assert "_cell.length_b 6.0" in converted


def test_roundtrip_conversion_preserves_values_for_basic_fields(converter: CIFFormatConverter):
    original = "\n".join(
        [
            "data_test",
            "_cell_length_a 5.0",
            "_cell_length_b 6.0",
        ]
    )

    modern, _ = converter.convert_to_modern_notation(original)
    legacy, _ = converter.convert_to_legacy_notation(modern)

    parser_a = CIFParser()
    parser_b = CIFParser()
    fields_original = parser_a.parse_file(original)
    fields_roundtrip = parser_b.parse_file(legacy)

    assert fields_original["_cell_length_a"].value == fields_roundtrip["_cell_length_a"].value
    assert fields_original["_cell_length_b"].value == fields_roundtrip["_cell_length_b"].value


def test_detect_cif2_constructs_flags_list_but_not_formula_brackets(converter: CIFFormatConverter):
    has_list = converter.detect_cif2_constructs("_field [1 2 3]")
    formula_brackets = converter.detect_cif2_constructs("_chemical_formula_sum '[Cu(CN)2]'")

    assert "list values [...]" in has_list
    assert "list values [...]" not in formula_brackets


def test_unknown_field_warning_added_for_legacy_conversion(converter: CIFFormatConverter):
    content = "_this_field_does_not_exist.anything 1"
    _, changes = converter.convert_to_legacy_notation(content)

    assert any("unknown data name" in change.lower() for change in changes)


def test_ensure_cif1_compliant_raises_for_cif2_constructs(converter: CIFFormatConverter):
    content = "#\\#CIF_2.0\ndata_test\n_field [1 2 3]\n"

    with pytest.raises(ValueError):
        converter.ensure_cif1_compliant(content)
