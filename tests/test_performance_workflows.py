"""Opt-in performance workflow baselines.

These tests intentionally measure end-to-end workflow timings from outside core
modules, so production files do not need embedded instrumentation code.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import time
from pathlib import Path
from typing import Callable, Dict, List

import pytest

from utils.CIF_parser import CIFParser
from utils.cif_data_validator import CIFDataValidator
from utils.cif_dictionary_manager import CIFDictionaryManager
from utils.cif_format_converter import CIFFormatConverter
from utils.data_name_validator import DataNameValidator


pytestmark = pytest.mark.perf

if os.getenv("CIVET_RUN_PERF_TESTS") != "1":
    pytest.skip(
        "Performance workflows are opt-in. Set CIVET_RUN_PERF_TESTS=1 to run.",
        allow_module_level=True,
    )


def _fixture_text(name: str) -> str:
    fixture_path = Path(__file__).parent / "fixtures" / "sample_cifs" / name
    return fixture_path.read_text(encoding="utf-8")


def _percentile(sorted_values: List[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = max(0, min(len(sorted_values) - 1, math.ceil((p / 100.0) * len(sorted_values)) - 1))
    return sorted_values[idx]


def _measure_ms(operation: Callable[[], None], runs: int = 15, warmup: int = 3) -> Dict[str, float]:
    for _ in range(warmup):
        operation()

    samples: List[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - start) * 1000.0)

    sorted_samples = sorted(samples)
    return {
        "runs": float(runs),
        "p50_ms": statistics.median(sorted_samples),
        "p95_ms": _percentile(sorted_samples, 95.0),
        "max_ms": sorted_samples[-1],
    }


def test_collect_workflow_baselines(tmp_path: Path):
    medium_content = _fixture_text("large_template.cif")
    loop_heavy_content = _fixture_text("electron_diffraction_dyn.cif")

    manager = CIFDictionaryManager()
    manager._ensure_loaded()

    converter = CIFFormatConverter(manager)
    data_name_validator = DataNameValidator(manager)

    def notation_detection() -> None:
        manager.detect_notation(medium_content)

    def syntax_detection() -> None:
        manager.detect_syntax_version(medium_content)

    def data_name_validation() -> None:
        data_name_validator.validate_cif_content(medium_content)

    def data_value_validation() -> None:
        parser = CIFParser()
        parser.parse_file(loop_heavy_content)
        CIFDataValidator().validate(parser, manager)

    def modern_conversion() -> None:
        converter.convert_to_modern_notation(medium_content)

    baseline = {
        "detect_notation": _measure_ms(notation_detection),
        "detect_syntax_version": _measure_ms(syntax_detection),
        "validate_data_names": _measure_ms(data_name_validation),
        "validate_data_values": _measure_ms(data_value_validation),
        "convert_to_modern_notation": _measure_ms(modern_conversion),
    }

    baseline_file = tmp_path / "performance-baseline.json"
    baseline_file.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    assert baseline_file.exists()
    for metric_name, metric_values in baseline.items():
        assert metric_values["p50_ms"] >= 0.0, metric_name
        assert metric_values["p95_ms"] >= metric_values["p50_ms"], metric_name
        assert metric_values["max_ms"] >= metric_values["p95_ms"], metric_name
