"""Behavior-focused tests for Data Name Validation dialog workflows."""

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton

from gui.dialogs.data_name_validation_dialog import DataNameValidationDialog
from utils.data_name_validator import (
    FieldAction,
    FieldCategory,
    FieldValidationResult,
    ValidationReport,
)


class _FakeValidator:
    def __init__(self):
        self.allowed_prefixes = set()
        self.allowed_fields = set()
        self.session_ignored = set()
        self.known_categories = set()

    def get_allowed_prefixes(self):
        return set(self.allowed_prefixes)

    def get_allowed_fields(self):
        return set(self.allowed_fields)

    def add_allowed_prefix(self, prefix):
        self.allowed_prefixes.add(prefix.lower())

    def add_allowed_field(self, field_name):
        self.allowed_fields.add(field_name.lower())

    def add_session_ignored(self, field_name):
        self.session_ignored.add(field_name.lower())

    def remove_allowed_prefix(self, prefix):
        self.allowed_prefixes.discard(prefix.lower())

    def remove_allowed_field(self, field_name):
        self.allowed_fields.discard(field_name.lower())

    def is_known_category(self, category):
        return category.lower() in self.known_categories


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _report_with_unknown_and_deprecated():
    unknown = FieldValidationResult(
        field_name="_unknown_field",
        category=FieldCategory.UNKNOWN,
        line_number=10,
        description="Unknown field",
        prefix="unknown",
    )
    deprecated = FieldValidationResult(
        field_name="_deprecated_field",
        category=FieldCategory.DEPRECATED,
        line_number=20,
        description="Deprecated field",
        modern_equivalent="_modern.field",
        successor_name="_modern_field",
        successor_already_exists=False,
    )
    report = ValidationReport(
        unknown_fields=[unknown],
        deprecated_fields=[deprecated],
        total_fields=2,
    )
    return report


def test_unknown_field_actions_mark_pending_and_enable_apply(app):
    _ = app
    validator = _FakeValidator()
    dialog = DataNameValidationDialog(_report_with_unknown_and_deprecated(), validator)

    dialog._on_allow_prefix("_unknown_field", "unknown")
    assert dialog._pending_actions["_unknown_field"] == FieldAction.ALLOW_PREFIX
    assert "unknown" in dialog._prefixes_to_allow
    assert dialog.apply_button.isEnabled() is True

    dialog._on_allow_field("_unknown_field")
    assert dialog._pending_actions["_unknown_field"] == FieldAction.ALLOW_FIELD
    assert "_unknown_field" in dialog._fields_to_allow

    dialog._on_delete_field("_unknown_field")
    assert dialog._pending_actions["_unknown_field"] == FieldAction.DELETE
    assert "_unknown_field" in dialog._fields_to_delete
    dialog.close()


def test_deprecated_actions_switch_between_add_and_replace_modes(app):
    _ = app
    validator = _FakeValidator()
    dialog = DataNameValidationDialog(_report_with_unknown_and_deprecated(), validator)

    dialog._on_update_deprecated("_deprecated_field", "_modern_field")
    assert dialog._pending_actions["_deprecated_field"] == FieldAction.DEPRECATION_UPDATE
    assert dialog._deprecated_updates["_deprecated_field"] == "_modern_field"
    assert "_deprecated_field" not in dialog._deprecated_replacements

    dialog._on_replace_deprecated("_deprecated_field", "_modern_field")
    assert dialog._pending_actions["_deprecated_field"] == FieldAction.DEPRECATION_REPLACE
    assert dialog._deprecated_replacements["_deprecated_field"] == "_modern_field"
    assert "_deprecated_field" not in dialog._deprecated_updates
    dialog.close()


def _report_with_checkcif_retained_deprecated_field():
    deprecated = FieldValidationResult(
        field_name="_cell_measurement_temperature",
        category=FieldCategory.DEPRECATED,
        line_number=5,
        description="Field is deprecated (retained for checkCIF compatibility - see README)",
        modern_equivalent="_diffrn_ambient_temperature",
        successor_name="_diffrn_ambient_temperature",
        successor_already_exists=True,
        checkcif_retain_required=True,
    )
    return ValidationReport(deprecated_fields=[deprecated], total_fields=1)


def test_checkcif_required_deprecated_field_cannot_be_deleted_or_replaced(app):
    """Regression: deprecated fields checkCIF still requires (e.g.
    _cell_measurement_temperature for PLAT197) must survive both the
    'Replace' and 'Delete' actions even if somehow triggered."""
    _ = app
    validator = _FakeValidator()
    dialog = DataNameValidationDialog(_report_with_checkcif_retained_deprecated_field(), validator)

    dialog._on_delete_field("_cell_measurement_temperature")
    assert "_cell_measurement_temperature" not in dialog._fields_to_delete
    assert "_cell_measurement_temperature" not in dialog._pending_actions

    dialog._on_replace_deprecated("_cell_measurement_temperature", "_diffrn_ambient_temperature")
    assert "_cell_measurement_temperature" not in dialog._deprecated_replacements
    assert "_cell_measurement_temperature" not in dialog._pending_actions
    dialog.close()


def test_undo_action_clears_pending_state_for_field(app):
    _ = app
    validator = _FakeValidator()
    dialog = DataNameValidationDialog(_report_with_unknown_and_deprecated(), validator)

    dialog._on_allow_field("_unknown_field")
    assert "_unknown_field" in dialog._pending_actions

    dialog._on_undo_action("_unknown_field")
    assert "_unknown_field" not in dialog._pending_actions
    assert "_unknown_field" not in dialog._fields_to_allow
    dialog.close()


def test_apply_changes_persists_validator_updates_and_emits_signal(app):
    _ = app
    validator = _FakeValidator()
    dialog = DataNameValidationDialog(_report_with_unknown_and_deprecated(), validator)

    emitted = []
    dialog.changes_requested.connect(lambda: emitted.append(True))

    dialog._on_allow_prefix("_unknown_field", "unknown")
    dialog._on_allow_field("_unknown_field")
    dialog._on_ignore_field("_deprecated_field")
    dialog._on_apply_changes()

    assert "unknown" in validator.allowed_prefixes
    assert "_unknown_field" in validator.allowed_fields
    assert "_deprecated_field" in validator.session_ignored
    assert emitted == [True]
    dialog.close()


def test_refresh_validation_clears_pending_actions_and_rebuilds_view(app):
    _ = app
    validator = _FakeValidator()
    dialog = DataNameValidationDialog(_report_with_unknown_and_deprecated(), validator)

    dialog._on_allow_field("_unknown_field")
    assert dialog.apply_button.isEnabled() is True

    new_report = ValidationReport(
        valid_fields=[
            FieldValidationResult(
                field_name="_cell_length_a",
                category=FieldCategory.VALID,
                line_number=1,
                description="Known in dictionary",
            )
        ],
        total_fields=1,
    )

    dialog.refresh_validation(new_report)

    assert dialog.apply_button.isEnabled() is False
    assert dialog._pending_actions == {}
    assert dialog.validation_report.total_fields == 1
    assert len(dialog._category_items) == 1
    assert FieldCategory.VALID in dialog._category_items
    dialog.close()


def _unknown_field_result_under_known_category():
    """e.g. _refln_frame_id: 'refln' is a real dictionary category, but
    'frame_id' isn't one of its recognized attributes."""
    return FieldValidationResult(
        field_name="_refln_frame_id",
        category=FieldCategory.UNKNOWN,
        line_number=7,
        description=(
            "'refln' is a known category, but the rest of this name isn't "
            "a recognized attribute of it - not found in loaded dictionaries"
        ),
        prefix="refln",
    )


def test_allow_prefix_button_disabled_with_explanation_when_prefix_is_real_category(app):
    """Regression: offering to "allow" a genuine dictionary category (e.g.
    'refln') as if it were a local prefix would silently accept any
    unrecognized field under that category. The button must stay visible
    (like a deprecated field's disabled 'Replace' button) but disabled,
    with a tooltip explaining why - not simply vanish."""
    _ = app
    validator = _FakeValidator()
    validator.known_categories = {"refln"}
    dialog = DataNameValidationDialog(
        ValidationReport(unknown_fields=[_unknown_field_result_under_known_category()], total_fields=1),
        validator,
    )

    buttons_widget = dialog._create_action_buttons(
        _unknown_field_result_under_known_category(), FieldCategory.UNKNOWN
    )
    prefix_btn = next(
        btn for btn in buttons_widget.findChildren(QPushButton) if btn.text() == "+ Prefix"
    )

    assert prefix_btn.isEnabled() is False
    assert "refln" in prefix_btn.toolTip()
    dialog.close()


def test_allow_field_requires_confirmation_when_prefix_is_real_category(app, monkeypatch):
    """Clicking "+ Field" for a field like _refln_frame_id must prompt for
    confirmation (declining leaves nothing pending) rather than silently
    exempting a data name that doesn't correspond to anything in the CIF
    standard."""
    _ = app
    validator = _FakeValidator()
    validator.known_categories = {"refln"}
    dialog = DataNameValidationDialog(
        ValidationReport(unknown_fields=[_unknown_field_result_under_known_category()], total_fields=1),
        validator,
    )

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    dialog._on_allow_field("_refln_frame_id", True, "refln")
    assert "_refln_frame_id" not in dialog._fields_to_allow
    assert "_refln_frame_id" not in dialog._pending_actions

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog._on_allow_field("_refln_frame_id", True, "refln")
    assert "_refln_frame_id" in dialog._fields_to_allow
    assert dialog._pending_actions["_refln_frame_id"] == FieldAction.ALLOW_FIELD
    dialog.close()


def test_allow_field_skips_confirmation_for_an_ordinary_unknown_field(app, monkeypatch):
    """An unknown field with no known-category collision (the common case -
    a genuine custom/local field) should be exempted immediately, with no
    confirmation prompt in the way."""
    _ = app
    validator = _FakeValidator()
    dialog = DataNameValidationDialog(_report_with_unknown_and_deprecated(), validator)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("QMessageBox.question should not be called here")

    monkeypatch.setattr(QMessageBox, "question", _fail_if_called)
    dialog._on_allow_field("_unknown_field")

    assert "_unknown_field" in dialog._fields_to_allow
    dialog.close()
    dialog.close()


def _report_with_loop_column():
    loop_field = FieldValidationResult(
        field_name="_atom_site_unknown",
        category=FieldCategory.UNKNOWN,
        line_number=10,
        description="Unknown field",
        prefix="atom_site",
        in_loop=True,
    )
    standalone_field = FieldValidationResult(
        field_name="_unknown_field",
        category=FieldCategory.UNKNOWN,
        line_number=20,
        description="Unknown field",
        prefix="unknown",
        in_loop=False,
    )
    return ValidationReport(
        unknown_fields=[loop_field, standalone_field],
        total_fields=2,
    )


def test_loop_column_shown_with_indicator_and_tooltip(app):
    _ = app
    validator = _FakeValidator()
    dialog = DataNameValidationDialog(_report_with_loop_column(), validator)

    loop_item = dialog._field_items["_atom_site_unknown"]
    assert "🔁" in loop_item.text(0)
    assert "loop_" in loop_item.toolTip(0)

    standalone_item = dialog._field_items["_unknown_field"]
    assert "🔁" not in standalone_item.text(0)
    assert standalone_item.toolTip(0) == ""
    dialog.close()


def test_deleting_a_loop_column_warns_and_respects_cancel(app, monkeypatch):
    _ = app
    validator = _FakeValidator()
    dialog = DataNameValidationDialog(_report_with_loop_column(), validator)

    questions = []
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: questions.append(a) or QMessageBox.StandardButton.No,
    )
    dialog._on_delete_field("_atom_site_unknown")

    assert questions  # the warning was shown
    assert "_atom_site_unknown" not in dialog._fields_to_delete
    assert "_atom_site_unknown" not in dialog._pending_actions
    dialog.close()


def test_deleting_a_loop_column_proceeds_when_confirmed(app, monkeypatch):
    _ = app
    validator = _FakeValidator()
    dialog = DataNameValidationDialog(_report_with_loop_column(), validator)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog._on_delete_field("_atom_site_unknown")

    assert "_atom_site_unknown" in dialog._fields_to_delete
    assert dialog._pending_actions["_atom_site_unknown"] == FieldAction.DELETE
    dialog.close()


def test_deleting_a_standalone_field_skips_the_loop_warning(app, monkeypatch):
    """A field that isn't a loop column should delete with no extra prompt."""
    _ = app
    validator = _FakeValidator()
    dialog = DataNameValidationDialog(_report_with_loop_column(), validator)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("QMessageBox.question should not be called here")

    monkeypatch.setattr(QMessageBox, "question", _fail_if_called)
    dialog._on_delete_field("_unknown_field")

    assert "_unknown_field" in dialog._fields_to_delete
    dialog.close()
