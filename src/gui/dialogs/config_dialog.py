"""Configuration dialog for CIF field checking parameters."""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                           QPushButton, QCheckBox, QGroupBox, QMessageBox,
                           QRadioButton)


class CheckConfigDialog(QDialog):
    """Configuration dialog for CIF field checking parameters."""

    def __init__(self, parent=None, block_names=None):
        """
        Args:
            parent: parent widget
            block_names: list of data-block codes (without the 'data_' prefix)
                found in the file. When more than one is given, the dialog
                shows a block-selection group so the user can choose which
                blocks the checks run on (default: all).
        """
        super().__init__(parent)
        self.setWindowTitle("Check Configuration")
        self.setModal(True)
        self.setMinimumWidth(500)

        # Initialize configuration settings
        self.auto_fill_missing = False
        self.skip_matching_defaults = False
        self.reformat_after_checks = False
        self.check_duplicates_aliases = True  # Enabled by default
        self.validate_data_names = True  # Enabled by default - validate against dictionaries
        self.block_names = block_names if block_names and len(block_names) > 1 else None
        self.block_checkboxes = []

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

        # Data-block selection and check mode (only for multi-block files)
        if self.block_names:
            blocks_group = QGroupBox("Data Blocks")
            blocks_layout = QVBoxLayout(blocks_group)

            blocks_label = QLabel(
                "This file contains multiple data blocks. Select which blocks "
                "the checks apply to:"
            )
            blocks_label.setWordWrap(True)
            blocks_layout.addWidget(blocks_label)

            for name in self.block_names:
                checkbox = QCheckBox(f"data_{name}")
                checkbox.setChecked(True)
                blocks_layout.addWidget(checkbox)
                self.block_checkboxes.append((name, checkbox))

            mode_label = QLabel("Check mode:")
            mode_label.setStyleSheet("margin-top: 8px;")
            blocks_layout.addWidget(mode_label)

            self.shared_mode_radio = QRadioButton(
                "Shared (RECOMMENDED): one prompt when all blocks agree on a value;\n"
                "per-block prompts only where values differ (e.g. temperature in a\n"
                "variable-temperature study)"
            )
            self.shared_mode_radio.setChecked(True)
            blocks_layout.addWidget(self.shared_mode_radio)

            self.independent_mode_radio = QRadioButton(
                "Independent: run the full check pass separately for every\n"
                "selected block"
            )
            blocks_layout.addWidget(self.independent_mode_radio)

            layout.addWidget(blocks_group)
        else:
            self.shared_mode_radio = None
            self.independent_mode_radio = None

        # Create pre-check cleanup group
        cleanup_group = QGroupBox("Pre-Check Cleanup")
        cleanup_layout = QVBoxLayout(cleanup_group)

        # Option: Validate data names against dictionaries (ENABLED BY DEFAULT)
        self.validate_data_names_checkbox = QCheckBox(
            "Validate data names against dictionaries (RECOMMENDED)\n"
            "(Fix malformed fields, flag unknown/deprecated fields)"
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

    def accept(self):
        """Validate before accepting: at least one block must be selected."""
        if self.block_checkboxes and not self.get_selected_blocks():
            QMessageBox.warning(
                self,
                "No Data Block Selected",
                "Select at least one data block to run checks on."
            )
            return
        super().accept()

    def get_selected_blocks(self):
        """Return the codes of the checked data blocks (None for single-block files)."""
        if not self.block_checkboxes:
            return None
        return [name for name, checkbox in self.block_checkboxes if checkbox.isChecked()]

    def get_block_mode(self):
        """'shared' or 'independent' for multi-block files, None otherwise."""
        if self.shared_mode_radio is None:
            return None
        return 'shared' if self.shared_mode_radio.isChecked() else 'independent'

    def get_config(self):
        """Get the current configuration settings."""
        return {
            'validate_data_names': self.validate_data_names_checkbox.isChecked(),
            'auto_fill_missing': self.auto_fill_checkbox.isChecked(),
            'skip_matching_defaults': self.skip_defaults_checkbox.isChecked(),
            'reformat_after_checks': self.reformat_checkbox.isChecked(),
            'check_duplicates_aliases': self.check_duplicates_checkbox.isChecked(),
            # None = single-block file (whole document); list = blocks to check
            'selected_blocks': self.get_selected_blocks(),
            # 'shared' (divergence-driven) or 'independent'; None for single-block
            'block_mode': self.get_block_mode()
        }
