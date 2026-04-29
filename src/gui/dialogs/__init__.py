"""Dialog classes for the CIVET application."""

# Dialog result codes — defined before imports so dialog modules can import them
RESULT_ABORT = 2
RESULT_STOP_SAVE = 3

from .input_dialog import CIFInputDialog
from .multiline_dialog import MultilineInputDialog
from .config_dialog import CheckConfigDialog
from .about_dialog import AboutDialog
from .data_name_validation_dialog import DataNameValidationDialog
from .recognised_prefixes_dialog import RecognisedPrefixesDialog

__all__ = [
    'CIFInputDialog',
    'MultilineInputDialog', 
    'CheckConfigDialog',
    'AboutDialog',
    'DataNameValidationDialog',
    'RecognisedPrefixesDialog',
    'RESULT_ABORT',
    'RESULT_STOP_SAVE'
]
