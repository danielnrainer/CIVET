"""Behavior-focused tests for field-checking decision workflows."""

from PyQt6.QtWidgets import QMessageBox

from gui.field_checking import FieldCheckingMixin
from utils.cif_dictionary_manager import FieldNotation


class _DummyTextEditor:
    def __init__(self, text: str):
        self._text = text

    def toPlainText(self):
        return self._text

    def setText(self, text: str):
        self._text = text


class _DecisionHarness(FieldCheckingMixin):
    def __init__(self, content: str):
        self.text_editor = _DummyTextEditor(content)
        self._zscore_called = False
        self._absolute_check_value = "dyn"
        self._electron_data = True
        self._probe = (None, None)

    def extract_field_value(self, lines, index, prefix):
        line = lines[index]
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0] == prefix:
            return parts[1]
        return ""

    def _apply_absolute_configuration_check(self, config, initial_state):
        _ = (config, initial_state)
        return self._absolute_check_value

    def _apply_abs_structure_z_score_check(self, config, initial_state):
        _ = (config, initial_state)
        self._zscore_called = True
        return True

    def _is_electron_diffraction_data(self):
        return self._electron_data

    def _get_radiation_probe(self):
        return self._probe


class _DummyRulesFieldChecker:
    def __init__(self):
        self.loaded_name = None
        self.loaded_content = None

    def load_field_set(self, name, file_path):
        self.loaded_name = name
        with open(file_path, 'r', encoding='utf-8') as handle:
            self.loaded_content = handle.read()


class _MismatchHarness(FieldCheckingMixin):
    def __init__(self, cif_content: str, rules_path: str, action: str):
        self.text_editor = _DummyTextEditor(cif_content)
        self.custom_field_rules_file = rules_path
        self.current_field_set = "Custom"
        self.modified = False
        self._action = action

        class _DictManager:
            @staticmethod
            def detect_notation(_content):
                return FieldNotation.LEGACY

        class _RulesValidator:
            @staticmethod
            def convert_field_rules_notation(content, target_notation):
                assert target_notation == "legacy"
                return content.replace("_cell.length_a", "_cell_length_a"), ["converted"]

        class _FormatConverter:
            @staticmethod
            def convert_to_modern_notation(_content):
                return "_cell.length_a 1", ["converted cif"]

            @staticmethod
            def convert_to_legacy_notation(_content):
                return "_cell_length_a 1", ["converted cif"]

        self.dict_manager = _DictManager()
        self.field_rules_validator = _RulesValidator()
        self.format_converter = _FormatConverter()
        self.field_checker = _DummyRulesFieldChecker()

    def _prompt_rules_notation_mismatch_action(self, cif_notation, rules_notation):
        assert cif_notation == "legacy"
        assert rules_notation == "modern"
        return self._action


def test_detect_electron_diffraction_from_probe_field():
    checker = _DecisionHarness("_diffrn_radiation.probe electron\n")

    assert FieldCheckingMixin._is_electron_diffraction_data(checker) is True


def test_detect_electron_diffraction_from_measurement_method_text():
    checker = _DecisionHarness("_diffrn_measurement.method 'Continuous electron diffraction'\n")
    # Use actual mixin logic for this test path.
    checker._electron_data = None

    assert FieldCheckingMixin._is_electron_diffraction_data(checker) is True


def test_absolute_configuration_field_name_follows_detected_notation():
    checker = _DecisionHarness("_cell.length_a 1\n")

    class _DictModern:
        def detect_notation(self, _content):
            return FieldNotation.MODERN

    class _DictLegacy:
        def detect_notation(self, _content):
            return FieldNotation.LEGACY

    checker.dict_manager = _DictModern()
    modern_fields = checker._get_absolute_configuration_fields()
    assert modern_fields[0] == "_chemical.absolute_configuration"

    checker.dict_manager = _DictLegacy()
    legacy_fields = checker._get_absolute_configuration_fields()
    assert legacy_fields[0] == "_chemical_absolute_configuration"


def test_absolute_structure_workflow_triggers_zscore_check_for_dyn_electron_data():
    checker = _DecisionHarness("_diffrn_radiation.probe electron\n")
    checker._absolute_check_value = "dyn"
    checker._electron_data = True

    result = checker._apply_absolute_structure_checks(config={"show_warnings": False}, initial_state="")

    assert result is True
    assert checker._zscore_called is True


def test_absolute_structure_workflow_stops_if_absolute_configuration_step_aborts():
    checker = _DecisionHarness("_diffrn_radiation.probe electron\n")
    checker._absolute_check_value = False
    checker._electron_data = True

    result = checker._apply_absolute_structure_checks(config={"show_warnings": False}, initial_state="")

    assert result is False
    assert checker._zscore_called is False


def test_mismatch_resolution_can_convert_rules_before_checks(tmp_path, monkeypatch):
    rules_path = tmp_path / "rules.cif_rules"
    rules_path.write_text("_cell.length_a 1\n", encoding="utf-8")
    checker = _MismatchHarness("_cell_length_a 1\n", str(rules_path), action="convert_rules")

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)

    result = checker._resolve_rules_cif_notation_mismatch_before_checks()

    assert result is True
    assert checker.field_checker.loaded_name == "Custom"
    assert checker.field_checker.loaded_content == "_cell_length_a 1\n"


def test_mismatch_resolution_can_convert_cif_before_checks(tmp_path, monkeypatch):
    rules_path = tmp_path / "rules.cif_rules"
    rules_path.write_text("_cell.length_a 1\n", encoding="utf-8")
    checker = _MismatchHarness("_cell_length_a 1\n", str(rules_path), action="convert_cif")

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    result = checker._resolve_rules_cif_notation_mismatch_before_checks()

    assert result is True
    assert checker.text_editor.toPlainText() == "_cell.length_a 1"
    assert checker.modified is True
