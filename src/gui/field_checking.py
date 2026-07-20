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
import hashlib
from typing import Dict, List, Tuple, TYPE_CHECKING

from PyQt6.QtWidgets import QDialog, QMessageBox, QFileDialog

from utils.CIF_field_parsing import safe_eval_expr, evaluate_condition
from utils.CIF_parser import (CIFField, CIFParser, update_audit_creation_method,
                              TextBlockTracker)
from utils.cif_dictionary_manager import FieldNotation
from utils.field_rules_validator import CIFFormatAnalyzer
from .check_progress import CheckProgressTracker, count_rule_steps
from .dialogs import (CIFInputDialog, MultilineInputDialog, CheckConfigDialog,
                      MultiBlockValueDialog, RESULT_ABORT, RESULT_STOP_SAVE)
from .dialogs.data_name_validation_dialog import DataNameValidationDialog
from .dialogs.field_conflict_dialog import FieldConflictDialog
from .dialogs.critical_issues_dialog import CriticalIssuesDialog

if TYPE_CHECKING:
    from .main_window import CIFEditor


SOHNCKE_SPACE_GROUPS = {
    1, 3, 4, 5, 16, 17, 18, 19, 20, 21, 22, 23, 24, 75, 76, 77, 78, 79,
    80, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 143, 144, 145, 146, 149,
    150, 151, 152, 153, 154, 155, 168, 169, 170, 171, 172, 173, 177, 178,
    179, 180, 181, 182, 195, 196, 197, 198, 199, 207, 208, 209, 210, 211,
    212, 213, 214,
}


class FieldCheckingMixin:
    """Mixin providing field checking workflow methods for CIFEditor."""

    def _set_editor_text(self, text: str) -> None:
        """Update the editor contents, preferring an incremental (non-rebuilding) edit.

        In the full application the editor is a CIFTextEditor exposed as
        ``self.cif_text_editor``; its ``replace_contents_incrementally`` edits
        only the changed region so the syntax highlighter re-processes just the
        affected blocks instead of the whole document. Standalone test harnesses
        provide a minimal ``self.text_editor`` stub with only ``setText`` - fall
        back to that when the rich editor is unavailable.
        """
        editor_widget = getattr(self, 'cif_text_editor', None)
        if editor_widget is not None and hasattr(editor_widget, 'replace_contents_incrementally'):
            editor_widget.replace_contents_incrementally(text)
        else:
            self.text_editor.setText(text)

    # ------------------------------------------------------------------
    # Data-block scoping
    #
    # When a multi-block file is checked, the run loops over the selected
    # blocks with `_active_check_block` set to the current block's code.
    # The helpers below then present the check pipeline with a virtual
    # document containing only that block's lines; writes are spliced back
    # into the full document. With no active block (single-block files,
    # and all non-check editing) they are transparent pass-throughs.
    # See .github/multi_data_block_plan.md.
    # ------------------------------------------------------------------

    @property
    def _check_block_scope(self):
        """Code of the data block checks are currently scoped to, or None."""
        return getattr(self, '_active_check_block', None)

    @staticmethod
    def _locate_block_span(lines, block_name):
        """Return the [start, end) line range of ``data_<block_name>``.

        The span includes the data_ header line and runs to the line before
        the next data_ header (or EOF). data_ tokens inside multiline text
        values and comments are ignored. Falls back to the whole document
        if the block is not found (so a stale scope can never corrupt
        content outside the file).
        """
        tracker = TextBlockTracker()
        start = None
        for i, raw_line in enumerate(lines):
            line = raw_line.strip()
            if tracker.consume(line):
                continue
            if line.startswith('#'):
                continue
            if line.lower().startswith('data_'):
                if start is not None:
                    return start, i
                if line[5:].lower() == block_name.lower():
                    start = i
        if start is None:
            return 0, len(lines)
        return start, len(lines)

    def _get_check_lines(self):
        """Return (lines, offset) for the current check scope.

        ``lines`` is the scoped document as a line list; ``offset`` is the
        absolute line number of its first line in the full document (0 when
        unscoped), for user-facing line references.
        """
        all_lines = self.text_editor.toPlainText().splitlines()
        scope = self._check_block_scope
        if not scope:
            return all_lines, 0
        start, end = self._locate_block_span(all_lines, scope)
        return all_lines[start:end], start

    def _get_check_text(self) -> str:
        """Return the text of the current check scope (whole document if unscoped)."""
        lines, _ = self._get_check_lines()
        return '\n'.join(lines)

    def _set_check_lines(self, lines) -> None:
        """Write scoped lines back, splicing into the full document if scoped."""
        scope = self._check_block_scope
        if not scope:
            self._set_editor_text('\n'.join(lines))
            return
        all_lines = self.text_editor.toPlainText().splitlines()
        start, end = self._locate_block_span(all_lines, scope)
        self._set_editor_text('\n'.join(all_lines[:start] + list(lines) + all_lines[end:]))

    def _set_check_text(self, text: str) -> None:
        """Text counterpart of _set_check_lines."""
        self._set_check_lines(text.splitlines())

    def _get_scoped_field_value(self, field_name):
        """Field lookup honouring the active block scope.

        Used by IF conditions and CALCULATE so they see only the block being
        checked; falls back to the parser's flat whole-file view when
        unscoped. The caller is responsible for keeping the parser current
        (ensure_parser_current).
        """
        scope = self._check_block_scope
        if scope:
            block = self.cif_parser.get_block(scope)
            return block.get_field_value(field_name) if block else None
        return self.cif_parser.get_field_value(field_name)

    def _check_block_label(self):
        """Banner text naming the scoped block for input dialogs (None when unscoped)."""
        scope = self._check_block_scope
        return f"Data block: data_{scope}" if scope else None

    def _get_check_progress(self) -> CheckProgressTracker:
        """Return the tracker for the currently running check pass.

        Lazily creates an inert zero-total tracker (advance()s are cheap
        no-ops that never produce a visible indicator) when called outside
        a run started via start_checks - e.g. from tests that call the
        rule-execution methods directly.
        """
        tracker = getattr(self, '_check_progress', None)
        if tracker is None:
            tracker = CheckProgressTracker()
            self._check_progress = tracker
        return tracker

    def _get_active_field_rules_path(self) -> str:
        """Return the currently selected .cif_rules source path, if any."""
        if hasattr(self, 'radio_builtin') and self.radio_builtin.isChecked():
            item_data = self.builtin_combo.currentData() if hasattr(self, 'builtin_combo') else None
            if isinstance(item_data, dict):
                return item_data.get('path', '') or ''

        if hasattr(self, 'radio_user') and self.radio_user.isChecked():
            if hasattr(self, 'user_combo'):
                return self.user_combo.currentData() or ''

        if getattr(self, 'current_field_set', None) == 'Custom':
            return getattr(self, 'custom_field_rules_file', '') or ''

        return getattr(self, 'custom_field_rules_file', '') or ''

    def _load_rules_content_into_current_field_set(self, rules_content: str) -> None:
        """Load rules content into the active field set via a temporary .cif_rules file."""
        import tempfile

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cif_rules', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(rules_content)
                temp_path = temp_file.name

            self.field_checker.load_field_set(self.current_field_set, temp_path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _build_converted_rules_suggestion_path(self, source_rules_path: str, target_notation: str) -> str:
        """Build a default output filename for converted rules."""
        base, ext = os.path.splitext(source_rules_path)
        if not ext:
            ext = '.cif_rules'

        if base.endswith('_legacy') and target_notation == 'modern':
            suggested_base = base[:-7]
        elif base.endswith('_modern') and target_notation == 'legacy':
            suggested_base = base[:-7]
        else:
            suggested_base = f"{base}_{target_notation}"

        return f"{suggested_base}{ext}"

    def _prompt_rules_notation_mismatch_action(
        self,
        cif_notation: str,
        rules_notation: str,
    ) -> str:
        """Prompt user for how to handle CIF/rules notation mismatch."""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Notation Mismatch: CIF vs Field Rules")
        msg_box.setText(
            f"Loaded CIF notation: {cif_notation}\n"
            f"Selected .cif_rules notation: {rules_notation}\n\n"
            "Choose how to proceed before running checks:"
        )

        convert_rules_btn = msg_box.addButton(
            f"Convert Rules to {cif_notation} and Run Checks",
            QMessageBox.ButtonRole.AcceptRole,
        )
        convert_cif_btn = msg_box.addButton(
            f"Convert CIF to {rules_notation} and Run Checks",
            QMessageBox.ButtonRole.AcceptRole,
        )
        run_as_is_btn = msg_box.addButton(
            "Run Checks As Is (Discouraged)",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_btn = msg_box.addButton(
            "Cancel",
            QMessageBox.ButtonRole.RejectRole,
        )
        msg_box.setDefaultButton(convert_rules_btn)

        msg_box.exec()
        clicked = msg_box.clickedButton()
        if clicked == convert_rules_btn:
            return 'convert_rules'
        if clicked == convert_cif_btn:
            return 'convert_cif'
        if clicked == run_as_is_btn:
            return 'run_as_is'
        if clicked == cancel_btn:
            return 'cancel'
        return 'cancel'

    def _resolve_rules_cif_notation_mismatch_before_checks(self) -> bool:
        """
        Detect CIF/rules notation mismatch and apply a user-selected strategy.

        Returns:
            True to continue checks, False to abort.
        """
        cif_content = self.text_editor.toPlainText()
        cif_notation = self.dict_manager.detect_notation(cif_content)
        if cif_notation not in {FieldNotation.LEGACY, FieldNotation.MODERN}:
            return True

        rules_path = self._get_active_field_rules_path()
        if not rules_path:
            return True

        try:
            with open(rules_path, 'r', encoding='utf-8') as file_handle:
                rules_content = file_handle.read()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Field Rules Read Error",
                f"Could not read selected field rules file:\n{rules_path}\n\n{exc}"
            )
            return False

        rules_notation = CIFFormatAnalyzer.analyze_cif_format(rules_content).lower()
        if rules_notation not in {'legacy', 'modern'}:
            return True

        cif_notation_str = 'legacy' if cif_notation == FieldNotation.LEGACY else 'modern'
        if cif_notation_str == rules_notation:
            return True

        action = self._prompt_rules_notation_mismatch_action(cif_notation_str, rules_notation)
        if action == 'cancel':
            return False
        if action == 'run_as_is':
            return True

        if action == 'convert_cif':
            if rules_notation == 'modern':
                converted_cif, changes = self.format_converter.convert_to_modern_notation(cif_content)
            else:
                converted_cif, changes = self.format_converter.convert_to_legacy_notation(cif_content)

            if converted_cif != cif_content:
                self._set_editor_text(converted_cif)
                self.modified = True
                QMessageBox.information(
                    self,
                    "CIF Converted",
                    f"Converted CIF to {rules_notation} notation before checks.\n"
                    f"Applied {len(changes)} change(s)."
                )
            return True

        # action == 'convert_rules'
        converted_rules, changes = self.field_rules_validator.convert_field_rules_notation(
            rules_content,
            cif_notation_str,
        )
        self._load_rules_content_into_current_field_set(converted_rules)

        save_reply = QMessageBox.question(
            self,
            "Save Converted Field Rules",
            f"Converted selected rules to {cif_notation_str} notation for this run.\n\n"
            "Do you also want to save the converted .cif_rules file?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if save_reply == QMessageBox.StandardButton.Yes:
            suggested_path = self._build_converted_rules_suggestion_path(rules_path, cif_notation_str)
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Converted Field Rules",
                suggested_path,
                "Field Rules Files (*.cif_rules);;All Files (*)",
            )
            if save_path:
                try:
                    with open(save_path, 'w', encoding='utf-8') as file_handle:
                        file_handle.write(converted_rules)
                    QMessageBox.information(
                        self,
                        "Field Rules Saved",
                        f"Saved converted rules to:\n{save_path}"
                    )
                except Exception as exc:
                    QMessageBox.warning(
                        self,
                        "Save Error",
                        f"Could not save converted rules:\n{exc}"
                    )

        QMessageBox.information(
            self,
            "Field Rules Converted",
            f"Using rules converted to {cif_notation_str} notation for this check run.\n"
            f"Applied {len(changes)} conversion note(s)."
        )
        return True

    def convert_selected_field_rules_notation(self):
        """Convert a selected .cif_rules file between legacy and modern notation."""
        active_rules_path = self._get_active_field_rules_path()
        default_dir = os.path.dirname(active_rules_path) if active_rules_path else ""
        rules_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Field Rules File to Convert",
            default_dir,
            "Field Rules Files (*.cif_rules);;All Files (*)",
        )
        if not rules_path:
            return

        try:
            with open(rules_path, 'r', encoding='utf-8') as file_handle:
                rules_content = file_handle.read()
        except Exception as exc:
            QMessageBox.warning(self, "Read Error", f"Could not read rules file:\n{exc}")
            return

        current_notation = CIFFormatAnalyzer.analyze_cif_format(rules_content).lower()
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Convert Field Rules Notation")
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setText(
            f"Selected file: {os.path.basename(rules_path)}\n"
            f"Detected notation: {current_notation}\n\n"
            "Choose target notation:"
        )

        to_modern_btn = msg_box.addButton("Convert to Modern", QMessageBox.ButtonRole.AcceptRole)
        to_legacy_btn = msg_box.addButton("Convert to Legacy", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()

        clicked = msg_box.clickedButton()
        if clicked == cancel_btn:
            return
        if clicked == to_modern_btn:
            target_notation = 'modern'
        elif clicked == to_legacy_btn:
            target_notation = 'legacy'
        else:
            return

        if current_notation == target_notation:
            QMessageBox.information(
                self,
                "No Conversion Needed",
                f"Selected rules are already in {target_notation} notation."
            )
            return

        converted_rules, changes = self.field_rules_validator.convert_field_rules_notation(
            rules_content,
            target_notation,
        )

        suggested_path = self._build_converted_rules_suggestion_path(rules_path, target_notation)
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Converted Field Rules",
            suggested_path,
            "Field Rules Files (*.cif_rules);;All Files (*)",
        )
        if not save_path:
            return

        try:
            with open(save_path, 'w', encoding='utf-8') as file_handle:
                file_handle.write(converted_rules)
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Failed to save converted rules:\n{exc}")
            return

        QMessageBox.information(
            self,
            "Conversion Complete",
            f"Saved converted rules to:\n{save_path}\n\n"
            f"Recorded {len(changes)} conversion note(s)."
        )

    def check_line(self, prefix, default_value=None, multiline=False, description="", suggestions=None, progress=None):
        """Check and potentially update a CIF field value."""
        removable_chars = "'"
        lines, line_offset = self._get_check_lines()

        for i, line in enumerate(lines):
            parts = line.split(None, 1)
            if parts and parts[0] == prefix:
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
                    f"Line {i + 1 + line_offset}:\n{line}\n\nDescription: {description}\n\nSuggested value: {default_value}\n\n",
                    current_value, default_value, operation_type=operation_type, suggestions=suggestions,
                    show_dialog_fn=lambda d: self._show_dialog_with_configured_interaction(
                        d, "dialogs.field_check_edit_mode"
                    ),
                    block_label=self._check_block_label(), progress=progress)

                if result in [RESULT_ABORT, RESULT_STOP_SAVE]:
                    return result
                elif result == QDialog.DialogCode.Accepted and value:
                    # Update the field value properly
                    self.update_field_value(lines, i, prefix, value)
                    self._set_check_lines(lines)
                return result

        QMessageBox.warning(self, "Line Not Found",
                          f"The line starting with '{prefix}' was not found.")
        return self.add_missing_line(prefix, lines, default_value, multiline, description, suggestions, progress=progress)

    def add_missing_line(self, prefix, lines, default_value=None, multiline=False, description="", suggestions=None, progress=None):
        """Add a missing CIF field with value."""
        value, result = CIFInputDialog.getText(
            self, "Add Missing Line",
            f"Data name '{prefix}' is missing.\n\nDescription: {description}\nSuggested value: {default_value}",
            default_value if default_value else "", default_value, operation_type="add", suggestions=suggestions,
            show_dialog_fn=lambda d: self._show_dialog_with_configured_interaction(
                d, "dialogs.field_check_edit_mode"
            ),
            block_label=self._check_block_label(), progress=progress)

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

        self._set_check_lines(lines)
        return result
    
    def check_line_with_config(self, prefix, default_value=None, multiline=False, description="", config=None, suggestions=None, progress=None):
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
        lines, line_offset = self._get_check_lines()

        # Check if field exists
        field_found = False
        for i, line in enumerate(lines):
            parts = line.split(None, 1)
            if parts and parts[0] == prefix:
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
                    f"Line {i + 1 + line_offset}:\n{line}\n\nDescription: {description}\n\nSuggested value: {default_value}\n\n",
                    current_value, default_value, operation_type=operation_type, suggestions=suggestions,
                    show_dialog_fn=lambda d: self._show_dialog_with_configured_interaction(
                        d, "dialogs.field_check_edit_mode"
                    ),
                    block_label=self._check_block_label(), progress=progress)

                if result in [RESULT_ABORT, RESULT_STOP_SAVE]:
                    return result
                elif result == QDialog.DialogCode.Accepted and value:
                    # Update the field value properly
                    self.update_field_value(lines, i, prefix, value)
                    self._set_check_lines(lines)
                return result

        # Field not found - handle missing field
        if not field_found:
            return self.add_missing_line_with_config(prefix, lines, default_value, multiline, description, config, suggestions, progress=progress)

        return QDialog.DialogCode.Accepted

    def add_missing_line_with_config(self, prefix, lines, default_value=None, multiline=False, description="", config=None, suggestions=None, progress=None):
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

            self._set_check_lines(lines)
            return QDialog.DialogCode.Accepted

        # Otherwise, use the normal missing line dialog
        return self.add_missing_line(prefix, lines, default_value, multiline, description, suggestions, progress=progress)
    
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

        # With an active block scope, look the fields up in (and insert into)
        # that data block only; unscoped, use the flat whole-file view.
        block_view = self.cif_parser.get_block(self._check_block_scope) if self._check_block_scope else None
        fields_view = block_view.fields if block_view else self.cif_parser.fields

        # Check if the deprecated field exists
        if deprecated_field not in fields_view:
            QMessageBox.warning(
                self,
                "Field Not Found",
                f"Could not find deprecated field '{deprecated_field}'"
            )
            return QDialog.DialogCode.Rejected

        # Check if modern field already exists
        if modern_field in fields_view:
            QMessageBox.information(
                self,
                "Already Present",
                f"The modern equivalent '{modern_field}' is already present in the CIF.\n\n"
                f"Both the deprecated field '{deprecated_field}' and its modern equivalent exist."
            )
            return QDialog.DialogCode.Accepted

        # Get the current value of the deprecated field
        deprecated_field_obj = fields_view[deprecated_field]
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
        fields_view[modern_field] = modern_field_obj
        if block_view is not None:
            self.cif_parser.fields.setdefault(modern_field, modern_field_obj)

        # Find the deprecated field's entry (searching only the scoped block's
        # entries when scoped - the entry dicts are shared with the parser's
        # flat list, so the index lookup below targets the right occurrence)
        search_entries = block_view.content_blocks if block_view else self.cif_parser.content_blocks
        for entry in search_entries:
            if entry['type'] == 'field' and getattr(entry['content'], 'name', None) == deprecated_field:
                insert_at = self.cif_parser.content_blocks.index(entry) + 1
                self.cif_parser.content_blocks.insert(
                    insert_at, {'type': 'field', 'content': modern_field_obj})
                break
        
        # Generate updated CIF content and update the text editor
        updated_content = self.cif_parser.generate_cif_content()
        self._set_editor_text(updated_content)
        self._check_duplicate_data_names("adding deprecated successor data names", block_on_conflicts=False)
        
        QMessageBox.information(
            self, 
            "Modern Field Added", 
            f"Added modern equivalent '{modern_field}' with the same value as '{deprecated_field}'.\n\n"
            f"Both fields now exist in the CIF for maximum compatibility."
        )
        return QDialog.DialogCode.Accepted
    
    def check_refine_special_details(self):
        """Check and edit _refine_special_details, block by block for multi-block files."""
        self.cif_parser.parse_file(self.text_editor.toPlainText())
        if not self.cif_parser.has_multiple_blocks():
            return self._check_refine_special_details_in_scope()

        for block_name in self.cif_parser.get_block_names():
            self._active_check_block = block_name
            try:
                result = self._check_refine_special_details_in_scope()
            finally:
                self._active_check_block = None
            if result in [RESULT_ABORT, RESULT_STOP_SAVE]:
                return result
        return QDialog.DialogCode.Accepted

    def _check_refine_special_details_in_scope(self):
        """Edit _refine_special_details within the current check scope (one
        data block during scoped runs, the whole document otherwise)."""
        content = self._get_check_text()

        # Parse only the scoped content, so field lookup and rewriting are
        # confined to the block being edited
        scope_parser = CIFParser()
        scope_parser.parse_file(content)

        # Detect data name notation to determine the correct data name
        detected_version = self.dict_manager.detect_notation(content)

        # Determine the appropriate field name based on notation
        if detected_version == FieldNotation.MODERN:
            field_name = '_refine.special_details'
        elif detected_version == FieldNotation.MIXED:
            # For MIXED format, check which field actually exists in the content
            if scope_parser.get_field_value('_refine.special_details') is not None:
                field_name = '_refine.special_details'
            elif scope_parser.get_field_value('_refine_special_details') is not None:
                field_name = '_refine_special_details'
            else:
                # Neither exists, so decide based on the predominant format
                # Check if this looks more like modern format by counting modern vs legacy fields
                all_fields = list(scope_parser.fields.keys())
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
        current_value = scope_parser.get_field_value(field_name)
        if current_value is None:
            current_value = template

        # Open dialog for editing
        dialog = MultilineInputDialog(current_value, self,
                                      block_label=self._check_block_label())
        dialog.setWindowTitle("Edit Refinement Special Details")
        result = self._show_dialog_with_configured_interaction(dialog)

        if result in [RESULT_ABORT, RESULT_STOP_SAVE]:
            return result
        elif result == QDialog.DialogCode.Accepted:
            updated_content = dialog.getText()

            # Update the field in the parser using the appropriate field name
            scope_parser.set_field_value(field_name, updated_content)

            # Regenerate the scoped content and write it back (trailing blank
            # line keeps blocks visually separated in scoped runs, since
            # generate_cif_content trims trailing empties)
            updated_cif = scope_parser.generate_cif_content()
            if self._check_block_scope:
                updated_cif += '\n'
            self._set_check_text(updated_cif)
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

        if not self._resolve_rules_cif_notation_mismatch_before_checks():
            return

        # Mandatory validation before starting checks (if not done already)
        if not self._ensure_field_rules_validated():
            return  # User cancelled or validation failed

        # Detect data blocks so multi-block files get block selection in the
        # config dialog (checks then run per selected block, in file order)
        self.cif_parser.parse_file(self.text_editor.toPlainText())
        block_names = self.cif_parser.get_block_names() if self.cif_parser.has_multiple_blocks() else None

        # Show configuration dialog first
        config_dialog = CheckConfigDialog(self, block_names=block_names)
        if self._show_dialog_with_configured_interaction(config_dialog) != QDialog.DialogCode.Accepted:
            return  # User cancelled

        # Get configuration settings
        config = config_dialog.get_config()

        # Store the initial state for potential restore
        initial_state = self.text_editor.toPlainText()

        # Set up the whole-run progress tracker (status bar + per-dialog
        # "Check N/Total" banners). `total` is an upper-bound estimate - see
        # check_progress.py - covering the field-rule pass plus one coarse
        # step per data block for each of the other pipeline phases below;
        # it grows on the fly if a run needs more steps than predicted.
        scopes = self._check_scopes(config)
        shared_mode = len(scopes) > 1 and (config.get('block_mode') or 'independent') == 'shared'
        fields_for_count = self.field_checker.get_field_set(self.current_field_set) or []
        rule_steps = count_rule_steps(fields_for_count)
        field_pass_steps = rule_steps if shared_mode else rule_steps * max(len(scopes), 1)

        estimated_total = field_pass_steps + len(scopes)  # + absolute-structure checks
        if config.get('validate_data_names', True):
            estimated_total += 1
        if config.get('check_duplicates_aliases', True):
            estimated_total += len(scopes)
        estimated_total += len(scopes)  # audit-creation-method update

        self._check_progress = CheckProgressTracker()
        if hasattr(self, 'update_check_progress'):
            self._check_progress.on_change(self.update_check_progress)
        self._check_progress.reset(estimated_total)

        # Suspend debounced/background compliance refreshes for the duration of
        # the check run. The loop rewrites the editor after every field, and each
        # rewrite would otherwise re-validate the whole file on a background
        # thread between dialogs. A single refresh runs when the batch completes.
        self._begin_compliance_batch()
        try:
            # PRE-CHECK: Validate data names against dictionaries (if enabled)
            # This now includes malformed field detection (e.g. _diffrn_flux_density → _diffrn.flux_density)
            if config.get('validate_data_names', True):
                validation_success = self._validate_data_names_before_checks()
                if not validation_success:
                    return  # User cancelled or aborted
                self._check_progress.advance(1)

            # Single field set processing
            success = self._process_single_field_set(config, initial_state)
            if not success:
                return

            # Check for duplicates and aliases LAST (if enabled), per selected
            # block: duplicates matter within a block, not across blocks
            if config.get('check_duplicates_aliases', True):
                for scope in self._check_scopes(config):
                    self._active_check_block = scope
                    try:
                        duplicate_check_success = self._check_duplicates_and_aliases(initial_state)
                    finally:
                        self._active_check_block = None
                    if not duplicate_check_success:
                        return  # User aborted or there was an error
                    self._check_progress.advance(1)

            # Update _audit_creation_method to include CIVET info after
            # successful checks, in every block that was checked
            for scope in self._check_scopes(config):
                self._active_check_block = scope
                try:
                    content = self._get_check_text()
                    cif_format = self.dict_manager.detect_cif_format(content)
                    updated_content = update_audit_creation_method(content, cif_format)
                    if updated_content != content:
                        self._set_check_text(updated_content)
                        self.modified = True
                finally:
                    self._active_check_block = None
                self._check_progress.advance(1)

            # If we get here, checks completed successfully
            if config.get('reformat_after_checks', False):
                self.reformat_file()
        finally:
            self._end_compliance_batch()
            self._check_progress.reset(0)  # clear the indicator

        self.update_window_title()
        QMessageBox.information(self, "Checks Complete", "Field checking completed successfully!")

    def _check_scopes(self, config):
        """Return the block scopes a check run iterates over.

        A list of block codes for multi-block runs (the blocks selected in
        the config dialog), or ``[None]`` meaning "whole document" for
        single-block files.
        """
        selected = config.get('selected_blocks')
        return list(selected) if selected else [None]

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
            
            summary += "\nThese fields use malformed data-name notation. "
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
                    self._set_editor_text(fixed_content)
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

    def _apply_action_rule(self, field_def, action, operations_applied):
        """Apply one DELETE/EDIT/APPEND/RENAME rule within the current scope.

        Returns True if the document was modified. Operation-summary entries
        are prefixed with the block name during scoped runs.
        """
        scope = self._check_block_scope
        op_prefix = f"data_{scope}: " if scope else ""
        lines, _ = self._get_check_lines()
        done = False
        if action == 'DELETE':
            lines, done = self.field_checker._delete_field(lines, field_def.name)
            if done:
                operations_applied.append(f"{op_prefix}DELETED: {field_def.name}")
        elif action == 'EDIT':
            lines, done = self.field_checker._edit_field(lines, field_def.name, field_def.default_value)
            if done:
                operations_applied.append(f"{op_prefix}EDITED: {field_def.name} → {field_def.default_value}")
        elif action == 'APPEND':
            lines, done = self.field_checker._append_field(lines, field_def.name, field_def.default_value)
            if done:
                operations_applied.append(f"{op_prefix}APPENDED to {field_def.name}")
        elif action == 'RENAME':
            lines, done = self.field_checker._rename_field(lines, field_def.name, field_def.rename_to)
            if done:
                operations_applied.append(f"{op_prefix}RENAMED: {field_def.name} → {field_def.rename_to}")
        if done:
            self._set_check_lines(lines)
        return done

    # ------------------------------------------------------------------
    # Shared (divergence-driven) multi-block execution
    #
    # In shared mode one rule pass covers all selected blocks: each field's
    # current value is collected from every block first, and a single prompt
    # is shown when they all agree (the resolution is applied to every
    # block). When values differ, the per-block MultiBlockValueDialog is
    # shown instead - one value is never silently applied over diverging
    # ones. See .github/multi_data_block_plan.md, sections 2.3/2.4.
    # ------------------------------------------------------------------

    def _blocks_banner(self, blocks):
        """Dialog banner naming the blocks a shared prompt applies to."""
        if len(blocks) == 1:
            return f"Data block: data_{blocks[0]}"
        names = ", ".join(f"data_{block}" for block in blocks)
        if len(names) > 70:
            names = names[:67] + "…"
        return f"All {len(blocks)} selected blocks: {names}"

    def _abort_run(self, initial_state):
        """Revert everything and report the abort; returns the 'abort' signal."""
        self._set_editor_text(initial_state)
        self.update_window_title()
        QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
        return 'abort'

    def _apply_value_in_block(self, block, field_name, value):
        """Set a field's value inside one data block (update in place, or
        append at the end of the block if the field is missing there)."""
        saved_scope = self._check_block_scope
        self._active_check_block = block
        try:
            lines, _ = self._get_check_lines()
            for i, line in enumerate(lines):
                parts = line.split(None, 1)
                if parts and parts[0] == field_name:
                    self.update_field_value(lines, i, field_name, value)
                    self._set_check_lines(lines)
                    return
            value_str = str(value).strip("'")
            if '\n' in value_str:
                lines.append(f"{field_name} \n;\n{value_str}\n;")
            else:
                if ' ' in value_str or ',' in value_str:
                    value_str = f"'{value_str}'"
                lines.append(f"{field_name} {value_str}")
            self._set_check_lines(lines)
        finally:
            self._active_check_block = saved_scope

    def _run_rule_per_block(self, field_def, blocks, config, initial_state,
                            ensure_parser_current, operations_applied, is_custom_or_user):
        """Fall back to scoped per-block execution of one rule (used by shared
        mode for CALCULATE, deprecated fields, and multiline divergence)."""
        for block in blocks:
            self._active_check_block = block
            try:
                signal = self._execute_rule(
                    field_def, config, initial_state, ensure_parser_current,
                    operations_applied, is_custom_or_user
                )
            finally:
                self._active_check_block = None
            if signal != 'continue':
                return signal
        return 'continue'

    def _execute_rule_shared(self, field_def, blocks, config, initial_state,
                             ensure_parser_current, operations_applied, is_custom_or_user):
        """Execute one rule across several data blocks in shared mode.

        Returns the same 'continue'/'stop'/'abort' signals as _execute_rule.
        """
        action = getattr(field_def, 'action', 'CHECK')

        # Action rules apply to every block, silently (same result as
        # running them independently per block)
        if action in ('DELETE', 'EDIT', 'APPEND', 'RENAME'):
            self._get_check_progress().advance(1)
            if not is_custom_or_user:
                return 'continue'
            modified = False
            for block in blocks:
                self._active_check_block = block
                try:
                    modified = self._apply_action_rule(field_def, action, operations_applied) or modified
                finally:
                    self._active_check_block = None
            if modified:
                ensure_parser_current()
            return 'continue'

        # IF: evaluate the condition per block; nested rules run shared
        # across the subset of blocks where it holds
        if action == 'IF':
            ensure_parser_current()
            condition = getattr(field_def, 'condition', None)
            if condition is None:
                return 'continue'
            matching = []
            for block in blocks:
                block_view = self.cif_parser.get_block(block)
                get_value = block_view.get_field_value if block_view else (lambda _name: None)
                if evaluate_condition(condition, get_value):
                    matching.append(block)
            if not matching:
                return 'continue'
            for nested_def in getattr(field_def, 'then_fields', None) or []:
                signal = self._execute_rule_shared(
                    nested_def, matching, config, initial_state,
                    ensure_parser_current, operations_applied, is_custom_or_user
                )
                if signal != 'continue':
                    return signal
            return 'continue'

        # CALCULATE always runs per block: its inputs (and hence results)
        # legitimately differ between blocks
        if action == 'CALCULATE':
            return self._run_rule_per_block(
                field_def, blocks, config, initial_state,
                ensure_parser_current, operations_applied, is_custom_or_user)

        # CHECK - deprecated fields keep their special add-modern-equivalent
        # flow, which is inherently per block
        if self.dict_manager.is_field_deprecated(field_def.name):
            return self._run_rule_per_block(
                field_def, blocks, config, initial_state,
                ensure_parser_current, operations_applied, is_custom_or_user)

        ensure_parser_current()
        values = {}
        for block in blocks:
            block_view = self.cif_parser.get_block(block)
            values[block] = block_view.get_field_value(field_def.name) if block_view else None

        # Multiline values don't fit the per-row divergence dialog; use the
        # normal scoped prompts per block instead
        if any(value is not None and '\n' in str(value) for value in values.values()):
            return self._run_rule_per_block(
                field_def, blocks, config, initial_state,
                ensure_parser_current, operations_applied, is_custom_or_user)

        self._get_check_progress().advance(1)
        distinct_values = set(values.values())
        if len(distinct_values) == 1:
            common_value = next(iter(distinct_values))
            if common_value is None:
                return self._shared_add_missing(field_def, blocks, config, initial_state)
            return self._shared_check_common(field_def, blocks, common_value, config, initial_state)
        return self._shared_resolve_divergent(field_def, blocks, values, initial_state)

    def _shared_check_common(self, field_def, blocks, common_value, config, initial_state):
        """One prompt for a field whose value agrees across all blocks; the
        resolution is applied to every block."""
        default_value = field_def.default_value
        clean_current = str(common_value).strip().strip("'\"")
        clean_default = str(default_value).strip().strip("'\"") if default_value else ""

        if config.get('skip_matching_defaults', False) and default_value and clean_current == clean_default:
            return 'continue'

        operation_type = "edit"
        if default_value and clean_current and clean_current != clean_default:
            operation_type = "different"

        value, result = CIFInputDialog.getText(
            self, "Edit Line",
            f"'{field_def.name}' has the same value in all selected data blocks.\n\n"
            f"Current value: {common_value}\n\nDescription: {field_def.description}\n\n"
            f"Suggested value: {default_value}\n\n",
            clean_current, default_value, operation_type=operation_type,
            suggestions=getattr(field_def, 'suggestions', None),
            show_dialog_fn=lambda d: self._show_dialog_with_configured_interaction(
                d, "dialogs.field_check_edit_mode"
            ),
            block_label=self._blocks_banner(blocks), progress=self._get_check_progress().snapshot())

        if result == RESULT_ABORT:
            return self._abort_run(initial_state)
        if result in (QDialog.DialogCode.Accepted, RESULT_STOP_SAVE) and value:
            for block in blocks:
                self._apply_value_in_block(block, field_def.name, value)
        if result == RESULT_STOP_SAVE:
            return 'stop'
        return 'continue'

    def _shared_add_missing(self, field_def, blocks, config, initial_state):
        """One prompt for a field missing from every selected block; the value
        is added to each of them."""
        default_value = field_def.default_value

        if config.get('auto_fill_missing', False) and default_value:
            for block in blocks:
                self._apply_value_in_block(block, field_def.name, str(default_value).strip("'"))
            return 'continue'

        value, result = CIFInputDialog.getText(
            self, "Add Missing Line",
            f"Data name '{field_def.name}' is missing in all selected data blocks.\n\n"
            f"Description: {field_def.description}\nSuggested value: {default_value}",
            default_value if default_value else "", default_value, operation_type="add",
            suggestions=getattr(field_def, 'suggestions', None),
            show_dialog_fn=lambda d: self._show_dialog_with_configured_interaction(
                d, "dialogs.field_check_edit_mode"
            ),
            block_label=self._blocks_banner(blocks), progress=self._get_check_progress().snapshot())

        if result == RESULT_ABORT:
            return self._abort_run(initial_state)
        if result in (QDialog.DialogCode.Accepted, RESULT_STOP_SAVE):
            for block in blocks:
                self._apply_value_in_block(block, field_def.name, value if value else "?")
        if result == RESULT_STOP_SAVE:
            return 'stop'
        return 'continue'

    def _shared_resolve_divergent(self, field_def, blocks, values, initial_state):
        """Per-block resolution for a field whose values differ between blocks."""
        values_dict, result = MultiBlockValueDialog.getValues(
            self, field_def.name, values, field_def.default_value, field_def.description,
            show_dialog_fn=lambda d: self._show_dialog_with_configured_interaction(
                d, "dialogs.field_check_edit_mode"
            ), progress=self._get_check_progress().snapshot())

        if result == RESULT_ABORT:
            return self._abort_run(initial_state)
        if result in (QDialog.DialogCode.Accepted, RESULT_STOP_SAVE) and values_dict:
            for block, new_value in values_dict.items():
                if not str(new_value).strip():
                    continue  # empty entry: leave this block unchanged/missing
                old_value = values.get(block)
                if old_value is not None and str(new_value) == str(old_value):
                    continue  # unchanged
                self._apply_value_in_block(block, field_def.name, new_value)
        if result == RESULT_STOP_SAVE:
            return 'stop'
        return 'continue'

    def _execute_rule(self, field_def, config, initial_state, ensure_parser_current,
                       operations_applied, is_custom_or_user):
        """Execute a single parsed rule: an action (DELETE/EDIT/APPEND/RENAME), a
        CHECK/CALCULATE prompt, or an IF/THEN conditional block.

        Called once per top-level rule by _process_single_field_set, and recursively
        for each nested rule inside an IF block's then_fields.

        Returns:
            'continue' to proceed to the next rule,
            'stop' to stop the run while keeping changes made so far (RESULT_STOP_SAVE),
            'abort' if the run was aborted (editor already restored to initial_state).
        """
        action = getattr(field_def, 'action', 'CHECK')

        # A rule is one pipeline step whether or not it ends up producing a
        # visible dialog (see check_progress.py); IF itself isn't a step -
        # its nested rules are, and each will advance when reached below.
        if action != 'IF':
            self._get_check_progress().advance(1)

        # --- Action rules (custom/user sets only) ---
        if action in ('DELETE', 'EDIT', 'APPEND', 'RENAME'):
            if not is_custom_or_user:
                return 'continue'  # Action rules are only applied for custom/user sets
            if self._apply_action_rule(field_def, action, operations_applied):
                ensure_parser_current()
            return 'continue'

        # --- IF / THEN conditional block ---
        if action == 'IF':
            ensure_parser_current()
            condition = getattr(field_def, 'condition', None)
            if condition is None or not evaluate_condition(condition, self._get_scoped_field_value):
                return 'continue'

            for nested_def in getattr(field_def, 'then_fields', None) or []:
                signal = self._execute_rule(
                    nested_def, config, initial_state, ensure_parser_current,
                    operations_applied, is_custom_or_user
                )
                if signal != 'continue':
                    return signal
            return 'continue'

        # --- CHECK / CALCULATE ---
        suggested_value = field_def.default_value
        description = field_def.description
        suggestions = getattr(field_def, 'suggestions', None)

        if action == 'CALCULATE' and hasattr(field_def, 'expression'):
            # Re-parse only if content changed since the last CALCULATE evaluation.
            ensure_parser_current()

            # Extract field references from expression
            field_refs = re.findall(r'_[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)*', field_def.expression)
            field_values = {}
            missing_fields = []

            for ref in field_refs:
                value = self._get_scoped_field_value(ref)
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
                return 'continue'

            # Evaluate the expression
            calculated = safe_eval_expr(field_def.expression, field_values)
            if calculated is not None:
                # Format to reasonable precision
                if abs(calculated) < 0.01 or abs(calculated) >= 10000:
                    suggested_value = f"{calculated:.4e}"
                else:
                    suggested_value = f"{calculated:.4f}".rstrip('0').rstrip('.')

                # Add calculation info to description
                current_val = self._get_scoped_field_value(field_def.name)
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
                return 'continue'

        result = self.check_line_with_config(
            field_def.name,
            suggested_value,
            False,
            description,
            config,
            suggestions,
            progress=self._get_check_progress().snapshot()
        )

        if result == RESULT_ABORT:
            self._set_editor_text(initial_state)
            self.update_window_title()
            QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
            return 'abort'
        if result == RESULT_STOP_SAVE:
            return 'stop'
        return 'continue'

    def _process_single_field_set(self, config, initial_state):
        """Process a single field set (Built-in, User, or Custom)."""
        try:
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
            
            # Parse the current CIF content once and only reparse when the content changes.
            parsed_content_hash = None

            def ensure_parser_current() -> str:
                nonlocal parsed_content_hash
                current_content = self.text_editor.toPlainText()
                current_hash = hashlib.sha1(current_content.encode('utf-8')).hexdigest()
                if current_hash != parsed_content_hash:
                    self.cif_parser.parse_file(current_content)
                    parsed_content_hash = current_hash
                return current_content

            ensure_parser_current()

            # Process rules in file order (fully sequential).
            # Action rules (DELETE/EDIT/APPEND/RENAME) are applied immediately when
            # encountered and the editor is updated before moving to the next rule.
            # CHECK/CALCULATE rules then run against the current (post-action) CIF
            # state, so a RENAME followed by a CHECK for the old name will find the
            # field missing and prompt to add it, and a CHECK for the new name will
            # find the renamed value and show it for confirmation.
            #
            # For multi-block files the full rule pass (and the absolute-
            # structure checks) runs once per selected data block, with all
            # reads and writes scoped to that block.
            is_custom_or_user = self.current_field_set == 'Custom' or self.current_field_set.startswith('User:')
            operations_applied = []
            scopes = self._check_scopes(config)
            shared_mode = len(scopes) > 1 and (config.get('block_mode') or 'independent') == 'shared'
            stopped = False

            try:
                if shared_mode:
                    # One rule pass covering all selected blocks: shared
                    # prompts where values agree, per-block resolution where
                    # they diverge
                    self.setWindowTitle(
                        f"CIVET{filename_part} - Checking {len(scopes)} data blocks "
                        f"(shared) with {field_set_display_name} fields")
                    for field_def in fields:
                        signal = self._execute_rule_shared(
                            field_def, list(scopes), config, initial_state,
                            ensure_parser_current, operations_applied, is_custom_or_user
                        )
                        if signal == 'abort':
                            return False
                        if signal == 'stop':
                            stopped = True
                            break

                    # Absolute-structure checks stay per block (each block
                    # has its own space group); skipped after stop-and-save
                    if not stopped:
                        for scope in scopes:
                            self._active_check_block = scope
                            if not self._apply_absolute_structure_checks(config, initial_state):
                                return False
                            self._get_check_progress().advance(1)
                else:
                    for scope_index, scope in enumerate(scopes):
                        self._active_check_block = scope
                        if scope is not None:
                            self.setWindowTitle(
                                f"CIVET{filename_part} - Checking data_{scope} "
                                f"({scope_index + 1}/{len(scopes)}) with {field_set_display_name} fields")

                        for field_def in fields:
                            signal = self._execute_rule(
                                field_def, config, initial_state, ensure_parser_current,
                                operations_applied, is_custom_or_user
                            )
                            if signal == 'abort':
                                return False
                            if signal == 'stop':
                                stopped = True
                                break

                        if not self._apply_absolute_structure_checks(config, initial_state):
                            return False
                        self._get_check_progress().advance(1)

                        if stopped:
                            break  # Stop-and-save ends the whole run, later blocks included
            finally:
                self._active_check_block = None

            # Show summary of any silent operations that were applied
            if operations_applied:
                ops_summary = '\n'.join(operations_applied)
                QMessageBox.information(self, "Operations Applied",
                                      f"Applied {len(operations_applied)} operations:\n\n{ops_summary}")

            return True

        except Exception as e:
            self._set_editor_text(initial_state)
            self.update_window_title()
            QMessageBox.critical(self, "Error During Checks", f"An error occurred: {str(e)}")
            return False
    
    def _get_absolute_configuration_fields(self):
        """Return absolute-configuration field names matching the current CIF notation."""
        content = self.text_editor.toPlainText()
        detected_version = self.dict_manager.detect_notation(content)

        if detected_version == FieldNotation.MODERN:
            return "_chemical.absolute_configuration", "_refine_ls.abs_structure_z-score"

        return "_chemical_absolute_configuration", "_refine_ls.abs_structure_z-score"

    def _get_space_group_number(self):
        """Return the IT space-group number from the current CIF, if present.

        Honours the active check-block scope: in per-block runs each data
        block's own space group is used.
        """
        SG_number = None
        lines, _ = self._get_check_lines()

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

        return SG_number

    def _is_sohncke_space_group(self):
        """Return True when the current CIF uses a Sohncke space group."""
        space_group_number = self._get_space_group_number()
        return space_group_number in SOHNCKE_SPACE_GROUPS

    def _get_inline_field_value(self, field_name):
        """Return the first inline value found for a field, stripped of quotes.

        Honours the active check-block scope, so per-block runs only see the
        block being checked.
        """
        lines, _ = self._get_check_lines()

        for index, line in enumerate(lines):
            if line.startswith(field_name):
                return self.extract_field_value(lines, index, field_name).strip().strip("'\"")

        return None

    def _is_electron_diffraction_data(self):
        """Detect electron-diffraction data from CIF content rather than rule-set choice."""
        probe_fields = (
            "_diffrn_radiation.probe",
            "_diffrn_radiation_probe",
        )
        for field_name in probe_fields:
            field_value = self._get_inline_field_value(field_name)
            if field_value and field_value.lower() == "electron":
                return True

        method_fields = (
            "_diffrn_measurement.method",
            "_diffrn_measurement_method",
        )
        for field_name in method_fields:
            field_value = self._get_inline_field_value(field_name)
            if field_value and "electron diffraction" in field_value.lower():
                return True

        return False

    def _get_radiation_probe(self):
        """Return the radiation probe field name and value, if present."""
        probe_fields = (
            "_diffrn_radiation.probe",
            "_diffrn_radiation_probe",
        )
        for field_name in probe_fields:
            field_value = self._get_inline_field_value(field_name)
            if field_value:
                return field_name, field_value

        return None, None

    def _apply_absolute_configuration_check(self, config, initial_state):
        """Ensure absolute configuration is checked for Sohncke space groups."""
        if not self._is_sohncke_space_group():
            return None

        abs_config_field, _ = self._get_absolute_configuration_fields()
        lines, _ = self._get_check_lines()

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
                self._set_editor_text(initial_state)
                self.update_window_title()
                QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                return False
            if result == RESULT_STOP_SAVE:
                return None
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
                self._set_editor_text(initial_state)
                self.update_window_title()
                QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                return False
            if result == RESULT_STOP_SAVE:
                return None

        lines, _ = self._get_check_lines()
        for line in lines:
            if line.startswith(abs_config_field):
                parts = line.split()
                if len(parts) > 1:
                    return parts[1].strip("'\"")
                break

        return None

    def _apply_abs_structure_z_score_check(self, config, initial_state):
        """Check the z-score field for electron-diffraction dynamical refinement."""
        _, z_score_field = self._get_absolute_configuration_fields()
        lines, _ = self._get_check_lines()
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
                self._set_editor_text(initial_state)
                self.update_window_title()
                QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                return False
            if result == RESULT_STOP_SAVE:
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
                self._set_editor_text(initial_state)
                self.update_window_title()
                QMessageBox.information(self, "Checks Aborted", "All changes have been reverted.")
                return False
            if result == RESULT_STOP_SAVE:
                return True

        return True

    def _apply_absolute_structure_checks(self, config, initial_state):
        """Apply Sohncke and electron-diffraction-specific absolute-structure checks."""
        absolute_config_value = self._apply_absolute_configuration_check(config, initial_state)

        if absolute_config_value is False:
            return False

        if absolute_config_value == 'dyn':
            probe_field, probe_value = self._get_radiation_probe()
            if (probe_value and probe_value.lower() != 'electron'
                    and config.get('show_warnings', True)):
                QMessageBox.warning(
                    self,
                    "Absolute Structure Warning",
                    f"{probe_field} is set to '{probe_value}', but absolute configuration is set to 'dyn'.\n\n"
                    "This combination is inconsistent: 'dyn' should only be used for electron-diffraction data."
                )

        if absolute_config_value == 'dyn' and self._is_electron_diffraction_data():
            return self._apply_abs_structure_z_score_check(config, initial_state)
        
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
            # Scoped to the active data block during per-block runs: duplicates
            # are a problem within a block, not across blocks (each block
            # legitimately repeats the same data names).
            content = self._get_check_text()

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
            
            # Show dialog with scrollable content, honoring configured editor
            # interaction behavior (browse/edit the main editor while open).
            issues_dialog = CriticalIssuesDialog(detailed_conflicts, deprecated_fields, self)
            raw_result = self._show_dialog_with_configured_interaction(
                issues_dialog, "dialogs.critical_issues_mode"
            )
            if raw_result == 2:  # Custom cancel code
                dialog_result = 0
            elif raw_result == QDialog.DialogCode.Accepted:
                dialog_result = 1
            else:
                dialog_result = 2
            
            if dialog_result == 0:  # Cancel
                # User wants to abort - restore initial state
                self._set_editor_text(initial_state)
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
                    content = self._get_check_text()
                
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
                    self._set_check_text(resolved_content)
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
