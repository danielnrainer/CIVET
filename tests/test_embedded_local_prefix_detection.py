"""Regression tests for DataNameValidator's embedded-local-prefix detection.

_detect_embedded_local_prefix() flags underscore-only field names like
_chemical_oxdiff_formula as a category ("chemical") plus an embedded local
prefix ("oxdiff") that should move after the dot per IUCr Volume G Ch3.1 -
or, for a legacy-format file, to the front of the name instead (a local
prefix can only legitimately be the first segment in underscore-only
notation - "_oxdiff_chemical_formula" is valid, "_chemical_oxdiff_formula"
never is, in any notation).

It only recognizes the middle segment as a prefix when there's positive
evidence it actually is one - registered, or explicitly user-allowed -
rather than guessing. Without that, a word like "frame" in "_refln_frame_id"
is just part of an ordinary, if unrecognized, two-word attribute name, not a
prefix, and no fix is fabricated for it.

Even once the prefix IS confirmed, the field as written is still not valid
in any notation (the prefix sits in the wrong place), so it's categorized as
a mandatory rename rather than being filed away as REGISTERED_LOCAL/
USER_ALLOWED ("already fine, nothing to do"), which would silently stop
flagging a field that still needs fixing:
- a registered (IUCr) prefix -> MALFORMED, same bucket as any other
  dictionary-verified malformed field.
- a user-allowed (personal, self-declared) prefix -> its own
  MALFORMED_USER_ALLOWED category, since it hasn't been vetted by anyone
  else the way a registered prefix has.
"""

from utils.cif_dictionary_manager import CIFDictionaryManager
from utils.data_name_validator import DataNameValidator, FieldCategory


def _validator() -> DataNameValidator:
    manager = CIFDictionaryManager()
    manager._ensure_loaded()
    return DataNameValidator(manager)


def test_unknown_attribute_under_known_category_is_not_treated_as_embedded_prefix():
    """_refln_frame_id: 'refln' is a real category but 'frame' is not a
    registered or user-allowed prefix, so no fix should be fabricated."""
    validator = _validator()

    result = validator.validate_field("_refln_frame_id")

    assert result.category == FieldCategory.UNKNOWN
    assert result.suggested_format == ""
    assert result.embedded_prefix == ""


def test_unknown_attribute_under_known_category_explains_why_in_description():
    """A plain "not found in loaded dictionaries" description doesn't tell
    the user why _refln_frame_id is unknown, or that 'refln' itself is
    fine - it's the rest of the name that isn't recognized."""
    validator = _validator()

    result = validator.validate_field("_refln_frame_id")

    assert "refln" in result.description
    assert "known category" in result.description


def test_registered_prefix_embedded_in_category_extension_is_flagged_malformed():
    """'shelx' is a registered IUCr prefix, so embedding it after a known
    category (_refine_shelx_res_checksum) is recognized - but the field as
    written is still not valid notation, so it's a mandatory-rename
    MALFORMED field, not REGISTERED_LOCAL ("nothing to do")."""
    validator = _validator()

    result = validator.validate_field("_refine_shelx_res_checksum")

    assert result.category == FieldCategory.MALFORMED
    assert result.embedded_prefix == "shelx"
    assert result.suggested_format == "_refine.shelx_res_checksum"


def test_longest_known_category_is_preferred_over_a_shorter_one():
    """_audit_contact_author_shelx_id: the real category is the deeper
    'audit_contact_author', not the shorter 'audit' with 'contact' wrongly
    read as an embedded prefix."""
    validator = _validator()

    result = validator.validate_field("_audit_contact_author_shelx_id")

    assert result.category == FieldCategory.MALFORMED
    assert result.embedded_prefix == "shelx"
    assert result.suggested_format == "_audit_contact_author.shelx_id"


def test_user_allowed_prefix_embedded_in_category_extension_is_flagged_malformed_user_allowed():
    """A not-yet-registered vendor prefix the user has explicitly allowed
    (e.g. via the recognised-prefixes dialog) is recognized when embedded
    in a category extension - but, same as the registered-prefix case, the
    field still needs a mandatory rename rather than being silently
    accepted as-is (this is the bug report: adding 'oxdiff' as a prefix
    must not make _chemical_oxdiff_formula stop being flagged). It's kept
    in its own MALFORMED_USER_ALLOWED category, distinct from plain
    MALFORMED, since a user-allowed prefix is a personal declaration, not
    an IUCr-vetted one."""
    validator = _validator()
    validator.add_allowed_prefix("oxdiff")
    try:
        result = validator.validate_field("_chemical_oxdiff_formula")

        assert result.category == FieldCategory.MALFORMED_USER_ALLOWED
        assert result.embedded_prefix == "oxdiff"
        assert result.suggested_format == "_chemical.oxdiff_formula"
    finally:
        validator.remove_allowed_prefix("oxdiff")


def test_category_check_is_not_limited_to_a_hardcoded_list():
    """is_known_category() must reflect the loaded dictionaries rather than
    a fixed guess list, so categories outside that old list still work."""
    manager = CIFDictionaryManager()
    manager._ensure_loaded()

    assert manager.is_known_category("audit_contact_author")
    assert manager.is_known_category("_audit_contact_author_")
    assert not manager.is_known_category("not_a_real_category")


def test_embedded_prefix_suggestion_is_legacy_reordered_in_a_legacy_file():
    """A local prefix can only legitimately be the first segment in
    underscore-only (legacy) CIF notation - _refine_shelx_res_checksum is
    not a valid legacy tag at all, so in a legacy-format file the fix
    should reorder it to _shelx_refine_res_checksum, not insert a dot."""
    validator = _validator()
    content = (
        "data_test\n"
        "_cell_length_a 5.0\n"
        "_refine_shelx_res_checksum 1234\n"
    )

    report = validator.validate_cif_content(content)

    [result] = report.malformed_fields
    assert result.embedded_prefix == "shelx"
    assert result.suggested_format == "_shelx_refine_res_checksum"


def test_embedded_prefix_suggestion_stays_dot_notation_in_a_modern_file():
    """The same embedded prefix, but in a file that's otherwise written in
    modern dot notation, should still be suggested as the modern dotted
    form (_refine.shelx_res_checksum)."""
    validator = _validator()
    content = (
        "data_test\n"
        "_cell.length_a 5.0\n"
        "_diffrn.ambient_temperature 293\n"
        "_refine_shelx_res_checksum 1234\n"
    )

    report = validator.validate_cif_content(content)

    [result] = report.malformed_fields
    assert result.embedded_prefix == "shelx"
    assert result.suggested_format == "_refine.shelx_res_checksum"


def test_user_allowed_embedded_prefix_suggestion_is_legacy_reordered_in_a_legacy_file():
    """Same legacy/modern format-awareness, but for the user-allowed
    (MALFORMED_USER_ALLOWED) path rather than the registered-prefix one."""
    validator = _validator()
    validator.add_allowed_prefix("oxdiff")
    try:
        content = "data_test\n_cell_length_a 5.0\n_chemical_oxdiff_formula C6H6\n"

        report = validator.validate_cif_content(content)

        [result] = report.malformed_user_allowed_fields
        assert result.embedded_prefix == "oxdiff"
        assert result.suggested_format == "_oxdiff_chemical_formula"
    finally:
        validator.remove_allowed_prefix("oxdiff")


def test_embedded_prefix_suggestion_does_not_stick_across_different_file_formats():
    """Regression: validate_field's per-field-name cache must not leak a
    format-specific (legacy/modern) mutation from one validate_cif_content
    call into the next call for a differently-formatted file re-using the
    same field name."""
    validator = _validator()
    validator.add_allowed_prefix("oxdiff")
    try:
        legacy_content = "data_test\n_cell_length_a 5.0\n_chemical_oxdiff_formula C6H6\n"
        modern_content = (
            "data_test\n_cell.length_a 5.0\n_diffrn.ambient_temperature 293\n"
            "_chemical_oxdiff_formula C6H6\n"
        )

        [legacy_result] = validator.validate_cif_content(legacy_content).malformed_user_allowed_fields
        assert legacy_result.suggested_format == "_oxdiff_chemical_formula"

        [modern_result] = validator.validate_cif_content(modern_content).malformed_user_allowed_fields
        assert modern_result.suggested_format == "_chemical.oxdiff_formula"

        # And back to legacy again - not permanently stuck on the modern form either.
        [legacy_again] = validator.validate_cif_content(legacy_content).malformed_user_allowed_fields
        assert legacy_again.suggested_format == "_oxdiff_chemical_formula"
    finally:
        validator.remove_allowed_prefix("oxdiff")


def test_legacy_format_for_embedded_prefix_helper_handles_bare_prefix_attribute():
    """When the attribute is nothing but the prefix itself (no remaining
    words), the legacy reordering should drop the now-empty tail rather
    than leaving a trailing underscore."""
    legacy_format = DataNameValidator._legacy_format_for_embedded_prefix(
        "shelx", "_refine.shelx"
    )

    assert legacy_format == "_shelx_refine"
