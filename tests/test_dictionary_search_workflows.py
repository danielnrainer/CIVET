"""Behavior-focused tests for dictionary search workflows."""

from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication

from gui.dialogs.dictionary_search_dialog import DictionarySearchDialog
from utils.cif_dictionary_manager import DictionarySearchResult


class _FakeDictManager:
    def __init__(self, results):
        self._results = results

    def get_detailed_dictionary_info(self):
        return [
            SimpleNamespace(
                name="cif_core_3.3.0.dic",
                dict_title="CIF_CORE",
                dict_type="core",
                is_active=True,
            )
        ]

    def search_dictionary_fields(self, query, dictionary_names=None, max_results=1000, include_description=False):
        _ = (query, dictionary_names, max_results, include_description)
        return list(self._results)

    def get_field_metadata(self, field_name):
        _ = field_name
        return None


def _result(field_name, category, matched_via_alias=False):
    return DictionarySearchResult(
        dictionary_name="cif_core_3.3.0.dic",
        dictionary_title="CIF_CORE",
        field_name=field_name,
        category_id=category,
        description="test description",
        type_contents="Text",
        units=None,
        aliases=[],
        matched_aliases=[],
        matched_via_alias=matched_via_alias,
        enumeration_values=[],
        examples=[],
    )


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_search_workflow_sorts_by_line_and_maps_back_to_source_row(app):
    _ = app
    results = [
        _result("_cell_length_a", "cell"),
        _result("_cell_length_b", "cell"),
    ]
    manager = _FakeDictManager(results)
    dialog = DictionarySearchDialog(manager)

    dialog.set_cif_navigation_hooks(
        get_cif_content=lambda: "\n".join([
            "data_test",
            "_cell_length_b 6.0",
            "_other value",
            "_cell_length_a 5.0",
        ]),
        go_to_line=lambda _line: None,
    )

    dialog.search_input.setText("cell")
    line_sort_index = dialog.sort_combo.findData("line_number")
    dialog.sort_combo.setCurrentIndex(line_sort_index)

    assert dialog._result_display_order[0] == 1
    dialog._show_selected_hit(0)
    details_html = dialog.details_text.toHtml()
    assert "_cell_length_b" in details_html
    assert "line 2" in details_html.lower()
    dialog.close()


def test_go_to_line_uses_display_to_source_mapping(app):
    _ = app
    results = [
        _result("_cell_length_a", "cell"),
        _result("_cell_length_b", "cell"),
    ]
    manager = _FakeDictManager(results)
    dialog = DictionarySearchDialog(manager)

    navigated = []
    dialog.set_cif_navigation_hooks(
        get_cif_content=lambda: "\n".join([
            "_cell_length_b 6.0",
            "_cell_length_a 5.0",
        ]),
        go_to_line=lambda line: navigated.append(line),
    )

    dialog.search_input.setText("cell")
    line_sort_index = dialog.sort_combo.findData("line_number")
    dialog.sort_combo.setCurrentIndex(line_sort_index)

    dialog.hits_list.setCurrentRow(0)
    dialog._go_to_selected_hit()
    assert navigated == [1]
    dialog.close()


def test_field_line_map_keeps_first_occurrence_for_duplicate_field_names(app):
    _ = app
    manager = _FakeDictManager([])
    dialog = DictionarySearchDialog(manager)

    dialog.set_cif_navigation_hooks(
        get_cif_content=lambda: "\n".join([
            "_cell_length_a 5.0",
            "_cell_length_a 5.1",
            "_cell_length_b 6.0",
        ]),
        go_to_line=lambda _line: None,
    )

    field_line_map = dialog._build_field_line_map()
    assert field_line_map["_cell_length_a"] == 1
    assert field_line_map["_cell_length_b"] == 3
    dialog.close()
