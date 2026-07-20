"""GUI mixin for CIF data-name integrity checks and conflict resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from PyQt6.QtWidgets import QDialog, QMessageBox

from utils.cif_data_name_integrity import (
    AliasValueMismatch,
    get_data_name_conflicts_requiring_resolution,
)
from .dialogs.field_conflict_dialog import FieldConflictDialog

if TYPE_CHECKING:
    from .main_window import CIFEditor


class DataNameIntegrityMixin:
    """Mixin providing data-name conflict checks for CIFEditor."""

    def _show_dialog_with_configured_interaction(
        self,
        dialog: QDialog,
        mode_setting_key: str = "dialogs.default_interaction_mode",
    ) -> int:
        raise NotImplementedError()

    if TYPE_CHECKING:
        # Declared for static type checkers only. The real implementation
        # lives in FormatHandlersMixin, which comes later than this mixin
        # in CIFEditor's MRO. Defining a runtime stub here (even one that
        # raises NotImplementedError) would shadow that implementation and
        # break auto-resolve for every caller, since Python resolves
        # self._auto_resolve_conflicts to the first match in MRO order.
        def _auto_resolve_conflicts(
            self,
            conflicts: Dict[str, List[str]],
            cif_content: str,
            cif_format: str = "modern",
        ) -> Dict[str, tuple]:
            ...

        # Block-scope helpers provided by FieldCheckingMixin (later in
        # CIFEditor's MRO); declared here for static type checkers only —
        # runtime stubs would shadow the real implementations.
        def _get_check_text(self) -> str: ...

        def _set_check_text(self, text: str) -> None: ...

    def _format_data_name_conflict_summary(
        self,
        conflicts: Dict[str, List[str]],
        mismatches: List[AliasValueMismatch],
        max_items: int = 8,
    ) -> str:
        """Create a concise summary of conflicts for user prompts."""
        lines: List[str] = []
        mismatch_by_canonical = {m.canonical_name: m for m in mismatches}

        items = list(conflicts.items())
        for canonical, alias_list in items[:max_items]:
            unique_aliases = sorted(set(alias_list))
            if len(unique_aliases) == 1:
                duplicate_field = unique_aliases[0]
                lines.append(f"- {duplicate_field}: appears {len(alias_list)} times")
                continue

            mismatch = mismatch_by_canonical.get(canonical)
            if mismatch:
                preview_parts: List[str] = []
                for alias in mismatch.aliases[:2]:
                    sig = mismatch.alias_signatures.get(alias, ())
                    if not sig:
                        preview = "(no value)"
                    elif sig[0] == "scalar" and len(sig) > 1:
                        preview = sig[1]
                    elif sig[0] == "loop":
                        preview = "[loop values differ]"
                    else:
                        preview = "[value differs]"
                    preview_parts.append(f"{alias}={preview}")
                preview = "; ".join(preview_parts)
                lines.append(f"- {canonical}: alias values differ ({preview})")
            else:
                joined_aliases = ", ".join(unique_aliases)
                lines.append(f"- {canonical}: {joined_aliases}")

        if len(items) > max_items:
            lines.append(f"- ... and {len(items) - max_items} more conflict(s)")

        return "\n".join(lines)

    def _check_duplicate_data_names(self, operation_name: str, block_on_conflicts: bool = False) -> bool:
        """Check and optionally resolve data-name integrity conflicts.

        Conflicts include:
        - direct duplicate data names
        - alias groups with mismatched values

        Alias groups with identical values are considered valid and are not
        flagged. For multi-block files the check runs once per data block:
        the same data name appearing in several blocks is legitimate, so
        duplicates only count within a block.
        """
        # Already inside a scoped per-block run (e.g. during field checks):
        # check just that block
        if getattr(self, '_active_check_block', None):
            return self._check_duplicate_data_names_in_scope(operation_name, block_on_conflicts)

        self.cif_parser.parse_file(self.text_editor.toPlainText())
        if not self.cif_parser.has_multiple_blocks():
            return self._check_duplicate_data_names_in_scope(operation_name, block_on_conflicts)

        for block_name in self.cif_parser.get_block_names():
            self._active_check_block = block_name
            try:
                block_ok = self._check_duplicate_data_names_in_scope(
                    f"{operation_name} (data_{block_name})", block_on_conflicts)
            finally:
                self._active_check_block = None
            if not block_ok:
                return False
        return True

    def _check_duplicate_data_names_in_scope(self, operation_name: str, block_on_conflicts: bool = False) -> bool:
        """Run the integrity check on the current check scope (one data block
        during scoped runs, the whole document otherwise)."""
        content = self._get_check_text()
        conflicts, mismatches = get_data_name_conflicts_requiring_resolution(content, self.dict_manager)

        if not conflicts:
            return True

        summary = self._format_data_name_conflict_summary(conflicts, mismatches)
        if block_on_conflicts:
            message = (
                f"Data-name integrity conflicts were found while {operation_name}.\n\n"
                f"{summary}\n\n"
                "These conflicts must be resolved before this operation can continue.\n\n"
                "Resolve now?"
            )
            proceed_reply = QMessageBox.question(
                self,
                "Data-Name Integrity Conflicts",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if proceed_reply != QMessageBox.StandardButton.Yes:
                return False
        else:
            message = (
                f"Data-name integrity conflicts were found after {operation_name}.\n\n"
                f"{summary}\n\n"
                "Resolve them now?"
            )
            proceed_reply = QMessageBox.question(
                self,
                "Data-Name Integrity Conflicts",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if proceed_reply != QMessageBox.StandardButton.Yes:
                return True

        cif_format = self.dict_manager.detect_cif_format(content)
        format_name = "legacy" if cif_format.lower() == "legacy" else "modern"
        method_reply = QMessageBox.question(
            self,
            "Choose Resolution Method",
            "How would you like to resolve data-name conflicts?\n\n"
            "- Yes: Resolve each conflict manually\n"
            f"- No: Auto-resolve using {format_name} notation and first available values\n"
            "- Cancel: Stop",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No,
        )

        if method_reply == QMessageBox.StandardButton.Cancel:
            return not block_on_conflicts

        resolutions = {}
        if method_reply == QMessageBox.StandardButton.Yes:
            dialog = FieldConflictDialog(conflicts, content, self, self.dict_manager, cif_format)
            if self._show_dialog_with_configured_interaction(dialog) == QDialog.DialogCode.Accepted:
                resolutions = dialog.get_resolutions()
            else:
                return not block_on_conflicts
        else:
            resolutions = self._auto_resolve_conflicts(conflicts, content, cif_format)

        if not resolutions:
            return not block_on_conflicts

        resolved_content, changes = self.dict_manager.apply_field_conflict_resolutions(content, resolutions)
        if changes:
            self._set_check_text(resolved_content)
            self.modified = True

        remaining_conflicts, _ = get_data_name_conflicts_requiring_resolution(
            self._get_check_text(),
            self.dict_manager,
        )
        if remaining_conflicts:
            QMessageBox.warning(
                self,
                "Conflicts Remain",
                "Some data-name conflicts could not be fully resolved."
                + ("\nThis operation will be stopped." if block_on_conflicts else "\nPlease review manually."),
            )
            return not block_on_conflicts

        if changes:
            QMessageBox.information(
                self,
                "Conflicts Resolved",
                f"Resolved {len(conflicts)} data-name conflict(s).",
            )

        return True
