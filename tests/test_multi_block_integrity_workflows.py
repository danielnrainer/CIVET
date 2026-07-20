"""Tests for phase 4 of multi-block support: block-aware integrity checks,
validation-report block context, and per-block standalone actions.
See .github/multi_data_block_plan.md.
"""

from PyQt6.QtWidgets import QDialog, QMessageBox

import gui.data_name_integrity as data_name_integrity_module
import gui.field_checking as field_checking_module
import gui.format_handlers as format_handlers_module
from gui.data_name_integrity import DataNameIntegrityMixin
from gui.field_checking import FieldCheckingMixin
from gui.format_handlers import FormatHandlersMixin
from utils.CIF_parser import CIFParser
from utils.cif_dictionary_manager import CIFDictionaryManager, FieldNotation
from utils.data_name_validator import DataNameValidator


class _DummyTextEditor:
    def __init__(self, text: str):
        self._text = text

    def toPlainText(self):
        return self._text

    def setText(self, text: str):
        self._text = text


def _dict_manager() -> CIFDictionaryManager:
    manager = CIFDictionaryManager()
    manager._ensure_loaded()
    return manager


# ---------------------------------------------------------------------------
# Validation report block context
# ---------------------------------------------------------------------------

def test_validator_attaches_block_context_for_multi_block_files():
    validator = DataNameValidator(_dict_manager())
    content = (
        "data_first\n"
        "_cell_length_a 5.0\n"
        "_totally_unknown_name 1\n"
        "\n"
        "data_second\n"
        "_cell_length_b 6.0\n"
    )

    report = validator.validate_cif_content(content)

    by_name = {}
    for bucket in (report.valid_fields, report.unknown_fields,
                   report.deprecated_fields, report.malformed_fields,
                   report.registered_local_fields, report.user_allowed_fields):
        for result in bucket:
            by_name[result.field_name] = result

    assert by_name["_cell_length_a"].block_name == "first"
    assert by_name["_totally_unknown_name"].block_name == "first"
    assert by_name["_cell_length_b"].block_name == "second"


def test_validator_leaves_block_context_empty_for_single_block():
    validator = DataNameValidator(_dict_manager())
    report = validator.validate_cif_content("data_only\n_cell_length_a 5.0\n")

    for result in report.valid_fields:
        assert result.block_name == ""
        assert result.block_occurrences == []


def test_validator_records_all_block_occurrences():
    validator = DataNameValidator(_dict_manager())
    content = (
        "data_first\n"
        "_totally_unknown_name 1\n"
        "\n"
        "data_second\n"
        "_totally_unknown_name 2\n"
        "_totally_unknown_name 3\n"  # same-block repeat: not a new occurrence
    )

    report = validator.validate_cif_content(content)

    result = next(r for r in report.unknown_fields
                  if r.field_name == "_totally_unknown_name")
    assert result.block_occurrences == [("first", 2), ("second", 5)]
    assert result.block_name == "first"


# ---------------------------------------------------------------------------
# Per-block duplicate/integrity checks
# ---------------------------------------------------------------------------

class _IntegrityHarness(DataNameIntegrityMixin, FieldCheckingMixin):
    """Same mixin order as CIFEditor."""

    def __init__(self, content: str, dict_manager):
        self.text_editor = _DummyTextEditor(content)
        self.cif_parser = CIFParser()
        self.dict_manager = dict_manager
        self.modified = False


def test_same_field_in_two_blocks_is_not_a_duplicate(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("no conflict prompt expected")

    monkeypatch.setattr(data_name_integrity_module.QMessageBox, "question", explode)

    content = (
        "data_one\n"
        "_cell_length_a 5.0\n"
        "_cell_length_b 6.0\n"
        "\n"
        "data_two\n"
        "_cell_length_a 7.0\n"
        "_cell_length_b 8.0\n"
    )
    harness = _IntegrityHarness(content, _dict_manager())

    assert harness._check_duplicate_data_names("test operation") is True


def test_duplicate_within_one_block_is_still_flagged_with_block_context(monkeypatch):
    prompts = []

    def fake_question(parent, title, message, *args, **kwargs):
        _ = (parent, title)
        prompts.append(message)
        return QMessageBox.StandardButton.No  # don't resolve, just continue

    monkeypatch.setattr(data_name_integrity_module.QMessageBox, "question", fake_question)

    content = (
        "data_one\n"
        "_cell_length_a 5.0\n"
        "_cell_length_a 5.5\n"
        "\n"
        "data_two\n"
        "_cell_length_a 7.0\n"
    )
    harness = _IntegrityHarness(content, _dict_manager())

    assert harness._check_duplicate_data_names("test operation") is True
    assert len(prompts) == 1  # only the block with the real duplicate prompts
    assert "(data_one)" in prompts[0]
    assert "_cell_length_a" in prompts[0]


# ---------------------------------------------------------------------------
# check_refine_special_details per block
# ---------------------------------------------------------------------------

class _FakeMultilineDialog:
    instances = []

    def __init__(self, text="", parent=None, context_text="", default_value=None,
                 operation_type="edit", block_label=None):
        _ = (parent, context_text, default_value, operation_type)
        self.initial_text = text
        self.block_label = block_label
        _FakeMultilineDialog.instances.append(self)

    def setWindowTitle(self, _title):
        pass

    def getText(self):
        suffix = self.block_label or "whole"
        return f"edited for {suffix}"


class _RefineHarness(FieldCheckingMixin):
    def __init__(self, content: str):
        self.text_editor = _DummyTextEditor(content)
        self.cif_parser = CIFParser()
        self.modified = False

        class _DictManager:
            @staticmethod
            def detect_notation(_content):
                return FieldNotation.LEGACY

        self.dict_manager = _DictManager()

    def update_status_bar(self):
        pass

    def _show_dialog_with_configured_interaction(self, dialog, mode_setting_key=None):
        _ = (dialog, mode_setting_key)
        return QDialog.DialogCode.Accepted


def test_refine_special_details_edits_each_block(monkeypatch):
    _FakeMultilineDialog.instances = []
    monkeypatch.setattr(field_checking_module, "MultilineInputDialog", _FakeMultilineDialog)

    content = (
        "data_one\n"
        "_cell_length_a 5.0\n"
        "\n"
        "data_two\n"
        "_cell_length_a 7.0\n"
    )
    harness = _RefineHarness(content)

    result = harness.check_refine_special_details()

    assert result == QDialog.DialogCode.Accepted
    assert [dialog.block_label for dialog in _FakeMultilineDialog.instances] == [
        "Data block: data_one",
        "Data block: data_two",
    ]

    full_lines = harness.text_editor.toPlainText().splitlines()
    split_index = full_lines.index("data_two")
    first_block = "\n".join(full_lines[:split_index])
    second_block = "\n".join(full_lines[split_index:])
    assert "edited for Data block: data_one" in first_block
    assert "edited for Data block: data_two" in second_block
    # Both blocks keep their own cell parameter untouched
    assert "_cell_length_a" in first_block
    assert "_cell_length_a" in second_block


class _CompatHarness(FormatHandlersMixin, FieldCheckingMixin):
    def __init__(self, content: str, dict_manager):
        self.text_editor = _DummyTextEditor(content)
        self.cif_parser = CIFParser()
        self.dict_manager = dict_manager
        self.modified = False

    def _check_duplicate_data_names(self, operation_name, block_on_conflicts=False):
        _ = (operation_name, block_on_conflicts)
        return True


class _CompatDictManager:
    """Just the mapping add_legacy_compatibility_fields needs."""

    @staticmethod
    def get_checkcif_compatibility_fields():
        return {"_cell_measurement_temperature"}

    @staticmethod
    def get_modern_equivalent(field_name, prefer_format="modern"):
        _ = prefer_format
        if field_name == "_cell_measurement_temperature":
            return "_diffrn.ambient_temperature"
        return None


def test_add_legacy_compatibility_fields_uses_each_blocks_own_values(monkeypatch):
    monkeypatch.setattr(format_handlers_module.QMessageBox, "question",
                        lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(format_handlers_module.QMessageBox, "information",
                        lambda *args, **kwargs: None)

    content = (
        "data_one\n"
        "_diffrn.ambient_temperature 100\n"
        "\n"
        "data_two\n"
        "_diffrn.ambient_temperature 200\n"
    )
    harness = _CompatHarness(content, _CompatDictManager())

    harness.add_legacy_compatibility_fields()

    full_lines = harness.text_editor.toPlainText().splitlines()
    split_index = full_lines.index("data_two")
    first_block = full_lines[:split_index]
    second_block = full_lines[split_index:]

    # Each block gets the compatibility field with its OWN temperature -
    # the old flat view would have used the last block's value for both
    assert any("_cell_measurement_temperature" in line and "100" in line
               for line in first_block)
    assert any("_cell_measurement_temperature" in line and "200" in line
               for line in second_block)


def test_refine_special_details_single_block_unchanged_flow(monkeypatch):
    _FakeMultilineDialog.instances = []
    monkeypatch.setattr(field_checking_module, "MultilineInputDialog", _FakeMultilineDialog)

    harness = _RefineHarness("data_only\n_cell_length_a 5.0\n")
    result = harness.check_refine_special_details()

    assert result == QDialog.DialogCode.Accepted
    assert len(_FakeMultilineDialog.instances) == 1
    assert _FakeMultilineDialog.instances[0].block_label is None
    assert "edited for whole" in harness.text_editor.toPlainText()


# ---------------------------------------------------------------------------
# Validation dialog block-scope prompt
# ---------------------------------------------------------------------------

import pytest
from PyQt6.QtWidgets import QApplication

from gui.dialogs import data_name_validation_dialog as validation_dialog_module
from gui.dialogs.data_name_validation_dialog import DataNameValidationDialog
from utils.data_name_validator import (
    FieldCategory, FieldValidationResult, ValidationReport,
)


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _multi_block_unknown_report():
    result = FieldValidationResult(
        field_name="_totally_unknown_name",
        category=FieldCategory.UNKNOWN,
        line_number=2,
        description="Unknown field",
        block_name="first",
        block_occurrences=[("first", 2), ("second", 5)],
    )
    report = ValidationReport(unknown_fields=[result], total_fields=1)
    return report


def test_validation_dialog_delete_asks_for_block_scope(app, monkeypatch):
    _ = app
    dialog = DataNameValidationDialog(
        _multi_block_unknown_report(), DataNameValidator(_dict_manager()))

    prompts = []

    def fake_get_item(parent, title, label, items, current=0, editable=True):
        _ = (parent, title, current, editable)
        prompts.append(list(items))
        return "Only data_second", True

    monkeypatch.setattr(validation_dialog_module.QInputDialog, "getItem", fake_get_item)

    dialog._on_delete_field("_totally_unknown_name")

    assert prompts == [["All blocks", "Only data_first", "Only data_second"]]
    assert dialog.get_fields_to_delete() == ["_totally_unknown_name"]
    assert dialog.get_action_block_scopes() == {"_totally_unknown_name": "second"}
    dialog.close()


def test_validation_dialog_scope_prompt_cancel_records_nothing(app, monkeypatch):
    _ = app
    dialog = DataNameValidationDialog(
        _multi_block_unknown_report(), DataNameValidator(_dict_manager()))

    monkeypatch.setattr(validation_dialog_module.QInputDialog, "getItem",
                        lambda *args, **kwargs: ("", False))

    dialog._on_delete_field("_totally_unknown_name")

    assert dialog.get_fields_to_delete() == []
    assert dialog.get_action_block_scopes() == {}
    dialog.close()


def test_validation_dialog_all_blocks_choice_leaves_scope_empty(app, monkeypatch):
    _ = app
    dialog = DataNameValidationDialog(
        _multi_block_unknown_report(), DataNameValidator(_dict_manager()))

    monkeypatch.setattr(validation_dialog_module.QInputDialog, "getItem",
                        lambda *args, **kwargs: ("All blocks", True))

    dialog._on_delete_field("_totally_unknown_name")

    assert dialog.get_fields_to_delete() == ["_totally_unknown_name"]
    assert dialog.get_action_block_scopes() == {}
    dialog.close()
