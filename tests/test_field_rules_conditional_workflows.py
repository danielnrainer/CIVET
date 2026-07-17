"""Behavior-focused tests for IF/THEN conditional blocks in .cif_rules files."""

from PyQt6.QtWidgets import QDialog

import gui.field_checking as field_checking_module
from gui.field_checking import FieldCheckingMixin
from utils.CIF_field_parsing import (
    CIFCondition, CIFField, CIFFieldChecker, evaluate_condition,
    load_cif_field_rules, parse_field_rules_content,
)
from utils.CIF_parser import CIFParser


def _write_rules(tmp_path, content):
    path = tmp_path / "rules.cif_rules"
    path.write_text(content, encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# evaluate_condition
# ---------------------------------------------------------------------------

def test_evaluate_condition_exists():
    lookup = {"_diffrn_radiation.probe": "electron"}.get
    assert evaluate_condition(CIFCondition("_diffrn_radiation.probe", "exists"), lookup) is True
    assert evaluate_condition(CIFCondition("_missing.field", "exists"), lookup) is False


def test_evaluate_condition_not_exists():
    lookup = {"_diffrn_radiation.probe": "electron"}.get
    assert evaluate_condition(CIFCondition("_missing.field", "not_exists"), lookup) is True
    assert evaluate_condition(CIFCondition("_diffrn_radiation.probe", "not_exists"), lookup) is False


def test_evaluate_condition_equals_strips_quotes_and_whitespace():
    lookup = {"_diffrn_radiation.probe": "'electron'"}.get
    assert evaluate_condition(CIFCondition("_diffrn_radiation.probe", "equals", "electron"), lookup) is True
    assert evaluate_condition(CIFCondition("_diffrn_radiation.probe", "equals", "x-ray"), lookup) is False


def test_evaluate_condition_not_equals_requires_field_present():
    lookup = {"_diffrn_radiation.probe": "electron"}.get
    assert evaluate_condition(CIFCondition("_diffrn_radiation.probe", "not_equals", "x-ray"), lookup) is True
    assert evaluate_condition(CIFCondition("_diffrn_radiation.probe", "not_equals", "electron"), lookup) is False
    # A missing field is neither equal nor "not equal" - use IF NOT: for absence.
    assert evaluate_condition(CIFCondition("_missing.field", "not_equals", "electron"), lookup) is False


# ---------------------------------------------------------------------------
# load_cif_field_rules parsing of IF: / IF NOT: ... ENDIF blocks
# ---------------------------------------------------------------------------

def test_parses_if_exists_block_with_nested_check(tmp_path):
    rules_path = _write_rules(tmp_path, """
IF: _diffrn_radiation.probe
    CHECK: _diffrn_radiation_wavelength 0.02508
ENDIF
""")
    fields = load_cif_field_rules(rules_path)

    assert len(fields) == 1
    if_field = fields[0]
    assert if_field.action == "IF"
    assert if_field.condition.field_name == "_diffrn_radiation.probe"
    assert if_field.condition.operator == "exists"
    assert len(if_field.then_fields) == 1
    nested = if_field.then_fields[0]
    assert nested.action == "CHECK"
    assert nested.name == "_diffrn_radiation_wavelength"
    assert nested.default_value == "0.02508"


def test_parses_if_equals(tmp_path):
    rules_path = _write_rules(tmp_path, """
IF: _diffrn_radiation.probe electron
    CHECK: _diffrn_radiation_wavelength 0.02508
ENDIF
""")
    fields = load_cif_field_rules(rules_path)

    assert len(fields) == 1
    assert fields[0].condition.operator == "equals"
    assert fields[0].condition.value == "electron"


def test_there_is_no_exists_keyword_the_word_is_treated_as_a_literal_value(tmp_path):
    """There is deliberately no "exists" keyword: "IF: _field exists" is just an
    equals-check against the literal string "exists". Use the bare "IF: _field"
    form (no trailing value) to test for existence."""
    rules_path = _write_rules(tmp_path, """
IF: _diffrn_radiation.probe exists
    CHECK: _diffrn.ambient_temperature 293
ENDIF
""")
    fields = load_cif_field_rules(rules_path)

    assert fields[0].condition.operator == "equals"
    assert fields[0].condition.value == "exists"


def test_parses_if_not_equals(tmp_path):
    rules_path = _write_rules(tmp_path, """
IF: _diffrn_radiation.probe != electron
    CHECK: _diffrn_radiation.polarizn_ratio 0.5
ENDIF
""")
    fields = load_cif_field_rules(rules_path)

    condition = fields[0].condition
    assert condition.operator == "not_equals"
    assert condition.value == "electron"


def test_parses_if_not_block(tmp_path):
    rules_path = _write_rules(tmp_path, """
IF NOT: _exptl_crystal.colour
    CHECK: _exptl_crystal.colour red
ENDIF
""")
    fields = load_cif_field_rules(rules_path)

    condition = fields[0].condition
    assert condition.field_name == "_exptl_crystal.colour"
    assert condition.operator == "not_exists"
    assert condition.value is None


def test_if_block_supports_all_nested_action_types(tmp_path):
    rules_path = _write_rules(tmp_path, """
IF: _diffrn_radiation.probe electron
    DELETE: _obsolete_field
    EDIT: _some_field new_value
    RENAME: _old_name _new_name
    CALCULATE: _diffrn.flux_density = _diffrn.flux_density / (_diffrn.total_exposure_time * 60)
    CHECK: _diffrn.ambient_temperature 293
ENDIF
""")
    fields = load_cif_field_rules(rules_path)
    nested_actions = [f.action for f in fields[0].then_fields]

    assert nested_actions == ["DELETE", "EDIT", "RENAME", "CALCULATE", "CHECK"]


def test_if_block_aggregates_repeated_check_suggestions_within_block(tmp_path):
    rules_path = _write_rules(tmp_path, """
IF: _diffrn_radiation.probe electron
    CHECK: _diffrn.ambient_temperature 100
    CHECK: _diffrn.ambient_temperature 293
ENDIF
""")
    fields = load_cif_field_rules(rules_path)
    then_fields = fields[0].then_fields

    assert len(then_fields) == 1
    assert then_fields[0].default_value == "100"
    assert then_fields[0].suggestions == ["100", "293"]


def test_unclosed_if_block_is_ignored_with_warning(tmp_path, capsys):
    rules_path = _write_rules(tmp_path, """
IF: _diffrn_radiation.probe electron
    CHECK: _diffrn.ambient_temperature 293
""")
    fields = load_cif_field_rules(rules_path)

    assert fields == []
    assert "no matching ENDIF" in capsys.readouterr().out


def test_rules_outside_blocks_still_parse_normally(tmp_path):
    rules_path = _write_rules(tmp_path, """
_cell_length_a 1.0

IF: _diffrn_radiation.probe electron
    CHECK: _diffrn.ambient_temperature 293
ENDIF

_cell_length_b 2.0
""")
    fields = load_cif_field_rules(rules_path)
    names = [f.name for f in fields]

    assert names == ["_cell_length_a", "_diffrn_radiation.probe", "_cell_length_b"]


def test_if_blocks_can_be_nested_two_levels_deep(tmp_path):
    rules_path = _write_rules(tmp_path, """
IF: _diffrn_radiation.probe electron
    CHECK: _diffrn_radiation_wavelength 0.02508
    IF: _diffrn_measurement.method
        CHECK: _diffrn.ambient_temperature 293
    ENDIF
    EDIT: _some_field new_value
ENDIF
""")
    fields = load_cif_field_rules(rules_path)

    assert len(fields) == 1
    outer = fields[0]
    assert outer.action == "IF"
    assert [f.action for f in outer.then_fields] == ["CHECK", "IF", "EDIT"]

    inner_if = outer.then_fields[1]
    assert inner_if.condition.field_name == "_diffrn_measurement.method"
    assert inner_if.condition.operator == "exists"
    assert len(inner_if.then_fields) == 1
    assert inner_if.then_fields[0].name == "_diffrn.ambient_temperature"


def test_if_blocks_nest_to_arbitrary_depth(tmp_path):
    rules_path = _write_rules(tmp_path, """
IF: _level.one
    IF: _level.two
        IF: _level.three
            CHECK: _deeply.nested value
        ENDIF
    ENDIF
ENDIF
""")
    fields = load_cif_field_rules(rules_path)

    level1 = fields[0]
    level2 = level1.then_fields[0]
    level3 = level2.then_fields[0]
    leaf = level3.then_fields[0]

    assert level1.condition.field_name == "_level.one"
    assert level2.condition.field_name == "_level.two"
    assert level3.condition.field_name == "_level.three"
    assert leaf.name == "_deeply.nested"
    assert leaf.default_value == "value"


def test_single_endif_closes_innermost_block_leaving_outer_unclosed(tmp_path, capsys):
    """Bracket-matching sanity check: with only one ENDIF present, it must close
    the innermost open block, not the outer one - leaving the outer IF (and
    therefore the whole thing, since it never closes) discarded."""
    rules_path = _write_rules(tmp_path, """
_cell_length_a 1.0

IF: _diffrn_radiation.probe electron
    IF: _diffrn_measurement.method
        CHECK: _diffrn.ambient_temperature 293
ENDIF
""")
    fields = load_cif_field_rules(rules_path)

    # Only the field before the broken block survives; the outer IF is discarded
    # because its own ENDIF was consumed by the inner block instead.
    assert [f.name for f in fields] == ["_cell_length_a"]

    output = capsys.readouterr().out
    assert "IF: _diffrn_radiation.probe electron" in output
    assert "no matching ENDIF" in output
    assert output.count("no matching ENDIF") == 1


def test_two_missing_endifs_warn_at_each_unclosed_level(tmp_path, capsys):
    rules_path = _write_rules(tmp_path, """
IF: _diffrn_radiation.probe electron
    IF: _diffrn_measurement.method
        CHECK: _diffrn.ambient_temperature 293
""")
    fields = load_cif_field_rules(rules_path)

    assert fields == []
    output = capsys.readouterr().out
    assert output.count("no matching ENDIF") == 2
    assert "_diffrn_radiation.probe" in output
    assert "_diffrn_measurement.method" in output


# ---------------------------------------------------------------------------
# parse_field_rules_content: malformed-rule issue reporting
#
# The real rules loader silently drops anything it can't parse (an IF block
# missing its ENDIF, a malformed condition, a malformed RENAME/CALCULATE/
# CHECK line, ...). parse_field_rules_content's `issues` output is what lets
# FieldRulesValidator surface these instead of reporting "no errors found"
# for a file that actually fails to load anything useful.
# ---------------------------------------------------------------------------

def test_reports_reproduction_of_user_reported_missing_endif_bug():
    """The exact scenario a user hit: an IF block with a nested CHECK and no
    ENDIF at all. The loader drops the whole block (and therefore the entire
    file, here); parse_field_rules_content must report why."""
    content = (
        "IF: _chemical_formula_moiety           'C28 H48 N2 O4'\n"
        "  CHECK: _chemical_formula_weight           476.702\n"
    )
    issues = []

    fields = parse_field_rules_content(content, issues=issues)

    assert fields == []  # confirms the loader really does drop everything
    assert len(issues) == 1
    line_no, message, field_name = issues[0]
    assert line_no == 1
    assert "no matching ENDIF" in message
    assert field_name == "_chemical_formula_moiety"


def test_reports_malformed_condition_and_discards_body_instead_of_leaking_it():
    """A condition that fails to parse must not let its nested rules leak
    into the outer (unconditional) scope - that would silently turn a guarded
    rule into one that always runs."""
    content = (
        "IF: not_a_field_name electron\n"
        "    CHECK: _cell.length_a 1\n"
        "ENDIF\n"
    )
    issues = []

    fields = parse_field_rules_content(content, issues=issues)

    assert fields == []  # the CHECK must NOT leak out and run unconditionally
    assert len(issues) == 1
    line_no, message, field_name = issues[0]
    assert line_no == 1
    assert "Malformed condition" in message
    assert field_name is None


def test_reports_malformed_rename_calculate_delete_check_lines():
    content = (
        "RENAME: _only_one_name\n"
        "CALCULATE: _no_expression =\n"
        "CALCULATE: no_equals_sign_here\n"
        "DELETE: not_a_field\n"
        "not_a_field_either 5\n"
    )
    issues = []

    fields = parse_field_rules_content(content, issues=issues)

    assert fields == []
    messages = [message for _line_no, message, _field_name in issues]
    assert len(messages) == 5
    assert any("Malformed RENAME" in m for m in messages)
    assert sum("Malformed CALCULATE" in m for m in messages) == 2
    assert any("Malformed DELETE" in m for m in messages)
    assert any("does not look like a CIF field name" in m for m in messages)

    # Line numbers must point at the actual offending lines.
    line_numbers = [line_no for line_no, _m, _f in issues]
    assert line_numbers == [1, 2, 3, 4, 5]


def test_well_formed_rules_report_no_malformed_issues():
    content = (
        "_cell.length_a 1\n"
        "DELETE: _obsolete_field\n"
        "RENAME: _old_name _new_name\n"
        "CALCULATE: _cell.volume = _cell.length_a * 2\n"
        "IF: _cell.length_a 1\n"
        "    CHECK: _cell.length_b 2\n"
        "ENDIF\n"
    )
    issues = []

    fields = parse_field_rules_content(content, issues=issues)

    assert issues == []
    assert len(fields) == 5


def test_stray_endif_is_reported_but_does_not_affect_surrounding_rules():
    content = (
        "_cell.length_a 1\n"
        "ENDIF\n"
        "_cell.length_b 2\n"
    )
    issues = []

    fields = parse_field_rules_content(content, issues=issues)

    assert [f.name for f in fields] == ["_cell.length_a", "_cell.length_b"]
    assert len(issues) == 1
    assert "Stray 'ENDIF'" in issues[0][1]


# ---------------------------------------------------------------------------
# End-to-end dispatch through FieldCheckingMixin._execute_rule
# ---------------------------------------------------------------------------

class _DummyTextEditor:
    def __init__(self, text: str):
        self._text = text

    def toPlainText(self):
        return self._text

    def setText(self, text: str):
        self._text = text


class _DictManager:
    @staticmethod
    def is_field_deprecated(_prefix):
        return False


class _RuleDispatchHarness(FieldCheckingMixin):
    def __init__(self, content: str):
        self.text_editor = _DummyTextEditor(content)
        self.cif_parser = CIFParser()
        self.cif_parser.parse_file(content)
        self.field_checker = CIFFieldChecker()  # real helpers for action rules
        self.dict_manager = _DictManager()

    def extract_field_value(self, lines, index, prefix):
        line = lines[index]
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0] == prefix:
            return parts[1]
        return ""

    def _show_dialog_with_configured_interaction(self, dialog, mode_setting_key=None):
        _ = (dialog, mode_setting_key)
        return QDialog.DialogCode.Accepted


def _ensure_parser_current_factory(harness):
    def _ensure():
        harness.cif_parser.parse_file(harness.text_editor.toPlainText())
    return _ensure


def test_if_block_runs_nested_check_when_condition_true(monkeypatch):
    content = "_diffrn_radiation.probe electron\n"
    harness = _RuleDispatchHarness(content)

    prompted = {}

    def fake_get_text(parent, title, prompt, current_value, default_value, **kwargs):
        _ = (parent, title, prompt, kwargs)
        prompted["called"] = True
        return default_value, QDialog.DialogCode.Accepted

    monkeypatch.setattr(field_checking_module.CIFInputDialog, "getText", fake_get_text)

    condition = CIFCondition("_diffrn_radiation.probe", "equals", "electron")
    nested = CIFField("_diffrn.ambient_temperature", "293", action="CHECK", suggestions=["293"])
    if_field = CIFField("_diffrn_radiation.probe", "", action="IF", condition=condition, then_fields=[nested])

    signal = harness._execute_rule(
        if_field, {}, content, _ensure_parser_current_factory(harness), [], is_custom_or_user=False
    )

    assert signal == "continue"
    assert prompted.get("called") is True
    assert "_diffrn.ambient_temperature" in harness.text_editor.toPlainText()


def test_if_block_skips_nested_check_when_condition_false(monkeypatch):
    content = "_diffrn_radiation.probe x-ray\n"
    harness = _RuleDispatchHarness(content)

    prompted = {"called": False}

    def fake_get_text(*args, **kwargs):
        prompted["called"] = True
        return "", QDialog.DialogCode.Accepted

    monkeypatch.setattr(field_checking_module.CIFInputDialog, "getText", fake_get_text)

    condition = CIFCondition("_diffrn_radiation.probe", "equals", "electron")
    nested = CIFField("_diffrn.ambient_temperature", "293", action="CHECK", suggestions=["293"])
    if_field = CIFField("_diffrn_radiation.probe", "", action="IF", condition=condition, then_fields=[nested])

    signal = harness._execute_rule(
        if_field, {}, content, _ensure_parser_current_factory(harness), [], is_custom_or_user=False
    )

    assert signal == "continue"
    assert prompted["called"] is False
    assert harness.text_editor.toPlainText() == content


def test_if_block_nested_edit_action_is_gated_by_is_custom_or_user():
    content = "_diffrn_radiation.probe electron\n_some_field old_value\n"

    condition = CIFCondition("_diffrn_radiation.probe", "equals", "electron")
    nested_edit = CIFField("_some_field", "new_value", action="EDIT")
    if_field = CIFField("_diffrn_radiation.probe", "", action="IF", condition=condition, then_fields=[nested_edit])

    # Built-in field set (is_custom_or_user=False): nested EDIT must not run.
    harness = _RuleDispatchHarness(content)
    harness._execute_rule(if_field, {}, content, _ensure_parser_current_factory(harness), [], is_custom_or_user=False)
    assert "old_value" in harness.text_editor.toPlainText()

    # Custom/user field set: nested EDIT should run.
    harness2 = _RuleDispatchHarness(content)
    harness2._execute_rule(if_field, {}, content, _ensure_parser_current_factory(harness2), [], is_custom_or_user=True)
    assert "new_value" in harness2.text_editor.toPlainText()


def test_nested_if_blocks_dispatch_through_execute_rule(monkeypatch):
    """A CIFField(action='IF') nested inside another IF's then_fields should be
    evaluated and dispatched by the same recursive _execute_rule call."""
    content = "_diffrn_radiation.probe electron\n_diffrn_measurement.method 'electron diffraction'\n"
    harness = _RuleDispatchHarness(content)

    prompted = {"called": False}

    def fake_get_text(parent, title, prompt, current_value, default_value, **kwargs):
        _ = (parent, title, prompt, kwargs)
        prompted["called"] = True
        return default_value, QDialog.DialogCode.Accepted

    monkeypatch.setattr(field_checking_module.CIFInputDialog, "getText", fake_get_text)

    inner_condition = CIFCondition("_diffrn_measurement.method", "exists")
    innermost_check = CIFField("_diffrn.ambient_temperature", "293", action="CHECK", suggestions=["293"])
    inner_if = CIFField(
        "_diffrn_measurement.method", "", action="IF",
        condition=inner_condition, then_fields=[innermost_check]
    )
    outer_condition = CIFCondition("_diffrn_radiation.probe", "equals", "electron")
    outer_if = CIFField(
        "_diffrn_radiation.probe", "", action="IF",
        condition=outer_condition, then_fields=[inner_if]
    )

    signal = harness._execute_rule(
        outer_if, {}, content, _ensure_parser_current_factory(harness), [], is_custom_or_user=False
    )

    assert signal == "continue"
    assert prompted["called"] is True
    assert "_diffrn.ambient_temperature" in harness.text_editor.toPlainText()


def test_nested_if_block_skipped_when_outer_condition_false(monkeypatch):
    content = "_diffrn_radiation.probe x-ray\n_diffrn_measurement.method 'electron diffraction'\n"
    harness = _RuleDispatchHarness(content)

    prompted = {"called": False}

    def fake_get_text(*args, **kwargs):
        prompted["called"] = True
        return "", QDialog.DialogCode.Accepted

    monkeypatch.setattr(field_checking_module.CIFInputDialog, "getText", fake_get_text)

    inner_condition = CIFCondition("_diffrn_measurement.method", "exists")
    innermost_check = CIFField("_diffrn.ambient_temperature", "293", action="CHECK", suggestions=["293"])
    inner_if = CIFField(
        "_diffrn_measurement.method", "", action="IF",
        condition=inner_condition, then_fields=[innermost_check]
    )
    outer_condition = CIFCondition("_diffrn_radiation.probe", "equals", "electron")
    outer_if = CIFField(
        "_diffrn_radiation.probe", "", action="IF",
        condition=outer_condition, then_fields=[inner_if]
    )

    signal = harness._execute_rule(
        outer_if, {}, content, _ensure_parser_current_factory(harness), [], is_custom_or_user=False
    )

    assert signal == "continue"
    assert prompted["called"] is False
    assert harness.text_editor.toPlainText() == content
