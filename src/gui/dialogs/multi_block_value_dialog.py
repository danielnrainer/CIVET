"""Dialog for resolving a field whose value differs between data blocks.

Used by the shared multi-block check mode: when the selected data blocks
disagree on a field's current value (e.g. _diffrn.ambient_temperature in a
variable-temperature study), this dialog shows one editable row per block
instead of silently applying a single value to all of them.
See .github/multi_data_block_plan.md, section 2.3.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QPushButton)
from PyQt6.QtCore import Qt
from . import RESULT_ABORT, RESULT_STOP_SAVE
from .progress_banner import build_check_progress_banner


class MultiBlockValueDialog(QDialog):
    """One editable value row per data block for a diverging field."""

    def __init__(self, field_name, block_values, default_value=None,
                 description="", parent=None, progress=None):
        """
        Args:
            field_name: the CIF data name being resolved
            block_values: dict {block_code: current value or None if the
                field is missing in that block}, in file order
            default_value: the rule's suggested value, if any
            description: rule description shown to the user
            progress: Optional (current, total) tuple for the "Check
                N/Total" banner; see CheckProgressTracker.snapshot().
        """
        super().__init__(parent)
        self.setWindowTitle("Resolve Per-Block Values")
        self.field_name = field_name
        self._edits = {}  # block_code -> QLineEdit

        # Orange "differs" styling, matching CIFInputDialog's convention
        self.setStyleSheet("""
            QDialog {
                background-color: #FFF3E0;
                border: 2px solid #FF9800;
            }
            QLabel {
                background-color: transparent;
            }
            QLineEdit {
                background-color: white;
                border: 1px solid #FF9800;
                padding: 5px;
            }
        """)

        layout = QVBoxLayout(self)

        progress_banner = build_check_progress_banner(progress)
        if progress_banner:
            layout.addWidget(progress_banner)

        header = QLabel("⚠️ VALUE DIFFERS BETWEEN DATA BLOCKS")
        header.setStyleSheet("font-weight: bold; color: #F57C00; padding: 5px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        intro = QLabel(
            f"'{field_name}' has different values in the selected data blocks.\n"
            "Review each block's value below .\n\n"
            + (f"Description: {description}\n" if description else "")
            + (f"Suggested value: {default_value}" if default_value else "")
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        for row, (block_code, value) in enumerate(block_values.items()):
            name_label = QLabel(f"data_{block_code}")
            name_label.setStyleSheet("font-weight: bold; color: #4A148C;")
            grid.addWidget(name_label, row, 0)

            edit = QLineEdit()
            if value is not None:
                edit.setText(str(value))
            else:
                edit.setPlaceholderText("(missing — leave empty to skip this block)")
                if default_value:
                    edit.setText(str(default_value))
            grid.addWidget(edit, row, 1)
            self._edits[block_code] = edit
        layout.addLayout(grid)

        # Convenience: force one value into every row
        same_row = QHBoxLayout()
        self._same_edit = QLineEdit()
        self._same_edit.setPlaceholderText("value for all blocks")
        if default_value:
            self._same_edit.setText(str(default_value))
        same_button = QPushButton("Set for all blocks")
        same_button.clicked.connect(self._apply_same_value)
        same_row.addWidget(self._same_edit)
        same_row.addWidget(same_button)
        layout.addLayout(same_row)

        button_box = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel Current")
        cancel_button.clicked.connect(self.reject)
        abort_button = QPushButton("Abort All Changes")
        abort_button.clicked.connect(lambda: self.done(RESULT_ABORT))
        stop_save_button = QPushButton("Stop && Save")
        stop_save_button.clicked.connect(lambda: self.done(RESULT_STOP_SAVE))
        button_box.addWidget(ok_button)
        button_box.addWidget(cancel_button)
        button_box.addWidget(abort_button)
        button_box.addWidget(stop_save_button)
        layout.addLayout(button_box)

        self.setMinimumWidth(650)

    def _apply_same_value(self):
        value = self._same_edit.text()
        for edit in self._edits.values():
            edit.setText(value)

    def get_block_values(self):
        """Return {block_code: entered value} (empty strings included)."""
        return {block: edit.text() for block, edit in self._edits.items()}

    @staticmethod
    def getValues(parent, field_name, block_values, default_value=None,
                  description="", show_dialog_fn=None, progress=None):
        """Show the dialog; returns (values_dict_or_None, result).

        Result codes follow CIFInputDialog.getText: Accepted (apply values),
        Rejected (skip field, no changes), RESULT_ABORT, RESULT_STOP_SAVE
        (apply values, then stop the run).
        """
        if show_dialog_fn is None:
            show_dialog_fn = lambda d: d.exec()

        dialog = MultiBlockValueDialog(field_name, block_values, default_value,
                                       description, parent, progress=progress)
        result = show_dialog_fn(dialog)

        if result == QDialog.DialogCode.Accepted:
            return dialog.get_block_values(), QDialog.DialogCode.Accepted
        if result == RESULT_STOP_SAVE:
            return dialog.get_block_values(), RESULT_STOP_SAVE
        if result == RESULT_ABORT:
            return None, RESULT_ABORT
        return None, QDialog.DialogCode.Rejected
