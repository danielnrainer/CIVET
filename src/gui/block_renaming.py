"""GUI mixin for renaming a CIF data block and its cross-references.

Wraps utils.cif_block_rename.rename_data_block with a picker dialog (which
data block, and its new name) and a summary of the incidental changes made
alongside the data_ header rename (VRF field names, _audit.block_code,
cross-block _audit_link.block_code references, ...). See that module for the
full list of places a rename touches, and why.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QDialog, QMessageBox, QTextEdit

from utils.CIF_parser import list_data_block_names
from utils.cif_block_rename import rename_data_block
from .dialogs.rename_block_dialog import RenameBlockDialog

if TYPE_CHECKING:
    from .main_window import CIFEditor


class BlockRenamingMixin:
    """Mixin providing the "Rename Data Block..." action for CIFEditor.

    Expects the host class to provide:
        - self.text_editor  (QTextEdit)
        - self._show_dialog_with_configured_interaction(dialog)  (defined on CIFEditor)
        - self._block_name_for_line(lines, line_index)  (from LoopEditingMixin;
          not redeclared here so LoopEditingMixin's implementation is used
          regardless of mixin order)
    """

    text_editor: QTextEdit

    def rename_data_block_dialog(self):
        """Open the rename-block dialog and apply the result, if any."""
        content = self.text_editor.toPlainText()
        block_names = list_data_block_names(content)

        if not block_names:
            QMessageBox.information(
                self, "Rename Data Block",
                "No data_ block was found in the current file.",
            )
            return

        lines = content.split('\n')
        cursor_line = self.text_editor.textCursor().blockNumber()
        preselected = self._block_name_for_line(lines, cursor_line)

        dialog = RenameBlockDialog(block_names, preselected_name=preselected, parent=self)
        if self._show_dialog_with_configured_interaction(dialog) != QDialog.DialogCode.Accepted:
            return

        old_name, new_name = dialog.get_result()
        if old_name is None:
            return

        try:
            result = rename_data_block(content, old_name, new_name)
        except ValueError as exc:
            QMessageBox.critical(self, "Rename Data Block", str(exc))
            return

        if not result.changed:
            QMessageBox.information(
                self, "Rename Data Block",
                "Nothing to change - the new name matches the current one.",
            )
            return

        self.text_editor.setText(result.content)

        summary = "\n".join(f"• {c}" for c in result.changes)
        QMessageBox.information(
            self, "Data Block Renamed",
            f"data_{old_name} was renamed to data_{new_name}.\n\nChanges made:\n{summary}",
        )
