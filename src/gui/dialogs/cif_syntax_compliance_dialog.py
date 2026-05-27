"""
CIF Syntax Compliance Dialog
=============================

Displays CIF 1.1 and CIF 2.0 syntax compliance results in a sortable tree
with colour-coded severity indicators.  Allows the user to navigate to any
flagged line in the editor and to trigger auto-fixes.
"""

from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QPushButton, QDialogButtonBox, QGroupBox, QTabWidget, QWidget,
    QHeaderView, QAbstractItemView, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

from utils.cif_syntax_compliance import ComplianceIssue


# Severity → (display text, background colour)
_SEVERITY_STYLE = {
    'error':   ('✖ Error',   QColor('#FFDEDE')),
    'warning': ('⚠ Warning', QColor('#FFF3CD')),
    'info':    ('ℹ Info',    QColor('#D9EDF7')),
}

# issue_type → short human label
_TYPE_LABEL = {
    'non_ascii_character':      'Non-ASCII char',
    'cif2_construct':           'CIF2 construct',
    'unquoted_bracket_value':   'Unquoted [ ]',
    'line_too_long':            'Line too long',
    'data_name_too_long':       'Name too long',
    'block_code_too_long':      'Code too long',
    'reserved_word_as_value':   'Reserved word',
    'missing_version_header':   'No header',
    'wrong_version_header':     'Wrong header',
    'invalid_unicode_char':     'Invalid Unicode',
    'unquoted_cif2_special_char': 'Unquoted [ ]{ }',
}


class CIFSyntaxComplianceDialog(QDialog):
    """Dialog showing CIF syntax compliance results for CIF 1.1 and CIF 2.0.

    Signals
    -------
    navigate_to_line(int)
        Emitted when the user double-clicks a row with a line number, or
        clicks the "Go to Line" button.
    refresh_requested
        Emitted when the user clicks the "Refresh" button.
    fix_all_requested
        Emitted when the user clicks "Fix All Auto-fixable".
    non_ascii_conversion_requested
        Emitted when the user clicks "Non-ASCII Conversion…".
    """

    navigate_to_line = pyqtSignal(int)
    refresh_requested = pyqtSignal()
    fix_all_requested = pyqtSignal(str)  # 'cif1', 'cif2', or 'all'
    non_ascii_conversion_requested = pyqtSignal()

    def __init__(
        self,
        issues_cif1: List[ComplianceIssue],
        issues_cif2: List[ComplianceIssue],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._issues_cif1 = issues_cif1
        self._issues_cif2 = issues_cif2
        self._setup_ui()
        self._populate(issues_cif1, issues_cif2)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("CIF Syntax Compliance Check")
        self.setModal(False)
        self.resize(1000, 580)

        layout = QVBoxLayout(self)

        # Overall summary
        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        # Tabbed view: CIF 2.0 | CIF 1.1 | All  (CIF 2.0 recommended first)
        self._tabs = QTabWidget()
        self._tree_cif2 = self._make_tree()
        self._tree_cif1 = self._make_tree()
        self._tree_all = self._make_tree()
        self._tabs.addTab(self._tree_cif2, "CIF 2.0")
        self._tabs.addTab(self._tree_cif1, "CIF 1.1")
        self._tabs.addTab(self._tree_all, "All Issues")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

        # Detail panel
        detail_group = QGroupBox("Details")
        detail_layout = QVBoxLayout(detail_group)
        self._detail_label = QLabel("Select a row to see details.")
        self._detail_label.setWordWrap(True)
        self._detail_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        detail_layout.addWidget(self._detail_label)
        layout.addWidget(detail_group)

        # Button row
        btn_box = QDialogButtonBox()

        self._goto_btn = QPushButton("Go to Line")
        self._goto_btn.setEnabled(False)
        self._goto_btn.setToolTip("Navigate to the flagged line in the editor")
        self._goto_btn.clicked.connect(self._on_goto_clicked)
        btn_box.addButton(self._goto_btn, QDialogButtonBox.ButtonRole.ActionRole)

        self._fix_all_btn = QPushButton("Fix All Auto-fixable")
        self._fix_all_btn.setEnabled(False)
        self._fix_all_btn.setToolTip(
            "Apply all auto-fixable corrections for the active tab's specification"
        )
        self._fix_all_btn.clicked.connect(self._on_fix_all_clicked)
        btn_box.addButton(self._fix_all_btn, QDialogButtonBox.ButtonRole.ActionRole)

        self._non_ascii_btn = QPushButton("Non-ASCII Conversion…")
        self._non_ascii_btn.setEnabled(False)
        self._non_ascii_btn.setToolTip(
            "Convert between Unicode and CIF 1.1 backslash-encoded characters"
        )
        self._non_ascii_btn.clicked.connect(self.non_ascii_conversion_requested)
        btn_box.addButton(self._non_ascii_btn, QDialogButtonBox.ButtonRole.ActionRole)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setToolTip("Re-run compliance check against current editor content")
        self._refresh_btn.clicked.connect(self.refresh_requested)
        btn_box.addButton(self._refresh_btn, QDialogButtonBox.ButtonRole.ActionRole)

        close_btn = btn_box.addButton(QDialogButtonBox.StandardButton.Close)
        close_btn.clicked.connect(self.accept)

        layout.addWidget(btn_box)

    def _make_tree(self) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setColumnCount(6)
        tree.setHeaderLabels(["Severity", "Spec", "Type", "Line", "Auto-fix", "Description"])
        tree.setAlternatingRowColors(True)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tree.setSortingEnabled(True)
        tree.sortByColumn(3, Qt.SortOrder.AscendingOrder)
        tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        tree.currentItemChanged.connect(self._on_selection_changed)
        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        return tree

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate(
        self,
        issues_cif1: List[ComplianceIssue],
        issues_cif2: List[ComplianceIssue],
    ) -> None:
        self._tree_cif1.clear()
        self._tree_cif2.clear()
        self._tree_all.clear()

        for issue in issues_cif1:
            self._add_item(self._tree_cif1, issue)
            self._add_item(self._tree_all, issue)
        for issue in issues_cif2:
            self._add_item(self._tree_cif2, issue)
            self._add_item(self._tree_all, issue)

        self._tree_cif1.resizeColumnToContents(3)
        self._tree_cif2.resizeColumnToContents(3)
        self._tree_all.resizeColumnToContents(3)

        all_issues = issues_cif1 + issues_cif2
        errors   = sum(1 for i in all_issues if i.severity == 'error')
        warnings = sum(1 for i in all_issues if i.severity == 'warning')
        infos    = sum(1 for i in all_issues if i.severity == 'info')
        fixable  = sum(1 for i in all_issues if i.auto_fixable)
        has_non_ascii = any(
            i.issue_type == 'non_ascii_character' for i in issues_cif1
        )

        if not all_issues:
            self._summary_label.setText(
                "No issues found — content appears compliant with the selected specifications."
            )
        else:
            parts = []
            if errors:
                parts.append(f"<b style='color:#c0392b'>{errors} error(s)</b>")
            if warnings:
                parts.append(f"<b style='color:#e67e22'>{warnings} warning(s)</b>")
            if infos:
                parts.append(f"<b style='color:#2980b9'>{infos} info</b>")
            fix_note = f" ({fixable} auto-fixable)" if fixable else ""
            self._summary_label.setText(
                "Found: " + ", ".join(parts) + fix_note +
                ". Double-click a row to navigate."
            )

        self._fix_all_btn.setEnabled(fixable > 0)
        self._non_ascii_btn.setEnabled(has_non_ascii)

        # Update tab labels with counts (order: CIF 2.0=0, CIF 1.1=1, All=2)
        self._tabs.setTabText(0, f"CIF 2.0 ({len(issues_cif2)})")
        self._tabs.setTabText(1, f"CIF 1.1 ({len(issues_cif1)})")
        self._tabs.setTabText(2, f"All Issues ({len(all_issues)})")

        # Keep Fix All button in sync with the active tab
        self._update_fix_all_btn(self._tabs.currentIndex())

    def _add_item(self, tree: QTreeWidget, issue: ComplianceIssue) -> None:
        sev_text, bg_color = _SEVERITY_STYLE.get(issue.severity, ('?', QColor('white')))
        type_label = _TYPE_LABEL.get(issue.issue_type, issue.issue_type)
        line_text = str(issue.line_number) if issue.line_number else "—"
        fix_text = "✔ Yes" if issue.auto_fixable else "✘ No"

        item = QTreeWidgetItem([
            sev_text,
            issue.spec,
            type_label,
            line_text,
            fix_text,
            issue.description,
        ])

        if issue.line_number:
            item.setData(3, Qt.ItemDataRole.UserRole, issue.line_number)
            item.setText(3, f"{issue.line_number:06d}")

        item.setData(0, Qt.ItemDataRole.UserRole + 1, issue)

        for col in range(6):
            item.setBackground(col, QBrush(bg_color))

        tree.addTopLevelItem(item)

    def update_issues(
        self,
        issues_cif1: List[ComplianceIssue],
        issues_cif2: List[ComplianceIssue],
    ) -> None:
        """Repopulate the dialog with fresh compliance results."""
        self._issues_cif1 = issues_cif1
        self._issues_cif2 = issues_cif2
        self._populate(issues_cif1, issues_cif2)
        self._detail_label.setText("Select a row to see details.")
        self._goto_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_tree(self) -> QTreeWidget:
        return self._tabs.currentWidget()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_tab_changed(self, index: int) -> None:
        self._detail_label.setText("Select a row to see details.")
        self._goto_btn.setEnabled(False)
        self._update_fix_all_btn(index)

    def _update_fix_all_btn(self, tab_index: int) -> None:
        """Update the Fix All button label and enabled state for the active tab.

        Tab order: 0 = CIF 2.0, 1 = CIF 1.1, 2 = All Issues.
        """
        if tab_index == 0:
            fixable = sum(1 for i in self._issues_cif2 if i.auto_fixable)
            self._fix_all_btn.setText("Fix All CIF 2.0 Auto-fixable")
        elif tab_index == 1:
            fixable = sum(1 for i in self._issues_cif1 if i.auto_fixable)
            self._fix_all_btn.setText("Fix All CIF 1.1 Auto-fixable")
        else:
            fixable = sum(
                1 for i in self._issues_cif1 + self._issues_cif2 if i.auto_fixable
            )
            self._fix_all_btn.setText("Fix All Auto-fixable")
        self._fix_all_btn.setEnabled(fixable > 0)

    def _on_fix_all_clicked(self) -> None:
        """Emit fix_all_requested with the active tab's spec scope."""
        idx = self._tabs.currentIndex()
        if idx == 0:
            self.fix_all_requested.emit('cif2')
        elif idx == 1:
            self.fix_all_requested.emit('cif1')
        else:
            self.fix_all_requested.emit('all')

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        line = item.data(3, Qt.ItemDataRole.UserRole)
        if line:
            self.navigate_to_line.emit(int(line))

    def _on_goto_clicked(self) -> None:
        tree = self._current_tree()
        item = tree.currentItem() if tree else None
        if item:
            line = item.data(3, Qt.ItemDataRole.UserRole)
            if line:
                self.navigate_to_line.emit(int(line))

    def _on_selection_changed(
        self, current: Optional[QTreeWidgetItem], _previous: Optional[QTreeWidgetItem]
    ) -> None:
        if current is None:
            self._detail_label.setText("Select a row to see details.")
            self._goto_btn.setEnabled(False)
            return

        issue: Optional[ComplianceIssue] = current.data(
            0, Qt.ItemDataRole.UserRole + 1
        )
        if issue:
            loc = f"Line {issue.line_number}" if issue.line_number else "No specific line"
            if issue.column:
                loc += f", col {issue.column}"
            fix = "Yes — can be auto-fixed" if issue.auto_fixable else "No — manual fix required"
            self._detail_label.setText(
                f"<b>Specification:</b> {issue.spec} &nbsp; "
                f"<b>Severity:</b> {issue.severity} &nbsp; "
                f"<b>Location:</b> {loc}<br>"
                f"<b>Auto-fixable:</b> {fix}<br>"
                f"<b>Description:</b> {issue.description}"
            )
        self._goto_btn.setEnabled(
            current.data(3, Qt.ItemDataRole.UserRole) is not None
        )
