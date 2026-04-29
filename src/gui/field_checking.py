"""
Field checking workflow mixin for CIFEditor.

This module contains the FieldCheckingMixin class which provides all field
checking, validation, and duplicate/alias resolution methods. It is designed
to be used as a mixin with the CIFEditor class in main_window.py.

Methods in this mixin access CIFEditor instance attributes (self.text_editor,
self.dict_manager, self.cif_parser, self.field_checker, etc.) and call
CIFEditor methods that remain in main_window.py (extract_field_value,
update_field_value, _show_dialog_with_configured_interaction, etc.).
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple, TYPE_CHECKING

from PyQt6.QtWidgets import QDialog, QMessageBox

from utils.CIF_field_parsing import safe_eval_expr
from utils.CIF_parser import CIFField, update_audit_creation_method
from utils.cif_dictionary_manager import FieldNotation
from .dialogs import (CIFInputDialog, MultilineInputDialog, CheckConfigDialog,
                      RESULT_ABORT, RESULT_STOP_SAVE)
from .dialogs.data_name_validation_dialog import DataNameValidationDialog
from .dialogs.field_conflict_dialog import FieldConflictDialog
from .dialogs.critical_issues_dialog import CriticalIssuesDialog

if TYPE_CHECKING:
    from .main_window import CIFEditor


class FieldCheckingMixin:
    """Mixin providing field checking workflow methods for CIFEditor."""

    def check_line(self, prefix, default_value=None, multiline=False, description="", suggestions=None):
        """Check and potentially update a CIF field value."""
        removable_chars = "'"
        lines = self.text_editor.toPlainText().splitlines()
        
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                current_value = self.extract_field_value(lines, i, prefix)
                
                # Determine operation type based on whether value differs from default
                operation_type = "edit"
                if default_value:
                    # Clean both values for comparison
                    clean_current = current_value.strip().strip("'\"")
                    clean_default = str(default_value).strip().strip("'\"")
                    if clean_current and clean_current != clean_default:
                        operation_type = "different"
                
                value, result = CIFInputDialog.getText(
                    self, "Edit Line",
                    f"Edit the line:\n{line}\n\nDescription: {description}\n\nSuggested value: {default_value}\n\n",
                    current_value, default_value, operation_type=operation_type, suggestions=suggestions)
                
                if result in [RESULT_ABORT, RESULT_STOP_SAVE]:
                    return result
                elif result == QDialog.DialogCode.Accepted and value:
                    # Update the field value properly
                    self.update_field_value(lines, i, prefix, value)
                    self.text_editor.setText("\n".join(lines))
                return result

        QMessageBox.warning(self, "Line Not Found",
                          f"The line starting with '{prefix}' was not found.")
        return self.add_missing_line(prefix, lines, default_value, multiline, description, suggestions)

    def add_missing_line(self, prefix, lines, default_value=None, multiline=False, description="", suggestions=None):
        """Add a missing CIF field with value."""
        value, result = CIFInputDialog.getText(
            self, "Add Missing Line",
            f"The line starting with '{prefix}' is missing.\n\nDescription: {description}\nSuggested value: {default_value}",
            default_value if default_value else "", default_value, operation_type="add", suggestions=suggestions)
        
        if result in [RESULT_ABORT, RESULT_STOP_SAVE]:
            return result
            
        removable_chars = "'"
        if result != QDialog.DialogCode.Accepted:
            return result
            
        if not value:
            value = "?"

        stripped_value = value.strip(removable_chars)
        if multiline:
            insert_index = len(lines)
            for i, line in enumerate(lines):
                if line.startswith(prefix.split("_")[0]):
                    insert_index = i + 1
            lines.insert(insert_index, 
                        f"{prefix} \n;\n{stripped_value}\n;")
        else:
            # Only quote if value has spaces or special chars
            if ' ' in stripped_value or ',' in stripped_value:
                formatted_value = f"'{stripped_value}'"
            else:
                formatted_value = stripped_value
            lines.append(f"{prefix} {formatted_value}")
        
        self.text_editor.setText("\n".join(lines))
        return result    
    
    def check_line_with_config(self, prefix, default_value=None, multiline=False, description="", config=None, suggestions=None):
        """Check and potentially update a CIF field value with configuration options."""
        if config is None:
            config = {'auto_fill_missing': False, 'skip_matching_defaults': False}
        
        # Check if this field is deprecated
        if self.dict_manager.is_field_deprecated(prefix):
            modern_equivalent = self.dict_manager.get_modern_equivalent(prefix, prefer_format="legacy")
            if modern_equivalent:
                # Add modern equivalent alongside deprecated field (keep both with same value)
                # Per expert advice: both deprecated and modern fields should coexist
                return self._add_modern_equivalent_field(prefix, modern_equivalent)
            else:
                # No modern equivalent available
                # For legacy CIF files, deprecated fields are expected and valid - skip warning
                # Only warn for modern CIF files where deprecated fields are unexpected
                content = self.text_editor.toPlainText()
                cif_format = self.dict_manager.detect_cif_format(content)
                
                if cif_format != "legacy":
                    # Show warning only for modern CIF files
                    QMessageBox.information(
                        self,
                        "Deprecated Field Notice", 
                        f"The field '{prefix}' is deprecated and has no modern equivalent.\n\n"
                        f"It will be processed as-is, but consider reviewing this field.",
                        QMessageBox.StandardButton.Ok
                    )
        
        removable_chars = "'"
        lines = self.text_editor.toPlainText().splitlines()
        
        # Check if field exists
        field_found = False
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                field_found = True
                current_value = self.extract_field_value(lines, i, prefix).strip(removable_chars)
                
                # If skip_matching_defaults is enabled and current value matches default
                if config.get('skip_matching_defaults', False) and default_value:
                    # Clean both values for comparison
                    clean_current = current_value.strip().strip("'\"")
                    clean_default = str(default_value).strip().strip("'\"")
                    if clean_current == clean_default:
                        return QDialog.DialogCode.Accepted  # Skip this field
                
                # Show normal edit dialog
                # Determine operation type based on whether value differs from default
                operation_type = "edit"
                if default_value:
                    # Clean both values for comparison
                    clean_current = current_value.strip().strip("'\"")
                    clean_default = str(default_value).strip().strip("'\"")
                    if clean_current and clean_current != clean_default:
                        operation_type = "different"
                
                value, result = CIFInputDialog.getText(
                    self, "Edit Line",
                    f"Edit the line:\n{line}\n\nDescription: {description}\n\nSuggested value: {default_value}\n\n",
                    current_value, default_value, operation_type=operation_type, suggestions=suggestions)
                
                if result in [RESULT_ABORT, RESULT_STOP_SAVE]:
                    return result
                elif result == QDialog.DialogCode.Accepted and value:
                    # Update the field value properly
                    self.update_field_value(lines, i, prefix, value)
                    self.text_editor.setText("\n".join(lines))
                return result
        
        # Field not found - handle missing field
        if not field_found:
            return self.add_missing_line_with_config(prefix, lines, default_value, multiline, description, config, suggestions)
        
        return QDialog.DialogCode.Accepted
    
    def add_missing_line_with_config(self, prefix, lines, default_value=None, multiline=False, description="", config=None, suggestions=None):
        """Add a missing CIF field with value, respecting configuration options."""
        if config is None:
            config = {'auto_fill_missing': False, 'skip_matching_defaults': False}
        
        # If auto_fill_missing is enabled, add the field silently with default value
        if config.get('auto_fill_missing', False) and default_value:
            removable_chars = "'"
            stripped_value = str(default_value).strip(removable_chars)
            
            if multiline:
                insert_index = len(lines)
                for i, line in enumerate(lines):
                    if line.startswith(prefix.split("_")[0]):
                        insert_index = i + 1
                lines.insert(insert_index, 
                            f"{prefix} \n;\n{stripped_value}\n;")
            else:
                # Only quote if value has spaces or special chars
                if ' ' in stripped_value or ',' in stripped_value:
                    formatted_value = f"'{stripped_value}'"
                else:
                    formatted_value = stripped_value
                lines.append(f"{prefix} {formatted_value}")
            
            self.text_editor.setText("\n".join(lines))
            return QDialog.DialogCode.Accepted
        
        # Otherwise, use the normal missing line dialog
        return self.add_missing_line(prefix, lines, default_value, multiline, description, suggestions)
    
    def _add_modern_equivalent_field(self, deprecated_field: str, modern_field: str):
        """
        Add the modern equivalent field alongside a deprecated field.
        
        Per expert advice, both the deprecated field AND its modern equivalent should
        exist in the CIF with the same value. This ensures compatibility with both
        legacy tools (that expect deprecated names) and modern tools (that expect
        new names).
        
        Args:
            deprecated_field: The deprecated field name (kept in place)
            modern_field: The modern equivalent field name (added if not present)
            
        Returns:
            QDialog.DialogCode.Accepted if successful, Rejected otherwise
        """
        content = self.text_editor.toPlainText()
        
        # Parse the CIF content using the CIF parser
        self.cif_parser.parse_file(content)
        
        # Check if the deprecated field exists
        if deprecated_field not in self.cif_parser.fields:
            QMessageBox.warning(
                self, 
                "Field Not Found", 
                f"Could not find deprecated field '{deprecated_field}'"
            )
            return QDialog.DialogCode.Rejected
        
        # Check if modern field already exists
        if modern_field in self.cif_parser.fields:
            QMessageBox.information(
                self, 
                "Already Present", 
                f"The modern equivalent '{modern_field}' is already present in the CIF.\n\n"
                f"Both the deprecated field '{deprecated_field}' and its modern equivalent exist."
            )
            return QDialog.DialogCode.Accepted
        
        # Get the current value of the deprecated field
        deprecated_field_obj = self.cif_parser.fields[deprecated_field]
        field_value = deprecated_field_obj.value
        
        # Create the modern field with the same value
        modern_field_obj = CIFField(
            name=modern_field,
            value=field_value,
            is_multiline=deprecated_field_obj.is_multiline,
            line_number=None,  # Will be placed after the deprecated field
            raw_lines=[]
        )
        
        # Add the modern field to the parser's fields
        self.cif_parser.fields[modern_field] = modern_field_obj
        
        # Find the deprecated field in content_blocks and insert modern field after it
        for i, block in enumerate(self.cif_parser.content_blocks):
            if block['type'] == 'field' and hasattr(block['content'], 'name') and block['content'].name == deprecated_field:
                # Insert the modern field block right after the deprecated field
                new_block = {
                    'type': 'field',
                    'content': modern_field_obj
                }
                self.cif_parser.content_blocks.insert(i + 1, new_block)
                break
        
        # Generate updated CIF content and update the text editor
        updated_content = self.cif_parser.generate_cif_content()
        self.text_editor.setText(updated_content)
        
        QMessageBox.information(
            self, 
            "Modern Field Added", 
            f"Added modern equivalent '{modern_field}' with the same value as '{deprecated_field}'.\n\n"
            f"Both fields now exist in the CIF for maximum compatibility."
        )
        return QDialog.DialogCode.Accepted
    
    def check_refine_special_details(self):
        """Check and edit _refine_special_details field, creating it if needed."""
        content = self.text_editor.toPlainText()
        
        # Parse the CIF content using the new parser
        self.cif_parser.parse_file(content)
        
        # Detect field notation to determine the correct field name
        detected_version = self.dict_manager.detect_notation(content)
        
        # Determine the appropriate field name based on notation
        if detected_version == FieldNotation.MODERN:
            field_name = '_refine.special_details'
        elif detected_version == FieldNotation.MIXED:
            # For MIXED format, check which field actually exists in the content
            if self.cif_parser.get_field_value('_refine.special_details') is not None:
                field_name = '_refine.special_details'
            elif self.cif_parser.get_field_value('_refine_special_details') is not None:
                field_name = '_refine_special_details'
            else:
                # Neither exists, so decide based on the predominant format
                # Check if this looks more like modern format by counting modern vs legacy fields
                all_fields = list(self.cif_parser.fields.keys())
                modern_fields = [f for f in all_fields if '.' in f]
                legacy_fields = [f for f in all_fields if '.' not in f]
                
                # If more modern fields, use modern naming
                if len(modern_fields) >= len(legacy_fields):
                    field_name = '_refine.special_details'
                else:
                    field_name = '_refine_special_details'
        else:
            # Default to legacy format (covers legacy, UNKNOWN)
            field_name = '_refine_special_details'
        
        template = (
            "STRUCTURE REFINEMENT\n"
            "- Refinement method\n"
            "- Special constraints and restraints\n"
            "- Special treatments"
        )
        
        # Get current value from the appropriate field name, or use template
        current_value = self.cif_parser.get_field_value(field_name)
        if current_value is None:
            current_value = template
        
        # Open dialog for editing
        dialog = MultilineInputDialog(current_value, self)
        dialog.setWindowTitle("Edit Refinement Special Details")
        result = self._show_dialog_with_configured_interaction(dialog)
        
        if result in [RESULT_ABORT, RESULT_STOP_SAVE]:
            return result
        elif result == QDialog.DialogCode.Accepted:
            updated_content = dialog.getText()
            
            # Update the field in the parser using the appropriate field name
            self.cif_parser.set_field_value(field_name, updated_content)
            
            # Generate updated CIF content and update the text editor
            updated_cif = self.cif_parser.generate_cif_content()
            self.text_editor.setText(updated_cif)
            self.modified = True
            self.update_status_bar()
            
            return QDialog.DialogCode.Accepted
        
        return QDialog.DialogCode.Rejected

    def start_checks(self):
        """Start checking CIF fields using the selected field definition set."""
        # Validate field set selection
        if self.radio_user.isChecked():
            if not self.current_field_set or not self.current_field_set.startswith('User:'):
                QMessageBox.warning(
                    self,
                    "No User Rules Selected",
                    "No user-defined field rules are loaded.\n\n"
                    "Please add .cif_rules files to your CIVET config directory "
                    "(Settings \u2192 Open Config Directory) and click the \u21bb refresh button."
                )
                return
        elif self.current_field_set == 'Custom':
            if not self.custom_field_rules_file:
                QMessageBox.warning(
                    self,
                    "No Custom File Selected",
                    "Please select a custom field definition file first."
                )
                return
            
            # Check if custom field set is loaded
            fields = self.field_checker.get_field_set('Custom')
            if not fields:
                QMessageBox.warning(
                    self,
                    "Custom File Not Loaded",
                    "The custom field definition file could not be loaded. "
                    "Please select a valid file."
                )
                return
        
        # Mandatory validation before starting checks (if not done already)
        if not self._ensure_field_rules_validated():
            return  # User cancelled or validation failed
        
        # Show configuration dialog first
        config_dialog = CheckConfigDialog(self)
        if self._show_dialog_with_configured_interaction(config_dialog) != QDialog.DialogCode.Accepted:
            return  # User cancelled
        
        # Get configuration settings
        config = config_dialog.get_config()
        
        # Store the initial state for potential restore
        initial_state = self.text_editor.toPlainText()
        
        # PRE-CHECK: Validate data names against dictionaries (if enabled)
        # This now includes malformed field detection (e.g. _diffrn_flux_density → _diffrn.flux_density)
        if config.get('validate_data_names', True):
            validation_success = self._validate_data_names_before_checks()
            if not validation_success:
                return  # User cancelled or aborted
        
        # Single field set processing
        success = self._process_single_field_set(config, initial_state)
        if not success:
            return
        
        # Check for duplicates and aliases LAST (if enabled)
        if config.get('check_duplicates_aliases', True):
            duplicate_check_success = self._check_duplicates_and_aliases(initial_state)
            if not duplicate_check_success:
                return  # User aborted or there was an error
        
        # Update _audit_creation_method to include CIVET info after successful checks
        content = self.text_editor.toPlainText()
        cif_format = self.dict_manager.detect_cif_format(content)
        updated_content = update_audit_creation_method(content, cif_format)
        if updated_content != content:
            self.text_editor.setText(updated_content)
            self.modified = True
        
        # If we get here, checks completed successfully
        if config.get('reformat_after_checks', False):
            self.reformat_file()
        
        self.update_window_title()
        QMessageBox.information(self, "Checks Complete", "Field checking completed successfully!")

    def _validate_data_names_before_checks(self) -> bool:
        """
        Validate all data names against dictionaries before running field checks.
        
        Shows the validation dialog if there are unknown or deprecated fields.
        
        Returns:
            True if processing completed (validation passed or user accepted),
            False if user explicitly cancelled
        """
        try:
            content = self.text_editor.toPlainText()
            if not content.strip():
                return True  # No content, continue
            
            # Clear validator cache and run validation
            self.data_name_validator.clear_cache()
            report = self.data_name_validator.validate_cif_content(content)
            
            # Check if there are any issues to report
            has_issues = (len(report.unknown_fields) > 0 or 
                         len(report.deprecated_fields) > 0 or
                         len(report.malformed_fields) > 0)
            
            if not has_issues:
                return True  # All fields valid, continue
            
            # Build a quick summary
            issues = []
            if report.malformed_fields:
                issues.append(f"{len(report.malformed_fields)} malformed field name(s)")
            if report.unknown_fields:
                issues.append(f"{len(report.unknown_fields)} unknown field(s)")
            if report.deprecated_fields:
                issues.append(f"{len(report.deprecated_fields)} deprecated field(s)")
            
            # Ask user if they want to review
            reply = QMessageBox.question(
                self,
                "Data Name Validation",
                f"Found {', '.join(issues)} in the CIF file.\n\n"
                "Would you like to review and resolve these before continuing with checks?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Cancel:
                return False  # User cancelled the entire operation
            
            if reply == QMessageBox.StandardButton.No:
                return True  # User chose to skip validation, continue with checks
            
            # Show the full validation dialog
            dialog = DataNameValidationDialog(report, self.data_name_validator, self)
            
            # Connect the changes_requested signal to apply actions and refresh
            def on_changes_requested():
                self._apply_validation_actions(dialog)
                # Clear cache and re-run validation
                self.data_name_validator.clear_cache()
                new_content = self.text_editor.toPlainText()
                new_report = self.data_name_validator.validate_cif_content(new_content)
                dialog.refresh_validation(new_report)
            
            dialog.changes_requested.connect(on_changes_requested)
            
            # Show dialog with configured editor interaction behavior.
            self._show_dialog_with_configured_interaction(
                dialog,
                "dialogs.data_name_validation_results_mode"
            )
            
            # If changes were applied, do final cleanup
            if dialog.has_changes_applied():
                self.data_name_validator.clear_cache()
            
            return True  # Continue with checks
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Data Name Validation Error",
                f"An error occurred during data name validation:\n{str(e)}\n\n"
                "Continuing with field checks..."
            )
            return True  # Continue despite error

    def _fix_malformed_fields_before_checks(self) -> bool:
        """
        Check for and fix malformed field names before running field checks.
        
        Returns:
            True if processing completed (fixes applied or none needed),
            False if user explicitly cancelled
        """
        try:
            content = self.text_editor.toPlainText()
            malformed = self.dict_manager.find_malformed_fields(content)
            
            if not malformed:
                return True  # No malformed fields, continue
            
            # Build summary
            summary = f"Found {len(malformed)} malformed field name(s) that should be fixed:\n\n"
            for item in malformed[:5]:  # Show first 5
                summary += f"• {item['original']} → {item['suggested']}\n"
            if len(malformed) > 5:
                summary += f"• ... and {len(malformed) - 5} more\n"
            
            summary += "\nThese fields use incorrect underscore-only format. "
            summary += "Fixing them will prevent duplicates when the correct fields are added during checks.\n\n"
            summary += "Would you like to fix these field names now?"
            
            reply = QMessageBox.question(
                self,
                "Fix Malformed Field Names",
                summary,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Cancel:
                return False  # User cancelled the entire operation
            
            if reply == QMessageBox.StandardButton.Yes:
                fixed_content, changes = self.dict_manager.fix_malformed_fields_in_content(content, malformed)
                if changes:
                    self.text_editor.setText(fixed_content)
                    self.modified = True
            
            return True  # Continue with checks (whether fixed or not)
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Malformed Field Check Error",
                f"An error occurred while checking for malformed fields:\n{str(e)}\n\n"
                "Continuing with field checks..."
            )
            return True  # Continue despite error

    def _process_single_field_set(self, config, initial_state):
        """Process a single field set (Built-in, User, or Custom)."""
        try:
            # Auto-switch to the paired legacy variant when the loaded CIF uses
            # legacy format and the selected built-in rule set has a paired
            # legacy variant registered (stored in the combo item data).
            # This is data-driven: any rules file whose stem has a sibling
            # ``{stem}_legacy.cif_rules`` qualifies — no name matching needed.
            item_data = self.builtin_combo.currentData() if self.radio_builtin.isChecked() else None
            legacy_path = item_data.get('legacy_path') if item_data else None

            if legacy_path and self.radio_builtin.isChecked():
                content = self.text_editor.toPlainText()
                cif_format = self.dict_manager.detect_cif_format(content)
                if cif_format.upper() == 'LEGACY':
                    self.field_checker.load_field_set(self.current_field_set, legacy_path)
                    QMessageBox.information(
                        self,
                        "CIF Format Compatibility",
                        "Detected legacy format. Automatically switched to the "
                        "legacy-compatible variant of the selected field rules."
                    )
                else:
                    # Reload the primary (modern) variant in case a previous run
                    # had switched to legacy.
                    primary_path = item_data.get('path', '')
                    if primary_path:
                        self.field_checker.load_field_set(self.current_field_set, primary_path)
            
            # Get the selected field set
            fields = self.field_checker.get_field_set(self.current_field_set)
            if not fields:
                QMessageBox.warning(self, "Warning", f"No {self.current_field_set} field definitions loaded.")
                return False
            
            # Update window title to show which field set is being used
            if self.current_field_set.startswith('User:'):
                field_set_display_name = self.current_field_set
            elif self.current_field_set == 'Custom':
                field_set_display_name = f'Custom ({os.path.basename(self.custom_field_rules_file) if self.custom_field_rules_file else "Unknown"})'
            else:
                # Built-in rules - use the internal name or make it human-readable
                field_set_display_name = self.current_field_set.replace('_', ' ')
            
            # Include filename in title during checking
            filename_part = f" {os.path.basename(self.current_file)}" if self.current_file else ""
            self.setWindowTitle(f"CIVET{filename_part} - Checking with {field_set_display_name} fields")
            
            # Parse the current CIF content
            content = self.text_editor.toPlainText()
            self.cif_parser.parse_file(content)
            
            # For custom or user sets, handle DELETE/EDIT/APPEND operations first
            is_custom_or_user = self.current_field_set == 'Custom' or self.current_field_set.startswith('User:')
            if is_custom_or_user:
                current_content = content
                operations_applied = []
                
                for field_def in fields:
                    if hasattr(field_def, 'action'):
                        if field_def.action == 'DELETE':
                            lines = current_content.splitlines()
                            lines, deleted = self.field_checker._delete_field(lines, field_def.name)
                            if deleted:
                                operations_applied.append(f"DELETED: {field_def.name}")
                                current_content = '\n'.join(lines)
                        elif field_def.action == 'EDIT':
                            lines = current_content.splitlines()
                            lines, edited = self.field_checker._edit_field(lines, field_def.name, field_def.default_value)
                            if edited:
                                operations_applied.append(f"EDITED: {field_def.name} → {field_def.default_value}")
                                current_content = '\n'.join(lines)
                        elif field_def.action == 'APPEND':
                            lines = current_content.splitlines()
                            lines, appended = self.field_checker._append_field(lines, field_def.name, field_def.default_value)
                            if appended:
                                operations_applied.append(f"APPENDED to {field_def.name}")
                                current_content = '\n'.join(lines)
                        elif field_def.action == 'RENAME':
                            lines = current_content.splitlines()
                            lines, renamed = self.field_checker._rename_field(lines, field_def.name, field_def.rename_to)
                            if renamed:
                                operations_applied.append(f"RENAMED: {field_def.name} → {field_def.rename_to}")
                                current_content = '\n'.join(lines)
                
                # Update content after DELETE/EDIT/APPEND/RENAME operations
                if operations_applied:
                    self.text_editor.setText(current_content)
                    ops_summary = '\n'.join(operations_applied)
                    QMessageBox.information(self, "Operations Applied", 
                                          f"Applied {len(operations_applied)} operations:\n\n{ops_summary}")
            
            # Process CHECK and CALCULATE actions (standard field checking)
            for field_def in fields:
                # Skip DELETE/EDIT/APPEND/RENAME actions as they're already processed
                if hasattr(field_def, 'action') and field_def.action in ['DELETE', 'EDIT', 'APPEND', 'RENAME']:
                    continue
                
                # For CALCULATE action, compute the suggested value from expression
                suggested_value = field_def.default_value
                description = field_def.description
                suggestions = getattr(field_def, 'suggestions', None)
                
                if hasattr(field_def, 'action') and field_def.action == 'CALCULATE' and hasattr(field_def, 'expression'):
                    # Re-parse CIF to get current values (content may have changed)
                    current_content = self.text_editor.toPlainText()
                    self.cif_parser.parse_file(current_content)
                    
                    # Extract field references from expression
                    field_refs = re.findall(r'_[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)*', field_def.expression)
                    field_values = {}
                    missing_fields = []
                    
                    for ref in field_refs:
                        value = self.cif_parser.get_field_value(ref)
                        if value is not None:
                            # Try to convert to number
                            try:
                                # Handle values with uncertainties like "1.234(5)"
                                clean_value = re.sub(r'\([^)]*\)', '', str(value))
                                field_values[ref] = float(clean_value)
                            except (ValueError, TypeError):
                                missing_fields.append(f"{ref} (non-numeric: {value})")
                        else:
                            missing_fields.append(ref)
                    
                    if missing_fields:
                        # Can't calculate - skip this field with warning
                        if config.get('show_warnings', True):
                            QMessageBox.warning(self, "CALCULATE Warning",
                                f"Cannot calculate {field_def.name}:\n"
                                f"Missing or non-numeric fields: {', '.join(missing_fields)}\n\n"
                                f"Expression: {field_def.expression}")
                        continue
                    
                    # Evaluate the expression
                    calculated = safe_eval_expr(field_def.expression, field_values)
                    if calculated is not None:
                        # Format to reasonable precision
                        if abs(calculated) < 0.01 or abs(calculated) >= 10000:
                            suggested_value = f"{calculated:.4e}"
                        else:
                            suggested_value = f"{calculated:.4f}".rstrip('0').rstrip('.')
                        
                        # Add calculation info to description
                        current_val = self.cif_parser.get_field_value(field_def.name)
                        description = (f"{field_def.description}\n" if field_def.description else "") + \
                                     f"Calculated: {field_def.expression}"
                        if current_val:
                            description += f"\nCurrent value: {current_val}"
                        
                        # Add current value as an option in suggestions
                        if current_val:
                            suggestions = [suggested_value]
                            if str(current_val) != suggested_value:
                                suggestions.append(str(current_val))
                    else:
                        if config.get('show_warnings', True):
                            QMessageBox.warning(self, "CALCULATE Warning",
                                f"Failed to evaluate expression for {field_def.name}:\n"
                                f"{field_def.expression}")
                        continue
                    
                result = self.check_line_with_config(
                    field_def.name,
                    suggested_value,
                    False,
                    description,
                    config,
                    suggestions
                )
                
                if result == RESULT_ABORT:
                    self.text_editor.setText(initial_state)
                    self.update_window_title()
                    QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                    return False
                elif result == RESULT_STOP_SAVE:
                    break
            
            # Apply special 3DED handling if needed
            is_3ded = '3D_ED' in self.current_field_set or '3DED' in self.current_field_set
            if is_3ded:
                self._apply_3ded_special_checks(config, initial_state)
            
            return True
            
        except Exception as e:
            self.text_editor.setText(initial_state)
            self.update_window_title()
            QMessageBox.critical(self, "Error During Checks", f"An error occurred: {str(e)}")
            return False
    
    def _apply_3ded_special_checks(self, config, initial_state):
        """Apply special 3DED checks for space groups and absolute configuration."""
        sohncke_groups = [1, 3, 4, 5, 16, 17, 18, 19, 20, 21, 22, 23, 24, 75, 76, 77, 78, 79, 80, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 143, 144, 145, 146, 149, 150, 151, 152, 153, 154, 155, 168, 169, 170, 171, 172, 173, 177, 178, 179, 180, 181, 182, 195, 196, 197, 198, 199, 207, 208, 209, 210, 211, 212, 213, 214]
        SG_number = None
        lines = self.text_editor.toPlainText().splitlines()
        
        # Find space group number
        for line in lines:
            if line.startswith("_space_group_IT_number"):
                parts = line.split()
                if len(parts) > 1:
                    try:
                        SG_number = int(parts[1].strip("'\""))
                    except Exception:
                        pass
                break
        
        # Check if we need absolute configuration handling
        if SG_number is not None and SG_number in sohncke_groups:
            # Detect field notation to use appropriate field names
            content = self.text_editor.toPlainText()
            detected_version = self.dict_manager.detect_notation(content)
            
            # Determine field names based on notation
            if detected_version == FieldNotation.MODERN:
                abs_config_field = "_chemical.absolute_configuration"
                z_score_field = "_refine_ls.abs_structure_z-score"
            else:
                # Use legacy format for legacy, MIXED, and UNKNOWN
                abs_config_field = "_chemical_absolute_configuration"
                z_score_field = "_refine_ls.abs_structure_z-score"
            
            found = False
            for line in lines:
                if line.startswith(abs_config_field):
                    found = True
                    break
            
            if found:
                result = self.check_line_with_config(
                    abs_config_field, 
                    default_value='dyn', 
                    multiline=False, 
                    description="Specify if/how absolute structure was determined.", 
                    config=config
                )
                if result == RESULT_ABORT:
                    self.text_editor.setText(initial_state)
                    self.update_window_title()
                    QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                    return False
                elif result == RESULT_STOP_SAVE:
                    return True
            else:
                result = self.add_missing_line_with_config(
                    abs_config_field, 
                    lines, 
                    default_value='dyn', 
                    multiline=False, 
                    description="Specify if/how absolute structure was determined.", 
                    config=config
                )
                if result == RESULT_ABORT:
                    self.text_editor.setText(initial_state)
                    self.update_window_title()
                    QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                    return False
                elif result == RESULT_STOP_SAVE:
                    return True
            
            # Check for z-score if configuration is 'dyn'
            lines = self.text_editor.toPlainText().splitlines()  # Re-get lines after potential changes
            chemical_absolute_config_value = None
            for line in lines:
                if line.startswith(abs_config_field):
                    parts = line.split()
                    if len(parts) > 1:
                        chemical_absolute_config_value = parts[1].strip("'\"")
                        break
            
            if chemical_absolute_config_value == 'dyn':
                # Check if z-score field exists
                found_z_score = False
                for line in lines:
                    if line.startswith(z_score_field):
                        found_z_score = True
                        break
                
                if found_z_score:
                    result = self.check_line_with_config(
                        z_score_field, 
                        default_value='', 
                        multiline=False, 
                        description="Z-score for absolute structure determination from dynamical refinement.", 
                        config=config
                    )
                    if result == RESULT_ABORT:
                        self.text_editor.setText(initial_state)
                        self.update_window_title()
                        QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                        return False
                    elif result == RESULT_STOP_SAVE:
                        return True
                else:
                    result = self.add_missing_line_with_config(
                        z_score_field, 
                        lines, 
                        default_value='', 
                        multiline=False, 
                        description="Z-score for absolute structure determination from dynamical refinement.", 
                        config=config
                    )
                    if result == RESULT_ABORT:
                        self.text_editor.setText(initial_state)
                        self.update_window_title()
                        QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                        return False
                    elif result == RESULT_STOP_SAVE:
                        return True
        
        return True

    def _check_duplicates_and_aliases(self, initial_state: str) -> bool:
        """
        Check for duplicate field names, alias conflicts, and deprecated fields.
        This should be called at the END of the checking procedure.
        
        Args:
            initial_state: Initial CIF content for potential restore
            
        Returns:
            True if check passed or conflicts were resolved, False if user aborted
        """
        try:
            content = self.text_editor.toPlainText()
            
            # Detect CIF format to determine if we should check for deprecated fields
            cif_format = self.dict_manager.detect_cif_format(content)
            is_legacy = cif_format.lower() == 'legacy'
            
            # Check for duplicates and aliases first
            conflicts = self.dict_manager.detect_field_aliases_in_cif(content)
            
            # Check for deprecated fields (skip for legacy CIFs as they're expected to be outdated)
            deprecated_fields = []
            if not is_legacy:
                lines = content.splitlines()
                
                for line_num, line in enumerate(lines, 1):
                    line_stripped = line.strip()
                    if line_stripped.startswith('_') and ' ' in line_stripped:
                        field_name = line_stripped.split()[0]
                        if self.dict_manager.is_field_deprecated(field_name):
                            # Skip if this field is already in a deprecated section
                            # (we don't want to flag fields we already moved to deprecated sections)
                            if not self._is_in_deprecated_section(content, line_num):
                                modern_equiv = self.dict_manager.get_modern_equivalent(field_name, prefer_format="LEGACY")
                                deprecated_fields.append({
                                    'field': field_name,
                                    'line_num': line_num,
                                    'line': line_stripped,
                                    'modern': modern_equiv
                                })
            
            # Filter conflicts to exclude those between main section and deprecated section
            lines = content.splitlines()
            filtered_conflicts = {}
            for canonical, alias_list in conflicts.items():
                # Check if this conflict involves fields that are in both main and deprecated sections
                main_section_fields = []
                deprecated_section_fields = []
                
                for alias in alias_list:
                    # Find this field in the content
                    field_in_deprecated = False
                    for line_num, line in enumerate(lines, 1):
                        line_stripped = line.strip()
                        if line_stripped.startswith(alias + ' ') or line_stripped.startswith(alias + '\t'):
                            if self._is_in_deprecated_section(content, line_num):
                                deprecated_section_fields.append(alias)
                                field_in_deprecated = True
                                break
                    
                    if not field_in_deprecated:
                        # Check if field exists in main section
                        for line_num, line in enumerate(lines, 1):
                            line_stripped = line.strip()
                            if line_stripped.startswith(alias + ' ') or line_stripped.startswith(alias + '\t'):
                                if not self._is_in_deprecated_section(content, line_num):
                                    main_section_fields.append(alias)
                                    break
                
                # Only report as conflict if:
                # 1. Multiple fields in main section, OR
                # 2. Multiple fields in deprecated section, OR  
                # 3. Fields only in one section but duplicated
                if (len(main_section_fields) > 1 or len(deprecated_section_fields) > 1 or
                    (len(main_section_fields) == 0 and len(deprecated_section_fields) > 0) or
                    (len(main_section_fields) > 0 and len(deprecated_section_fields) == 0)):
                    filtered_conflicts[canonical] = alias_list
                # If we have one field in main and one in deprecated, this is by design, not a conflict
            
            conflicts = filtered_conflicts
            
            # If no conflicts and no deprecated fields found - all good!
            if not conflicts and not deprecated_fields:
                return True
            
            # Build detailed report
            report_summary = ""
            has_critical_issues = False
            
            if conflicts:
                has_critical_issues = True
                report_summary += "⚠️ DUPLICATE/ALIAS FIELD CONFLICTS DETECTED ⚠️\n\n"
                report_summary += "CIF databases will reject files with duplicate field names or conflicting aliases.\n\n"
                report_summary += f"Found {len(conflicts)} conflict(s):\n\n"
                
                for canonical, alias_list in conflicts.items():
                    # Check if this is a direct duplicate (same field multiple times)
                    unique_aliases = set(alias_list)
                    if len(unique_aliases) == 1:
                        duplicate_field = list(unique_aliases)[0]
                        duplicate_count = len(alias_list)
                        report_summary += f"• '{duplicate_field}' appears {duplicate_count} times (DUPLICATE)\n"
                    else:
                        # Multiple different aliases present
                        report_summary += f"• Canonical field '{canonical}' has multiple forms:\n"
                        for alias in alias_list:
                            report_summary += f"    - {alias}\n"
                    report_summary += "\n"
                
                report_summary += "These conflicts MUST be resolved before database submission.\n\n"
            
            if deprecated_fields:
                if report_summary:
                    report_summary += "---\n\n"
                
                report_summary += "📅 DEPRECATED FIELDS DETECTED\n\n"
                report_summary += f"Found {len(deprecated_fields)} deprecated field(s) that can be modernized:\n\n"
                
                for dep_field in deprecated_fields:
                    report_summary += f"• Line {dep_field['line_num']}: {dep_field['field']}\n"
                    if dep_field['modern']:
                        report_summary += f"  → Modern equivalent: {dep_field['modern']}\n"
                    else:
                        report_summary += f"  → No modern equivalent (consider removal)\n"
                    report_summary += "\n"
                
                report_summary += "Modernizing these fields improves CIF compatibility and reduces validation warnings.\n\n"
            
            # Convert conflicts to detailed structure for dialog
            detailed_conflicts = {}
            for canonical, alias_list in conflicts.items():
                detailed_conflicts[canonical] = []
                for alias in alias_list:
                    # Find line number and value for this alias
                    for line_num, line in enumerate(lines, 1):
                        line_stripped = line.strip()
                        if line_stripped.startswith(alias + ' ') or line_stripped.startswith(alias + '\t'):
                            # Extract value
                            parts = line_stripped.split(None, 1)
                            value = parts[1] if len(parts) > 1 else ''
                            
                            detailed_conflicts[canonical].append({
                                'line_num': line_num,
                                'alias': alias,
                                'value': value,
                                'is_deprecated': self.dict_manager.is_field_deprecated(alias)
                            })
                            break
            
            # Show dialog with scrollable content
            dialog_result = CriticalIssuesDialog.show_dialog(detailed_conflicts, deprecated_fields, self)
            
            if dialog_result == 0:  # Cancel
                # User wants to abort - restore initial state
                self.text_editor.setText(initial_state)
                self.update_window_title()
                QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                return False
                
            elif dialog_result == 2:  # No - keep issues
                # User wants to continue with all issues
                if has_critical_issues:
                    # Warn them about critical issues
                    final_warning = QMessageBox.warning(
                        self,
                        "Warning: Unresolved Issues",
                        "⚠️ WARNING ⚠️\n\n"
                        "Proceeding with unresolved issues.\n\n" +
                        ("Your CIF file may be REJECTED by databases due to duplicate/alias conflicts.\n\n" if conflicts else "") +
                        ("Deprecated fields may cause validation warnings.\n\n" if deprecated_fields else "") +
                        "Are you absolutely sure you want to continue?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if final_warning == QMessageBox.StandardButton.No:
                        # Give them another chance to resolve
                        return self._check_duplicates_and_aliases(initial_state)
                
                # They insist on keeping issues
                return True
                    
            else:  # Yes - resolve issues
                success = True
                
                # Handle duplicate/alias conflicts first
                if conflicts:
                    success = self._resolve_duplicate_conflicts(conflicts, content, initial_state)
                    if not success:
                        return False
                    # Update content after conflict resolution
                    content = self.text_editor.toPlainText()
                
                # Handle deprecated fields
                if deprecated_fields and success:
                    success = self._resolve_deprecated_fields(deprecated_fields, initial_state)
                
                return success
                    
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Field Check Error",
                f"An error occurred while checking fields:\n{str(e)}\n\n"
                "Please check the file manually for duplicate field names and deprecated fields."
            )
            return True  # Continue despite error
    
    def _is_in_deprecated_section(self, content: str, line_num: int) -> bool:
        """Check if a line is within a deprecated section of the CIF file."""
        lines = content.splitlines()
        
        # Find the deprecated section boundaries
        deprecated_section_start = None
        deprecated_section_end = None
        
        for i in range(len(lines)):
            line = lines[i].strip()
            if "# DEPRECATED FIELDS" in line:
                deprecated_section_start = i
                # Look for the end of this section (closing ###... line)
                for j in range(i + 1, len(lines)):
                    end_line = lines[j].strip()
                    if end_line.startswith('#') and len(end_line) > 70 and all(c == '#' for c in end_line):
                        # Check if this is actually a closing border
                        if j + 1 < len(lines):
                            next_line = lines[j + 1].strip()
                            if not next_line or next_line.startswith('data_'):
                                deprecated_section_end = j
                                break
                        else:
                            # End of file
                            deprecated_section_end = j
                            break
                break
        
        # Check if our target line is within the deprecated section
        if deprecated_section_start is not None:
            end_line = deprecated_section_end if deprecated_section_end is not None else len(lines) - 1
            target_line_index = line_num - 1  # Convert to 0-based indexing
            return deprecated_section_start <= target_line_index <= end_line
        
        return False
    
    def _resolve_duplicate_conflicts(self, conflicts: Dict, content: str, initial_state: str) -> bool:
        """Resolve duplicate/alias conflicts using existing infrastructure."""
        try:
            # Detect CIF format to use appropriate resolution strategy
            cif_format = self.dict_manager.detect_cif_format(content)
            format_name = "legacy" if cif_format.lower() == 'legacy' else "modern"
            
            # Ask user how they want to resolve
            resolve_reply = QMessageBox.question(
                self, 
                "Conflict Resolution Method",
                f"Choose conflict resolution method:\n\n" +
                f"• Yes: Let me choose for each conflict individually\n" +
                f"• No: Auto-resolve using {format_name} format + first available values",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No  # Default to auto-resolve
            )
            
            if resolve_reply == QMessageBox.StandardButton.Yes:
                # Manual resolution using existing dialog
                dialog = FieldConflictDialog(conflicts, content, self, self.dict_manager, cif_format)
                if self._show_dialog_with_configured_interaction(dialog) == QDialog.DialogCode.Accepted:
                    resolutions = dialog.get_resolutions()
                else:
                    # User cancelled the dialog - ask if they want to abort or auto-resolve
                    fallback = QMessageBox.question(
                        self,
                        "Resolution Cancelled",
                        "Manual resolution cancelled.\n\n"
                        "Would you like to auto-resolve instead?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if fallback == QMessageBox.StandardButton.Yes:
                        resolutions = self._auto_resolve_conflicts(conflicts, content, cif_format)
                    else:
                        # They don't want to resolve at all
                        return False
            else:
                # Auto-resolve
                resolutions = self._auto_resolve_conflicts(conflicts, content, cif_format)
            
            # Apply the resolutions
            if resolutions:
                resolved_content, changes = self.dict_manager.apply_field_conflict_resolutions(content, resolutions)
                
                if changes:
                    self.text_editor.setText(resolved_content)
                    self.modified = True
                    
                    change_summary = f"✅ Successfully resolved {len(conflicts)} conflict(s):\n\n"
                    for change in changes:
                        change_summary += f"• {change}\n"
                    
                    QMessageBox.information(self, "Conflicts Resolved", change_summary)
                    
                    # Verify conflicts are actually resolved
                    verify_conflicts = self.dict_manager.detect_field_aliases_in_cif(
                        self.text_editor.toPlainText()
                    )
                    if verify_conflicts:
                        # Still have conflicts - this shouldn't happen, but handle it
                        QMessageBox.warning(
                            self,
                            "Warning: Conflicts Remain",
                            f"Some conflicts could not be fully resolved.\n\n"
                            f"{len(verify_conflicts)} conflict(s) still present.\n\n"
                            "Manual review may be required."
                        )
                    return True
                else:
                    QMessageBox.information(self, "No Changes Made", 
                                          "No changes were needed to resolve the conflicts.")
                    return True
            
            return True
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Conflict Resolution Error",
                f"An error occurred while resolving conflicts:\n{str(e)}"
            )
            return False
    
    def _resolve_deprecated_fields(self, deprecated_fields: List[Dict], initial_state: str) -> bool:
        """Resolve deprecated fields by adding modern equivalents alongside them."""
        try:
            resolved_count = 0
            changes_made = []
            
            for dep_field in deprecated_fields:
                field_name = dep_field['field']
                modern_equiv = dep_field['modern']
                
                if modern_equiv:
                    # Add the modern field alongside the deprecated one (keep both)
                    result = self._add_modern_equivalent_field(field_name, modern_equiv)
                    if result == QDialog.DialogCode.Accepted:
                        resolved_count += 1
                        changes_made.append(f"Added {modern_equiv} (kept {field_name})")
            
            if resolved_count > 0:
                change_summary = f"✅ Added successors for {resolved_count} deprecated field(s):\n\n"
                for change in changes_made:
                    change_summary += f"• {change}\n"
                change_summary += "\nBoth deprecated and successor field names now exist in the CIF."
                
                QMessageBox.information(self, "Successor Fields Added", change_summary)
            else:
                QMessageBox.information(self, "No Changes Made", 
                                      "No successor fields could be added (they may already exist).")
            
            return True
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Deprecated Field Resolution Error",
                f"An error occurred while modernizing deprecated fields:\n{str(e)}"
            )
            return False
