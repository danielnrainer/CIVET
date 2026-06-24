"""
Dictionary Search Dialog
========================

Search loaded CIF dictionaries for data names and categories.
"""

from html import escape
from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSplitter,
    QComboBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from utils.cif_dictionary_manager import CIFDictionaryManager, DictionarySearchResult


class DictionarySearchDialog(QDialog):
    """Dialog for searching loaded dictionaries and inspecting field metadata."""

    def __init__(self, dict_manager: CIFDictionaryManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.dict_manager = dict_manager
        self._results: List[DictionarySearchResult] = []
        self._result_line_numbers: List[int] = []
        self._result_present_names: List[List[str]] = []
        self._result_display_order: List[int] = []
        self._get_cif_content: Optional[Callable[[], str]] = None
        self._go_to_line: Optional[Callable[[int], None]] = None
        self._set_hitlist_highlights: Optional[Callable[[List[int], Optional[int]], None]] = None
        self._dictionary_actions: Dict[str, QAction] = {}
        self._all_dictionaries_action: Optional[QAction] = None
        self._selected_dictionary_names: Optional[List[str]] = None
        self._updating_dictionary_selection = False

        self.setWindowTitle("Search Dictionaries")
        self.setMinimumSize(650, 400)
        self.resize(850, 600)

        self._setup_ui()
        self._populate_dictionary_selector()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search data names, categories, or definitions..."
        )
        self.search_input.textChanged.connect(self._run_search)
        top_row.addWidget(self.search_input, 1)

        self.include_description_checkbox = QCheckBox("Include descriptions")
        self.include_description_checkbox.setChecked(False)
        self.include_description_checkbox.setToolTip(
            "When enabled, search also matches field definition text."
        )
        self.include_description_checkbox.toggled.connect(self._on_description_toggle)
        top_row.addWidget(self.include_description_checkbox)

        self.dictionary_filter_button = QToolButton()
        self.dictionary_filter_button.setMinimumWidth(320)
        self.dictionary_filter_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.dictionary_filter_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.dictionary_filter_button.setText("All Loaded Dictionaries")

        self.dictionary_menu = QMenu(self)
        self.dictionary_filter_button.setMenu(self.dictionary_menu)
        top_row.addWidget(self.dictionary_filter_button)

        layout.addLayout(top_row)

        options_row = QHBoxLayout()
        self.present_in_cif_checkbox = QCheckBox("Present in CIF")
        self.present_in_cif_checkbox.setChecked(False)
        self.present_in_cif_checkbox.setToolTip("Show only hits that are found in the loaded CIF.")
        self.present_in_cif_checkbox.toggled.connect(self._refresh_hit_list)
        options_row.addWidget(self.present_in_cif_checkbox)

        self.aliases_checkbox = QCheckBox("Aliases")
        self.aliases_checkbox.setChecked(False)
        self.aliases_checkbox.setToolTip("Show only hits that were matched via an alias.")
        self.aliases_checkbox.toggled.connect(self._refresh_hit_list)
        options_row.addWidget(self.aliases_checkbox)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Sort by category", "category")
        self.sort_combo.addItem("Sort by presence", "presence")
        self.sort_combo.addItem("Sort by line number", "line_number")
        self.sort_combo.currentIndexChanged.connect(self._refresh_hit_list)
        options_row.addWidget(self.sort_combo)

        options_row.addStretch()
        layout.addLayout(options_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.hits_list = QListWidget()
        self.hits_list.currentRowChanged.connect(self._show_selected_hit)
        self.hits_list.itemDoubleClicked.connect(self._go_to_selected_hit)
        splitter.addWidget(self.hits_list)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlaceholderText("Search and select a hit to view details.")
        self.details_text.setStyleSheet(
            "QTextEdit { padding: 8px; line-height: 1.25; }"
        )
        splitter.addWidget(self.details_text)

        splitter.setSizes([450, 400])
        layout.addWidget(splitter, 1)

        button_row = QHBoxLayout()
        self.goto_line_button = QPushButton("Go to Line")
        self.goto_line_button.setEnabled(False)
        self.goto_line_button.clicked.connect(self._go_to_selected_hit)
        button_row.addWidget(self.goto_line_button)

        button_row.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        legend_row = QHBoxLayout()
        legend_label = QLabel(
            "Legend: [*] present in current CIF, [~] matched via alias, [ ] not present."
        )
        legend_label.setStyleSheet("color: #666666; font-size: 11px;")
        legend_row.addWidget(legend_label)
        legend_row.addStretch()
        layout.addLayout(legend_row)

    def set_cif_navigation_hooks(
        self,
        get_cif_content: Callable[[], str],
        go_to_line: Callable[[int], None],
        set_hitlist_highlights: Optional[Callable[[List[int], Optional[int]], None]] = None,
    ) -> None:
        """Set callbacks for checking/executing navigation into current CIF content."""
        self._get_cif_content = get_cif_content
        self._go_to_line = go_to_line
        self._set_hitlist_highlights = set_hitlist_highlights

    def _populate_dictionary_selector(self) -> None:
        self.dictionary_menu.clear()
        self._dictionary_actions.clear()

        self._all_dictionaries_action = QAction("All dictionaries", self)
        self._all_dictionaries_action.setCheckable(True)
        self._all_dictionaries_action.toggled.connect(self._on_all_dictionaries_toggled)
        self.dictionary_menu.addAction(self._all_dictionaries_action)
        self.dictionary_menu.addSeparator()

        dictionaries = self.dict_manager.get_detailed_dictionary_info()
        for info in dictionaries:
            label = info.name
            if info.dict_title:
                label = f"{info.name} ({info.dict_title})"

            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(info.name)
            action.toggled.connect(lambda checked, name=info.name: self._on_dictionary_toggled(name, checked))
            self.dictionary_menu.addAction(action)
            self._dictionary_actions[info.name] = action

        default_core_name = self._find_active_core_dictionary_name(dictionaries)
        if default_core_name and default_core_name in self._dictionary_actions:
            self._set_selected_dictionaries([default_core_name], run_search=False)
        else:
            self._set_all_dictionaries_selected(run_search=False)

    def _is_core_dictionary(self, dict_info) -> bool:
        """Return True when dictionary metadata indicates a core dictionary."""
        dict_type = (getattr(dict_info, "dict_type", "") or "").lower()
        if dict_type == "core":
            return True

        name_text = (getattr(dict_info, "name", "") or "").lower()
        if "cif_core" in name_text:
            return True

        title_text = (getattr(dict_info, "dict_title", "") or "").lower()
        return "core" in title_text

    def _find_active_core_dictionary_name(self, dictionaries) -> Optional[str]:
        """Pick the active CORE dictionary (preferred default) if available."""
        active_core = [info for info in dictionaries if self._is_core_dictionary(info) and getattr(info, "is_active", False)]
        if active_core:
            return active_core[0].name

        any_core = [info for info in dictionaries if self._is_core_dictionary(info)]
        if any_core:
            return any_core[0].name

        return None

    def _set_all_dictionaries_selected(self, run_search: bool = True) -> None:
        """Select all dictionaries (represented by no explicit dictionary filter)."""
        self._updating_dictionary_selection = True
        try:
            if self._all_dictionaries_action is not None:
                self._all_dictionaries_action.setChecked(True)
            for action in self._dictionary_actions.values():
                action.setChecked(False)
        finally:
            self._updating_dictionary_selection = False

        self._selected_dictionary_names = None
        self._update_dictionary_filter_button_text()
        if run_search:
            self._run_search()

    def _set_selected_dictionaries(self, dictionary_names: List[str], run_search: bool = True) -> None:
        """Select an explicit set of dictionaries to search."""
        selected_names = [name for name in dictionary_names if name in self._dictionary_actions]
        if not selected_names:
            self._set_all_dictionaries_selected(run_search=run_search)
            return

        selected_set = set(selected_names)
        self._updating_dictionary_selection = True
        try:
            if self._all_dictionaries_action is not None:
                self._all_dictionaries_action.setChecked(False)
            for name, action in self._dictionary_actions.items():
                action.setChecked(name in selected_set)
        finally:
            self._updating_dictionary_selection = False

        self._selected_dictionary_names = selected_names
        self._update_dictionary_filter_button_text()
        if run_search:
            self._run_search()

    def _update_dictionary_filter_button_text(self) -> None:
        """Refresh visible summary text for dictionary filter selection."""
        if not self._selected_dictionary_names:
            self.dictionary_filter_button.setText("All Loaded Dictionaries")
            return

        if len(self._selected_dictionary_names) == 1:
            self.dictionary_filter_button.setText(self._selected_dictionary_names[0])
            return

        self.dictionary_filter_button.setText(f"{len(self._selected_dictionary_names)} dictionaries selected")

    def _on_all_dictionaries_toggled(self, checked: bool) -> None:
        """Handle toggling of the All dictionaries filter option."""
        if self._updating_dictionary_selection:
            return

        if checked:
            self._set_all_dictionaries_selected(run_search=True)
            return

        # Keep selection valid: if user unticks All without selecting dictionaries,
        # revert back to All so we never end up with an empty filter.
        if not any(action.isChecked() for action in self._dictionary_actions.values()):
            self._set_all_dictionaries_selected(run_search=True)

    def _on_dictionary_toggled(self, dictionary_name: str, checked: bool) -> None:
        """Handle toggling of an individual dictionary checkbox option."""
        if self._updating_dictionary_selection:
            return

        if checked and self._all_dictionaries_action is not None and self._all_dictionaries_action.isChecked():
            self._updating_dictionary_selection = True
            try:
                self._all_dictionaries_action.setChecked(False)
            finally:
                self._updating_dictionary_selection = False

        selected = [name for name, action in self._dictionary_actions.items() if action.isChecked()]
        if not selected:
            self._set_all_dictionaries_selected(run_search=True)
            return

        self._selected_dictionary_names = selected
        self._update_dictionary_filter_button_text()
        self._run_search()

    def _run_search(self) -> None:
        query = self.search_input.text().strip()
        dictionary_names = self._selected_dictionary_names

        self.hits_list.clear()
        self._results = []
        self._result_line_numbers = []
        self._result_present_names = []
        self._result_display_order = []
        self.details_text.clear()
        self.goto_line_button.setEnabled(False)
        self._update_hitlist_highlights(None)

        if not query:
            self.details_text.setPlainText("Type in the search bar to find data names, aliases, and categories.")
            return

        self._results = self.dict_manager.search_dictionary_fields(
            query=query,
            dictionary_names=dictionary_names,
            max_results=1000,
            include_description=self.include_description_checkbox.isChecked(),
        )

        if not self._results:
            self.details_text.setPlainText("No results found.")
            return

        self._build_hit_metadata()
        self._refresh_hit_list()

    def _build_hit_metadata(self) -> None:
        """Resolve per-result line positions and present names before filtering/sorting."""
        field_line_map = self._build_field_line_map()

        self._result_line_numbers = []
        self._result_present_names = []

        for result in self._results:
            hit_line, present_names = self._resolve_hit_info(result, field_line_map)
            self._result_line_numbers.append(hit_line)
            self._result_present_names.append(present_names)

    def _get_status_symbol(self, result: DictionarySearchResult, present_names: List[str], hit_line: int) -> str:
        """Return the list marker for a result based on how it appears in the CIF."""
        if hit_line <= 0:
            return "[ ]"

        has_canonical, has_alias = self._get_presence_flags(result, present_names)

        if has_canonical and has_alias:
            return "[*~]"
        if has_alias:
            return "[~]"
        return "[*]"

    def _get_presence_flags(self, result: DictionarySearchResult, present_names: List[str]) -> tuple[bool, bool]:
        """Return whether the canonical name and any alias are present in the CIF."""
        present_name_set = {name.lower() for name in present_names}
        canonical_name = result.field_name.lower()
        has_canonical = canonical_name in present_name_set
        has_alias = any(name != canonical_name for name in present_name_set)
        return has_canonical, has_alias

    def _refresh_hit_list(self, *_args) -> None:
        """Apply filtering and sorting to the currently loaded search results."""
        self.hits_list.clear()
        self.details_text.clear()
        self.goto_line_button.setEnabled(False)
        self._result_display_order = []
        self._update_hitlist_highlights(None)

        if not self._results:
            return

        filtered_rows = []
        for row, result in enumerate(self._results):
            hit_line = self._result_line_numbers[row] if row < len(self._result_line_numbers) else 0
            if self.present_in_cif_checkbox.isChecked() and hit_line <= 0:
                continue
            if self.aliases_checkbox.isChecked() and not (result.matched_via_alias and hit_line > 0):
                continue
            filtered_rows.append(row)

        sort_mode = self.sort_combo.currentData()
        if sort_mode == "line_number":
            filtered_rows.sort(
                key=lambda row: (
                    self._result_line_numbers[row] <= 0,
                    self._result_line_numbers[row] if row < len(self._result_line_numbers) else 0,
                    self._results[row].category_id.lower() if self._results[row].category_id else "",
                    self._results[row].field_name.lower(),
                    self._results[row].dictionary_name.lower(),
                )
            )
        elif sort_mode == "presence":
            filtered_rows.sort(
                key=lambda row: (
                    0 if (self._result_line_numbers[row] if row < len(self._result_line_numbers) else 0) > 0 else 1,
                    self._results[row].category_id.lower() if self._results[row].category_id else "",
                    self._results[row].field_name.lower(),
                    self._results[row].dictionary_name.lower(),
                )
            )
        else:
            filtered_rows.sort(
                key=lambda row: (
                    self._results[row].category_id.lower() if self._results[row].category_id else "",
                    self._results[row].field_name.lower(),
                    self._results[row].dictionary_name.lower(),
                )
            )

        self._result_display_order = filtered_rows

        if not filtered_rows:
            self.details_text.setPlainText("No results match the current filters.")
            return

        for row in filtered_rows:
            result = self._results[row]
            hit_line = self._result_line_numbers[row] if row < len(self._result_line_numbers) else 0
            present_names = self._result_present_names[row] if row < len(self._result_present_names) else []
            category = result.category_id or "(no category)"        
            status_symbol = self._get_status_symbol(result, present_names, hit_line)
            item_text = f"{status_symbol} {result.field_name}  [{category}]"
            item = QListWidgetItem(item_text)
            if hit_line > 0:
                tip = [
                    f"Dictionary: {result.dictionary_name}",
                    f"Found in current CIF at line {hit_line}",
                ]
                if present_names:
                    tip.append(f"Present in CIF as: {', '.join(present_names)}")
            else:
                tip = [
                    f"Dictionary: {result.dictionary_name}",
                    "Not found in current CIF",
                ]

            if result.matched_aliases:
                aliases_text = ", ".join(result.matched_aliases[:5])
                if len(result.matched_aliases) > 5:
                    aliases_text += ", ..."
                tip.append(f"Matched alias: {aliases_text}")

            item.setToolTip("\n".join(tip))
            self.hits_list.addItem(item)

        self.hits_list.setCurrentRow(0)

    def _format_description_html(self, description: str) -> str:
        """Reflow wrapped dictionary text while preserving blank-line paragraph breaks."""
        normalized = (description or "").replace("\r\n", "\n").replace("\r", "\n")
        if not normalized.strip():
            return "<p style='margin-top: 0;'>(No definition text available in loaded metadata)</p>"

        paragraphs: List[str] = []
        current_lines: List[str] = []

        for line in normalized.split("\n"):
            stripped = line.strip()
            if not stripped:
                if current_lines:
                    paragraphs.append(" ".join(current_lines))
                    current_lines = []
                continue
            current_lines.append(stripped)

        if current_lines:
            paragraphs.append(" ".join(current_lines))

        if not paragraphs:
            return "<p style='margin-top: 0;'>(No definition text available in loaded metadata)</p>"

        return "".join(
            f"<p style='margin: 0 0 10px 0; white-space: normal;'>{escape(paragraph)}</p>"
            for paragraph in paragraphs
        )

    def _show_selected_hit(self, row: int) -> None:
        if row < 0 or row >= len(self._result_display_order):
            self.details_text.clear()
            self.goto_line_button.setEnabled(False)
            self._update_hitlist_highlights(None)
            return

        source_row = self._result_display_order[row]
        result = self._results[source_row]
        hit_line = self._result_line_numbers[source_row] if source_row < len(self._result_line_numbers) else 0

        presence_text = f"Yes (line {hit_line})" if hit_line > 0 else "No"
        line_text = str(hit_line) if hit_line > 0 else "-"
        dict_title = result.dictionary_title or "(not specified)"
        category = result.category_id or "(not specified)"
        dtype = result.type_contents or "(not specified)"
        description = result.description or ""
        description_html = self._format_description_html(description)
        units = result.units or ""
        units_row = ""
        if units:
            units_row = (
                "<tr><td style='padding: 3px 8px 3px 0; vertical-align: middle;'><b>Units:</b></td>"
                f"<td style='padding: 3px 0; vertical-align: middle;'><code>{escape(units)}</code></td></tr>"
            )
        aliases = list(result.aliases or [])
        aliases_html = (
            "<ul style='margin-top: 0;'>"
            + "".join(f"<li><code>{escape(alias)}</code></li>" for alias in aliases)
            + "</ul>"
        ) if aliases else "<p style='margin-top: 0;'>(No aliases listed in loaded metadata)</p>"
        present_names = self._result_present_names[source_row] if source_row < len(self._result_present_names) else []
        matched_alias_text = ", ".join(present_names) if present_names else "-"
        _, has_alias = self._get_presence_flags(result, present_names)

        if result.enumeration_values:
            value_items = "".join(f"<li><code>{escape(value)}</code></li>" for value in result.enumeration_values)
            values_section = (
                "<h3 style='margin: 12px 0 6px 0;'>Allowed Values</h3>"
                f"<ul style='margin-top: 0;'>{value_items}</ul>"
            )
        elif result.examples:
            value_items = "".join(f"<li><code>{escape(example)}</code></li>" for example in result.examples)
            values_section = (
                "<h3 style='margin: 12px 0 6px 0;'>Examples</h3>"
                f"<ul style='margin-top: 0;'>{value_items}</ul>"
            )
        else:
            values_section = (
                "<h3 style='margin: 12px 0 6px 0;'>Examples</h3>"
                "<p style='margin-top: 0;'>(No examples listed in loaded metadata)</p>"
            )

        html_content = f"""
        <h2 style='margin: 0 0 10px 0;'><code>{escape(result.field_name)}</code></h2>
        <table style='border-collapse: collapse; width: 100%;'>
            <tr><td style='padding: 3px 8px 3px 0; vertical-align: middle;'><b>Dictionary:</b></td><td style='padding: 3px 0; vertical-align: middle;'>{escape(result.dictionary_name)}</td></tr>
            <tr><td style='padding: 3px 8px 3px 0; vertical-align: middle;'><b>Dictionary title:</b></td><td style='padding: 3px 0; vertical-align: middle;'>{escape(dict_title)}</td></tr>
            <tr><td style='padding: 3px 8px 3px 0; vertical-align: middle;'><b>Category:</b></td><td style='padding: 3px 0; vertical-align: middle;'><code>{escape(category)}</code></td></tr>
            <tr><td style='padding: 3px 8px 3px 0; vertical-align: middle;'><b>Type:</b></td><td style='padding: 3px 0; vertical-align: middle;'><code>{escape(dtype)}</code></td></tr>
            {units_row}
            <tr><td style='padding: 3px 8px 3px 0; vertical-align: middle;'><b>Found in current CIF:</b></td><td style='padding: 3px 0; vertical-align: middle;'>{escape(presence_text)}</td></tr>
            <tr><td style='padding: 3px 8px 3px 0; vertical-align: middle;'><b>Line in current CIF:</b></td><td style='padding: 3px 0; vertical-align: middle;'>{escape(line_text)}</td></tr>
            <tr><td style='padding: 3px 8px 3px 0; vertical-align: top;'><b>Alias present in CIF:</b></td><td style='padding: 3px 0; vertical-align: top;'>{'Yes' if has_alias else 'No'}{': '}<code>{escape(matched_alias_text)}</code></td></tr>
        </table>
        <h3 style='margin: 12px 0 6px 0;'>Known Aliases</h3>
        {aliases_html}
        <h3 style='margin: 12px 0 6px 0;'>Description</h3>
        {description_html}
        {values_section}
        """

        self.details_text.setHtml(html_content)
        self.goto_line_button.setEnabled(hit_line > 0 and self._go_to_line is not None)
        self._update_hitlist_highlights(hit_line if hit_line > 0 else None)

    def _update_hitlist_highlights(self, selected_line: Optional[int]) -> None:
        """Update temporary editor highlights for the current hit list and selected row."""
        if self._set_hitlist_highlights is None:
            return

        line_numbers: List[int] = []
        for source_row in self._result_display_order:
            if source_row >= len(self._result_line_numbers):
                continue
            line_number = self._result_line_numbers[source_row]
            if line_number > 0:
                line_numbers.append(line_number)

        self._set_hitlist_highlights(line_numbers, selected_line)

    def closeEvent(self, event) -> None:
        """Clear temporary editor highlights when the dialog closes."""
        if self._set_hitlist_highlights is not None:
            self._set_hitlist_highlights([], None)
        super().closeEvent(event)

    def _build_field_line_map(self) -> Dict[str, int]:
        """Build map of field names to first line number in current CIF content."""
        if self._get_cif_content is None:
            return {}

        content = self._get_cif_content() or ""
        field_line_map: Dict[str, int] = {}
        for line_number, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("_"):
                continue

            parts = stripped.split(None, 1)
            if not parts:
                continue

            field_name = parts[0].lower()
            if field_name not in field_line_map:
                field_line_map[field_name] = line_number

        return field_line_map

    def _resolve_hit_info(self, result: DictionarySearchResult, field_line_map: Dict[str, int]) -> tuple[int, List[str]]:
        """Resolve first matching CIF line and name for a canonical dictionary search hit."""
        if not field_line_map:
            return 0, []

        candidate_names = {result.field_name.lower()}
        candidate_names.update(alias.lower() for alias in (result.aliases or []))

        metadata = self.dict_manager.get_field_metadata(result.field_name)
        if metadata:
            definition_id = getattr(metadata, "definition_id", None)
            if definition_id:
                candidate_names.add(definition_id.lower())

            for alias in getattr(metadata, "aliases", []):
                alias_name = getattr(alias, "name", None)
                if alias_name:
                    candidate_names.add(alias_name.lower())

        matched_entries = [
            (field_line_map[name], name)
            for name in candidate_names
            if name in field_line_map
        ]
        if not matched_entries:
            return 0, []

        matched_entries.sort(key=lambda item: item[0])
        line_number = matched_entries[0][0]
        present_names = [name for _, name in matched_entries]
        return line_number, present_names

    def _go_to_selected_hit(self, *_args) -> None:
        """Navigate editor to selected hit line when available."""
        if self._go_to_line is None:
            return

        row = self.hits_list.currentRow()
        if row < 0 or row >= len(self._result_display_order):
            return

        source_row = self._result_display_order[row]
        line_number = self._result_line_numbers[source_row] if source_row < len(self._result_line_numbers) else 0
        if line_number > 0:
            self._go_to_line(line_number)

    def _on_description_toggle(self, checked: bool) -> None:
        """Re-run search when include-description scope changes."""
        self._run_search()
