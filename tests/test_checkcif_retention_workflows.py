"""Regression tests for checkCIF-compatibility field retention.

Some deprecated legacy field names (e.g. _cell_measurement_temperature) must
be retained even when their modern successor is already present, because
checkCIF's PLAT197 check does not yet recognise the modern name. See
field_rules/checkcif_compatibility.cif_rules and the README.
"""

from utils.CIF_parser import CIFParser
from utils.cif_dictionary_manager import CIFDictionaryManager
from utils.cif_format_converter import CIFFormatConverter
from utils.data_name_validator import DataNameValidator, FieldCategory


def _manager() -> CIFDictionaryManager:
    manager = CIFDictionaryManager()
    manager._ensure_loaded()
    return manager


def test_is_checkcif_compatibility_field_matches_configured_list():
    manager = _manager()

    assert manager.is_checkcif_compatibility_field("_cell_measurement_temperature") is True
    assert manager.is_checkcif_compatibility_field("_CELL_MEASUREMENT_TEMPERATURE") is True
    assert manager.is_checkcif_compatibility_field("_diffrn_ambient_temperature") is False


def test_format_converter_and_dictionary_manager_share_the_same_compatibility_list():
    manager = _manager()
    converter = CIFFormatConverter(manager)

    assert converter.checkcif_compatibility_fields == manager.get_checkcif_compatibility_fields()


def test_deprecated_field_result_flags_checkcif_retention_when_successor_present():
    manager = _manager()
    validator = DataNameValidator(manager)

    content = "\n".join(
        [
            "data_test",
            "_cell_measurement_temperature 293",
            "_diffrn_ambient_temperature 293",
            "",
        ]
    )

    report = validator.validate_cif_content(content)

    matches = [
        r for r in report.deprecated_fields
        if r.field_name.lower() == "_cell_measurement_temperature"
    ]
    assert len(matches) == 1
    result = matches[0]
    assert result.category == FieldCategory.DEPRECATED
    assert result.successor_already_exists is True
    assert result.checkcif_retain_required is True


def test_deprecated_field_not_flagged_for_checkcif_retention_when_not_in_compat_list():
    manager = _manager()
    validator = DataNameValidator(manager)

    # _diffrn_radiation_source is deprecated but not a checkCIF-compatibility field.
    content = "\n".join(
        [
            "data_test",
            "_diffrn_radiation_source 'Rotating anode'",
            "",
        ]
    )

    report = validator.validate_cif_content(content)

    matches = [
        r for r in report.deprecated_fields
        if r.field_name.lower() == "_diffrn_radiation_source"
    ]
    assert len(matches) == 1
    assert matches[0].checkcif_retain_required is False


def test_add_legacy_compatibility_fields_uses_the_shared_compatibility_list():
    """Regression: CIF_parser.add_legacy_compatibility_fields() used to carry
    its own hardcoded, out-of-sync field list. It must now source fields from
    the same field_rules/checkcif_compatibility.cif_rules list as everything
    else, including fields not present in the old hardcoded list."""
    manager = _manager()
    parser = CIFParser()

    # _geom_angle is in checkcif_compatibility.cif_rules but was NOT part of
    # the old hardcoded list in CIF_parser.py - it must be covered now.
    content = "\n".join(
        [
            "data_test",
            "_geom_angle.value 109.5",
            "",
        ]
    )
    parser.parse_file(content)

    report = parser.add_legacy_compatibility_fields(manager)

    assert "_geom_angle" in parser.fields
    assert "_geom_angle" in report


def test_compatibility_fields_are_split_into_deprecation_and_notation_issues():
    """The .cif_rules file tags each field with its issue type via a '###'
    annotation line; deprecation-issue fields are is_field_deprecated,
    notation-issue fields are not."""
    manager = _manager()

    deprecation_fields = manager.get_checkcif_deprecation_fields()
    notation_fields = manager.get_checkcif_notation_fields()

    assert "_cell_measurement_temperature" in deprecation_fields
    assert "_geom_angle" in notation_fields
    assert "_atom_site_aniso_label" in notation_fields

    # Categories must not overlap, and every field is deprecated iff it's
    # tagged as a deprecation issue (empirically true for the current list).
    assert deprecation_fields.isdisjoint(notation_fields)
    for field in deprecation_fields:
        assert manager.is_field_deprecated(field) is True
    for field in notation_fields:
        assert manager.is_field_deprecated(field) is False


def test_alias_conflict_resolution_keeps_notation_issue_field_for_simple_fields():
    """Regression: resolving a legacy/modern alias conflict for a checkCIF
    'modern notation issue' field (e.g. _geom_angle) must never drop the
    legacy form, even if the user chose to keep only the modern one."""
    manager = _manager()

    content = "data_test\n_geom_angle 109.5\n_geom_angle.value 109.5\n"
    conflicts = manager.detect_field_aliases_in_cif(content)
    canonical = next(iter(conflicts))

    resolved, changes = manager.apply_field_conflict_resolutions(
        content, {canonical: ("_geom_angle.value", "109.5", False)}
    )

    assert "_geom_angle 109.5" in resolved
    assert "_geom_angle.value 109.5" in resolved
    assert any("Synchronized alias" in c for c in changes)


def test_alias_conflict_resolution_keeps_notation_issue_field_in_loop():
    """Regression: loop-based alias resolution can't keep both aliases, so it
    must retain the checkCIF-required legacy field instead of the user's
    chosen modern one (e.g. _atom_site_aniso_label over _atom_site_aniso.label)."""
    manager = _manager()

    content = "\n".join(
        [
            "data_test",
            "loop_",
            "_atom_site_aniso_label",
            "_atom_site_aniso.label",
            "C1",
            "C1",
            "",
        ]
    )
    conflicts = manager.detect_field_aliases_in_cif(content)
    canonical = next(iter(conflicts))

    resolved, changes = manager.apply_field_conflict_resolutions(
        content, {canonical: ("_atom_site_aniso.label", "", False)}
    )

    assert "_atom_site_aniso_label" in resolved
    assert "_atom_site_aniso.label" not in resolved
    assert any("checkCIF requires this legacy field name" in c for c in changes)
