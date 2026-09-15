"""Behavior-focused tests for LoopEditorDialog."""

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

from gui.dialogs.loop_editor_dialog import LoopEditorDialog, LoopOption


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


@pytest.fixture(autouse=True)
def _no_modal_popups(monkeypatch):
    """Prevent any un-mocked QMessageBox call from blocking on a real popup."""
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)


def _make_option(field_names=None, data_rows=None, label="Line 2: ...", block_label=None, block_name=None):
    field_names = field_names or ["_atom_site_label", "_atom_site_fract_x"]
    data_rows = data_rows if data_rows is not None else [["C1", "0.5"], ["C2", "0.75"]]
    return LoopOption(
        label=label, field_names=field_names, data_rows=data_rows,
        block_label=block_label, block_name=block_name)


def _make_dialog(app, field_names=None, data_rows=None, block_label=None):
    """A dialog pre-loaded on its one (and only) loop option, as if the
    cursor were already inside that loop when the dialog was opened."""
    _ = app
    option = _make_option(field_names, data_rows, block_label=block_label)
    return LoopEditorDialog([option], preselected_index=0)


def test_initial_table_reflects_input(app):
    dialog = _make_dialog(app)
    source_index, names, rows = dialog.get_result()
    assert source_index == 0
    assert names == ["_atom_site_label", "_atom_site_fract_x"]
    assert rows == [["C1", "0.5"], ["C2", "0.75"]]


def test_summary_label_reflects_column_and_row_counts(app):
    dialog = _make_dialog(app)
    assert dialog.summary_label.text() == "2 columns (data names), 2 rows"

    dialog._add_row()
    assert dialog.summary_label.text() == "2 columns (data names), 3 rows"


def test_summary_label_updates_after_column_delete(app, monkeypatch):
    dialog = _make_dialog(app)
    monkeypatch.setattr(
        "gui.dialogs.loop_editor_dialog.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    dialog.table.setCurrentCell(0, 1)
    dialog._delete_column()
    assert dialog.summary_label.text() == "1 column (data name), 2 rows"


def test_edit_cell_value(app):
    dialog = _make_dialog(app)
    dialog.table.item(0, 1).setText("0.999")
    _idx, _names, rows = dialog.get_result()
    assert rows[0] == ["C1", "0.999"]


def test_add_row_appends_placeholder_row(app):
    dialog = _make_dialog(app)
    dialog._add_row()
    _idx, names, rows = dialog.get_result()
    assert len(rows) == 3
    assert rows[2] == ["?", "?"]
    assert names == ["_atom_site_label", "_atom_site_fract_x"]


def test_delete_selected_rows(app):
    dialog = _make_dialog(app)
    dialog.table.selectRow(0)
    dialog._delete_selected_rows()
    _idx, _names, rows = dialog.get_result()
    assert rows == [["C2", "0.75"]]


def test_delete_selected_rows_refuses_to_empty_the_loop(app):
    dialog = _make_dialog(app)
    dialog.table.selectAll()
    dialog._delete_selected_rows()
    _idx, _names, rows = dialog.get_result()
    # Both rows still present - a loop needs at least one data row
    assert len(rows) == 2


def test_add_column_appends_named_column_with_placeholder_values(app, monkeypatch):
    dialog = _make_dialog(app)
    monkeypatch.setattr(
        "gui.dialogs.loop_editor_dialog.QInputDialog.getText",
        lambda *a, **k: ("_atom_site_fract_z", True),
    )
    dialog._add_column()
    _idx, names, rows = dialog.get_result()
    assert names == ["_atom_site_label", "_atom_site_fract_x", "_atom_site_fract_z"]
    assert rows[0] == ["C1", "0.5", "?"]
    assert rows[1] == ["C2", "0.75", "?"]


def test_add_column_to_blank_new_loop_seeds_one_row(app, monkeypatch):
    """A loop needs at least one row - adding the first column to a blank
    'New Loop' table must not leave it with a column but zero rows."""
    dialog = LoopEditorDialog([_make_option()], preselected_index=None)
    monkeypatch.setattr(
        "gui.dialogs.loop_editor_dialog.QInputDialog.getText",
        lambda *a, **k: ("_a", True),
    )
    dialog._add_column()
    _idx, names, rows = dialog.get_result()
    assert names == ["_a"]
    assert rows == [["?"]]


def test_add_column_rejects_duplicate_name(app, monkeypatch):
    dialog = _make_dialog(app)
    warnings = []
    monkeypatch.setattr(
        "gui.dialogs.loop_editor_dialog.QInputDialog.getText",
        lambda *a, **k: ("_atom_site_label", True),
    )
    monkeypatch.setattr(
        "gui.dialogs.loop_editor_dialog.QMessageBox.warning",
        lambda *a, **k: warnings.append(a),
    )
    dialog._add_column()
    _idx, names, _rows = dialog.get_result()
    assert names == ["_atom_site_label", "_atom_site_fract_x"]
    assert warnings


def test_rename_column_updates_header_and_result(app, monkeypatch):
    dialog = _make_dialog(app)
    dialog.table.setCurrentCell(0, 1)
    monkeypatch.setattr(
        "gui.dialogs.loop_editor_dialog.QInputDialog.getText",
        lambda *a, **k: ("_atom_site_fract_y", True),
    )
    dialog._rename_column()
    _idx, names, rows = dialog.get_result()
    assert names == ["_atom_site_label", "_atom_site_fract_y"]
    # Values are untouched by a rename
    assert rows == [["C1", "0.5"], ["C2", "0.75"]]


def test_delete_column_removes_name_and_every_row_value(app, monkeypatch):
    dialog = _make_dialog(app)
    dialog.table.setCurrentCell(0, 1)
    monkeypatch.setattr(
        "gui.dialogs.loop_editor_dialog.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    dialog._delete_column()
    _idx, names, rows = dialog.get_result()
    assert names == ["_atom_site_label"]
    assert rows == [["C1"], ["C2"]]


def test_set_column_value_applies_to_every_row(app, monkeypatch):
    dialog = _make_dialog(app)
    dialog.table.setCurrentCell(0, 1)
    monkeypatch.setattr(
        "gui.dialogs.loop_editor_dialog.QInputDialog.getText",
        lambda *a, **k: ("0.25", True),
    )
    dialog._set_column_value()
    _idx, _names, rows = dialog.get_result()
    assert rows == [["C1", "0.25"], ["C2", "0.25"]]


# -- the built-in loop picker --------------------------------------------


def test_no_preselection_starts_on_blank_new_loop(app):
    option = _make_option()
    dialog = LoopEditorDialog([option], preselected_index=None)
    source_index, names, rows = dialog.get_result()
    assert source_index is None
    assert names == []
    assert rows == []
    assert dialog.summary_label.text() == "0 columns (data names), 0 rows"


def test_combo_lists_new_loop_plus_every_option(app):
    option_a = _make_option(label="Loop A")
    option_b = _make_option(label="Loop B")
    dialog = LoopEditorDialog([option_a, option_b], preselected_index=None)
    combo_texts = [dialog.loop_combo.itemText(i) for i in range(dialog.loop_combo.count())]
    assert combo_texts == ["➕ New Loop (not yet in the file)", "Loop A", "Loop B"]


def test_preselected_index_loads_that_option_and_selects_it_in_combo(app):
    option_a = _make_option(field_names=["_a"], data_rows=[["1"]], label="Loop A")
    option_b = _make_option(field_names=["_b"], data_rows=[["2"]], label="Loop B")
    dialog = LoopEditorDialog([option_a, option_b], preselected_index=1)

    assert dialog.loop_combo.currentText() == "Loop B"
    source_index, names, rows = dialog.get_result()
    assert source_index == 1
    assert names == ["_b"]
    assert rows == [["2"]]


def test_switching_combo_selection_reloads_the_table(app):
    option_a = _make_option(field_names=["_a"], data_rows=[["1"]], label="Loop A")
    option_b = _make_option(field_names=["_b"], data_rows=[["2"]], label="Loop B")
    dialog = LoopEditorDialog([option_a, option_b], preselected_index=0)

    dialog.loop_combo.setCurrentIndex(2)  # index 0 is "New Loop", so Loop B is 2
    source_index, names, rows = dialog.get_result()
    assert source_index == 1
    assert names == ["_b"]
    assert rows == [["2"]]


def test_switching_to_new_loop_clears_the_table(app):
    option = _make_option()
    dialog = LoopEditorDialog([option], preselected_index=0)

    dialog.loop_combo.setCurrentIndex(0)  # "New Loop"
    source_index, names, rows = dialog.get_result()
    assert source_index is None
    assert names == []
    assert rows == []


def test_block_banner_reflects_selected_options_block_label(app):
    option_a = _make_option(label="Loop A", block_label="Data block: data_a")
    option_b = _make_option(label="Loop B", block_label="Data block: data_b")
    dialog = LoopEditorDialog([option_a, option_b], preselected_index=0)

    # isHidden() reflects the banner's own visibility flag regardless of
    # whether the (never-shown-in-tests) dialog window itself is visible.
    assert not dialog._block_banner.isHidden()
    assert "Data block: data_a" in dialog._block_banner.text()

    dialog.loop_combo.setCurrentIndex(2)  # Loop B
    assert "Data block: data_b" in dialog._block_banner.text()


def test_block_banner_hidden_when_no_label(app):
    dialog = _make_dialog(app, block_label=None)
    assert dialog._block_banner.isHidden()


def test_new_loop_block_label_shown_while_new_loop_selected(app):
    option = _make_option()
    dialog = LoopEditorDialog(
        [option], preselected_index=None, new_loop_block_label="Data block: data_c")
    assert not dialog._block_banner.isHidden()
    assert "Data block: data_c" in dialog._block_banner.text()


# -- frozen first column --------------------------------------------------


def test_freeze_checkbox_is_checked_by_default(app):
    dialog = _make_dialog(app)
    assert dialog._freeze_checkbox.isChecked()
    assert not dialog._frozen_table.isHidden()


def test_frozen_table_shows_only_column_zero(app):
    dialog = _make_dialog(app, field_names=["_a", "_b", "_c"], data_rows=[["1", "2", "3"]])
    assert dialog._frozen_table.isColumnHidden(0) is False
    assert dialog._frozen_table.isColumnHidden(1) is True
    assert dialog._frozen_table.isColumnHidden(2) is True


def test_frozen_table_shares_model_and_selection_with_main_table(app):
    dialog = _make_dialog(app)
    assert dialog._frozen_table.model() is dialog.table.model()
    assert dialog._frozen_table.selectionModel() is dialog.table.selectionModel()


def test_editing_via_frozen_table_updates_main_table(app):
    dialog = _make_dialog(app)
    index = dialog._frozen_table.model().index(0, 0)
    dialog._frozen_table.model().setData(index, "EDITED")
    assert dialog.table.item(0, 0).text() == "EDITED"


def test_unchecking_freeze_hides_frozen_table(app):
    dialog = _make_dialog(app)
    dialog._freeze_checkbox.setChecked(False)
    assert dialog._frozen_table.isHidden()

    dialog._freeze_checkbox.setChecked(True)
    assert not dialog._frozen_table.isHidden()


def test_frozen_table_hidden_when_loop_is_blank(app):
    dialog = LoopEditorDialog([_make_option()], preselected_index=None)
    assert dialog._frozen_table.isHidden()


def test_frozen_column_tracks_added_column_becoming_first(app, monkeypatch):
    """Deleting column 0 promotes column 1 to first - the freeze must follow."""
    dialog = _make_dialog(app, field_names=["_a", "_b"], data_rows=[["1", "2"]])
    dialog.table.setCurrentCell(0, 0)
    monkeypatch.setattr(
        "gui.dialogs.loop_editor_dialog.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    dialog._delete_column()  # removes _a, leaving _b as the new column 0
    assert dialog._frozen_table.isColumnHidden(0) is False


def test_frozen_geometry_updates_on_dialog_show(app):
    dialog = _make_dialog(app, field_names=["_a"], data_rows=[["1"], ["2"], ["3"]])
    dialog.show()
    app.processEvents()
    try:
        # The overlay's laid-out height should track the real table, not the
        # near-zero size it had before the dialog was ever shown.
        assert dialog._frozen_table.geometry().height() > 50
    finally:
        dialog.close()


# -- header styling and label preview length ------------------------------


def test_header_row_is_bold(app):
    dialog = _make_dialog(app)
    assert dialog.table.horizontalHeader().font().bold()
    assert dialog._frozen_table.horizontalHeader().font().bold()


def test_loop_option_label_previews_two_names_not_three():
    from gui.loop_editing import LoopEditingMixin
    from utils.CIF_parser import CIFLoop

    class _Host(LoopEditingMixin):
        pass

    loop_obj = CIFLoop(["_a", "_b", "_c"], [["1", "2", "3"]])
    label = _Host()._loop_option_label(0, loop_obj)
    assert label == "Line 1: _a, _b, ... (1 row(s))"

    loop_obj_two = CIFLoop(["_a", "_b"], [["1", "2"]])
    label_two = _Host()._loop_option_label(0, loop_obj_two)
    assert label_two == "Line 1: _a, _b (1 row(s))"


# -- filter by data block --------------------------------------------------


def test_no_block_filter_shown_for_single_block(app):
    option = _make_option(block_name="a")
    dialog = LoopEditorDialog([option], preselected_index=0)
    assert dialog._block_checkboxes == {}


def test_block_filter_shown_and_checked_by_default_for_multiple_blocks(app):
    option_a = _make_option(label="Loop A", block_name="a")
    option_b = _make_option(label="Loop B", block_name="b")
    dialog = LoopEditorDialog([option_a, option_b], preselected_index=0)

    assert set(dialog._block_checkboxes.keys()) == {"a", "b"}
    assert all(cb.isChecked() for cb in dialog._block_checkboxes.values())
    combo_texts = [dialog.loop_combo.itemText(i) for i in range(dialog.loop_combo.count())]
    assert combo_texts == ["➕ New Loop (not yet in the file)", "Loop A", "Loop B"]


def test_unchecking_a_block_hides_its_loops_from_the_picker(app):
    option_a = _make_option(label="Loop A", block_name="a")
    option_b = _make_option(label="Loop B", block_name="b")
    dialog = LoopEditorDialog([option_a, option_b], preselected_index=0)

    dialog._block_checkboxes["b"].setChecked(False)

    combo_texts = [dialog.loop_combo.itemText(i) for i in range(dialog.loop_combo.count())]
    assert combo_texts == ["➕ New Loop (not yet in the file)", "Loop A"]


def test_filtering_out_the_selected_loop_falls_back_to_new_loop(app):
    option_a = _make_option(label="Loop A", block_name="a")
    option_b = _make_option(label="Loop B", block_name="b")
    dialog = LoopEditorDialog([option_a, option_b], preselected_index=0)

    dialog._block_checkboxes["a"].setChecked(False)

    source_index, names, rows = dialog.get_result()
    assert source_index is None
    assert names == []
    assert rows == []


def test_rechecking_a_block_restores_its_loops(app):
    option_a = _make_option(label="Loop A", block_name="a")
    option_b = _make_option(label="Loop B", block_name="b")
    dialog = LoopEditorDialog([option_a, option_b], preselected_index=0)

    dialog._block_checkboxes["b"].setChecked(False)
    dialog._block_checkboxes["b"].setChecked(True)

    combo_texts = [dialog.loop_combo.itemText(i) for i in range(dialog.loop_combo.count())]
    assert combo_texts == ["➕ New Loop (not yet in the file)", "Loop A", "Loop B"]
    # The originally-selected loop is still selected - untouched by the
    # round trip through hidden and back.
    source_index, _names, _rows = dialog.get_result()
    assert source_index == 0


def test_new_loop_always_offered_regardless_of_block_filter(app):
    option_a = _make_option(label="Loop A", block_name="a")
    option_b = _make_option(label="Loop B", block_name="b")
    dialog = LoopEditorDialog([option_a, option_b], preselected_index=None)

    dialog._block_checkboxes["a"].setChecked(False)
    dialog._block_checkboxes["b"].setChecked(False)

    combo_texts = [dialog.loop_combo.itemText(i) for i in range(dialog.loop_combo.count())]
    assert combo_texts == ["➕ New Loop (not yet in the file)"]
