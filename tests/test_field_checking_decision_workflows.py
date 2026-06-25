"""Behavior-focused tests for field-checking decision workflows."""

from gui.field_checking import FieldCheckingMixin
from utils.cif_dictionary_manager import FieldNotation


class _DummyTextEditor:
    def __init__(self, text: str):
        self._text = text

    def toPlainText(self):
        return self._text


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
