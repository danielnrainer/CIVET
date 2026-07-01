"""Generate external performance baselines for core CIVET workflows.

Usage:
    python tests/performance/performance_baseline.py
    python tests/performance/performance_baseline.py --runs 25 --warmup 5 --output tests/performance/baseline-latest.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.CIF_parser import CIFParser
from utils.cif_data_validator import CIFDataValidator
from utils.cif_dictionary_manager import CIFDictionaryManager
from utils.cif_format_converter import CIFFormatConverter
from utils.data_name_validator import DataNameValidator


def _fixture_text(name: str) -> str:
    fixture_path = REPO_ROOT / "tests" / "fixtures" / "sample_cifs" / name
    return fixture_path.read_text(encoding="utf-8")


def _percentile(sorted_values: List[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = max(0, min(len(sorted_values) - 1, math.ceil((p / 100.0) * len(sorted_values)) - 1))
    return sorted_values[idx]


def _measure_ms(operation: Callable[[], None], runs: int, warmup: int) -> Dict[str, float]:
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


def build_baseline(runs: int, warmup: int) -> Dict[str, Dict[str, float]]:
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

    return {
        "detect_notation": _measure_ms(notation_detection, runs=runs, warmup=warmup),
        "detect_syntax_version": _measure_ms(syntax_detection, runs=runs, warmup=warmup),
        "validate_data_names": _measure_ms(data_name_validation, runs=runs, warmup=warmup),
        "validate_data_values": _measure_ms(data_value_validation, runs=runs, warmup=warmup),
        "convert_to_modern_notation": _measure_ms(modern_conversion, runs=runs, warmup=warmup),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate workflow performance baselines for CIVET.")
    parser.add_argument("--runs", type=int, default=15, help="Timed runs per workflow")
    parser.add_argument("--warmup", type=int, default=3, help="Warmup runs per workflow")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "tests" / "performance" / "baseline-latest.json",
        help="Output JSON file path",
    )
    args = parser.parse_args()

    baseline = build_baseline(runs=args.runs, warmup=args.warmup)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    print(f"Wrote baseline to: {args.output}")
    print(json.dumps(baseline, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
