"""
CIF Value Validation Dialog
============================

Displays the results of CIFDataValidator as a sortable tree with colour-coded
severity indicators (error / warning / info).  Allows the user to navigate to
any flagged line in the main editor.
"""

from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QPushButton, QDialogButtonBox, QGroupBox, QSizePolicy, QHeaderView,
    QAbstractItemView, QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QBrush

from utils.cif_data_validator import ValidationIssue


# Severity → (icon-text, background-colour)
_SEVERITY_STYLE = {
    'error':   ('✖ Error',   QColor('#FFDEDE')),
    'warning': ('⚠ Warning', QColor('#FFF3CD')),
    'info':    ('ℹ Info',    QColor('#D9EDF7')),
}

# Issue type → short human label
_TYPE_LABEL = {
    'loop_incomplete': 'Loop count',
    'type_mismatch':   'Type mismatch',
    'enum_violation':  'Enum violation',
}


class CIFValueValidationDialog(QDialog):
    """Dialog that shows CIF data-value validation results.

    Signals
    -------
    navigate_to_line(int)
        Emitted when the user double-clicks an issue row that has a line number.
        The integer is the 1-based line number.
    """

    navigate_to_line = pyqtSignal(int)
    refresh_requested = pyqtSignal()

    def __init__(
        self,
        issues: List[ValidationIssue],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._issues = issues
        self._setup_ui()
        self._populate(issues)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("Validate Data Values")
        self.setModal(True)
        self.resize(900, 560)

        layout = QVBoxLayout(self)

        # Summary bar
        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setColumnCount(5)
        self._tree.setHeaderLabels(["Severity", "Type", "Line", "Field", "Message"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setSortingEnabled(True)
        self._tree.sortByColumn(2, Qt.SortOrder.AscendingOrder)   # sort by line by default
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._tree.setColumnWidth(3, 220)

        layout.addWidget(self._tree)

        # Detail label
        detail_group = QGroupBox("Details")
        detail_layout = QVBoxLayout(detail_group)
        self._detail_label = QLabel("Select a row to see details.")
        self._detail_label.setWordWrap(True)
        self._detail_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        detail_layout.addWidget(self._detail_label)
        layout.addWidget(detail_group)

        self._tree.currentItemChanged.connect(self._on_selection_changed)

        # Buttons
        btn_box = QDialogButtonBox()
        self._goto_btn = QPushButton("Go to Line")
        self._goto_btn.setEnabled(False)
        self._goto_btn.setToolTip("Navigate to the flagged line in the editor (double-click also works)")
        self._goto_btn.clicked.connect(self._on_goto_clicked)
        btn_box.addButton(self._goto_btn, QDialogButtonBox.ButtonRole.ActionRole)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setToolTip("Re-run validation against the current editor content")
        self._refresh_btn.clicked.connect(self.refresh_requested)
        btn_box.addButton(self._refresh_btn, QDialogButtonBox.ButtonRole.ActionRole)

        close_btn = btn_box.addButton(QDialogButtonBox.StandardButton.Close)
        close_btn.clicked.connect(self.accept)

        layout.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate(self, issues: List[ValidationIssue]) -> None:
        self._tree.clear()

        errors   = [i for i in issues if i.severity == 'error']
        warnings = [i for i in issues if i.severity == 'warning']
        infos    = [i for i in issues if i.severity == 'info']

        if not issues:
            summary = "No issues found — all checked values appear consistent with dictionary definitions."
            self._summary_label.setText(summary)
            return

        parts = []
        if errors:
            parts.append(f"<b style='color:#c0392b'>{len(errors)} error(s)</b>")
        if warnings:
            parts.append(f"<b style='color:#e67e22'>{len(warnings)} warning(s)</b>")
        if infos:
            parts.append(f"<b style='color:#2980b9'>{len(infos)} info</b>")
        self._summary_label.setText("Found: " + ", ".join(parts) + ". Double-click a row to navigate to that line.")

        for issue in issues:
            sev_text, bg_color = _SEVERITY_STYLE.get(issue.severity, ('?', QColor('white')))
            type_label = _TYPE_LABEL.get(issue.issue_type, issue.issue_type)
            line_text = str(issue.line_number) if issue.line_number else "—"

            item = QTreeWidgetItem([
                sev_text,
                type_label,
                line_text,
                issue.field_name,
                issue.message,
            ])
            # Store the raw line number for sort / navigation
            if issue.line_number:
                item.setData(2, Qt.ItemDataRole.UserRole, issue.line_number)
                # Use zero-padded string so text-sort keeps numeric order
                item.setText(2, f"{issue.line_number:06d}")

            item.setData(0, Qt.ItemDataRole.UserRole + 1, issue)  # store full issue

            for col in range(5):
                item.setBackground(col, QBrush(bg_color))

            self._tree.addTopLevelItem(item)

        # Resize line column so zero-padded numbers aren't too wide
        self._tree.resizeColumnToContents(2)

    def update_issues(self, issues: List[ValidationIssue]) -> None:
        """Repopulate the dialog with a fresh list of validation issues."""
        self._issues = issues
        self._populate(issues)
        self._detail_label.setText("Select a row to see details.")
        self._goto_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        line = item.data(2, Qt.ItemDataRole.UserRole)
        if line:
            self.navigate_to_line.emit(int(line))

    def _on_goto_clicked(self) -> None:
        item = self._tree.currentItem()
        if item:
            line = item.data(2, Qt.ItemDataRole.UserRole)
            if line:
                self.navigate_to_line.emit(int(line))

    def _on_selection_changed(self, current: QTreeWidgetItem, _previous) -> None:
        if current is None:
            self._detail_label.setText("Select a row to see details.")
            self._goto_btn.setEnabled(False)
            return

        issue: ValidationIssue = current.data(0, Qt.ItemDataRole.UserRole + 1)
        if issue is None:
            return

        parts = [f"<b>Field:</b> {issue.field_name}"]
        if issue.line_number:
            parts.append(f"<b>Line:</b> {issue.line_number}")
        if issue.value is not None:
            parts.append(f"<b>Value:</b> <code>{issue.value}</code>")
        if issue.expected is not None:
            parts.append(f"<b>Expected:</b> {issue.expected}")
        parts.append(f"<b>Message:</b> {issue.message}")

        self._detail_label.setText("&nbsp;&nbsp;".join(parts))
        self._goto_btn.setEnabled(bool(issue.line_number))
