"""Workflow tests for CIVET entrypoint CLI parsing."""

import pytest

import main


def test_parse_cli_args_defaults_to_no_file():
    args = main._parse_cli_args([])
    assert args.cif_file is None


def test_parse_cli_args_accepts_optional_file_path():
    args = main._parse_cli_args(["path\\to\\example.cif"])
    assert args.cif_file == "path\\to\\example.cif"


def test_parse_cli_args_ignores_unknown_options():
    args = main._parse_cli_args(["path\\to\\example.cif", "--some-qt-flag", "value"])
    assert args.cif_file == "path\\to\\example.cif"


def test_parse_cli_args_help_exits_cleanly():
    with pytest.raises(SystemExit) as exc_info:
        main._parse_cli_args(["--help"])

    assert exc_info.value.code == 0
