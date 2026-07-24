"""Workflow tests for CIVET's headless CLI (src/cli.py).

Covers the `check`, `convert`, and `lint-rules` subcommands added to expose
the GUI's validation/conversion modules for CI/batch use (see
.github/cif_tooling_comparison.md #14 and .github/future_changes.md).
"""

import json
import os

import pytest

import cli


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "sample_cifs")
FIELD_RULES_DIR = os.path.join(os.path.dirname(__file__), "..", "field_rules")


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# check_content / convert_content (the programmatic API)
# ---------------------------------------------------------------------------

def test_check_content_reports_no_issues_for_clean_minimal_cif():
    dict_manager = cli.build_dictionary_manager()
    content = open(os.path.join(FIXTURES_DIR, "minimal.cif"), encoding="utf-8").read()

    report = cli.check_content(content, dict_manager)

    assert report["blocks"] == ["minimal"]
    assert report["error_count"] == 0


def test_check_content_flags_unknown_data_name():
    dict_manager = cli.build_dictionary_manager()
    content = (
        "#\\#CIF_1.1\n"
        "data_test\n"
        "_this_is_not_a_real_field 42\n"
    )

    report = cli.check_content(content, dict_manager)

    unknown_issues = [i for i in report["issues"] if i["issue_type"] == "unknown"]
    assert any(i["field"] == "_this_is_not_a_real_field" for i in unknown_issues)


def test_check_content_can_disable_individual_checks():
    dict_manager = cli.build_dictionary_manager()
    content = (
        "#\\#CIF_1.1\n"
        "data_test\n"
        "_this_is_not_a_real_field 42\n"
    )

    report = cli.check_content(content, dict_manager, check_data_names=False)

    assert not any(i["source"] == "data_name" for i in report["issues"])


def test_convert_content_notation_round_trip():
    dict_manager = cli.build_dictionary_manager()
    content = "#\\#CIF_1.1\ndata_test\n_cell_length_a 5.432\n"

    modern, changes = cli.convert_content(content, dict_manager, to_notation="modern")
    assert "_cell.length_a" in modern
    assert changes

    legacy, _ = cli.convert_content(modern, dict_manager, to_notation="legacy")
    assert "_cell_length_a" in legacy


def test_convert_content_to_cif1_raises_on_cif2_only_constructs():
    dict_manager = cli.build_dictionary_manager()
    content = "#\\#CIF_2.0\ndata_test\n_some_list [1 2 3]\n"

    with pytest.raises(ValueError):
        cli.convert_content(content, dict_manager, to_syntax="cif1")


# ---------------------------------------------------------------------------
# `civet check` CLI
# ---------------------------------------------------------------------------

def test_cli_check_exits_zero_for_clean_file(capsys):
    path = os.path.join(FIXTURES_DIR, "minimal.cif")

    exit_code = cli.main(["check", path])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "no issues found" in captured.out


def test_cli_check_json_output_is_parseable(tmp_path, capsys):
    path = _write(tmp_path, "bad.cif", "#\\#CIF_1.1\ndata_test\n_not_a_real_field 1\n")

    exit_code = cli.main(["check", path, "--format", "json"])
    captured = capsys.readouterr()

    payload = json.loads(captured.out)
    assert payload["files"][0]["file"] == path
    assert exit_code == 0  # unknown-field is a warning, not an error


def test_cli_check_missing_file_reports_error_and_exit_code(capsys):
    exit_code = cli.main(["check", "does_not_exist.cif"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "does_not_exist.cif" in captured.err


def test_cli_check_quiet_prints_one_line_per_file(tmp_path, capsys):
    path = _write(tmp_path, "ok.cif", "#\\#CIF_1.1\ndata_test\n_cell_length_a 5.432\n")

    cli.main(["check", path, "--quiet"])
    captured = capsys.readouterr()

    assert len(captured.out.strip().splitlines()) == 2  # per-file line + TOTAL line


# ---------------------------------------------------------------------------
# `civet convert` CLI
# ---------------------------------------------------------------------------

def test_cli_convert_writes_to_output_file(tmp_path):
    src = _write(tmp_path, "src.cif", "#\\#CIF_1.1\ndata_test\n_cell_length_a 5.432\n")
    dest = str(tmp_path / "out.cif")

    exit_code = cli.main(["convert", src, "--to-notation", "modern", "-o", dest, "--quiet"])

    assert exit_code == 0
    assert "_cell.length_a" in open(dest, encoding="utf-8").read()


def test_cli_convert_in_place(tmp_path):
    src = _write(tmp_path, "src.cif", "#\\#CIF_1.1\ndata_test\n_cell_length_a 5.432\n")

    exit_code = cli.main(["convert", src, "--to-notation", "modern", "--in-place", "--quiet"])

    assert exit_code == 0
    assert "_cell.length_a" in open(src, encoding="utf-8").read()


def test_cli_convert_requires_a_target(tmp_path, capsys):
    src = _write(tmp_path, "src.cif", "#\\#CIF_1.1\ndata_test\n_cell_length_a 5.432\n")

    exit_code = cli.main(["convert", src])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "specify at least one" in captured.err


# ---------------------------------------------------------------------------
# `civet lint-rules` CLI
# ---------------------------------------------------------------------------

def test_cli_lint_rules_on_bundled_3ded_rules(capsys):
    rules_path = os.path.join(FIELD_RULES_DIR, "3ded.cif_rules")

    exit_code = cli.main(["lint-rules", rules_path])
    captured = capsys.readouterr()

    assert exit_code in (0, 1)
    assert "field(s)" in captured.out
