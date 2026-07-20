"""Dialog classes for the CIVET application."""

# Dialog result codes — defined before imports so dialog modules can import them
RESULT_ABORT = 2
RESULT_STOP_SAVE = 3

from .input_dialog import CIFInputDialog
from .multiline_dialog import MultilineInputDialog
from .multi_block_value_dialog import MultiBlockValueDialog
from .config_dialog import CheckConfigDialog
from .about_dialog import AboutDialog
from .data_name_validation_dialog import DataNameValidationDialog
from .recognised_prefixes_dialog import RecognisedPrefixesDialog
from .cif_syntax_compliance_dialog import CIFSyntaxComplianceDialog
from .non_ascii_conversion_dialog import NonAsciiConversionDialog
from .dictionary_search_dialog import DictionarySearchDialog

__all__ = [
    'CIFInputDialog',
    'MultilineInputDialog',
    'MultiBlockValueDialog',
    'CheckConfigDialog',
    'AboutDialog',
    'DataNameValidationDialog',
    'RecognisedPrefixesDialog',
    'CIFSyntaxComplianceDialog',
    'NonAsciiConversionDialog',
    'DictionarySearchDialog',
    'RESULT_ABORT',
    'RESULT_STOP_SAVE'
]
