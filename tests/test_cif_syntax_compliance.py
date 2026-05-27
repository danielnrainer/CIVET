"""Tests for CIF syntax compliance checking (cif_syntax_compliance.py).

Covers:
- CIF1ComplianceChecker: non-ASCII, CIF2 constructs, brackets, line length,
  name lengths, reserved words as values, version header.
- CIF2ComplianceChecker: header, line length, unquoted special chars.
- check_compliance() aggregation function.
- Detect_syntax_version returns UNKNOWN for headerless files.
- Semicolons not at column 0 don't trigger text-block toggle.
- Same-line triple-quote open+close doesn't flip state permanently.
- Non-ASCII encoding maps and conversion functions.
"""

import sys
import os
import pytest

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check1(content: str):
    """Return CIF 1.1 compliance issues for content."""
    from utils.cif_syntax_compliance import CIF1ComplianceChecker
    return CIF1ComplianceChecker().check(content)


def _check2(content: str):
    """Return CIF 2.0 compliance issues for content."""
    from utils.cif_syntax_compliance import CIF2ComplianceChecker
    return CIF2ComplianceChecker().check(content)


def _check(content: str):
    """Return {'cif1': [...], 'cif2': [...]} for content."""
    from utils.cif_syntax_compliance import check_compliance
    return check_compliance(content)


def _issue_types(issues) -> list:
    return [i.issue_type for i in issues]


# ===========================================================================
# CIF1ComplianceChecker
# ===========================================================================

class TestCIF1ComplianceChecker:

    # ------------------------------------------------------------------
    # Version header checks
    # ------------------------------------------------------------------

    def test_no_issues_with_valid_cif1_header(self):
        content = '#\\#CIF_1.1\ndata_test\n_cell.length_a 5.43\n'
        issues = _check1(content)
        header_issues = [i for i in issues if 'header' in i.issue_type]
        assert header_issues == []

    def test_no_header_raises_missing_version_header(self):
        content = 'data_test\n_cell.length_a 5.43\n'
        issues = _check1(content)
        types = _issue_types(issues)
        assert 'missing_version_header' in types

    def test_cif2_header_raises_wrong_version_header(self):
        content = '#\\#CIF_2.0\ndata_test\n_cell.length_a 5.43\n'
        issues = _check1(content)
        types = _issue_types(issues)
        assert 'wrong_version_header' in types

    def test_cif2_header_wrong_version_header_is_error(self):
        """A CIF2.0 header is an error for CIF1.1 compliance, not just a warning."""
        content = '#\\#CIF_2.0\ndata_test\n_cell.length_a 5.43\n'
        issues = _check1(content)
        wrong = [i for i in issues if i.issue_type == 'wrong_version_header']
        assert all(i.severity == 'error' for i in wrong)

    def test_missing_version_header_is_auto_fixable(self):
        content = 'data_test\n_cell.length_a 5.43\n'
        issues = _check1(content)
        header_issues = [i for i in issues if i.issue_type == 'missing_version_header']
        assert all(i.auto_fixable for i in header_issues)

    # ------------------------------------------------------------------
    # Character-set checks
    # ------------------------------------------------------------------

    def test_pure_ascii_content_no_charset_issues(self):
        content = '#\\#CIF_1.1\ndata_test\n_cell.length_a 5.43\n'
        issues = _check1(content)
        charset = [i for i in issues if i.issue_type == 'non_ascii_character']
        assert charset == []

    def test_non_ascii_char_detected(self):
        content = '#\\#CIF_1.1\ndata_test\n_name \u00c5ngstrom\n'  # Å
        issues = _check1(content)
        charset = [i for i in issues if i.issue_type == 'non_ascii_character']
        assert len(charset) >= 1

    def test_non_ascii_error_severity(self):
        content = '#\\#CIF_1.1\ndata_test\n_name \u00c5ngstrom\n'
        issues = _check1(content)
        charset = [i for i in issues if i.issue_type == 'non_ascii_character']
        assert all(i.severity == 'error' for i in charset)

    def test_known_unicode_non_ascii_is_auto_fixable(self):
        """Å has a known CIF 1.1 encoding, so auto_fixable should be True."""
        from utils.cif_char_encoding import CIF11_UNICODE_TO_BACKSLASH
        content = '#\\#CIF_1.1\ndata_test\n_name \u00c5ngstrom\n'  # U+00C5 Å
        issues = _check1(content)
        charset = [i for i in issues if i.issue_type == 'non_ascii_character']
        # Å is in the encoding map
        if '\u00c5' in CIF11_UNICODE_TO_BACKSLASH:
            assert any(i.auto_fixable for i in charset)

    # ------------------------------------------------------------------
    # CIF2 construct detection
    # ------------------------------------------------------------------

    def test_list_in_cif1_raises_issue(self):
        content = '#\\#CIF_1.1\ndata_test\n_field [a b c]\n'
        issues = _check1(content)
        types = _issue_types(issues)
        assert 'cif2_construct' in types

    def test_table_in_cif1_raises_issue(self):
        content = '#\\#CIF_1.1\ndata_test\n_field {"key": "val"}\n'
        issues = _check1(content)
        types = _issue_types(issues)
        assert 'cif2_construct' in types

    def test_triple_quote_in_cif1_raises_issue(self):
        content = '#\\#CIF_1.1\ndata_test\n_field """some text"""\n'
        issues = _check1(content)
        types = _issue_types(issues)
        assert 'cif2_construct' in types

    def test_normal_semicolon_block_no_cif2_issue(self):
        """Semicolon blocks are valid CIF 1.1 — should not be flagged as CIF2."""
        content = '#\\#CIF_1.1\ndata_test\n_field\n;some value\n;\n'
        issues = _check1(content)
        cif2 = [i for i in issues if i.issue_type == 'cif2_construct']
        assert cif2 == []

    # ------------------------------------------------------------------
    # Semicolon at non-zero column should NOT trigger block
    # ------------------------------------------------------------------

    def test_semicolon_not_at_column_0_not_a_block(self):
        """A semicolon inside a value (not at column 0) should NOT start a
        semicolon block, so a triple-quote inside a quoted value on the same
        line should still be flagged."""
        content = '#\\#CIF_1.1\ndata_test\n_field "value ; with semicolon"\n'
        # No false CIF2 flags from misidentifying the semicolon as a block
        issues = _check1(content)
        cif2 = [i for i in issues if i.issue_type == 'cif2_construct']
        assert cif2 == []

    # ------------------------------------------------------------------
    # Same-line triple-quote open+close
    # ------------------------------------------------------------------

    def test_same_line_triple_quote_cif2_construct_detected(self):
        """Triple quote that opens and closes on the same line should still
        register as a CIF2 construct, not leave state flipped."""
        content = '#\\#CIF_1.1\ndata_test\n_field """short"""\n_next_field 1\n'
        issues = _check1(content)
        cif2 = [i for i in issues if i.issue_type == 'cif2_construct']
        # Should detect the triple-quote on line 3
        assert len(cif2) >= 1

    def test_same_line_triple_quote_does_not_flip_state(self):
        """After a same-line open+close triple-quote, subsequent lines should
        NOT be treated as inside a triple-quoted block."""
        content = (
            '#\\#CIF_1.1\n'
            'data_test\n'
            '_a """val"""\n'        # open and close on same line
            '_b normal_value\n'     # should not be flagged
            '_c normal_value2\n'
        )
        issues = _check1(content)
        # Only 1 CIF2 issue for the triple-quote line, not additional phantom ones
        cif2 = [i for i in issues if i.issue_type == 'cif2_construct']
        # There could be 1 (for `_a """val"""`)
        lines_flagged = {i.line_number for i in cif2}
        # _b and _c (line 4, 5) should NOT be flagged
        assert 4 not in lines_flagged
        assert 5 not in lines_flagged

    # ------------------------------------------------------------------
    # Line length
    # ------------------------------------------------------------------

    def test_long_line_flagged(self):
        """CIF1.1 hard limit is 2048 chars per line."""
        long_val = 'x' * 2050
        content = f'#\\#CIF_1.1\ndata_test\n_field {long_val}\n'
        issues = _check1(content)
        types = _issue_types(issues)
        assert 'line_too_long' in types

    def test_2048_char_line_ok(self):
        # Exactly 2048 chars is fine; 2049 triggers the issue
        content = '#\\#CIF_1.1\ndata_test\n_field ' + 'a' * (2048 - 7) + '\n'
        issues = _check1(content)
        long = [i for i in issues if i.issue_type == 'line_too_long']
        assert long == []

    def test_2049_char_line_flagged(self):
        content = '#\\#CIF_1.1\ndata_test\n_field ' + 'a' * (2049 - 7) + '\n'
        issues = _check1(content)
        long = [i for i in issues if i.issue_type == 'line_too_long']
        assert len(long) >= 1

    # ------------------------------------------------------------------
    # Name lengths
    # ------------------------------------------------------------------

    def test_field_name_within_limit_ok(self):
        name = '_' + 'a' * 31  # 32 chars total (common limit is 32 or 74)
        content = f'#\\#CIF_1.1\ndata_test\n{name} 1\n'
        issues = _check1(content)
        name_issues = [i for i in issues if i.issue_type == 'long_data_name']
        assert name_issues == []

    def test_excessively_long_field_name_flagged(self):
        """Data names > 75 chars are flagged (issue_type = 'data_name_too_long')."""
        name = '_' + 'a' * 80  # 81 chars > 75 limit
        content = f'#\\#CIF_1.1\ndata_test\n{name} 1\n'
        issues = _check1(content)
        name_issues = [i for i in issues if i.issue_type == 'data_name_too_long']
        assert len(name_issues) >= 1

    # ------------------------------------------------------------------
    # Reserved words as values
    # ------------------------------------------------------------------

    def test_reserved_word_stop_as_value_flagged(self):
        """'stop_' is a CIF1.1 reserved word that must not appear as an unquoted value."""
        content = '#\\#CIF_1.1\ndata_test\n_field stop_\n'
        issues = _check1(content)
        reserved = [i for i in issues if i.issue_type == 'reserved_word_as_value']
        assert len(reserved) >= 1

    def test_reserved_word_global_as_value_flagged(self):
        content = '#\\#CIF_1.1\ndata_test\n_field global_\n'
        issues = _check1(content)
        reserved = [i for i in issues if i.issue_type == 'reserved_word_as_value']
        assert len(reserved) >= 1

    def test_normal_value_not_flagged_as_reserved(self):
        content = '#\\#CIF_1.1\ndata_test\n_field some_value\n'
        issues = _check1(content)
        reserved = [i for i in issues if i.issue_type == 'reserved_word_as_value']
        assert reserved == []


# ===========================================================================
# CIF2ComplianceChecker
# ===========================================================================

class TestCIF2ComplianceChecker:

    def test_valid_cif2_header_no_header_issue(self):
        content = '#\\#CIF_2.0\ndata_test\n_cell.length_a 5.43\n'
        issues = _check2(content)
        header = [i for i in issues if i.issue_type in ('missing_version_header', 'wrong_version_header')]
        assert header == []

    def test_missing_cif2_header_flagged(self):
        content = 'data_test\n_cell.length_a 5.43\n'
        issues = _check2(content)
        types = _issue_types(issues)
        assert 'missing_version_header' in types

    def test_cif1_header_flagged_for_cif2_as_wrong_header(self):
        """A CIF1.1 header in a CIF2 context is wrong_version_header, not missing."""
        content = '#\\#CIF_1.1\ndata_test\n_cell.length_a 5.43\n'
        issues = _check2(content)
        types = _issue_types(issues)
        assert 'wrong_version_header' in types
        assert 'missing_version_header' not in types

    def test_line_over_2048_flagged(self):
        long_val = 'x' * 2050
        content = f'#\\#CIF_2.0\ndata_test\n_field {long_val}\n'
        issues = _check2(content)
        types = _issue_types(issues)
        assert 'line_too_long' in types

    def test_line_under_2048_ok(self):
        long_val = 'x' * 80
        content = f'#\\#CIF_2.0\ndata_test\n_field {long_val}\n'
        issues = _check2(content)
        long = [i for i in issues if i.issue_type == 'long_line']
        assert long == []


# ===========================================================================
# check_compliance() aggregation
# ===========================================================================

class TestCheckCompliance:

    def test_returns_dict_with_cif1_and_cif2_keys(self):
        result = _check('data_test\n_field value\n')
        assert 'cif1' in result
        assert 'cif2' in result

    def test_cif1_results_are_lists(self):
        result = _check('data_test\n_field value\n')
        assert isinstance(result['cif1'], list)
        assert isinstance(result['cif2'], list)

    def test_compliant_cif1_no_errors(self):
        content = '#\\#CIF_1.1\ndata_test\n_cell_length_a 5.43\n'
        result = _check(content)
        errors = [i for i in result['cif1'] if i.severity == 'error']
        assert errors == []

    def test_compliant_cif2_no_errors(self):
        content = '#\\#CIF_2.0\ndata_test\n_cell.length_a 5.43\n'
        result = _check(content)
        errors = [i for i in result['cif2'] if i.severity == 'error']
        assert errors == []


# ===========================================================================
# is_cif1_compliant / is_cif2_compliant
# ===========================================================================

class TestComplianceConvenienceFunctions:

    def test_is_cif1_compliant_true_for_valid(self):
        from utils.cif_syntax_compliance import is_cif1_compliant
        content = '#\\#CIF_1.1\ndata_test\n_field value\n'
        assert is_cif1_compliant(content) is True

    def test_is_cif1_compliant_false_for_non_ascii(self):
        from utils.cif_syntax_compliance import is_cif1_compliant
        content = '#\\#CIF_1.1\ndata_test\n_field \u00c5 value\n'
        assert is_cif1_compliant(content) is False

    def test_is_cif2_compliant_true_for_valid(self):
        from utils.cif_syntax_compliance import is_cif2_compliant
        content = '#\\#CIF_2.0\ndata_test\n_field value\n'
        assert is_cif2_compliant(content) is True

    def test_is_cif2_compliant_false_for_no_header(self):
        from utils.cif_syntax_compliance import is_cif2_compliant
        content = 'data_test\n_field value\n'
        assert is_cif2_compliant(content) is False


# ===========================================================================
# Detect_syntax_version returns UNKNOWN
# ===========================================================================

class TestDetectSyntaxVersion:

    def test_headerless_no_constructs_returns_unknown(self):
        """Bug F: A headerless file with no CIF2 constructs should return
        UNKNOWN, not CIF1."""
        from utils.cif_dictionary_manager import CIFDictionaryManager, CIFSyntaxVersion
        dm = CIFDictionaryManager()
        content = 'data_test\n_cell.length_a 5.43\n'
        result = dm.detect_syntax_version(content)
        assert result == CIFSyntaxVersion.UNKNOWN

    def test_cif2_header_returns_cif2(self):
        from utils.cif_dictionary_manager import CIFDictionaryManager, CIFSyntaxVersion
        dm = CIFDictionaryManager()
        content = '#\\#CIF_2.0\ndata_test\n_field value\n'
        result = dm.detect_syntax_version(content)
        assert result == CIFSyntaxVersion.CIF2

    def test_cif1_header_returns_cif1(self):
        from utils.cif_dictionary_manager import CIFDictionaryManager, CIFSyntaxVersion
        dm = CIFDictionaryManager()
        content = '#\\#CIF_1.1\ndata_test\n_field value\n'
        result = dm.detect_syntax_version(content)
        assert result == CIFSyntaxVersion.CIF1

    def test_cif2_construct_no_header_returns_cif2(self):
        from utils.cif_dictionary_manager import CIFDictionaryManager, CIFSyntaxVersion
        dm = CIFDictionaryManager()
        content = 'data_test\n_field [a b c]\n'
        result = dm.detect_syntax_version(content)
        assert result == CIFSyntaxVersion.CIF2


# ===========================================================================
# Semicolons not at column 0 don't trigger text-block toggle
# ===========================================================================

class TestSemicolonColumn0:

    def test_semicolon_inside_value_not_treated_as_block_start(self):
        """A semicolon that is part of a quoted value (not at column 0) must
        not trigger the 'in_text_block' toggle, so subsequent lines are not
        wrongly classified as inside a text block."""
        from utils.cif_format_converter import CIFFormatConverter
        # The semicolon here is inside a quoted value, not at column 0
        content = 'data_test\n_field "value; with semicolon"\n_other [a b]\n'
        constructs = CIFFormatConverter._detect_cif2_constructs_static(content)
        # [a b] is after a quoted semicolon — it should still be detected
        assert len(constructs) > 0

    def test_semicolon_at_column_0_starts_text_block(self):
        """A semicolon at column 0 should start/end a text block and protect
        content inside from being treated as CIF2 constructs."""
        from utils.cif_format_converter import CIFFormatConverter
        # [a b] is inside a semicolon text block — should NOT be a CIF2 construct
        content = 'data_test\n_field\n;\n[a b] not a list\n;\n'
        constructs = CIFFormatConverter._detect_cif2_constructs_static(content)
        assert constructs == []


# ===========================================================================
# Same-line triple-quote in _detect_cif2_constructs_static
# ===========================================================================

class TestSameLineTripleQuote:

    def test_same_line_open_close_triple_quote_detected(self):
        """A triple-quoted string on a single line should be detected as a CIF2
        construct."""
        from utils.cif_format_converter import CIFFormatConverter
        content = 'data_test\n_field """value on one line"""\n'
        constructs = CIFFormatConverter._detect_cif2_constructs_static(content)
        assert any('triple' in c.lower() for c in constructs)

    def test_after_same_line_triple_quote_state_reset(self):
        """After a same-line open+close triple-quote, subsequent lines are
        not treated as inside a triple-quoted block."""
        from utils.cif_format_converter import CIFFormatConverter
        content = (
            'data_test\n'
            '_a """short"""\n'     # opens and closes
            '_b normal_value\n'
            '_c [1 2 3]\n'         # should be detected as a list, not hidden
        )
        constructs = CIFFormatConverter._detect_cif2_constructs_static(content)
        # [1 2 3] on _c line should be detected
        assert any('list' in c.lower() or '[' in c for c in constructs)


# ===========================================================================
# Inline comments stripped before bracket check
# ===========================================================================

class TestInlineCommentStripping:

    def test_hash_in_comment_not_treated_as_bracket(self):
        """An inline comment with # followed by brackets should not be flagged
        as a CIF2 construct."""
        from utils.cif_format_converter import CIFFormatConverter
        content = 'data_test\n_field value # comment [not a list]\n'
        constructs = CIFFormatConverter._detect_cif2_constructs_static(content)
        assert constructs == []


# ===========================================================================
# Non-ASCII encoding maps and conversion functions
# ===========================================================================

class TestNonAsciiEncodingMaps:

    def test_angstrom_in_map(self):
        from utils.cif_char_encoding import CIF11_UNICODE_TO_BACKSLASH
        assert '\u00c5' in CIF11_UNICODE_TO_BACKSLASH  # Å

    def test_degree_in_map(self):
        from utils.cif_char_encoding import CIF11_UNICODE_TO_BACKSLASH
        assert '\u00b0' in CIF11_UNICODE_TO_BACKSLASH  # °

    def test_reverse_map_built(self):
        from utils.cif_char_encoding import CIF11_BACKSLASH_TO_UNICODE
        assert '\\%A' in CIF11_BACKSLASH_TO_UNICODE

    def test_reverse_map_correct_value(self):
        from utils.cif_char_encoding import CIF11_BACKSLASH_TO_UNICODE
        assert CIF11_BACKSLASH_TO_UNICODE['\\%A'] == '\u00c5'

    def test_roundtrip_angstrom(self):
        from utils.cif_char_encoding import (
            convert_unicode_to_cif11, convert_cif11_to_unicode
        )
        original = 'Temperature: 293 K, d = 5.43 \u00c5'
        encoded = convert_unicode_to_cif11(original)
        assert '\u00c5' not in encoded
        assert '\\%A' in encoded
        decoded = convert_cif11_to_unicode(encoded)
        assert decoded == original

    def test_convert_unicode_multiple_chars(self):
        from utils.cif_char_encoding import convert_unicode_to_cif11
        text = '\u00c5 \u00b0 \u00b1'  # Å ° ±
        result = convert_unicode_to_cif11(text)
        assert '\u00c5' not in result
        assert '\u00b0' not in result
        assert '\u00b1' not in result

    def test_convert_cif11_partial_roundtrip(self):
        """Only selected chars are converted back."""
        from utils.cif_char_encoding import convert_cif11_to_unicode
        text = 'Length \\%A and angle \\%G'
        result = convert_cif11_to_unicode(text)
        assert 'Å' in result or '\u00c5' in result

    def test_detect_non_ascii_chars_empty(self):
        from utils.cif_char_encoding import detect_non_ascii_chars
        result = detect_non_ascii_chars('plain ascii text 123')
        assert result == []

    def test_detect_non_ascii_chars_single(self):
        from utils.cif_char_encoding import detect_non_ascii_chars
        result = detect_non_ascii_chars('Hello \u00c5')  # Å
        assert len(result) == 1
        char, code, count, fixable = result[0]
        assert char == '\u00c5'
        assert code == '\\%A'
        assert count == 1
        assert fixable is True

    def test_detect_non_ascii_chars_unknown(self):
        """An obscure Unicode char with no mapping should be auto_fixable=False."""
        from utils.cif_char_encoding import detect_non_ascii_chars
        # U+2603 SNOWMAN — unlikely to be in CIF11 map
        result = detect_non_ascii_chars('snowman \u2603 here')
        assert len(result) == 1
        char, code, count, fixable = result[0]
        assert char == '\u2603'
        assert code is None
        assert fixable is False

    def test_detect_non_ascii_multiple_occurrences(self):
        from utils.cif_char_encoding import detect_non_ascii_chars
        result = detect_non_ascii_chars('\u00c5 \u00c5 \u00c5')
        assert len(result) == 1
        _, _, count, _ = result[0]
        assert count == 3
