"""
Format handling mixin for CIFEditor.

This module contains CIF format detection, conversion, validation, and
field standardization methods extracted from main_window.py. The mixin
is designed to be used as a base class for CIFEditor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Tuple

from PyQt6.QtWidgets import QMessageBox, QDialog

from utils.cif_dictionary_manager import CIFVersion, FieldNotation, CIFSyntaxVersion
# TEMPORARY: Import modern format warning - remove when checkCIF fully supports modern notation
from utils.format_compatibility_warning import show_modern_format_warning
from .dialogs.field_conflict_dialog import FieldConflictDialog

if TYPE_CHECKING:
    from .main_window import CIFEditor


class FormatHandlersMixin:
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
        """Detect field notation and update the status display"""
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
            f"Field notation: {notation_text.get(notation, 'Unknown')}\n"
            f"Syntax version: {syntax_text.get(syntax_version, 'Unknown')}"
        )
        
        if notation == FieldNotation.MIXED:
            message += "\n\nConsider using 'Fix Mixed Notation' to resolve."
        
        QMessageBox.information(self, "CIF Format Detection", message)

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
                change_summary = f"Made {len(changes)} changes:\n" + "\n".join(changes[:5])
                if len(changes) > 5:
                    change_summary += f"\n... and {len(changes)-5} more"
                QMessageBox.information(self, "Conversion Complete", 
                                      f"Field names converted to legacy notation.\n\n{change_summary}")
                
                # If file has CIF2 header, offer to ensure CIF 1.1 compliance
                syntax_ver = self.dict_manager.detect_syntax_version(converted_content)
                if syntax_ver == CIFSyntaxVersion.CIF2:
                    reply = QMessageBox.question(
                        self, "CIF 1.1 Compliance",
                        "This file still has a CIF 2.0 header.\n\n"
                        "Would you also like to ensure CIF 1.1 compliance?\n"
                        "(This will replace the CIF 2.0 header with CIF 1.1.)",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        self.ensure_cif1_compliance()
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
                change_summary = f"Made {len(changes)} changes:\n" + "\n".join(changes[:5])
                if len(changes) > 5:
                    change_summary += f"\n... and {len(changes)-5} more"
                QMessageBox.information(self, "Conversion Complete", 
                                      f"Field names converted to modern notation.\n\n{change_summary}")
            else:
                QMessageBox.information(self, "No Changes", 
                                      "File is already in modern notation or no conversion was needed.")
        except Exception as e:
            QMessageBox.critical(self, "Conversion Error", 
                               f"Failed to convert to modern notation:\n{str(e)}")

    def fix_mixed_format(self):
        """Fix mixed field notation by converting to consistent notation"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        # First detect current notation
        notation = self.dict_manager.detect_notation(content)
        if notation != FieldNotation.MIXED:
            QMessageBox.information(self, "No Mixed Notation", 
                                  "File does not appear to have mixed field notation.")
            return
        
        # Ask user which notation to convert to
        reply = QMessageBox.question(self, "Choose Target Notation",
                                   "Convert mixed field notation to:\n\n" +
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
                change_summary = f"Made {len(changes)} changes:\n" + "\n".join(changes[:5])
                if len(changes) > 5:
                    change_summary += f"\n... and {len(changes)-5} more"
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

    def _auto_resolve_conflicts(self, conflicts: Dict[str, List[str]], cif_content: str, cif_format: str = 'modern') -> Dict[str, Tuple[str, str]]:
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
            
            resolutions[canonical_field] = (chosen_field, chosen_value)
        
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
            
            summary += "These fields use incorrect underscore-only format instead of the proper category.attribute format.\n\n"
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
        """Check for deprecated fields in the current CIF file and offer to replace them"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            # Parse CIF content to find all fields
            lines = content.splitlines()
            found_deprecated = []
            
            for line_num, line in enumerate(lines, 1):
                line_stripped = line.strip()
                if line_stripped.startswith('_') and ' ' in line_stripped:
                    field_name = line_stripped.split()[0]
                    if self.dict_manager.is_field_deprecated(field_name):
                        modern_equiv = self.dict_manager.get_modern_equivalent(field_name, prefer_format="LEGACY")
                        found_deprecated.append({
                            'field': field_name,
                            'line_num': line_num,
                            'line': line_stripped,
                            'modern': modern_equiv
                        })
            
            if not found_deprecated:
                QMessageBox.information(self, "No Deprecated Fields", 
                                      "No deprecated fields were found in the current CIF file.")
                return
            
            # Build summary of deprecated fields
            summary = f"Found {len(found_deprecated)} deprecated field(s):\n\n"
            for item in found_deprecated:
                summary += f"• Line {item['line_num']}: {item['field']}\n"
                if item['modern']:
                    summary += f"  → Modern equivalent: {item['modern']}\n"
                else:
                    summary += f"  → No modern equivalent (consider removal)\n"
                summary += "\n"
            
            # Check if any fields can actually be replaced
            replaceable_count = sum(1 for item in found_deprecated if item['modern'])
            
            if replaceable_count == 0:
                QMessageBox.information(
                    self, 
                    "Deprecated Fields Found",
                    summary + "None of these deprecated fields have modern equivalents available.\n\n" +
                    "Consider reviewing and potentially removing these fields manually."
                )
                return
            
            # Ask user what to do
            reply = QMessageBox.question(
                self, 
                "Deprecated Fields Found",
                summary + f"Would you like to replace the {replaceable_count} deprecated field(s) " +
                "that have modern equivalents?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Replace deprecated fields
                updated_content = content
                changes_made = []
                
                # Process in reverse order to maintain line numbers
                for item in reversed(found_deprecated):
                    if item['modern']:
                        old_line = item['line']
                        parts = old_line.split(None, 1)
                        if len(parts) > 1:
                            new_line = f"{item['modern']} {parts[1]}"
                            updated_content = updated_content.replace(old_line, new_line)
                            changes_made.append(f"Replaced {item['field']} → {item['modern']}")
                
                if changes_made:
                    self.text_editor.setText(updated_content)
                    self.modified = True
                    
                    change_summary = f"Successfully updated {len(changes_made)} deprecated field(s):\n\n"
                    for change in changes_made:
                        change_summary += f"• {change}\n"
                    
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
