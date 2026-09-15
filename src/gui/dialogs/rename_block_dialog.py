"""Dialog for renaming a CIF data block."""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox,
                              QLineEdit, QLabel, QDialogButtonBox)

from utils.cif_block_rename import validate_new_block_name


class RenameBlockDialog(QDialog):
    """Pick a data block and a new name for it.

    Live-validates the new name (non-empty, no whitespace/reserved
    characters, not already used by another block in the file) and only
    enables OK once it is usable.
    """

    def __init__(self, block_names, preselected_name=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rename Data Block")
        self.block_names = list(block_names)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Renaming updates the data_ header, any _vrf_ validation-reply-form "
            "field names, _audit.block_code, and cross-block _audit_link.block_code "
            "references that point at this block (including inside a loop_). "
            "Nothing else in the file is touched."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.block_combo = QComboBox()
        self.block_combo.addItems([f"data_{name}" for name in self.block_names])
        if preselected_name in self.block_names:
            self.block_combo.setCurrentIndex(self.block_names.index(preselected_name))
        form.addRow("Block to rename:", self.block_combo)

        self.new_name_edit = QLineEdit()
        form.addRow("New name:", self.new_name_edit)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #C62828;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.block_combo.currentIndexChanged.connect(self._validate)
        self.new_name_edit.textChanged.connect(self._validate)
        self.new_name_edit.setFocus()
        self.setMinimumWidth(440)

    def current_old_name(self):
        idx = self.block_combo.currentIndex()
        return self.block_names[idx] if 0 <= idx < len(self.block_names) else None

    def _validate(self):
        old_name = self.current_old_name()
        new_name = self.new_name_edit.text()
        if old_name is None:
            self.error_label.setText("No data block selected.")
            self.ok_button.setEnabled(False)
            return
        error = validate_new_block_name(new_name, self.block_names, old_name)
        if error:
            self.error_label.setText(error)
            self.ok_button.setEnabled(False)
        elif new_name == old_name:
            self.error_label.setText("Enter a different name to rename this block.")
            self.ok_button.setEnabled(False)
        else:
            self.error_label.setText("")
            self.ok_button.setEnabled(True)

    def get_result(self):
        """Return (old_name, new_name). Only meaningful after Accepted."""
        return self.current_old_name(), self.new_name_edit.text()
