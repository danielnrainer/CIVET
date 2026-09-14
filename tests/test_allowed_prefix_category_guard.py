"""Regression tests: a real dictionary category must never be treated as
an allowed local prefix.

A user could end up with a genuine category (e.g. 'refln') in their
allowed-prefixes list - for instance by clicking "+ Prefix" on an unknown
field like _refln_frame_id before this guard existed. If honoured, that
entry would silently accept *any* unrecognized field under that category
(e.g. _refln_anything) as a known local extension, masking real typos and
errors. DataNameValidator must refuse to add such an entry, and must
disregard one that's already present (e.g. from a hand-edited config file
or a pre-fix version of CIVET).
"""

import pytest

from utils.cif_dictionary_manager import CIFDictionaryManager
from utils.data_name_validator import DataNameValidator, FieldCategory


def _validator() -> DataNameValidator:
    manager = CIFDictionaryManager()
    manager._ensure_loaded()
    return DataNameValidator(manager)


@pytest.fixture(autouse=True)
def _no_leftover_allowed_prefixes():
    """Guard against polluting the real on-disk user-preferences file if a
    test fails mid-way; every test here explicitly cleans up itself too."""
    yield
    validator = _validator()
    for leftover in ("refln", "not_a_real_category"):
        if leftover in validator.get_allowed_prefixes():
            validator.remove_allowed_prefix(leftover)


def test_add_allowed_prefix_refuses_a_real_dictionary_category():
    validator = _validator()

    added = validator.add_allowed_prefix("refln")

    assert added is False
    assert "refln" not in validator.get_allowed_prefixes()


def test_add_allowed_prefix_accepts_a_genuine_local_prefix():
    validator = _validator()

    try:
        added = validator.add_allowed_prefix("not_a_real_category")

        assert added is True
        assert "not_a_real_category" in validator.get_allowed_prefixes()
    finally:
        validator.remove_allowed_prefix("not_a_real_category")


def test_stale_category_entry_in_allowed_prefixes_is_disregarded():
    """Simulates a config file corrupted by the pre-fix bug: 'refln' is
    already present in _user_allowed_prefixes (bypassing add_allowed_prefix
    entirely, the way loading an old hand-edited/legacy file would), and
    must still not short-circuit validation of _refln_frame_id."""
    validator = _validator()
    validator._user_allowed_prefixes.add("refln")

    result = validator.validate_field("_refln_frame_id")

    assert result.category == FieldCategory.UNKNOWN
