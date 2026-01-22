"""Configuration dialog for CIF field checking parameters."""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QPushButton, QCheckBox, QGroupBox)


class CheckConfigDialog(QDialog):
    """Configuration dialog for CIF field checking parameters."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Check Configuration")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        # Initialize configuration settings
        self.auto_fill_missing = False
        self.skip_matching_defaults = False
        self.reformat_after_checks = False
        self.check_duplicates_aliases = True  # Enabled by default
        self.fix_malformed_fields = True  # Enabled by default - new option
        self.validate_data_names = True  # Enabled by default - validate against dictionaries
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # Add title and description
        title_label = QLabel("Configure CIF Field Checking")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        description_label = QLabel(
            "Configure how the field checking process should behave:"
        )
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        
        # Create pre-check cleanup group
        cleanup_group = QGroupBox("Pre-Check Cleanup")
        cleanup_layout = QVBoxLayout(cleanup_group)
        
        # Option: Fix malformed field names (ENABLED BY DEFAULT)
        self.fix_malformed_checkbox = QCheckBox(
            "Fix malformed field names (RECOMMENDED)\n"
            "(Correct fields like _diffrn_total_exposure_time → _diffrn.total_exposure_time)"
        )
        self.fix_malformed_checkbox.setChecked(self.fix_malformed_fields)
        self.fix_malformed_checkbox.setStyleSheet("font-weight: bold;")
        cleanup_layout.addWidget(self.fix_malformed_checkbox)
        
        # Option: Validate data names against dictionaries (ENABLED BY DEFAULT)
        self.validate_data_names_checkbox = QCheckBox(
            "Validate data names against dictionaries (RECOMMENDED)\n"
            "(Check all field names are valid, flag unknown/deprecated fields)"
        )
        self.validate_data_names_checkbox.setChecked(self.validate_data_names)
        self.validate_data_names_checkbox.setStyleSheet("font-weight: bold;")
        cleanup_layout.addWidget(self.validate_data_names_checkbox)
        
        layout.addWidget(cleanup_group)
        
        # Create configuration group
        config_group = QGroupBox("Checking Options")
        config_layout = QVBoxLayout(config_group)
        
        # Option 1: Auto-fill missing fields
        self.auto_fill_checkbox = QCheckBox(
            "Automatically fill missing fields with default values\n"
            "(No user prompts for missing fields - they will be added silently)"
        )
        self.auto_fill_checkbox.setChecked(self.auto_fill_missing)
        config_layout.addWidget(self.auto_fill_checkbox)
        
        # Option 2: Skip fields that match defaults
        self.skip_defaults_checkbox = QCheckBox(
            "Skip prompts for fields that already match default values\n"
            "(Fields with correct default values will not prompt for editing)"
        )
        self.skip_defaults_checkbox.setChecked(self.skip_matching_defaults)
        config_layout.addWidget(self.skip_defaults_checkbox)
        
        # Option 3: Reformat file after checks
        self.reformat_checkbox = QCheckBox(
            "Reformat file after checks complete\n"
            "(Automatically reformat CIF file for proper line lengths and formatting)"
        )
        self.reformat_checkbox.setChecked(self.reformat_after_checks)
        config_layout.addWidget(self.reformat_checkbox)
        
        # Option 4: Check for duplicates and aliases (ENABLED BY DEFAULT)
        self.check_duplicates_checkbox = QCheckBox(
            "Check for duplicate and alias fields (RECOMMENDED)\n"
            "(Verify no duplicate field names or conflicting aliases - required for database submission)"
        )
        self.check_duplicates_checkbox.setChecked(self.check_duplicates_aliases)
        self.check_duplicates_checkbox.setStyleSheet("font-weight: bold;")  # Emphasize importance
        config_layout.addWidget(self.check_duplicates_checkbox)
        
        layout.addWidget(config_group)
        
        # Add buttons
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("Start Checks")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        
        layout.addLayout(button_layout)
    
    def get_config(self):
        """Get the current configuration settings."""
        return {
            'fix_malformed_fields': self.fix_malformed_checkbox.isChecked(),
            'validate_data_names': self.validate_data_names_checkbox.isChecked(),
            'auto_fill_missing': self.auto_fill_checkbox.isChecked(),
            'skip_matching_defaults': self.skip_defaults_checkbox.isChecked(),
            'reformat_after_checks': self.reformat_checkbox.isChecked(),
            'check_duplicates_aliases': self.check_duplicates_checkbox.isChecked()
        }
