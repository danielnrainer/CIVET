"""
Format handling mixin for CIFEditor.

This module contains CIF format detection, conversion, validation, and
field standardization methods extracted from main_window.py. The mixin
is designed to be used as a base class for CIFEditor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Tuple, Optional, cast

from PyQt6.QtWidgets import QMessageBox, QDialog, QWidget, QTextEdit

from utils.cif_dictionary_manager import CIFVersion, FieldNotation, CIFSyntaxVersion
# TEMPORARY: Import modern format warning - remove when checkCIF fully supports modern notation
from utils.format_compatibility_warning import show_modern_format_warning
from .dialogs.field_conflict_dialog import FieldConflictDialog

if TYPE_CHECKING:
    from .main_window import CIFEditor
    from utils.CIF_parser import CIFParser
    from utils.cif_dictionary_manager import CIFDictionaryManager
    from utils.cif_format_converter import CIFFormatConverter


if TYPE_CHECKING:
    _FormatHandlersWidgetBase = QWidget
else:
    class _FormatHandlersWidgetBase:
        """Runtime no-op base; QWidget only needed for static typing."""
        pass


class FormatHandlersMixin(_FormatHandlersWidgetBase):
    """Mixin providing CIF format handling methods for CIFEditor.

    Expects the host class to provide:
        - self.text_editor          (CIFTextEditor)
        - self.dict_manager         (CIFDictionaryManager)
        - self.format_converter     (CIFFormatConverter)
        - self.cif_parser           (CIFParser)
        - self.modified             (bool)
        - self.current_cif_version  (CIFVersion)
        - self.update_cif_version_display()
        - self._show_dialog_with_configured_interaction(dialog)
    """

    # Host-provided attributes/methods for static type checkers.
    text_editor: QTextEdit
    dict_manager: 'CIFDictionaryManager'
    format_converter: 'CIFFormatConverter'
    cif_parser: 'CIFParser'
    modified: bool
    current_cif_version: CIFVersion

    def update_cif_version_display(self) -> None:
        raise NotImplementedError()

    def _show_dialog_with_configured_interaction(
        self,
        dialog: QDialog,
        mode_setting_key: str = "dialogs.default_interaction_mode",
    ) -> int:
        raise NotImplementedError()

    def _check_duplicate_data_names(self, operation_name: str, block_on_conflicts: bool = False) -> bool:
        raise NotImplementedError()

    def _ensure_cif2_header(self, content: str) -> str:
        """Ensure CIF2 header is present at the start of content.
        
        Adds ``#\\#CIF_2.0`` if missing, replaces ``#\\#CIF_1.x`` if present.
        """
        lines = content.split('\n')
        for i, line in enumerate(lines[:5]):
            stripped = line.strip()
            if stripped.startswith('#\\#CIF_2.0'):
                return content  # Already has CIF2 header
            if stripped.startswith('#\\#CIF_1'):
                lines[i] = '#\\#CIF_2.0'
                return '\n'.join(lines)
            if stripped.startswith('data_'):
                lines.insert(i, '#\\#CIF_2.0')
                lines.insert(i + 1, '')
                return '\n'.join(lines)
        
        return '#\\#CIF_2.0\n\n' + content

    # Backward-compatible alias
    _ensure_modern_header = _ensure_cif2_header

    def detect_and_update_cif_version(self, content=None):
        """Detect data name notation and update the status display"""
        if content is None:
            content = self.text_editor.toPlainText()
        
        self.current_cif_version = self.dict_manager.detect_notation(content)
        self.update_cif_version_display()

    def detect_cif_version(self):
        """Menu action to detect and display CIF notation and syntax version"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        notation = self.dict_manager.detect_notation(content)
        syntax_version = self.dict_manager.detect_syntax_version(content)
        self.current_cif_version = notation
        self.update_cif_version_display()
        
        notation_text = {
            FieldNotation.LEGACY: "Legacy (underscore notation)",
            FieldNotation.MODERN: "Modern (dot notation)",
            FieldNotation.MIXED: "Mixed (both underscore and dot notation)",
            FieldNotation.UNKNOWN: "Unknown (no fields detected)"
        }
        
        syntax_text = {
            CIFSyntaxVersion.CIF1: "CIF 1.1",
            CIFSyntaxVersion.CIF2: "CIF 2.0",
            CIFSyntaxVersion.UNKNOWN: "Unknown"
        }
        
        message = (
            f"Data name notation: {notation_text.get(notation, 'Unknown')}\n"
            f"Syntax version: {syntax_text.get(syntax_version, 'Unknown')}"
        )
        
        if notation == FieldNotation.MIXED:
            message += "\n\nConsider using 'Fix Mixed Notation' to resolve."
        
        QMessageBox.information(self, "CIF Format Detection", message)

    def _format_conversion_change_summary(self, changes: List[str], max_main_changes: int = 5) -> str:
        """Create a readable summary that preserves warnings even for long change lists."""
        if not changes:
            return "No changes were reported."

        warning_lines = [c for c in changes if c.strip().startswith("Warning:")]
        normal_lines = [c for c in changes if not c.strip().startswith("Warning:")]

        summary_lines = [f"Changes made:"]

        if normal_lines:
            shown = normal_lines[:max_main_changes]
            summary_lines.extend(shown)
            remaining = len(normal_lines) - len(shown)
            if remaining > 0:
                summary_lines.append(f"... and {remaining} more change(s)")

        if warning_lines:
            summary_lines.append("")
            summary_lines.append("---------\n")
            for i in warning_lines:
                summary_lines.append(i)
                summary_lines.append("")  # Add spacing between warnings
            # summary_lines.extend(warning_lines)

        return "\n".join(summary_lines)

    def convert_to_legacy(self):
        """Convert current CIF field names to legacy notation"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            converted_content, changes = self.format_converter.convert_to_legacy_notation(content)
            if converted_content != content:
                self.text_editor.setText(converted_content)
                self.modified = True
                self.current_cif_version = FieldNotation.LEGACY
                self.update_cif_version_display()
                self._check_duplicate_data_names("legacy notation conversion", block_on_conflicts=False)
                change_summary = self._format_conversion_change_summary(changes)
                QMessageBox.information(self, "Conversion Complete", 
                                      f"Field names converted to legacy notation.\n\n{change_summary}")
            else:
                QMessageBox.information(self, "No Changes", 
                                      "File is already in legacy notation or no conversion was needed.")
        except Exception as e:
            QMessageBox.critical(self, "Conversion Error", 
                               f"Failed to convert to legacy notation:\n{str(e)}")

    def convert_to_modern(self):
        """Convert current CIF field names to modern notation"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        # TEMPORARY: Show warning about modern format compatibility
        if not show_modern_format_warning(self, "CIF notation conversion"):
            return  # User chose not to proceed
        
        try:
            converted_content, changes = self.format_converter.convert_to_modern_notation(content)
            if converted_content != content:
                self.text_editor.setText(converted_content)
                self.modified = True
                self.current_cif_version = FieldNotation.MODERN
                self.update_cif_version_display()
                self._check_duplicate_data_names("modern notation conversion", block_on_conflicts=False)
                change_summary = self._format_conversion_change_summary(changes)
                QMessageBox.information(self, "Conversion Complete", 
                                      f"Field names converted to modern notation.\n\n{change_summary}")
            else:
                QMessageBox.information(self, "No Changes", 
                                      "File is already in modern notation or no conversion was needed.")
        except Exception as e:
            QMessageBox.critical(self, "Conversion Error", 
                               f"Failed to convert to modern notation:\n{str(e)}")

    def fix_mixed_format(self):
        """Fix mixed data name notation by converting to consistent notation"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        # First detect current notation
        notation = self.dict_manager.detect_notation(content)
        if notation != FieldNotation.MIXED:
            QMessageBox.information(self, "No Mixed Notation", 
                                  "File does not appear to have mixed data name notation.")
            return
        
        # Ask user which notation to convert to
        reply = QMessageBox.question(self, "Choose Target Notation",
                                   "Convert mixed data name notation to:\n\n" +
                                   "Yes: Modern notation (dot syntax, recommended)\n" +
                                   "No: Legacy notation (underscore syntax, for compatibility)\n" +
                                   "Cancel: Abort conversion",
                                   QMessageBox.StandardButton.Yes |
                                   QMessageBox.StandardButton.No |
                                   QMessageBox.StandardButton.Cancel)
        
        if reply == QMessageBox.StandardButton.Cancel:
            return
        
        try:
            if reply == QMessageBox.StandardButton.Yes:
                # Convert to modern notation
                fixed_content, changes = self.format_converter.fix_mixed_format(content, target_version=FieldNotation.MODERN)
                target_notation = FieldNotation.MODERN
                notation_name = "modern"
            else:
                # Convert to legacy notation
                fixed_content, changes = self.format_converter.fix_mixed_format(content, target_version=FieldNotation.LEGACY)
                target_notation = FieldNotation.LEGACY
                notation_name = "legacy"
            
            if fixed_content != content:
                self.text_editor.setText(fixed_content)
                self.modified = True
                self.current_cif_version = target_notation
                self.update_cif_version_display()
                self._check_duplicate_data_names("mixed-notation fix", block_on_conflicts=False)
                change_summary = self._format_conversion_change_summary(changes)
                QMessageBox.information(self, "Notation Fixed", 
                                      f"Mixed notation successfully resolved to {notation_name}.\n\n{change_summary}")
            else:
                QMessageBox.information(self, "No Changes", 
                                      "No notation issues were found to fix.")
        except Exception as e:
            QMessageBox.critical(self, "Fix Error", 
                               f"Failed to fix mixed notation:\n{str(e)}")

    def standardize_cif_fields(self):
        """Resolve CIF field alias conflicts with user control"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            # Check for alias conflicts first
            conflicts = self.dict_manager.detect_field_aliases_in_cif(content)
            
            if not conflicts:
                QMessageBox.information(self, "No Alias Conflicts", 
                                      "No field alias conflicts were found.\n\n" +
                                      "This tool only resolves cases where the same field " +
                                      "appears in multiple forms (e.g., both _diffrn_source_type " +
                                      "and _diffrn_source_make in the same file).")
                return
            
            # Show conflict summary and let user choose resolution approach
            conflict_summary = f"Found {len(conflicts)} field alias conflicts:\n\n"
            for canonical, alias_list in conflicts.items():
                conflict_summary += f"• {canonical}:\n"
                for alias in alias_list:
                    conflict_summary += f"    - {alias}\n"
                conflict_summary += "\n"
            
            # Ask user how they want to resolve conflicts
            reply = QMessageBox.question(self, "Field Alias Conflicts Found",
                                       conflict_summary + 
                                       "How would you like to resolve these conflicts?\n\n" +
                                       "• Yes: Let me choose for each conflict individually\n" +
                                       "• No: Auto-resolve using modern format + first available values\n" +
                                       "• Cancel: Don't resolve conflicts",
                                       QMessageBox.StandardButton.Yes |
                                       QMessageBox.StandardButton.No |
                                       QMessageBox.StandardButton.Cancel)
            
            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.Yes:
                # Detect CIF format for appropriate resolution
                cif_format = self.dict_manager.detect_cif_format(content)
                
                # Let user resolve conflicts individually
                dialog = FieldConflictDialog(conflicts, content, self, self.dict_manager, cif_format)
                if self._show_dialog_with_configured_interaction(dialog) == QDialog.DialogCode.Accepted:
                    resolutions = dialog.get_resolutions()
                else:
                    return  # User cancelled
            else:
                # Detect CIF format for auto-resolve
                cif_format = self.dict_manager.detect_cif_format(content)
                
                # Auto-resolve using appropriate format + first available values
                resolutions = self._auto_resolve_conflicts(conflicts, content, cif_format)
            
            # Apply the resolutions
            if resolutions:
                resolved_content, changes = self.dict_manager.apply_field_conflict_resolutions(content, resolutions)
                
                if changes:
                    self.text_editor.setText(resolved_content)
                    self.modified = True
                    
                    change_summary = f"Successfully resolved {len(conflicts)} field alias conflicts:\n\n"
                    for change in changes:
                        change_summary += f"• {change}\n"
                    
                    QMessageBox.information(self, "Conflicts Resolved", change_summary)
                else:
                    QMessageBox.information(self, "No Changes Made", 
                                          "No changes were needed to resolve the conflicts.")
                
        except Exception as e:
            QMessageBox.critical(self, "Conflict Resolution Error", 
                               f"Failed to resolve field alias conflicts:\n{str(e)}")

    def _auto_resolve_conflicts(self, conflicts: Dict[str, List[str]], cif_content: str, cif_format: str = 'modern') -> Dict[str, Tuple[str, str, bool]]:
        """Auto-resolve conflicts using the appropriate format and first available values"""
        resolutions = {}
        
        lines = cif_content.split('\n')
        
        for canonical_field, alias_list in conflicts.items():
            # Choose field format based on CIF format
            if cif_format.lower() == 'legacy':
                # For legacy CIFs, prefer the legacy equivalent
                chosen_field = self.dict_manager.get_modern_equivalent(canonical_field, prefer_format='legacy')
                if not chosen_field or chosen_field == canonical_field:
                    # No specific legacy form available, use first alias or canonical
                    chosen_field = alias_list[0] if alias_list else canonical_field
            else:
                # For modern CIFs, use the canonical (modern) field
                chosen_field = canonical_field
            
            # Find the first available value
            chosen_value = ""
            for alias in alias_list:
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped.startswith(alias + ' '):
                        parts = line_stripped.split(None, 1)
                        if len(parts) > 1:
                            chosen_value = parts[1]
                            break
                if chosen_value:
                    break
            
            # Fallback if no value found
            if not chosen_value:
                chosen_value = "?"
            
            # Auto-resolve keeps the recommended single field by default.
            resolutions[canonical_field] = (chosen_field, chosen_value, False)
        
        return resolutions

    def fix_malformed_field_names(self):
        """
        Detect and fix malformed field names that look like incorrectly formatted 
        versions of known dictionary fields.
        
        For example: _diffrn_total_exposure_time → _diffrn.total_exposure_time
        
        These fields arise when data processing software outputs field names 
        using only underscores instead of the correct category.attribute format.
        """
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            # Find malformed fields
            malformed = self.dict_manager.find_malformed_fields(content)
            
            if not malformed:
                QMessageBox.information(
                    self, 
                    "No Malformed Fields Found",
                    "No incorrectly formatted field names were detected.\n\n"
                    "All unknown fields in this CIF file are either:\n"
                    "• Valid dictionary fields\n"
                    "• Truly custom/unknown fields that cannot be automatically corrected"
                )
                return
            
            # Build a summary of what was found
            summary = f"Found {len(malformed)} malformed field name(s):\n\n"
            for item in malformed:
                summary += f"• Line {item['line_number']}: {item['original']}\n"
                summary += f"  → Should be: {item['suggested']}\n\n"
            
            summary += "These fields appear to use malformed data-name notation and can be auto-corrected.\n\n"
            summary += "Would you like to fix all of these field names?"
            
            # Ask user to confirm
            reply = QMessageBox.question(
                self,
                "Fix Malformed Field Names",
                summary,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Apply fixes
                fixed_content, changes = self.dict_manager.fix_malformed_fields_in_content(content, malformed)
                
                if changes:
                    self.text_editor.setText(fixed_content)
                    self.modified = True
                    self._check_duplicate_data_names("malformed data-name correction", block_on_conflicts=False)
                    
                    change_summary = f"Fixed {len(changes)} malformed field name(s):\n\n"
                    change_summary += "\n".join(f"• {change}" for change in changes[:10])
                    if len(changes) > 10:
                        change_summary += f"\n• ... and {len(changes) - 10} more"
                    
                    QMessageBox.information(self, "Malformed Fields Fixed", change_summary)
                else:
                    QMessageBox.information(self, "No Changes Made", 
                                          "No changes were applied.")
                    
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Fixing Malformed Fields",
                f"An error occurred while fixing malformed field names:\n{str(e)}"
            )

    def check_deprecated_fields(self):
        """Check deprecated fields using the shared data-name validator pipeline."""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            # Use the same validation path as the Data Name Validation dialog.
            self.data_name_validator.clear_cache()
            report = self.data_name_validator.validate_cif_content(content)
            found_deprecated = report.deprecated_fields

            if not found_deprecated:
                QMessageBox.information(self, "No Deprecated Fields", 
                                      "No deprecated fields were found in the current CIF file.")
                return
            
            # Build summary of deprecated fields
            summary = f"Found {len(found_deprecated)} deprecated field(s):\n\n"
            for item in found_deprecated:
                summary += f"• Line {item.line_number}: {item.field_name}\n"
                successor = item.successor_name or item.modern_equivalent
                if successor:
                    summary += f"  → Successor: {successor}\n"
                    if item.successor_already_exists:
                        summary += "  → Successor already present in this CIF\n"
                else:
                    summary += "  → No successor available\n"
                summary += "\n"
            
            # Check if any fields can actually be replaced
            replaceable_map: Dict[str, str] = {}
            skipped_existing = 0
            for item in found_deprecated:
                successor = item.successor_name or item.modern_equivalent
                if not successor:
                    continue
                if item.successor_already_exists:
                    skipped_existing += 1
                    continue
                replaceable_map[item.field_name.lower()] = successor

            replaceable_count = len(replaceable_map)
            
            if replaceable_count == 0:
                extra_note = ""
                if skipped_existing:
                    extra_note = (
                        f"\n{skipped_existing} deprecated field(s) already have their successor "
                        "present in this CIF."
                    )
                QMessageBox.information(
                    self, 
                    "Deprecated Fields Found",
                    summary + "None of these deprecated fields can be safely auto-replaced.\n\n" +
                    "Use CIF Validation > Validate Data Names for per-field add/replace/delete control."
                    + extra_note
                )
                return
            
            # Ask user what to do
            reply = QMessageBox.question(
                self, 
                "Deprecated Fields Found",
                summary + f"Would you like to replace the {replaceable_count} deprecated field(s) " +
                "with their successor names?\n"
                "Note: fields where the successor already exists are skipped to avoid duplicates.\n\n"
                "Alternatively, you can use CIF Validation > Validate Data Names for better per-field control.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Replace deprecated field names line-by-line to avoid accidental global substitutions.
                updated_lines = []
                changes_made = []

                for line in content.splitlines():
                    stripped = line.lstrip()
                    if stripped.startswith('_'):
                        parts = stripped.split(None, 1)
                        field_name = parts[0]
                        replacement = replaceable_map.get(field_name.lower())
                        if replacement:
                            leading_ws = line[:len(line) - len(stripped)]
                            remainder = f" {parts[1]}" if len(parts) > 1 else ""
                            line = f"{leading_ws}{replacement}{remainder}"
                            changes_made.append(f"Replaced {field_name} → {replacement}")
                    updated_lines.append(line)
                
                if changes_made:
                    updated_content = "\n".join(updated_lines)
                    self.text_editor.setText(updated_content)
                    self.modified = True
                    self._check_duplicate_data_names("deprecated data-name replacement", block_on_conflicts=False)
                    
                    change_summary = f"Successfully updated {len(changes_made)} deprecated field(s):\n\n"
                    for change in changes_made:
                        change_summary += f"• {change}\n"

                    if skipped_existing:
                        change_summary += (
                            f"\nSkipped {skipped_existing} field(s) because their successor already exists."
                        )
                    
                    QMessageBox.information(self, "Fields Updated", change_summary)
                else:
                    QMessageBox.information(self, "No Changes Made", 
                                          "No fields could be automatically replaced.")
                
        except Exception as e:
            QMessageBox.critical(self, "Deprecated Field Check Error", 
                               f"Failed to check for deprecated fields:\n{str(e)}")

    def add_legacy_compatibility_fields(self):
        """Add deprecated fields alongside modern equivalents for validation tool compatibility."""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            # Parse the current CIF content
            self.cif_parser.parse_file(content)
            
            # Show explanation dialog
            reply = QMessageBox.question(
                self, 
                "Add Legacy Compatibility Fields",
                "This feature adds deprecated fields alongside their modern equivalents "
                "to ensure compatibility with validation tools (like checkCIF/PLAT) that "
                "haven't been updated to recognize modern field names.\n\n"
                "Example: If you have '_diffrn.ambient_temperature', this will also add "
                "'_cell_measurement_temperature' with the same value.\n\n"
                "This is safe and won't affect the scientific meaning of your CIF file.\n\n"
                "Proceed with adding compatibility fields?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # Add compatibility fields
            report = self.cif_parser.add_legacy_compatibility_fields(self.dict_manager)
            
            # Generate the updated CIF content
            updated_content = self.cif_parser.generate_cif_content()
            
            # Update the editor
            self.text_editor.setText(updated_content)
            self.modified = True
            self._check_duplicate_data_names("adding legacy compatibility data names", block_on_conflicts=False)
            
            # Show results
            if "Added" in report:
                QMessageBox.information(
                    self, 
                    "Compatibility Fields Added", 
                    report + "\n\nYour CIF file is now more compatible with legacy validation tools."
                )
            else:
                QMessageBox.information(
                    self, 
                    "No Changes Needed", 
                    report
                )
                
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Compatibility Fields Error", 
                f"Failed to add compatibility fields:\n{str(e)}\n\n"
                "This might happen if the CIF file has parsing issues or if the dictionary "
                "manager is not properly initialized."
            )

    def ensure_cif2_compliance(self):
        """Ensure the current CIF content is CIF 2.0 compliant (add header if needed)."""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            updated, was_changed = self.format_converter.ensure_cif2_compliant(content)
            if was_changed:
                self.text_editor.setText(updated)
                self.modified = True
                QMessageBox.information(self, "CIF 2.0 Header Added",
                                      "A CIF 2.0 header (#\\#CIF_2.0) has been added to the file.")
            else:
                QMessageBox.information(self, "Already CIF 2.0 Compliant",
                                      "This file already has a CIF 2.0 header.")
        except Exception as e:
            QMessageBox.critical(self, "Compliance Error",
                               f"Failed to ensure CIF 2.0 compliance:\n{str(e)}")

    def ensure_cif1_compliance(self):
        """Ensure the current CIF content is CIF 1.1 compliant (replace header, check for CIF2 constructs)."""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            issues = self.format_converter.check_cif1_compliance(content)
            if issues:
                issue_text = "\n".join(f"• {issue}" for issue in issues)
                QMessageBox.warning(self, "CIF 1.1 Compliance Issues",
                                   f"Cannot ensure CIF 1.1 compliance. The following issues were found:\n\n"
                                   f"{issue_text}\n\n"
                                   "Please resolve these issues first (e.g., remove CIF2-only constructs).")
                return
            
            updated, was_changed = self.format_converter.ensure_cif1_compliant(content)
            if was_changed:
                self.text_editor.setText(updated)
                self.modified = True
                QMessageBox.information(self, "CIF 1.1 Compliance",
                                      "The CIF header has been set to CIF 1.1 (data_).")
            else:
                QMessageBox.information(self, "Already CIF 1.1 Compliant",
                                      "This file is already CIF 1.1 compliant.")
        except Exception as e:
            QMessageBox.critical(self, "Compliance Error",
                               f"Failed to ensure CIF 1.1 compliance:\n{str(e)}")

    def check_syntax_compliance(self):
        """Show the CIF Syntax Compliance dialog for the current editor content."""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return

        from utils.cif_syntax_compliance import check_compliance
        from .dialogs.cif_syntax_compliance_dialog import CIFSyntaxComplianceDialog
        from .dialogs.non_ascii_conversion_dialog import NonAsciiConversionDialog
        from utils.cif_char_encoding import (
            detect_non_ascii_chars, convert_unicode_to_cif11,
            convert_cif11_to_unicode, CIF11_UNICODE_TO_BACKSLASH,
        )

        results = check_compliance(content)
        dialog = CIFSyntaxComplianceDialog(results['cif1'], results['cif2'], self)

        def _goto(line_number: int):
            self._navigate_editor_to_line(line_number)

        def _refresh():
            fresh = self.text_editor.toPlainText()
            res = check_compliance(fresh)
            dialog.update_issues(res['cif1'], res['cif2'])

        def _fix_all(spec: str):
            """Apply auto-fixable issues scoped to *spec* ('cif1', 'cif2', or 'all')."""
            from utils.cif2_value_formatting import fix_cif2_compliance_issues
            current = self.text_editor.toPlainText()
            changed = False

            # Fix CIF2 special-char quoting (CIF2-scoped only)
            if spec in ('cif2', 'all'):
                fixed, fixes = fix_cif2_compliance_issues(current)
                if fixes:
                    current = fixed
                    changed = True

            # Add/fix version headers based on scope
            res = check_compliance(current)
            issues_in_scope = []
            if spec in ('cif1', 'all'):
                issues_in_scope += res['cif1']
            if spec in ('cif2', 'all'):
                issues_in_scope += res['cif2']

            for issue in issues_in_scope:
                if not issue.auto_fixable:
                    continue
                if issue.issue_type == 'missing_version_header':
                    if issue.spec == 'CIF2':
                        if not current.lstrip().startswith('#\\#CIF_2.0'):
                            current = '#\\#CIF_2.0\n' + current
                            changed = True
                    else:  # CIF1.1
                        if not current.lstrip().startswith('#\\#CIF_'):
                            current = '#\\#CIF_1.1\n' + current
                            changed = True
                elif issue.issue_type == 'wrong_version_header':
                    lines = current.split('\n')
                    for idx, line in enumerate(lines[:5]):
                        if line.strip().startswith('#\\#CIF_2.0'):
                            lines[idx] = '#\\#CIF_1.1'
                            changed = True
                            break
                    current = '\n'.join(lines)

            if changed:
                self.text_editor.setText(current)
                self.modified = True

            # Refresh dialog
            fresh_res = check_compliance(self.text_editor.toPlainText())
            dialog.update_issues(fresh_res['cif1'], fresh_res['cif2'])

            if not changed:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    dialog, "No Changes",
                    "No auto-fixable issues were found or could be applied."
                )

        def _show_non_ascii():
            current = self.text_editor.toPlainText()
            occurrences = cast(
                List[Tuple[str, Optional[str], int, bool]],
                detect_non_ascii_chars(current),
            )
            if not occurrences:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    dialog, "No Non-ASCII Characters",
                    "No non-ASCII characters were found in the current content."
                )
                return
            na_dialog = NonAsciiConversionDialog(occurrences, 'unicode_to_cif11', dialog)

            def _apply(direction: str, chars: list):
                cur = self.text_editor.toPlainText()
                if direction == 'unicode_to_cif11':
                    for ch in chars:
                        code = CIF11_UNICODE_TO_BACKSLASH.get(ch)
                        if code:
                            cur = cur.replace(ch, code)
                else:
                    from utils.cif_char_encoding import CIF11_BACKSLASH_TO_UNICODE
                    for ch in chars:
                        code = CIF11_UNICODE_TO_BACKSLASH.get(ch)
                        if code:
                            cur = cur.replace(code, ch)
                self.text_editor.setText(cur)
                self.modified = True
                fresh_res = check_compliance(self.text_editor.toPlainText())
                dialog.update_issues(fresh_res['cif1'], fresh_res['cif2'])

            na_dialog.conversion_requested.connect(_apply)
            na_dialog.exec()

        dialog.navigate_to_line.connect(_goto)
        dialog.refresh_requested.connect(_refresh)
        dialog.fix_all_requested.connect(_fix_all)
        dialog.non_ascii_conversion_requested.connect(_show_non_ascii)

        self._show_dialog_with_configured_interaction(
            dialog, "dialogs.syntax_compliance_mode"
        )
