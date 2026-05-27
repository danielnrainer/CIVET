"""
Non-ASCII Character Conversion Dialog
=======================================

Allows the user to convert between Unicode characters and their CIF 1.1
backslash-encoded representations (:func:`convert_unicode_to_cif11` and
:func:`convert_cif11_to_unicode`).

The dialog shows a summary of distinct characters found in the current CIF
content, with checkboxes for selective conversion.
"""

from typing import List, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QPushButton, QDialogButtonBox, QGroupBox, QWidget, QButtonGroup,
    QRadioButton, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont


class NonAsciiConversionDialog(QDialog):
    """Dialog for converting between Unicode and CIF 1.1 backslash encodings.

    Signals
    -------
    conversion_requested(str, list)
        Emitted when the user clicks "Apply Selected".
        First argument is the direction: ``'unicode_to_cif11'`` or
        ``'cif11_to_unicode'``.  Second argument is the list of Unicode
        characters (or CIF 1.1 codes) to convert.
    """

    conversion_requested = pyqtSignal(str, list)

    # Columns in the tree
    _COL_CHECK   = 0
    _COL_UNICODE = 1
    _COL_CHAR    = 2
    _COL_CIF11   = 3
    _COL_COUNT   = 4
    _COL_NOTE    = 5

    def __init__(
        self,
        # List of (char, cif11_encoding_or_None, occurrence_count, auto_fixable)
        occurrences: List[Tuple[str, Optional[str], int, bool]],
        direction: str = 'unicode_to_cif11',
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._occurrences = occurrences
        self._direction = direction
        self._setup_ui()
        self._populate(occurrences)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("Non-ASCII Character Conversion")
        self.setModal(True)
        self.resize(820, 480)

        layout = QVBoxLayout(self)

        # Direction selector
        dir_group = QGroupBox("Conversion Direction")
        dir_layout = QHBoxLayout(dir_group)
        self._dir_grp = QButtonGroup(self)
        self._radio_to_cif11 = QRadioButton(
            "Unicode → CIF 1.1 backslash encoding  (e.g. Å → \\%A)"
        )
        self._radio_to_unicode = QRadioButton(
            "CIF 1.1 backslash encoding → Unicode  (e.g. \\%A → Å)"
        )
        self._dir_grp.addButton(self._radio_to_cif11, 0)
        self._dir_grp.addButton(self._radio_to_unicode, 1)
        if self._direction == 'cif11_to_unicode':
            self._radio_to_unicode.setChecked(True)
        else:
            self._radio_to_cif11.setChecked(True)
        dir_layout.addWidget(self._radio_to_cif11)
        dir_layout.addWidget(self._radio_to_unicode)
        layout.addWidget(dir_group)

        # Info label
        self._info_label = QLabel(
            "Select the characters to convert and click Apply Selected."
        )
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        # Tree
        self._tree = QTreeWidget()
        self._tree.setColumnCount(6)
        self._tree.setHeaderLabels([
            "✔", "Unicode", "Char", "CIF 1.1 Code", "Occurrences", "Note",
        ])
        self._tree.setAlternatingRowColors(True)
        self._tree.setSortingEnabled(True)
        self._tree.sortByColumn(self._COL_UNICODE, Qt.SortOrder.AscendingOrder)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        header = self._tree.header()
        header.setSectionResizeMode(self._COL_CHECK,   QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_UNICODE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_CHAR,    QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_CIF11,   QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_COUNT,   QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._COL_NOTE,    QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self._tree)

        # Select all / deselect all
        sel_layout = QHBoxLayout()
        sel_all_btn = QPushButton("Select All")
        sel_all_btn.clicked.connect(self._select_all)
        desel_all_btn = QPushButton("Deselect All")
        desel_all_btn.clicked.connect(self._deselect_all)
        sel_fixable_btn = QPushButton("Select Auto-fixable Only")
        sel_fixable_btn.clicked.connect(self._select_fixable)
        sel_layout.addWidget(sel_all_btn)
        sel_layout.addWidget(desel_all_btn)
        sel_layout.addWidget(sel_fixable_btn)
        sel_layout.addStretch()
        layout.addLayout(sel_layout)

        # Buttons
        btn_box = QDialogButtonBox()
        self._apply_btn = QPushButton("Apply Selected")
        self._apply_btn.setDefault(True)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_box.addButton(self._apply_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = btn_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate(
        self,
        occurrences: List[Tuple[str, Optional[str], int, bool]],
    ) -> None:
        self._tree.clear()
        has_unfixable = False

        for char, cif11_code, count, auto_fixable in occurrences:
            cif11_text = cif11_code if cif11_code else "—"
            note = "" if auto_fixable else "No known CIF 1.1 encoding"
            bg = QColor('#FFDEDE') if not auto_fixable else QColor('white')

            item = QTreeWidgetItem([
                "",
                f"U+{ord(char):04X}",
                char,
                cif11_text,
                str(count),
                note,
            ])
            item.setCheckState(
                self._COL_CHECK,
                Qt.CheckState.Checked if auto_fixable else Qt.CheckState.Unchecked,
            )
            item.setData(self._COL_CHECK, Qt.ItemDataRole.UserRole, char)
            item.setData(self._COL_CHECK, Qt.ItemDataRole.UserRole + 1, cif11_code)
            item.setData(self._COL_CHECK, Qt.ItemDataRole.UserRole + 2, auto_fixable)

            if not auto_fixable:
                has_unfixable = True
                for col in range(6):
                    item.setBackground(col, QBrush(bg))

            # Make char column use a larger font for readability
            font = QFont()
            font.setPointSize(12)
            item.setFont(self._COL_CHAR, font)

            self._tree.addTopLevelItem(item)

        if has_unfixable:
            self._info_label.setText(
                "Characters highlighted in red have no known CIF 1.1 encoding "
                "and cannot be automatically converted."
            )

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _select_all(self) -> None:
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            root.child(i).setCheckState(self._COL_CHECK, Qt.CheckState.Checked)

    def _deselect_all(self) -> None:
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            root.child(i).setCheckState(self._COL_CHECK, Qt.CheckState.Unchecked)

    def _select_fixable(self) -> None:
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            fixable = item.data(self._COL_CHECK, Qt.ItemDataRole.UserRole + 2)
            item.setCheckState(
                self._COL_CHECK,
                Qt.CheckState.Checked if fixable else Qt.CheckState.Unchecked,
            )

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        direction = (
            'cif11_to_unicode'
            if self._radio_to_unicode.isChecked()
            else 'unicode_to_cif11'
        )
        selected_chars = []
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.checkState(self._COL_CHECK) == Qt.CheckState.Checked:
                char = item.data(self._COL_CHECK, Qt.ItemDataRole.UserRole)
                selected_chars.append(char)

        if selected_chars:
            self.conversion_requested.emit(direction, selected_chars)
        self.accept()
