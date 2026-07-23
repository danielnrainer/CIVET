"""Tests for DDL1 _list_link_parent / _list_link_child handling.

These tags declare a parent/child key relationship between two DDL1 data
items (e.g. a powder dictionary's "_pd_phase_id" as parent of
"_pd_refln_phase_id"). Previously the values were extracted into
DDL1BlockData but never reached FieldMetadata or any validation path -- see
.github/cif_tooling_comparison.md section 6/14.
"""

import textwrap

import pytest

from utils.CIF_parser import CIFParser
from utils.cif_data_validator import CIFDataValidator
from utils.cif_ddl1_parser import DDL1DictionaryParser
from utils.cif_dictionary_manager import CIFDictionaryManager


DDL1_DICT_CONTENT = textwrap.dedent("""\
    data_on_this_dictionary
    _dictionary_name  'test_link.dic'
    _dictionary_version  1.0
    _dictionary_update  2026-07-23

    data_test_parent_id
    _name  '_test_parent_id'
    _category  test_category
    _type  char
    _definition
    ;
     Test parent identifier.
    ;
    _list  yes

    data_test_child_id
    _name  '_test_child_id'
    _category  test_category
    _type  char
    _definition
    ;
     Test child identifier, linked to its parent.
    ;
    _list  yes
    _list_link_parent  '_test_parent_id'
    """)


@pytest.fixture
def ddl1_dict_path(tmp_path):
    path = tmp_path / "test_link.dic"
    path.write_text(DDL1_DICT_CONTENT, encoding="utf-8")
    return str(path)


def test_ddl1_parser_extracts_list_link_parent_value(ddl1_dict_path):
    """_list_link_parent's value starts with '_' -- must not be swallowed by
    the generic 'value looks like the next tag' heuristic in
    _extract_single_value()."""
    parser = DDL1DictionaryParser(ddl1_dict_path)
    parser.parse_dictionary()

    child_meta = parser.get_field_metadata('_test_child_id')
    assert child_meta is not None
    assert child_meta.list_link_parent == '_test_parent_id'
    assert child_meta.list_link_child is None

    parent_meta = parser.get_field_metadata('_test_parent_id')
    assert parent_meta is not None
    assert parent_meta.list_link_parent is None


def test_dictionary_manager_reports_relational_link(ddl1_dict_path):
    manager = CIFDictionaryManager()
    manager._register_dictionary_lazy(ddl1_dict_path)
    manager._ensure_loaded()

    links = manager.get_relational_links()

    assert ('_test_child_id', '_test_parent_id') in links


def test_parent_child_check_flags_unmatched_child_value(ddl1_dict_path):
    manager = CIFDictionaryManager()
    manager._register_dictionary_lazy(ddl1_dict_path)
    manager._ensure_loaded()

    content = "\n".join([
        "_test_parent_id  phaseA",
        "_test_child_id   phaseB",
        "",
    ])
    parser = CIFParser()
    parser.parse_file(content)

    issues = CIFDataValidator().check_parent_child_links(parser, manager)

    assert any(
        i.issue_type == 'parent_child_violation'
        and i.severity == 'error'
        and i.field_name == '_test_child_id'
        for i in issues
    )


def test_parent_child_check_accepts_matching_value(ddl1_dict_path):
    manager = CIFDictionaryManager()
    manager._register_dictionary_lazy(ddl1_dict_path)
    manager._ensure_loaded()

    content = "\n".join([
        "_test_parent_id  phaseA",
        "_test_child_id   phaseA",
        "",
    ])
    parser = CIFParser()
    parser.parse_file(content)

    issues = CIFDataValidator().check_parent_child_links(parser, manager)

    assert issues == []


def test_parent_child_check_is_noop_without_declared_links():
    """Managers with no DDL1 relational links (e.g. the default cif_core-only
    manager) should short-circuit to an empty list rather than scan values."""
    manager = CIFDictionaryManager()
    manager._ensure_loaded()

    parser = CIFParser()
    parser.parse_file("_cell.length_a 1.0\n")

    issues = CIFDataValidator().check_parent_child_links(parser, manager)

    assert issues == []
