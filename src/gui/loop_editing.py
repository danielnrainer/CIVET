"""GUI mixin for locating and editing loop_ structures in the CIF text.

A CIF loop_ is a table: the data names in its header are column headers, and
each data row is one record holding one value per column. This mixin finds
every loop_ in the document, opens LoopEditorDialog pre-loaded with the one
under the text cursor (or blank, ready to build a new loop, if the cursor
isn't inside one - the dialog's own picker lets the user load a different
loop without a separate popup), and splices the result back into the
document without touching anything else in the file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

from PyQt6.QtWidgets import QDialog, QTextEdit

from utils.CIF_parser import CIFParser, CIFLoop
from .dialogs.loop_editor_dialog import LoopEditorDialog, LoopOption

if TYPE_CHECKING:
    from .main_window import CIFEditor


class LoopEditingMixin:
    """Mixin providing a general-purpose loop_ table editor for CIFEditor.

    Expects the host class to provide:
        - self.text_editor  (QTextEdit)
        - self.modified     (bool)
        - self.update_status_bar()
        - self._show_dialog_with_configured_interaction(dialog)
    """

    text_editor: QTextEdit
    modified: bool

    def update_status_bar(self) -> None:
        raise NotImplementedError()

    def _show_dialog_with_configured_interaction(
        self,
        dialog: QDialog,
        mode_setting_key: str = "dialogs.default_interaction_mode",
    ) -> int:
        raise NotImplementedError()

    def _find_loops(self, lines: List[str]) -> List[Tuple[int, int, CIFLoop]]:
        """Scan raw document lines for every loop_.

        Returns a list of (start_index, lines_consumed, CIFLoop) tuples, in
        document order. ``lines[start_index:start_index + lines_consumed]``
        is exactly the loop's own text (the ``loop_`` line through its last
        data row).
        """
        helper = CIFParser()
        loops: List[Tuple[int, int, CIFLoop]] = []
        idx = 0
        in_multiline = False
        while idx < len(lines):
            stripped = lines[idx].strip()

            if stripped.startswith(';'):
                in_multiline = not in_multiline
                idx += 1
                continue
            if in_multiline:
                idx += 1
                continue

            if stripped.lower() == 'loop_':
                loop_obj, consumed = helper._parse_loop(lines, idx)
                if loop_obj is not None:
                    loops.append((idx, consumed, loop_obj))
                    idx += consumed
                    continue

            idx += 1
        return loops

    def _block_name_for_line(self, lines: List[str], line_index: int) -> Optional[str]:
        """Return the data_ block code (e.g. 'crystal1') containing
        line_index, or None if no data_ header precedes it."""
        for i in range(line_index, -1, -1):
            stripped = lines[i].strip()
            if stripped.lower().startswith('data_'):
                return stripped[5:]
        return None

    def _block_label_for_line(self, lines: List[str], line_index: int) -> Optional[str]:
        """Return 'Data block: data_X' for the block containing line_index, or
        None for single-block files where the label would be uninformative."""
        parser = CIFParser()
        parser.parse_file('\n'.join(lines))
        if not parser.has_multiple_blocks():
            return None
        block_name = self._block_name_for_line(lines, line_index)
        return f"Data block: data_{block_name}" if block_name else None

    def _loop_option_label(self, start_idx: int, loop_obj: CIFLoop) -> str:
        """Short description of a loop_ for the dialog's loop picker."""
        names_preview = ", ".join(loop_obj.field_names[:2])
        if len(loop_obj.field_names) > 2:
            names_preview += ", ..."
        return f"Line {start_idx + 1}: {names_preview} ({len(loop_obj.data_rows)} row(s))"

    def edit_loop_at_cursor(self):
        """Open the loop editor, pre-loaded with the loop_ under the cursor.

        If the cursor isn't positioned inside a loop, the dialog opens with
        a blank "New Loop" table instead - the user can still load any
        existing loop from the dialog's own picker, or build a new one.
        """
        content = self.text_editor.toPlainText()
        lines = content.split('\n')
        loops = self._find_loops(lines)

        cursor_line = self.text_editor.textCursor().blockNumber()
        cursor_index = next(
            (i for i, entry in enumerate(loops)
             if entry[0] <= cursor_line < entry[0] + entry[1]),
            None,
        )

        loop_options = [
            LoopOption(
                label=self._loop_option_label(start_idx, loop_obj),
                field_names=loop_obj.field_names,
                data_rows=loop_obj.data_rows,
                block_label=self._block_label_for_line(lines, start_idx),
                block_name=self._block_name_for_line(lines, start_idx),
            )
            for start_idx, _consumed, loop_obj in loops
        ]

        dialog = LoopEditorDialog(
            loop_options,
            preselected_index=cursor_index,
            parent=self,
            new_loop_block_label=self._block_label_for_line(lines, cursor_line),
        )
        if self._show_dialog_with_configured_interaction(dialog) != QDialog.DialogCode.Accepted:
            return

        source_index, new_field_names, new_rows = dialog.get_result()

        if source_index is not None:
            start_idx, consumed, _loop_obj = loops[source_index]
            self._splice_loop(lines, start_idx, consumed, new_field_names, new_rows)
        elif new_field_names:
            self._insert_new_loop(lines, cursor_line, new_field_names, new_rows)
        # else: "New Loop" was never built into anything - nothing to do.

    def _splice_loop(
        self,
        lines: List[str],
        start_idx: int,
        consumed: int,
        new_field_names: List[str],
        new_rows: List[List[str]],
    ) -> None:
        """Replace one loop's lines with the edited version, leaving the rest
        of the document untouched. An empty field list drops the loop
        entirely."""
        helper = CIFParser()
        if new_field_names:
            new_loop_lines = helper._format_loop(CIFLoop(new_field_names, new_rows))
        else:
            new_loop_lines = []

        new_lines = lines[:start_idx] + new_loop_lines + lines[start_idx + consumed:]
        self.text_editor.setText('\n'.join(new_lines))
        self.modified = True
        self.update_status_bar()

    def _insert_new_loop(
        self,
        lines: List[str],
        insert_at_line: int,
        field_names: List[str],
        data_rows: List[List[str]],
    ) -> None:
        """Insert a brand-new loop_ built in the dialog at insert_at_line,
        leaving the rest of the document untouched."""
        helper = CIFParser()
        new_loop_lines = list(helper._format_loop(CIFLoop(field_names, data_rows)))
        if insert_at_line >= len(lines) or lines[insert_at_line].strip() != '':
            new_loop_lines.append('')

        new_lines = lines[:insert_at_line] + new_loop_lines + lines[insert_at_line:]
        self.text_editor.setText('\n'.join(new_lines))
        self.modified = True
        self.update_status_bar()
