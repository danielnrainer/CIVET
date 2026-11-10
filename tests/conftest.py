"""
pytest configuration file for the CIF_checker test suite.

Adds src/ to sys.path so that ``import utils.xxx`` works.
"""
import sys
import os
import pytest

# Ensure src/ is on the import path for all test modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Match the application default: prefer PySide6, fall back to PyQt6.
os.environ.setdefault("QT_API", "pyside6")


def pytest_configure(config):
	"""Register custom markers used in the test suite."""
	config.addinivalue_line(
		"markers",
		"perf: performance baseline/regression tests (opt-in via CIVET_RUN_PERF_TESTS=1)",
	)
