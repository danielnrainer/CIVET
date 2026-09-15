"""Behavior-focused tests for LoopEditingMixin (finding and splicing loop_)."""

import pytest
from PyQt6.QtWidgets import QApplication, QDialog

from gui import main_window
from gui import loop_editing
from gui.main_window import CIFEditor


class _FakeLoopEditorDialog:
    """Stand-in for LoopEditorDialog that skips real UI interaction.

    By default it round-trips whatever was preselected (or the blank "New
    Loop" slate when nothing was), unedited; individual tests monkeypatch
    ``get_result`` on the class to simulate the user making changes.
    """

    last_instance = None

    def __init__(self, loop_options, preselected_index=None, parent=None,
                 new_loop_block_label=None):
        self.loop_options = list(loop_options)
        self.preselected_index = preselected_index
        self.new_loop_block_label = new_loop_block_label
        if preselected_index is None:
            self.result = (None, [], [])
        else:
            option = self.loop_options[preselected_index]
            self.result = (
                preselected_index,
                list(option.field_names),
                [list(row) for row in option.data_rows],
            )
        _FakeLoopEditorDialog.last_instance = self

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
    """Move the text cursor onto the (0-indexed) line that matches ``text`` exactly."""
    lines = editor.text_editor.toPlainText().split('\n')
    line_number = lines.index(text)
    block = editor.text_editor.document().findBlockByNumber(line_number)
    cursor = editor.text_editor.textCursor()
    cursor.setPosition(block.position())
    editor.text_editor.setTextCursor(cursor)


def test_find_loops_locates_single_loop(editor):
    editor.text_editor.setText(
        "data_a\nloop_\n_atom_site_label\n_atom_site_fract_x\nC1 0.5\nC2 0.75\n\n"
        "_cell_length_a 5.0\n")
    lines = editor.text_editor.toPlainText().split('\n')
    loops = editor._find_loops(lines)
    assert len(loops) == 1
    start_idx, consumed, loop_obj = loops[0]
    assert lines[start_idx] == "loop_"
    assert lines[start_idx + consumed] == ""
    assert loop_obj.field_names == ["_atom_site_label", "_atom_site_fract_x"]
    assert loop_obj.data_rows == [["C1", "0.5"], ["C2", "0.75"]]


def test_find_loops_skips_loop_text_inside_multiline_value(editor):
    editor.text_editor.setText(
        "data_a\n_note\n;\nsee loop_ below\n;\nloop_\n_a\n_b\n1 2\n")
    lines = editor.text_editor.toPlainText().split('\n')
    loops = editor._find_loops(lines)
    assert len(loops) == 1
    assert loops[0][2].field_names == ["_a", "_b"]


def test_edit_loop_at_cursor_edits_loop_under_cursor(editor, monkeypatch):
    monkeypatch.setattr(loop_editing, "LoopEditorDialog", _FakeLoopEditorDialog)
    editor.text_editor.setText(
        "data_a\nloop_\n_atom_site_label\n_atom_site_fract_x\nC1 0.5\nC2 0.75\n\n"
        "_cell_length_a 5.0\n")
    _place_cursor_on_line_containing(editor, "_atom_site_label")

    # Simulate the user deleting a row in the dialog, keeping the same loop
    def _dropped_second_row(self):
        source_index, field_names, data_rows = self.result
        return source_index, field_names, [data_rows[0]]
    monkeypatch.setattr(_FakeLoopEditorDialog, "get_result", _dropped_second_row)

    editor.edit_loop_at_cursor()

    assert _FakeLoopEditorDialog.last_instance.preselected_index == 0
    content = editor.text_editor.toPlainText()
    assert "C2" not in content
    assert "C1 0.5" in content
    assert "_cell_length_a 5.0" in content


def test_edit_loop_at_cursor_deleting_all_columns_removes_the_loop(editor, monkeypatch):
    monkeypatch.setattr(loop_editing, "LoopEditorDialog", _FakeLoopEditorDialog)
    editor.text_editor.setText(
        "data_a\nloop_\n_a\n_b\n1 2\n3 4\n\n_cell_length_a 5.0\n")
    _place_cursor_on_line_containing(editor, "loop_")

    def _drop_everything(self):
        return self.preselected_index, [], []
    monkeypatch.setattr(_FakeLoopEditorDialog, "get_result", _drop_everything)

    editor.edit_loop_at_cursor()

    content = editor.text_editor.toPlainText()
    assert "loop_" not in content
    assert "_cell_length_a 5.0" in content


def test_edit_loop_at_cursor_with_no_loops_opens_blank_dialog(editor, monkeypatch):
    monkeypatch.setattr(loop_editing, "LoopEditorDialog", _FakeLoopEditorDialog)
    original_content = "data_a\n_cell_length_a 5.0\n"
    editor.text_editor.setText(original_content)
    _place_cursor_on_line_containing(editor, "_cell_length_a 5.0")

    editor.edit_loop_at_cursor()

    assert _FakeLoopEditorDialog.last_instance.loop_options == []
    assert _FakeLoopEditorDialog.last_instance.preselected_index is None
    # Nothing was built in the dialog, so the document is untouched
    assert editor.text_editor.toPlainText() == original_content


def test_edit_loop_at_cursor_offers_all_loops_when_cursor_outside_any(editor, monkeypatch):
    monkeypatch.setattr(loop_editing, "LoopEditorDialog", _FakeLoopEditorDialog)
    editor.text_editor.setText(
        "data_a\n"
        "loop_\n_a\n_b\n1 2\n\n"
        "loop_\n_c\n_d\n3 4\n\n"
        "_cell_length_a 5.0\n"
    )
    # Cursor sits on the standalone field, outside both loops
    _place_cursor_on_line_containing(editor, "_cell_length_a 5.0")

    def _pick_second_loop(self):
        option = self.loop_options[1]
        return 1, list(option.field_names), [list(row) for row in option.data_rows]
    monkeypatch.setattr(_FakeLoopEditorDialog, "get_result", _pick_second_loop)

    editor.edit_loop_at_cursor()

    assert _FakeLoopEditorDialog.last_instance.preselected_index is None
    assert len(_FakeLoopEditorDialog.last_instance.loop_options) == 2

    content = editor.text_editor.toPlainText()
    # The targeted (second) loop round-tripped unchanged...
    assert "_c" in content and "_d" in content and "3 4" in content
    # ...and the other loop was left completely untouched
    assert "_a" in content and "_b" in content and "1 2" in content


def test_edit_loop_at_cursor_inserts_a_brand_new_loop(editor, monkeypatch):
    monkeypatch.setattr(loop_editing, "LoopEditorDialog", _FakeLoopEditorDialog)
    editor.text_editor.setText("data_a\n_cell_length_a 5.0\n")
    _place_cursor_on_line_containing(editor, "_cell_length_a 5.0")

    def _build_new_loop(self):
        return None, ["_a", "_b"], [["1", "2"]]
    monkeypatch.setattr(_FakeLoopEditorDialog, "get_result", _build_new_loop)

    editor.edit_loop_at_cursor()

    content = editor.text_editor.toPlainText()
    assert "loop_" in content
    assert "1 2" in content
    lines = content.split('\n')
    # Inserted right before the cursor's original line, which is still present
    assert lines.index("loop_") < lines.index("_cell_length_a 5.0")


def test_edit_loop_at_cursor_omits_block_label_for_single_block_file(editor, monkeypatch):
    monkeypatch.setattr(loop_editing, "LoopEditorDialog", _FakeLoopEditorDialog)
    editor.text_editor.setText("data_a\nloop_\n_a\n_b\n1 2\n")
    _place_cursor_on_line_containing(editor, "loop_")

    editor.edit_loop_at_cursor()

    assert _FakeLoopEditorDialog.last_instance.loop_options[0].block_label is None
    # block_name is still populated even when there's only one block - the
    # dialog's block filter just won't show since there's nothing to filter.
    assert _FakeLoopEditorDialog.last_instance.loop_options[0].block_name == "a"


def test_edit_loop_at_cursor_passes_block_label_for_multi_block_file(editor, monkeypatch):
    monkeypatch.setattr(loop_editing, "LoopEditorDialog", _FakeLoopEditorDialog)
    editor.text_editor.setText(
        "data_a\n_cell_length_a 5.0\n\n"
        "data_b\nloop_\n_a\n_b\n1 2\n"
    )
    _place_cursor_on_line_containing(editor, "loop_")

    editor.edit_loop_at_cursor()

    assert _FakeLoopEditorDialog.last_instance.loop_options[0].block_label == "Data block: data_b"
    assert _FakeLoopEditorDialog.last_instance.loop_options[0].block_name == "b"


def test_edit_loop_at_cursor_passes_new_loop_block_label(editor, monkeypatch):
    monkeypatch.setattr(loop_editing, "LoopEditorDialog", _FakeLoopEditorDialog)
    editor.text_editor.setText(
        "data_a\n_cell_length_a 5.0\n\n"
        "data_b\n_cell_length_a 6.0\n"
    )
    _place_cursor_on_line_containing(editor, "_cell_length_a 6.0")

    editor.edit_loop_at_cursor()

    assert _FakeLoopEditorDialog.last_instance.new_loop_block_label == "Data block: data_b"
