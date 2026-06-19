"""Tests for data-name integrity checks and alias conflict resolution."""

from utils.cif_data_name_integrity import (
    get_data_name_conflicts_requiring_resolution,
)
from utils.cif_dictionary_manager import CIFDictionaryManager


def _build_manager() -> CIFDictionaryManager:
    manager = CIFDictionaryManager()
    manager._ensure_loaded()
    return manager


def test_equal_alias_values_are_not_flagged_as_conflict():
    manager = _build_manager()

    content = "\n".join(
        [
            "data_test",
            "_diffrn_detector.make 'Rigaku HyPix-ED'",
            "_diffrn_detector.type 'Rigaku HyPix-ED'",
            "",
        ]
    )

    conflicts, mismatches = get_data_name_conflicts_requiring_resolution(content, manager)

    assert conflicts == {}
    assert mismatches == []


def test_mismatched_alias_values_are_flagged_as_conflict():
    manager = _build_manager()

    content = "\n".join(
        [
            "data_test",
            "_diffrn_detector.make 'Rigaku HyPix-ED'",
            "_diffrn_detector.type 'Rigaku HyPix'",
            "",
        ]
    )

    conflicts, mismatches = get_data_name_conflicts_requiring_resolution(content, manager)

    assert "_diffrn_detector.make" in conflicts
    assert any(m.canonical_name == "_diffrn_detector.make" for m in mismatches)


def test_map_to_legacy_resolves_modern_alias_name():
    manager = _build_manager()

    # This modern dot alias must resolve via the canonical definition mapping.
    assert manager.map_to_legacy("_diffrn_detector.type") == "_diffrn_detector_type"


def test_convert_cif_format_to_legacy_prefers_non_deprecated_alias():
    manager = _build_manager()

    content = "\n".join(
        [
            "data_test",
            "_diffrn_reflns.av_sigmaI_over_netI 1",
            "",
        ]
    )

    converted_content, changes = manager.convert_cif_format(content, "LEGACY")

    assert "_diffrn_reflns_av_unetI/netI 1" in converted_content
    assert "_diffrn_reflns_av_sigmaI/netI" not in converted_content
    assert any("Converted '_diffrn_reflns.av_sigmaI_over_netI' to '_diffrn_reflns_av_unetI/netI'" in change for change in changes)


def test_convert_cif_format_to_legacy_keeps_existing_preferred_alias():
    manager = _build_manager()

    content = "\n".join(
        [
            "data_test",
            "_diffrn_reflns_av_unetI/netI 1",
            "",
        ]
    )

    converted_content, changes = manager.convert_cif_format(content, "LEGACY")

    assert converted_content == content
    assert changes == []


def test_resolution_can_keep_aliases_and_sync_values():
    manager = _build_manager()

    content = "\n".join(
        [
            "data_test",
            "_diffrn_detector.make 'Rigaku HyPix-ED'",
            "_diffrn_detector.type 'Rigaku HyPix'",
            "",
        ]
    )

    resolutions = {
        "_diffrn_detector.make": (
            "_diffrn_detector.make",
            "Rigaku HyPix-ED",
            True,
        )
    }

    resolved_content, changes = manager.apply_field_conflict_resolutions(content, resolutions)

    assert "_diffrn_detector.make 'Rigaku HyPix-ED'" in resolved_content
    assert "_diffrn_detector.type 'Rigaku HyPix-ED'" in resolved_content
    assert len([l for l in resolved_content.splitlines() if l.strip().startswith("_diffrn_detector.make")]) == 1
    assert len([l for l in resolved_content.splitlines() if l.strip().startswith("_diffrn_detector.type")]) == 1
    assert any("Synchronized alias" in c for c in changes)
