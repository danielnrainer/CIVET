"""Tests for per-data-block field checking (phases 2-3 of multi-block support).

Covers the block-scope machinery in FieldCheckingMixin (scoped reads/writes
spliced into the full document, scoped field lookups, per-block rule
execution), the shared divergence-driven mode, and the block-selection
additions to CheckConfigDialog. See .github/multi_data_block_plan.md.
"""

import pytest
from PyQt6.QtWidgets import QApplication, QDialog

import gui.field_checking as field_checking_module
from gui.field_checking import FieldCheckingMixin
from gui.dialogs import CheckConfigDialog, MultiBlockValueDialog, RESULT_ABORT
from utils.CIF_parser import CIFParser
from utils.CIF_field_parsing import CIFField as RuleField, CIFCondition, CIFFieldChecker


MULTI_BLOCK_CIF = "\n".join(
    [
        "data_xtal_100K",
        "_diffrn.ambient_temperature 100",
        "_dummy_field remove_me",
        "_shared_field original",
        "",
        "data_xtal_200K",
        "_diffrn.ambient_temperature 200",
        "_dummy_field remove_me",
        "_shared_field original",
    ]
)


class _DummyTextEditor:
    def __init__(self, text: str):
        self._text = text

    def toPlainText(self):
        return self._text

    def setText(self, text: str):
        self._text = text


class _ScopeHarness(FieldCheckingMixin):
    def __init__(self, content: str):
        self.text_editor = _DummyTextEditor(content)
        self.cif_parser = CIFParser()
        self.field_checker = CIFFieldChecker()

    def _ensure_parser_current(self):
        content = self.text_editor.toPlainText()
        self.cif_parser.parse_file(content)
        return content

    def run_rule(self, rule, scope):
        """Execute one rule with the given block scope active."""
        self._active_check_block = scope
        operations = []
        try:
            signal = self._execute_rule(
                rule, {'show_warnings': False}, self.text_editor.toPlainText(),
                self._ensure_parser_current, operations, True
            )
        finally:
            self._active_check_block = None
        return signal, operations


def test_get_check_text_scoped_and_unscoped():
    harness = _ScopeHarness(MULTI_BLOCK_CIF)

    assert harness._get_check_text() == MULTI_BLOCK_CIF

    harness._active_check_block = "xtal_200K"
    scoped = harness._get_check_text()
    assert scoped.startswith("data_xtal_200K")
    assert "_diffrn.ambient_temperature 200" in scoped
    assert "100" not in scoped

    lines, offset = harness._get_check_lines()
    assert lines[0] == "data_xtal_200K"
    assert offset == 5  # data_xtal_200K is line 6 of the file (0-based offset 5)


def test_set_check_text_splices_only_the_scoped_block():
    harness = _ScopeHarness(MULTI_BLOCK_CIF)
    harness._active_check_block = "xtal_100K"

    scoped = harness._get_check_text()
    harness._set_check_text(scoped.replace("original", "edited"))

    full = harness.text_editor.toPlainText()
    first_block, second_block = full.split("data_xtal_200K")
    assert "_shared_field edited" in first_block
    assert "_shared_field original" in second_block
    # Block order and headers survive the splice
    assert full.index("data_xtal_100K") < full.index("data_xtal_200K")


def test_locate_block_span_falls_back_to_whole_document():
    harness = _ScopeHarness(MULTI_BLOCK_CIF)
    lines = MULTI_BLOCK_CIF.splitlines()
    assert harness._locate_block_span(lines, "no_such_block") == (0, len(lines))


def test_get_scoped_field_value_reads_the_active_block():
    harness = _ScopeHarness(MULTI_BLOCK_CIF)
    harness._ensure_parser_current()

    assert harness._get_scoped_field_value("_diffrn.ambient_temperature") == "200"  # flat: last wins

    harness._active_check_block = "xtal_100K"
    assert harness._get_scoped_field_value("_diffrn.ambient_temperature") == "100"

    harness._active_check_block = "xtal_200K"
    assert harness._get_scoped_field_value("_diffrn.ambient_temperature") == "200"


def test_delete_rule_only_affects_scoped_block():
    harness = _ScopeHarness(MULTI_BLOCK_CIF)
    rule = RuleField("_dummy_field", "", "", "DELETE")

    signal, operations = harness.run_rule(rule, "xtal_100K")

    assert signal == 'continue'
    assert operations == ["data_xtal_100K: DELETED: _dummy_field"]
    full = harness.text_editor.toPlainText()
    first_block, second_block = full.split("data_xtal_200K")
    assert "_dummy_field" not in first_block
    assert "_dummy_field remove_me" in second_block


def test_edit_rule_only_affects_scoped_block():
    harness = _ScopeHarness(MULTI_BLOCK_CIF)
    rule = RuleField("_shared_field", "changed", "", "EDIT")

    signal, _operations = harness.run_rule(rule, "xtal_200K")

    assert signal == 'continue'
    full = harness.text_editor.toPlainText()
    first_block, second_block = full.split("data_xtal_200K")
    assert "_shared_field original" in first_block
    assert "changed" in second_block


def test_if_condition_evaluated_per_block():
    # IF _diffrn.ambient_temperature == 100 THEN DELETE _dummy_field:
    # holds in xtal_100K but not in xtal_200K.
    condition = CIFCondition("_diffrn.ambient_temperature", "equals", "100")
    nested_delete = RuleField("_dummy_field", "", "", "DELETE")
    rule = RuleField("_diffrn.ambient_temperature", "", "", "IF",
                     condition=condition, then_fields=[nested_delete])

    harness = _ScopeHarness(MULTI_BLOCK_CIF)
    _signal, operations = harness.run_rule(rule, "xtal_200K")
    assert operations == []  # condition false in this block: nothing deleted
    assert harness.text_editor.toPlainText().count("_dummy_field") == 2

    _signal, operations = harness.run_rule(rule, "xtal_100K")
    assert operations == ["data_xtal_100K: DELETED: _dummy_field"]
    assert harness.text_editor.toPlainText().count("_dummy_field") == 1


def test_check_scopes_from_config():
    harness = _ScopeHarness(MULTI_BLOCK_CIF)
    assert harness._check_scopes({}) == [None]
    assert harness._check_scopes({'selected_blocks': None}) == [None]
    assert harness._check_scopes({'selected_blocks': ["a", "b"]}) == ["a", "b"]


class _SharedHarness(_ScopeHarness):
    """Harness with the extra collaborators the shared-mode paths need."""

    def __init__(self, content: str):
        super().__init__(content)

        class _DictManager:
            @staticmethod
            def is_field_deprecated(_name):
                return False

        self.dict_manager = _DictManager()

    def update_field_value(self, lines, index, field_name, value):
        value_str = str(value)
        if ' ' in value_str or ',' in value_str:
            value_str = f"'{value_str}'"
        lines[index] = f"{field_name} {value_str}"

    def update_window_title(self):
        pass

    def _show_dialog_with_configured_interaction(self, dialog, mode_setting_key=None):
        _ = mode_setting_key
        return dialog.exec()

    def run_shared(self, rule, blocks, config=None):
        operations = []
        signal = self._execute_rule_shared(
            rule, blocks, config or {}, self.text_editor.toPlainText(),
            self._ensure_parser_current, operations, True
        )
        return signal, operations


def _patch_get_text(monkeypatch, reply, calls=None):
    """Replace CIFInputDialog.getText with a canned (value, result) reply."""
    def fake_get_text(parent, title, text, value="", default_value=None,
                      operation_type="edit", suggestions=None, show_dialog_fn=None,
                      block_label=None):
        _ = (parent, title, value, default_value, operation_type, suggestions, show_dialog_fn)
        if calls is not None:
            calls.append({'text': text, 'block_label': block_label})
        return reply

    monkeypatch.setattr(field_checking_module.CIFInputDialog, "getText", fake_get_text)


def test_shared_check_agreement_single_prompt_applies_to_all(monkeypatch):
    harness = _SharedHarness(MULTI_BLOCK_CIF)
    calls = []
    _patch_get_text(monkeypatch, ("updated", QDialog.DialogCode.Accepted), calls)

    rule = RuleField("_shared_field", "suggested", "desc")
    signal, _ops = harness.run_shared(rule, ["xtal_100K", "xtal_200K"])

    assert signal == 'continue'
    assert len(calls) == 1  # one prompt for both blocks
    assert "All 2 selected blocks" in calls[0]['block_label']
    assert harness.text_editor.toPlainText().count("_shared_field updated") == 2


def test_shared_check_divergent_uses_per_block_dialog(monkeypatch):
    harness = _SharedHarness(MULTI_BLOCK_CIF)

    seen = {}

    def fake_get_values(parent, field_name, block_values, default_value=None,
                        description="", show_dialog_fn=None):
        _ = (parent, default_value, description, show_dialog_fn)
        seen['field'] = field_name
        seen['values'] = dict(block_values)
        return {"xtal_100K": "110", "xtal_200K": "210"}, QDialog.DialogCode.Accepted

    monkeypatch.setattr(field_checking_module.MultiBlockValueDialog, "getValues", fake_get_values)
    _patch_get_text(monkeypatch, (None, QDialog.DialogCode.Rejected))  # must not be used

    rule = RuleField("_diffrn.ambient_temperature", "", "desc")
    signal, _ops = harness.run_shared(rule, ["xtal_100K", "xtal_200K"])

    assert signal == 'continue'
    assert seen['field'] == "_diffrn.ambient_temperature"
    assert seen['values'] == {"xtal_100K": "100", "xtal_200K": "200"}
    full = harness.text_editor.toPlainText()
    first_block, second_block = full.split("data_xtal_200K")
    assert "_diffrn.ambient_temperature 110" in first_block
    assert "_diffrn.ambient_temperature 210" in second_block


def test_shared_check_missing_everywhere_adds_to_all(monkeypatch):
    harness = _SharedHarness(MULTI_BLOCK_CIF)
    _patch_get_text(monkeypatch, ("filled", QDialog.DialogCode.Accepted))

    rule = RuleField("_brand_new_field", "filled", "desc")
    signal, _ops = harness.run_shared(rule, ["xtal_100K", "xtal_200K"])

    assert signal == 'continue'
    full = harness.text_editor.toPlainText()
    first_block, second_block = full.split("data_xtal_200K")
    assert "_brand_new_field filled" in first_block
    assert "_brand_new_field filled" in second_block


def test_shared_check_skips_when_all_match_default(monkeypatch):
    harness = _SharedHarness(MULTI_BLOCK_CIF)

    def explode(*args, **kwargs):
        raise AssertionError("no dialog should be shown")

    monkeypatch.setattr(field_checking_module.CIFInputDialog, "getText", explode)
    monkeypatch.setattr(field_checking_module.MultiBlockValueDialog, "getValues", explode)

    rule = RuleField("_shared_field", "original", "desc")
    signal, _ops = harness.run_shared(rule, ["xtal_100K", "xtal_200K"],
                                      {'skip_matching_defaults': True})
    assert signal == 'continue'
    assert harness.text_editor.toPlainText().count("_shared_field original") == 2


def test_shared_if_condition_narrows_blocks_for_nested_rules(monkeypatch):
    calls = []
    _patch_get_text(monkeypatch, ("seen", QDialog.DialogCode.Accepted), calls)

    condition = CIFCondition("_diffrn.ambient_temperature", "equals", "100")
    nested_check = RuleField("_shared_field", "suggested", "desc")
    rule = RuleField("_diffrn.ambient_temperature", "", "", "IF",
                     condition=condition, then_fields=[nested_check])

    harness = _SharedHarness(MULTI_BLOCK_CIF)
    signal, _ops = harness.run_shared(rule, ["xtal_100K", "xtal_200K"])

    assert signal == 'continue'
    # Nested CHECK ran shared across the matching subset only
    assert len(calls) == 1
    assert calls[0]['block_label'] == "Data block: data_xtal_100K"
    full = harness.text_editor.toPlainText()
    first_block, second_block = full.split("data_xtal_200K")
    assert "_shared_field seen" in first_block
    assert "_shared_field original" in second_block


def test_shared_delete_applies_to_all_blocks():
    harness = _SharedHarness(MULTI_BLOCK_CIF)
    rule = RuleField("_dummy_field", "", "", "DELETE")

    signal, operations = harness.run_shared(rule, ["xtal_100K", "xtal_200K"])

    assert signal == 'continue'
    assert operations == [
        "data_xtal_100K: DELETED: _dummy_field",
        "data_xtal_200K: DELETED: _dummy_field",
    ]
    assert "_dummy_field" not in harness.text_editor.toPlainText()


def test_shared_abort_restores_initial_state(monkeypatch):
    harness = _SharedHarness(MULTI_BLOCK_CIF)
    monkeypatch.setattr(field_checking_module.QMessageBox, "information",
                        lambda *args, **kwargs: None)
    _patch_get_text(monkeypatch, (None, RESULT_ABORT))

    rule = RuleField("_shared_field", "suggested", "desc")
    signal, _ops = harness.run_shared(rule, ["xtal_100K", "xtal_200K"])

    assert signal == 'abort'
    assert harness.text_editor.toPlainText() == MULTI_BLOCK_CIF


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_multi_block_value_dialog_rows_and_set_all(app):
    _ = app
    dialog = MultiBlockValueDialog(
        "_diffrn.ambient_temperature",
        {"xtal_100K": "100", "xtal_200K": None},
        default_value="293",
    )

    values = dialog.get_block_values()
    assert values["xtal_100K"] == "100"
    assert values["xtal_200K"] == "293"  # missing row prefilled with the default

    dialog._same_edit.setText("150")
    dialog._apply_same_value()
    assert set(dialog.get_block_values().values()) == {"150"}
    dialog.close()


def test_check_config_dialog_block_selection(app):
    _ = app
    dialog = CheckConfigDialog(block_names=["xtal_100K", "xtal_200K"])
    config = dialog.get_config()
    assert config['selected_blocks'] == ["xtal_100K", "xtal_200K"]  # default: all

    # Unticking a block removes it from the selection
    dialog.block_checkboxes[0][1].setChecked(False)
    assert dialog.get_config()['selected_blocks'] == ["xtal_200K"]
    dialog.close()


def test_check_config_dialog_single_block_has_no_selection(app):
    _ = app
    single = CheckConfigDialog(block_names=["only"])
    plain = CheckConfigDialog()

    assert plain.get_config()['selected_blocks'] is None
    assert single.get_config()['selected_blocks'] is None
    assert plain.get_config()['block_mode'] is None
    assert single.get_config()['block_mode'] is None
    single.close()
    plain.close()


def test_check_config_dialog_block_mode_defaults_to_shared(app):
    _ = app
    dialog = CheckConfigDialog(block_names=["a", "b"])
    assert dialog.get_config()['block_mode'] == 'shared'

    dialog.independent_mode_radio.setChecked(True)
    assert dialog.get_config()['block_mode'] == 'independent'
    dialog.close()
