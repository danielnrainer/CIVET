"""Behavior-focused tests for BlockRenamingMixin (the "Rename Data Block..." action)."""

import pytest
from PyQt6.QtWidgets import QApplication, QDialog

from gui import main_window
from gui import block_renaming
from gui.main_window import CIFEditor


class _FakeRenameDialog:
    """Stand-in for RenameBlockDialog that returns a canned result."""

    last_instance = None

    def __init__(self, block_names, preselected_name=None, parent=None):
        self.block_names = list(block_names)
        self.preselected_name = preselected_name
        self.result = (preselected_name or (block_names[0] if block_names else None), "")
        _FakeRenameDialog.last_instance = self

    def get_result(self):
        return self.result


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


@pytest.fixture
def editor(app, monkeypatch):
    _ = app
    monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(main_window.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(main_window.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(main_window.QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr(main_window.QMessageBox, "question",
                         lambda *a, **k: main_window.QMessageBox.StandardButton.Discard)
    window = CIFEditor()
    window.update_status_bar = lambda: None
    monkeypatch.setattr(
        window, "_show_dialog_with_configured_interaction",
        lambda dialog, *a, **k: QDialog.DialogCode.Accepted,
    )
    yield window
    window.close()
    window.deleteLater()


def _place_cursor_on_line_containing(editor, text):
    lines = editor.text_editor.toPlainText().split('\n')
    line_number = lines.index(text)
    block = editor.text_editor.document().findBlockByNumber(line_number)
    cursor = editor.text_editor.textCursor()
    cursor.setPosition(block.position())
    editor.text_editor.setTextCursor(cursor)


def test_rename_dialog_preselects_block_under_cursor(editor, monkeypatch):
    monkeypatch.setattr(block_renaming, "RenameBlockDialog", _FakeRenameDialog)
    editor.text_editor.setText("data_a\n_x 1\ndata_b\n_x 2\n")
    _place_cursor_on_line_containing(editor, "_x 2")

    _FakeRenameDialog.last_instance = None
    editor.rename_data_block_dialog()

    assert _FakeRenameDialog.last_instance is not None
    assert _FakeRenameDialog.last_instance.preselected_name == "b"


def test_rename_applies_result_and_updates_editor(editor, monkeypatch):
    monkeypatch.setattr(block_renaming, "RenameBlockDialog", _FakeRenameDialog)
    editor.text_editor.setText(
        "data_old_name\n"
        "_vrf_PLAT020_old_name\n"
        ";\n"
        "PROBLEM: x\nRESPONSE: y\n"
        ";\n"
    )

    def _result(self):
        return "old_name", "new_name"
    monkeypatch.setattr(_FakeRenameDialog, "get_result", _result)

    editor.rename_data_block_dialog()

    content = editor.text_editor.toPlainText()
    assert "data_new_name" in content
    assert "_vrf_PLAT020_new_name" in content
    assert "old_name" not in content


def test_rename_no_op_when_dialog_cancelled(editor, monkeypatch):
    monkeypatch.setattr(block_renaming, "RenameBlockDialog", _FakeRenameDialog)
    original = "data_old_name\n_x 1\n"
    editor.text_editor.setText(original)

    monkeypatch.setattr(
        editor, "_show_dialog_with_configured_interaction",
        lambda dialog, *a, **k: QDialog.DialogCode.Rejected,
    )

    editor.rename_data_block_dialog()

    assert editor.text_editor.toPlainText() == original


def test_rename_reports_error_for_invalid_new_name(editor, monkeypatch):
    monkeypatch.setattr(block_renaming, "RenameBlockDialog", _FakeRenameDialog)
    original = "data_a\n_x 1\ndata_b\n_x 2\n"
    editor.text_editor.setText(original)

    def _result(self):
        return "a", "b"  # collides with the existing data_b block
    monkeypatch.setattr(_FakeRenameDialog, "get_result", _result)

    errors = []
    monkeypatch.setattr(main_window.QMessageBox, "critical", lambda *a, **k: errors.append(a))

    editor.rename_data_block_dialog()

    assert errors
    assert editor.text_editor.toPlainText() == original
