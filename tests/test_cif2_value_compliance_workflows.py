"""Behavior-focused tests for CIF2 value compliance workflows."""

from utils.cif2_value_formatting import (
    choose_quote_style,
    fix_cif2_compliance_issues,
    format_cif2_value,
    needs_quoting,
    validate_cif2_content,
)


def test_needs_quoting_handles_basic_and_special_cases():
    assert needs_quoting("plain_token") is False
    assert needs_quoting("has space") is True
    assert needs_quoting("[a b]") is True
    assert needs_quoting("data_block") is True


def test_choose_quote_style_uses_triple_quotes_when_both_quote_types_present():
    value = "alpha 'beta' and \"gamma\""
    quoted = choose_quote_style(value)

    assert quoted.startswith("'''") or quoted.startswith('"""')


def test_format_cif2_value_multiline_prefers_triple_quotes_when_requested():
    value = "line1\nline2"
    formatted = format_cif2_value(value, prefer_triple_quotes=True)

    assert formatted.startswith("'''") or formatted.startswith('"""')


def test_validate_cif2_content_flags_unquoted_bracket_values():
    content = "_field [a b]\n"
    issues = validate_cif2_content(content)

    assert len(issues) == 1
    assert issues[0][1] == "_field"


def test_validate_cif2_content_ignores_brackets_inside_semicolon_text_block():
    content = "\n".join(
        [
            "_note",
            ";",
            "[a b]",
            ";",
        ]
    )
    issues = validate_cif2_content(content)

    assert issues == []


def test_fix_cif2_compliance_quotes_unquoted_special_values():
    content = "_field [a b]\n"
    fixed, fixes = fix_cif2_compliance_issues(content)

    assert len(fixes) == 1
    assert "_field '[a b]'" in fixed or '_field "[a b]"' in fixed
