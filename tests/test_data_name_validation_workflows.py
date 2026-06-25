"""Behavior-focused tests for Data Name Validation dialog workflows."""

import pytest
from PyQt6.QtWidgets import QApplication

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
