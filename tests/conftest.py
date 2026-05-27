"""
pytest configuration file for the CIF_checker test suite.

Adds src/ to sys.path so that ``import utils.xxx`` works.
"""
import sys
import os

# Ensure src/ is on the import path for all test modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
