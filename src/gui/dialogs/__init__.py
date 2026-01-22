"""Dialog classes for the CIVET application."""

from .input_dialog import CIFInputDialog
from .multiline_dialog import MultilineInputDialog
from .config_dialog import CheckConfigDialog
from .about_dialog import AboutDialog
from .data_name_validation_dialog import DataNameValidationDialog
from .recognised_prefixes_dialog import RecognisedPrefixesDialog

# Dialog result codes for consistency
RESULT_ABORT = 2
RESULT_STOP_SAVE = 3

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
