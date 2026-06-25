"""Behavior-focused tests for dialog navigation workflows."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from gui.dialogs.cif_value_validation_dialog import CIFValueValidationDialog
from utils.cif_data_validator import ValidationIssue


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_value_validation_dialog_emits_navigation_signal_on_double_click(app):
    _ = app
    issues = [
        ValidationIssue(
            issue_type="type_mismatch",
            severity="warning",
            field_name="_cell.length_a",
            message="Not numeric",
            line_number=12,
        )
    ]
    dialog = CIFValueValidationDialog(issues)

    emitted_lines = []
    dialog.navigate_to_line.connect(lambda line: emitted_lines.append(line))

    item = dialog._tree.topLevelItem(0)
    dialog._on_item_double_clicked(item, 0)

    assert emitted_lines == [12]
    dialog.close()


def test_value_validation_dialog_selection_updates_details_and_button_state(app):
    _ = app
    issues = [
        ValidationIssue(
            issue_type="loop_incomplete",
            severity="error",
            field_name="_a, _b",
            message="Incomplete loop row",
            line_number=7,
            expected="multiple of 2",
            value="1",
        ),
        ValidationIssue(
            issue_type="type_mismatch",
            severity="warning",
            field_name="_cell.length_a",
            message="Not numeric",
            line_number=None,
        ),
    ]
    dialog = CIFValueValidationDialog(issues)

    with_line_item = None
    without_line_item = None
    for idx in range(dialog._tree.topLevelItemCount()):
        item = dialog._tree.topLevelItem(idx)
        issue = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if issue and issue.line_number:
            with_line_item = item
        if issue and not issue.line_number:
            without_line_item = item

    assert with_line_item is not None
    assert without_line_item is not None

    dialog._on_selection_changed(with_line_item, None)
    assert dialog._goto_btn.isEnabled() is True
    assert "Field:" in dialog._detail_label.text()
    assert "Line:" in dialog._detail_label.text()

    dialog._on_selection_changed(without_line_item, with_line_item)
    assert dialog._goto_btn.isEnabled() is False
    dialog.close()


def test_value_validation_dialog_update_issues_resets_detail_panel(app):
    _ = app
    initial = [
        ValidationIssue(
            issue_type="type_mismatch",
            severity="warning",
            field_name="_cell.length_a",
            message="Not numeric",
            line_number=9,
        )
    ]
    dialog = CIFValueValidationDialog(initial)

    dialog._detail_label.setText("Changed by selection")
    dialog._goto_btn.setEnabled(True)

    dialog.update_issues([])

    assert "Select a row" in dialog._detail_label.text()
    assert dialog._goto_btn.isEnabled() is False
    assert dialog._tree.topLevelItemCount() == 0
    dialog.close()
