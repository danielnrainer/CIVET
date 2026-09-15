"""
Loop Editor Dialog
===================

Lets the user view and edit a CIF loop_ as a spreadsheet-style table: each
data name is a column header and each row is one record holding one value
per column. Supports adding/removing/renaming columns (data items), adding/
removing rows, editing individual cells, and setting every row's value for
one column in a single action.

The dialog also doubles as the picker for "which loop_ do I want to edit":
a combo box at the top lists every loop_ found in the document plus a
"New Loop" entry for building one from scratch, so callers never need a
separate selection popup.
"""

from typing import List, NamedTuple, Optional, Tuple

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableView,
    QTableWidgetItem, QLabel, QMessageBox, QInputDialog, QDialogButtonBox,
    QAbstractItemView, QGroupBox, QComboBox, QCheckBox, QHeaderView,
)

from gui.collapsible_widgets import CollapsibleSection

# Consistent with the action-button colour language used elsewhere in the
# app (e.g. the Data Name Validation dialog): green = add, red = delete,
# blue = rename/set.
_COLOR_ADD = "#27ae60"
_COLOR_DELETE = "#c0392b"
_COLOR_EDIT = "#2980b9"


class LoopOption(NamedTuple):
    """One selectable entry in the dialog's loop picker."""
    label: str
    field_names: List[str]
    data_rows: List[List[str]]
    block_label: Optional[str] = None
    block_name: Optional[str] = None


class LoopEditorDialog(QDialog):
    """Pick, view, and edit a CIF loop's column (data name) and row (value)
    structure - or build a brand-new loop from scratch."""

    def __init__(self, loop_options: List[LoopOption],
                 preselected_index: Optional[int] = None,
                 parent=None, new_loop_block_label: Optional[str] = None):
        """
        loop_options: every loop_ found in the document, in document order.
        preselected_index: index into loop_options to load initially, or
            None to start from the blank "New Loop" slate (e.g. when the
            text cursor wasn't positioned inside any existing loop).
        new_loop_block_label: data-block banner text to show while "New
            Loop" is selected (the block the new loop would be inserted into).
        """
        super().__init__(parent)
        self._loop_options = loop_options
        self._new_loop_block_label = new_loop_block_label
        self._field_names: List[str] = []

        self.setWindowTitle("Edit Loop")
        self.setModal(True)
        self.resize(760, 560)
        self.setMinimumSize(560, 400)

        layout = QVBoxLayout(self)

        # Filter by data block - only shown when the loops on offer actually
        # span more than one block, since otherwise there's nothing to filter.
        distinct_blocks = []
        for option in loop_options:
            if option.block_name and option.block_name not in distinct_blocks:
                distinct_blocks.append(option.block_name)

        self._block_checkboxes: dict = {}
        if len(distinct_blocks) > 1:
            blocks_group = QGroupBox("Filter by Data Block")
            blocks_layout = QHBoxLayout(blocks_group)
            for block_name in distinct_blocks:
                checkbox = QCheckBox(f"data_{block_name}")
                checkbox.setChecked(True)
                checkbox.toggled.connect(self._on_block_filter_changed)
                blocks_layout.addWidget(checkbox)
                self._block_checkboxes[block_name] = checkbox
            blocks_layout.addStretch()
            layout.addWidget(blocks_group)

        # Loop picker - lets the user load any loop_ in the file into the
        # table below, or start building a brand-new one, without ever
        # leaving this dialog.
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Editing:"))
        self.loop_combo = QComboBox()
        self.loop_combo.setToolTip(
            "Switching loops replaces the table below with the selected "
            "loop's data."
        )
        self.loop_combo.currentIndexChanged.connect(self._on_loop_selected)
        selector_layout.addWidget(self.loop_combo, 1)
        layout.addLayout(selector_layout)

        # Banner naming the data block the loaded loop belongs to (multi-
        # block files only); updated whenever the selection changes.
        self._block_banner = QLabel()
        self._block_banner.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #4A148C; "
            "background-color: rgba(156, 39, 176, 0.12); "
            "border: 1px solid #9C27B0; border-radius: 3px; padding: 5px;")
        self._block_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._block_banner.setVisible(False)
        layout.addWidget(self._block_banner)

        # "How to use" - helpful the first time, noise afterwards: collapsed
        # by default, matching the app's other instructional sections.
        instructions_section = CollapsibleSection("How to use this dialog", expanded=False)
        instructions_text = QLabel(
            "<b>Columns</b> (data items): add, rename, or delete one - deleting a "
            "column removes its value from every row too, and deleting every "
            "column removes the loop entirely.<br>"
            "<b>Rows</b>: add or delete records - a loop always needs at least one.<br>"
            "Double-click any cell to edit its value directly, or use "
            "<b>Set All Values in Column...</b> to set one column to the same "
            "value everywhere at once.<br>"
            "<b>Freeze First Column</b> keeps the first column in view while "
            "scrolling through the rest - untick it if you'd rather scroll freely."
        )
        instructions_text.setWordWrap(True)
        instructions_section.addWidget(instructions_text)
        layout.addWidget(instructions_section)

        summary_row = QHBoxLayout()
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("color: palette(mid); padding: 2px 0;")
        summary_row.addWidget(self.summary_label)
        summary_row.addStretch()
        self._freeze_checkbox = QCheckBox("📌 Freeze First Column")
        self._freeze_checkbox.setChecked(True)
        self._freeze_checkbox.setToolTip(
            "Keep the first column visible while scrolling through the others."
        )
        self._freeze_checkbox.toggled.connect(self._on_freeze_toggled)
        summary_row.addWidget(self._freeze_checkbox)
        layout.addLayout(summary_row)

        self.table = QTableWidget(0, 0, self)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        # The header row holds the data names - make that stand out from the
        # ordinary data-value rows below it.
        header_font = self.table.horizontalHeader().font()
        header_font.setBold(True)
        self.table.horizontalHeader().setFont(header_font)
        layout.addWidget(self.table)
        self._setup_frozen_column()

        rows_group = QGroupBox("Rows")
        rows_layout = QHBoxLayout(rows_group)

        add_row_btn = QPushButton("➕ Add Row")
        add_row_btn.setStyleSheet(f"color: {_COLOR_ADD};")
        add_row_btn.setToolTip("Append a new row filled with '?' (unknown) placeholders.")
        add_row_btn.clicked.connect(self._add_row)
        rows_layout.addWidget(add_row_btn)

        delete_row_btn = QPushButton("🗑️ Delete Row(s)")
        delete_row_btn.setStyleSheet(f"color: {_COLOR_DELETE};")
        delete_row_btn.setToolTip("Delete the selected row(s). A loop needs at least one row.")
        delete_row_btn.clicked.connect(self._delete_selected_rows)
        rows_layout.addWidget(delete_row_btn)
        rows_layout.addStretch()
        layout.addWidget(rows_group)

        cols_group = QGroupBox("Columns (Data Items)")
        cols_layout = QHBoxLayout(cols_group)

        add_col_btn = QPushButton("➕ Add Column...")
        add_col_btn.setStyleSheet(f"color: {_COLOR_ADD};")
        add_col_btn.setToolTip("Add a new data name as a column, filled with '?' in every row.")
        add_col_btn.clicked.connect(self._add_column)
        cols_layout.addWidget(add_col_btn)

        rename_col_btn = QPushButton("✏️ Rename Column...")
        rename_col_btn.setStyleSheet(f"color: {_COLOR_EDIT};")
        rename_col_btn.setToolTip(
            "Select a cell in the column to rename, then click here. Values are kept."
        )
        rename_col_btn.clicked.connect(self._rename_column)
        cols_layout.addWidget(rename_col_btn)

        delete_col_btn = QPushButton("🗑️ Delete Column")
        delete_col_btn.setStyleSheet(f"color: {_COLOR_DELETE};")
        delete_col_btn.setToolTip(
            "Select a cell in the column to delete, then click here. Removes the "
            "data name AND its value from every row."
        )
        delete_col_btn.clicked.connect(self._delete_column)
        cols_layout.addWidget(delete_col_btn)

        set_col_btn = QPushButton("🔁 Set All Values in Column...")
        set_col_btn.setStyleSheet(f"color: {_COLOR_EDIT};")
        set_col_btn.setToolTip(
            "Select a cell in the column to update, then click here to set every "
            "row's value for that column at once."
        )
        set_col_btn.clicked.connect(self._set_column_value)
        cols_layout.addWidget(set_col_btn)
        cols_layout.addStretch()
        layout.addWidget(cols_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Load the initial selection: the loop under the cursor, or the
        # blank "New Loop" slate when the cursor wasn't inside one.
        self._rebuild_loop_combo(preselected_index)

    # -- loop picker -------------------------------------------------------

    def _on_loop_selected(self, _combo_index: int) -> None:
        self._load_option(self.loop_combo.currentData())

    def _on_block_filter_changed(self, _checked: bool) -> None:
        self._rebuild_loop_combo(self.loop_combo.currentData())

    def _checked_block_names(self) -> Optional[set]:
        """Block names currently checked in the filter, or None when the
        filter isn't shown at all (meaning: show loops from every block)."""
        if not self._block_checkboxes:
            return None
        return {name for name, checkbox in self._block_checkboxes.items() if checkbox.isChecked()}

    def _rebuild_loop_combo(self, preferred_source_index: Optional[int]) -> None:
        """Repopulate the combo from self._loop_options, respecting the
        block filter. Restores preferred_source_index's selection if it's
        still visible, otherwise falls back to "New Loop"."""
        visible_blocks = self._checked_block_names()

        self.loop_combo.blockSignals(True)
        self.loop_combo.clear()
        self.loop_combo.addItem("➕ New Loop (not yet in the file)", None)
        for i, option in enumerate(self._loop_options):
            if visible_blocks is not None and option.block_name not in visible_blocks:
                continue
            self.loop_combo.addItem(option.label, i)

        restore_combo_index = 0
        for combo_index in range(self.loop_combo.count()):
            if self.loop_combo.itemData(combo_index) == preferred_source_index:
                restore_combo_index = combo_index
                break
        self.loop_combo.setCurrentIndex(restore_combo_index)
        self.loop_combo.blockSignals(False)

        self._load_option(self.loop_combo.currentData())

    def _load_option(self, source_index: Optional[int]) -> None:
        """Populate the table from loop_options[source_index], or clear it
        to a blank slate when source_index is None ("New Loop")."""
        if source_index is None:
            field_names: List[str] = []
            data_rows: List[List[str]] = []
            block_label = self._new_loop_block_label
        else:
            option = self._loop_options[source_index]
            field_names, data_rows, block_label = (
                option.field_names, option.data_rows, option.block_label)

        self._field_names = list(field_names)
        self._set_block_label(block_label)

        self.table.clear()
        self.table.setRowCount(len(data_rows))
        self.table.setColumnCount(len(self._field_names))
        self.table.setHorizontalHeaderLabels(self._field_names)
        for row_idx, row in enumerate(data_rows):
            for col_idx, value in enumerate(row):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        self._update_summary()

    def _set_block_label(self, text: Optional[str]) -> None:
        if text:
            self._block_banner.setText(f"📦 {text}")
            self._block_banner.setVisible(True)
        else:
            self._block_banner.setVisible(False)

    # -- frozen first column ------------------------------------------------
    #
    # A second QTableView sharing the main table's model *and* selection
    # model, cropped to column 0 and overlaid on top of it. Sharing both
    # means cell edits and selection stay in sync automatically - only the
    # overlay's geometry and which column it shows need to be kept current.

    def _setup_frozen_column(self) -> None:
        frozen = QTableView(self.table)
        frozen.setModel(self.table.model())
        frozen.setSelectionModel(self.table.selectionModel())
        frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        frozen.verticalHeader().hide()
        frozen.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        frozen.horizontalHeader().setFont(self.table.horizontalHeader().font())
        frozen.setEditTriggers(self.table.editTriggers())
        frozen.setSelectionMode(self.table.selectionMode())
        frozen.setSelectionBehavior(self.table.selectionBehavior())
        frozen.setAlternatingRowColors(True)
        frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.setStyleSheet(
            "QTableView { border: none; background-color: palette(base); }"
        )
        self._frozen_table = frozen

        self.table.verticalScrollBar().valueChanged.connect(
            frozen.verticalScrollBar().setValue)
        frozen.verticalScrollBar().valueChanged.connect(
            self.table.verticalScrollBar().setValue)
        self.table.horizontalHeader().sectionResized.connect(self._on_column_resized)
        self.table.installEventFilter(self)

        self._sync_frozen_columns()
        self._update_frozen_geometry()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.table and event.type() == QEvent.Type.Resize:
            self._update_frozen_geometry()
        return super().eventFilter(obj, event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # The table's real, laid-out size isn't final until the dialog is
        # actually shown - recompute once here so the overlay isn't left at
        # whatever (near-zero) size it had during __init__.
        self._update_frozen_geometry()

    def _on_freeze_toggled(self, _checked: bool) -> None:
        self._update_frozen_geometry()

    def _on_column_resized(self, logical_index: int, _old_size: int, new_size: int) -> None:
        if logical_index == 0:
            self._frozen_table.setColumnWidth(0, new_size)
            self._update_frozen_geometry()

    def _sync_frozen_columns(self) -> None:
        """Show only column 0 in the frozen overlay, matching its width."""
        col_count = self.table.columnCount()
        for col in range(col_count):
            self._frozen_table.setColumnHidden(col, col != 0)
        if col_count > 0:
            self._frozen_table.setColumnWidth(0, self.table.columnWidth(0))

    def _update_frozen_geometry(self) -> None:
        if self.table.columnCount() == 0 or not self._freeze_checkbox.isChecked():
            self._frozen_table.hide()
            return
        self._frozen_table.setGeometry(
            self.table.verticalHeader().width() + self.table.frameWidth(),
            self.table.frameWidth(),
            self.table.columnWidth(0),
            self.table.viewport().height() + self.table.horizontalHeader().height(),
        )
        self._frozen_table.show()
        self._frozen_table.raise_()

    # -- internal helpers ------------------------------------------------

    def _current_column(self) -> Optional[int]:
        col = self.table.currentColumn()
        return col if col >= 0 else None

    def _cell_text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text() if item is not None else ""

    def _is_duplicate_name(self, name: str, except_index: Optional[int] = None) -> bool:
        return any(
            i != except_index and existing.lower() == name.lower()
            for i, existing in enumerate(self._field_names)
        )

    def _update_summary(self) -> None:
        cols = self.table.columnCount()
        rows = self.table.rowCount()
        self.summary_label.setText(
            f"{cols} column{'s' if cols != 1 else ''} (data name{'s' if cols != 1 else ''}), "
            f"{rows} row{'s' if rows != 1 else ''}"
        )
        # Row/column count changes can shift the vertical header's width
        # (e.g. 9 -> 10 rows) and which column is "first", so re-sync both.
        self._sync_frozen_columns()
        self._update_frozen_geometry()

    # -- row actions -------------------------------------------------------

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col in range(self.table.columnCount()):
            self.table.setItem(row, col, QTableWidgetItem("?"))
        self._update_summary()

    def _delete_selected_rows(self):
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "No Rows Selected", "Select one or more rows to delete.")
            return
        if self.table.columnCount() > 0 and len(rows) >= self.table.rowCount():
            QMessageBox.warning(
                self, "Cannot Remove All Rows",
                "A loop needs at least one data row. To remove the loop "
                "entirely, delete all of its columns instead."
            )
            return
        for row in rows:
            self.table.removeRow(row)
        self._update_summary()

    # -- column actions ------------------------------------------------

    def _add_column(self):
        name, ok = QInputDialog.getText(
            self, "Add Column", "New data name (e.g. _atom_site.label):")
        if not ok or not name.strip():
            return
        name = name.strip()
        if not name.startswith('_'):
            QMessageBox.warning(self, "Invalid Data Name", "A CIF data name must start with '_'.")
            return
        if self._is_duplicate_name(name):
            QMessageBox.warning(self, "Duplicate Data Name", f"'{name}' is already a column in this loop.")
            return

        col = self.table.columnCount()
        self.table.insertColumn(col)
        self._field_names.append(name)
        self.table.setHorizontalHeaderLabels(self._field_names)
        if self.table.rowCount() == 0:
            # A loop needs at least one row; seed one for the first column
            # added to a blank "New Loop" table.
            self.table.insertRow(0)
        for row in range(self.table.rowCount()):
            self.table.setItem(row, col, QTableWidgetItem("?"))
        self._update_summary()

    def _rename_column(self):
        col = self._current_column()
        if col is None:
            QMessageBox.information(self, "No Column Selected", "Select a column to rename.")
            return
        current_name = self._field_names[col]
        name, ok = QInputDialog.getText(
            self, "Rename Column", "New data name:", text=current_name)
        if not ok or not name.strip():
            return
        name = name.strip()
        if not name.startswith('_'):
            QMessageBox.warning(self, "Invalid Data Name", "A CIF data name must start with '_'.")
            return
        if self._is_duplicate_name(name, except_index=col):
            QMessageBox.warning(self, "Duplicate Data Name", f"'{name}' is already a column in this loop.")
            return
        self._field_names[col] = name
        self.table.setHorizontalHeaderLabels(self._field_names)

    def _delete_column(self):
        col = self._current_column()
        if col is None:
            QMessageBox.information(self, "No Column Selected", "Select a column to delete.")
            return
        name = self._field_names[col]
        reply = QMessageBox.question(
            self, "Delete Column",
            f"Delete '{name}' and its value from every row?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.table.removeColumn(col)
        del self._field_names[col]
        self._update_summary()

    def _set_column_value(self):
        col = self._current_column()
        if col is None:
            QMessageBox.information(self, "No Column Selected", "Select a column to set values for.")
            return
        if self.table.rowCount() == 0:
            return
        current = self._cell_text(0, col)
        value, ok = QInputDialog.getText(
            self, "Set All Values in Column",
            f"New value for every row of '{self._field_names[col]}':",
            text=current)
        if not ok:
            return
        for row in range(self.table.rowCount()):
            self.table.setItem(row, col, QTableWidgetItem(value))

    # -- result ----------------------------------------------------------

    def get_result(self) -> Tuple[Optional[int], List[str], List[List[str]]]:
        """Return (source_index, field_names, data_rows).

        source_index is the index into the loop_options passed to the
        constructor identifying the existing loop this replaces, or None
        when "New Loop" is the active selection - meaning these field names
        and rows should be inserted as a brand-new loop instead.
        """
        rows = [
            [self._cell_text(row, col) for col in range(self.table.columnCount())]
            for row in range(self.table.rowCount())
        ]
        return self.loop_combo.currentData(), list(self._field_names), rows
