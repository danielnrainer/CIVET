"""Behavior-focused tests for main window workflows."""

import pytest
from PyQt6.QtWidgets import QApplication

from gui import main_window
from gui.main_window import CIFEditor
from utils import cif_data_validator as cif_data_validator_module
from utils.cif_data_validator import ValidationIssue


class _Signal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _FakeValidationDialog:
    instances = []

    def __init__(self, issues, parent=None):
        self.issues = list(issues)
        self.parent = parent
        self.navigate_to_line = _Signal()
        self.refresh_requested = _Signal()
        _FakeValidationDialog.instances.append(self)

    def update_issues(self, issues):
        self.issues = list(issues)


class _FakeValidator:
    def __init__(self, issues):
        self._issues = list(issues)

    def validate(self, parser, dict_manager):
        _ = (parser, dict_manager)
        return list(self._issues)


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


@pytest.fixture
def editor(app, monkeypatch):
    _ = app
    monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("", ""))
    monkeypatch.setattr(main_window.QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_window.QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_window.QMessageBox, "critical", lambda *args, **kwargs: None)
    window = CIFEditor()
    yield window
    window.close()
    window.deleteLater()


def _stub_window_updates(editor):
    editor.prompt_for_dictionary_suggestions = lambda *args, **kwargs: None
    editor._refresh_compliance_status = lambda: None
    editor.update_status_bar = lambda: None
    editor.add_to_recent_files = lambda *args, **kwargs: None
    editor.update_window_title = lambda *args, **kwargs: None


def test_main_window_open_file_loads_content(editor, tmp_path):
    _stub_window_updates(editor)
    content = "data_test\n_cell_length_a 5.0\n"
    cif_path = tmp_path / "open_target.cif"
    cif_path.write_text(content, encoding="utf-8")

    editor.current_file = str(cif_path)
    editor.open_file(initial=True)

    assert editor.text_editor.toPlainText() == content
    assert editor.modified is False


def test_main_window_save_file_overwrites_existing_content(editor, tmp_path, monkeypatch):
    _stub_window_updates(editor)
    cif_path = tmp_path / "save_target.cif"
    editor.current_file = str(cif_path)
    editor.text_editor.setText("data_save\n_cell_length_a 5.0\n")
    editor.modified = True
    monkeypatch.setattr(editor, "_check_duplicate_data_names", lambda *args, **kwargs: True)
    monkeypatch.setattr(main_window.QMessageBox, "question", lambda *args, **kwargs: main_window.QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(main_window, "update_audit_creation_date", lambda content, cif_format: content)
    monkeypatch.setattr(main_window, "update_audit_creation_method", lambda content, cif_format: content)

    editor.save_file()

    assert cif_path.exists()
    assert cif_path.read_text(encoding="utf-8") == "data_save\n_cell_length_a 5.0"
    assert editor.modified is False


def test_main_window_validate_data_values_uses_validation_dialog(editor, monkeypatch):
    _stub_window_updates(editor)
    _FakeValidationDialog.instances.clear()
    issues = [
        ValidationIssue(
            issue_type="type_mismatch",
            severity="warning",
            field_name="_cell.length_a",
            message="Not numeric",
            line_number=2,
        )
    ]
    editor.text_editor.setText("data_test\n_cell_length_a bad\n")
    monkeypatch.setattr(cif_data_validator_module, "CIFDataValidator", lambda: _FakeValidator(issues))
    monkeypatch.setattr(main_window, "CIFValueValidationDialog", _FakeValidationDialog)
    monkeypatch.setattr(editor, "_show_dialog_with_configured_interaction", lambda *args, **kwargs: None)

    captured_status_updates = []
    monkeypatch.setattr(editor, "_update_status_panel_values", lambda received: captured_status_updates.append(list(received)))

    editor.validate_data_values()

    assert _FakeValidationDialog.instances
    assert _FakeValidationDialog.instances[0].issues == issues
    assert captured_status_updates
    assert captured_status_updates[-1] == issues


def test_main_window_validate_data_values_rejects_empty_content(editor, monkeypatch):
    _stub_window_updates(editor)
    editor.text_editor.setText("   \n")
    captured_messages = []
    monkeypatch.setattr(main_window.QMessageBox, "information", lambda *args, **kwargs: captured_messages.append(args[1:3]))

    editor.validate_data_values()

    assert captured_messages
    assert captured_messages[0][0] == "No Content"