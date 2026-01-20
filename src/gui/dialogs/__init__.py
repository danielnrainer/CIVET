"""Dialog classes for the CIVET application."""

from .input_dialog import CIFInputDialog
from .multiline_dialog import MultilineInputDialog
from .config_dialog import CheckConfigDialog
from .about_dialog import AboutDialog

# Dialog result codes for consistency
RESULT_ABORT = 2
RESULT_STOP_SAVE = 3

__all__ = [
    'CIFInputDialog',
    'MultilineInputDialog', 
    'CheckConfigDialog',
    'AboutDialog',
    'RESULT_ABORT',
    'RESULT_STOP_SAVE'
]
