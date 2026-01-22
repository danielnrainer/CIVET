"""
Data Name Validation Dialog
===========================

Dialog for displaying CIF data name validation results and allowing users
to take actions on unknown, deprecated, and other field categories.
"""

from typing import Dict, List, Optional, Set
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QPushButton, QComboBox, QGroupBox, QWidget, QDialogButtonBox, QFrame,
    QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from utils.data_name_validator import (
    ValidationReport, FieldValidationResult, FieldCategory, FieldAction, DataNameValidator
)


class DataNameValidationDialog(QDialog):
    """
    Dialog for displaying CIF data name validation results.
    
    This dialog shows categorized validation results (valid, registered local,
    unknown, deprecated fields) and allows users to take actions on each field
    such as allowing prefixes, deleting fields, or updating deprecated fields.
    """
    
    # Category display configuration
    CATEGORY_CONFIG = {
        FieldCategory.UNKNOWN: {
            'icon': '⚠',
            'color': '#e67e22',  # Orange
            'label': 'Unknown Fields',
            'expanded': True,
        },
        FieldCategory.DEPRECATED: {
            'icon': '⚡',
            'color': '#9b59b6',  # Purple
            'label': 'Deprecated Fields',
            'expanded': True,
        },
        FieldCategory.REGISTERED_LOCAL: {
            'icon': 'ⓘ',
            'color': '#3498db',  # Blue
            'label': 'Registered Local Fields',
            'expanded': False,
        },
        FieldCategory.USER_ALLOWED: {
            'icon': '👤',
            'color': '#27ae60',  # Green
            'label': 'User Allowed Fields',
            'expanded': False,
        },
        FieldCategory.VALID: {
            'icon': '✓',
            'color': '#27ae60',  # Green
            'label': 'Valid Fields',
            'expanded': False,
        },
    }
    
    def __init__(
        self,
        validation_report: ValidationReport,
        validator: DataNameValidator,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the DataNameValidationDialog.
        
        Args:
            validation_report: ValidationReport containing results to display
            validator: DataNameValidator to apply user actions
            parent: Parent widget
        """
        super().__init__(parent)
        self.validation_report = validation_report
        self.validator = validator
        
        # Track pending actions
        self._pending_actions: Dict[str, FieldAction] = {}
        self._fields_to_delete: Set[str] = set()
        self._deprecated_updates: Dict[str, str] = {}  # old_name -> new_name
        self._format_corrections: Dict[str, str] = {}  # old_name -> corrected_name
        self._prefixes_to_allow: Set[str] = set()
        self._fields_to_allow: Set[str] = set()
        
        # Tree item references for updating UI after actions
        self._field_items: Dict[str, QTreeWidgetItem] = {}
        self._category_items: Dict[FieldCategory, QTreeWidgetItem] = {}
        
        self._setup_ui()
        self._populate_tree()
    
    def _setup_ui(self) -> None:
        """Build the dialog UI."""
        self.setWindowTitle("CIF Data Name Validation Results")
        self.setModal(True)
        self.setMinimumSize(750, 550)
        self.resize(850, 650)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Summary section
        self._create_summary_section(layout)
        
        # Filter section
        self._create_filter_section(layout)
        
        # Tree widget for categorized fields
        self._create_tree_section(layout)
        
        # Allowed prefixes section
        self._create_allowed_prefixes_section(layout)
        
        # Dialog buttons
        self._create_button_section(layout)
    
    def _create_summary_section(self, layout: QVBoxLayout) -> None:
        """Create the summary bar with counts."""
        summary_frame = QFrame()
        summary_frame.setFrameShape(QFrame.Shape.StyledPanel)
        summary_frame.setStyleSheet("QFrame { background-color: palette(base); padding: 8px; }")
        
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(12, 8, 12, 8)
        
        # Total count
        total_label = QLabel(f"<b>Summary:</b> {self.validation_report.total_fields} fields checked")
        summary_layout.addWidget(total_label)
        
        summary_layout.addStretch()
        
        # Category counts with icons
        counts = [
            (FieldCategory.VALID, len(self.validation_report.valid_fields)),
            (FieldCategory.REGISTERED_LOCAL, len(self.validation_report.registered_local_fields)),
            (FieldCategory.USER_ALLOWED, len(self.validation_report.user_allowed_fields)),
            (FieldCategory.UNKNOWN, len(self.validation_report.unknown_fields)),
            (FieldCategory.DEPRECATED, len(self.validation_report.deprecated_fields)),
        ]
        
        for category, count in counts:
            if count > 0:
                config = self.CATEGORY_CONFIG[category]
                count_label = QLabel(
                    f"<span style='color: {config['color']};'>{config['icon']}</span> {count}"
                )
                count_label.setToolTip(f"{count} {config['label'].lower()}")
                summary_layout.addWidget(count_label)
        
        layout.addWidget(summary_frame)
    
    def _create_filter_section(self, layout: QVBoxLayout) -> None:
        """Create the filter dropdown."""
        filter_layout = QHBoxLayout()
        
        filter_label = QLabel("Filter:")
        filter_layout.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All Categories", None)
        
        # Add categories that have items
        if self.validation_report.unknown_fields:
            self.filter_combo.addItem(
                f"⚠ Unknown ({len(self.validation_report.unknown_fields)})",
                FieldCategory.UNKNOWN
            )
        if self.validation_report.deprecated_fields:
            self.filter_combo.addItem(
                f"⚡ Deprecated ({len(self.validation_report.deprecated_fields)})",
                FieldCategory.DEPRECATED
            )
        if self.validation_report.registered_local_fields:
            self.filter_combo.addItem(
                f"ⓘ Registered Local ({len(self.validation_report.registered_local_fields)})",
                FieldCategory.REGISTERED_LOCAL
            )
        if self.validation_report.user_allowed_fields:
            self.filter_combo.addItem(
                f"👤 User Allowed ({len(self.validation_report.user_allowed_fields)})",
                FieldCategory.USER_ALLOWED
            )
        if self.validation_report.valid_fields:
            self.filter_combo.addItem(
                f"✓ Valid ({len(self.validation_report.valid_fields)})",
                FieldCategory.VALID
            )
        
        self.filter_combo.setMinimumWidth(200)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_combo)
        
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
    
    def _create_tree_section(self, layout: QVBoxLayout) -> None:
        """Create the tree widget for displaying categorized fields."""
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Field", "Details"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 350)
        self.tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout.addWidget(self.tree, stretch=1)
    
    def _create_allowed_prefixes_section(self, layout: QVBoxLayout) -> None:
        """Create the allowed prefixes information section."""
        prefixes_group = QGroupBox("Allowed Prefixes")
        prefixes_layout = QHBoxLayout(prefixes_group)
        
        # Get current allowed prefixes
        allowed = self.validator.get_allowed_prefixes()
        if allowed:
            prefixes_text = ", ".join(sorted(allowed))
        else:
            prefixes_text = "(none)"
        
        self.prefixes_label = QLabel(f"Currently allowed: <b>{prefixes_text}</b>")
        prefixes_layout.addWidget(self.prefixes_label)
        
        prefixes_layout.addStretch()
        
        manage_button = QPushButton("Manage...")
        manage_button.setToolTip("Manage allowed prefixes and fields")
        manage_button.clicked.connect(self._on_manage_prefixes)
        prefixes_layout.addWidget(manage_button)
        
        layout.addWidget(prefixes_group)
    
    def _create_button_section(self, layout: QVBoxLayout) -> None:
        """Create the dialog buttons."""
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.apply_button = QPushButton("Apply Changes")
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self._on_apply_changes)
        self._update_apply_button()
        button_layout.addWidget(self.apply_button)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def _populate_tree(self) -> None:
        """Fill the tree with validation results."""
        self.tree.clear()
        self._field_items.clear()
        self._category_items.clear()
        
        # Order categories: unknown and deprecated first (expanded), then others
        category_order = [
            (FieldCategory.UNKNOWN, self.validation_report.unknown_fields),
            (FieldCategory.DEPRECATED, self.validation_report.deprecated_fields),
            (FieldCategory.REGISTERED_LOCAL, self.validation_report.registered_local_fields),
            (FieldCategory.USER_ALLOWED, self.validation_report.user_allowed_fields),
            (FieldCategory.VALID, self.validation_report.valid_fields),
        ]
        
        for category, fields in category_order:
            if not fields:
                continue
            
            config = self.CATEGORY_CONFIG[category]
            
            # Create category item
            category_item = QTreeWidgetItem([
                f"{config['icon']} {config['label']} ({len(fields)})",
                ""
            ])
            
            # Style category header
            font = QFont()
            font.setBold(True)
            category_item.setFont(0, font)
            category_item.setForeground(0, QColor(config['color']))
            
            self.tree.addTopLevelItem(category_item)
            self._category_items[category] = category_item
            
            # Add field items
            for field_result in fields:
                self._create_field_item(category_item, field_result, category)
            
            # Set expansion state
            category_item.setExpanded(config['expanded'])
    
    def _create_field_item(
        self,
        parent_item: QTreeWidgetItem,
        field_result: FieldValidationResult,
        category: FieldCategory
    ) -> None:
        """
        Create a tree item for a field with action buttons.
        
        Args:
            parent_item: Parent tree widget item (category)
            field_result: Validation result for this field
            category: The field's category
        """
        # Create field item
        details = field_result.description
        if field_result.line_number > 0:
            details = f"(line {field_result.line_number}) {details}"
        if field_result.modern_equivalent:
            details += f" → {field_result.modern_equivalent}"
        if field_result.suggested_dictionary:
            details += f" (try loading: {field_result.suggested_dictionary})"
        
        field_item = QTreeWidgetItem([field_result.field_name, details])
        parent_item.addChild(field_item)
        
        self._field_items[field_result.field_name.lower()] = field_item
        
        # Create widget with action buttons
        button_widget = self._create_action_buttons(field_result, category)
        self.tree.setItemWidget(field_item, 1, button_widget)
    
    def _create_action_buttons(
        self,
        field_result: FieldValidationResult,
        category: FieldCategory
    ) -> QWidget:
        """
        Create action buttons for a field based on its category.
        
        Args:
            field_result: Validation result for this field
            category: The field's category
            
        Returns:
            QWidget containing the action buttons
        """
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        
        # Add description label
        details = field_result.description
        if field_result.line_number > 0:
            details = f"(line {field_result.line_number}) {details}"
        if field_result.modern_equivalent:
            details += f" → {field_result.modern_equivalent}"
        if field_result.suggested_dictionary:
            details += f" (try: {field_result.suggested_dictionary})"
        
        label = QLabel(details)
        label.setStyleSheet("color: gray;")
        layout.addWidget(label)
        
        layout.addStretch()
        
        field_name = field_result.field_name
        prefix = field_result.prefix
        # Use embedded_prefix if available (for category extensions like _chemical_oxdiff_formula)
        effective_prefix = field_result.embedded_prefix if field_result.embedded_prefix else prefix
        
        if category == FieldCategory.UNKNOWN:
            # Correct format button (if format suggestion is available for embedded prefixes)
            if field_result.suggested_format:
                correct_btn = QPushButton(f"Correct to {field_result.suggested_format}")
                correct_btn.setToolTip(f"Apply correct dot notation: {field_result.suggested_format}")
                correct_btn.setStyleSheet("color: #27ae60;")  # Green
                correct_btn.clicked.connect(
                    lambda checked, fn=field_name, sf=field_result.suggested_format: 
                        self._on_correct_format(fn, sf)
                )
                layout.addWidget(correct_btn)
            
            # Allow prefix button (if prefix exists - use embedded_prefix if available)
            if effective_prefix:
                allow_prefix_btn = QPushButton(f"Allow _{effective_prefix}_")
                allow_prefix_btn.setToolTip(f"Add '{effective_prefix}' to allowed prefixes list")
                allow_prefix_btn.clicked.connect(
                    lambda checked, fn=field_name, p=effective_prefix: self._on_allow_prefix(fn, p)
                )
                layout.addWidget(allow_prefix_btn)
            
            # Allow field button
            allow_field_btn = QPushButton("Allow field")
            allow_field_btn.setToolTip("Add this specific field to allowed list")
            allow_field_btn.clicked.connect(
                lambda checked, fn=field_name: self._on_allow_field(fn)
            )
            layout.addWidget(allow_field_btn)
            
            # Delete button
            delete_btn = QPushButton("Delete")
            delete_btn.setToolTip("Mark this field for deletion from CIF")
            delete_btn.setStyleSheet("color: #c0392b;")
            delete_btn.clicked.connect(
                lambda checked, fn=field_name: self._on_delete_field(fn)
            )
            layout.addWidget(delete_btn)
            
            # Ignore button
            ignore_btn = QPushButton("Ignore")
            ignore_btn.setToolTip("Ignore this field for this session only")
            ignore_btn.clicked.connect(
                lambda checked, fn=field_name: self._on_ignore_field(fn)
            )
            layout.addWidget(ignore_btn)
        
        elif category == FieldCategory.DEPRECATED:
            modern_name = field_result.modern_equivalent
            
            # Update button (if modern equivalent exists)
            if modern_name:
                update_btn = QPushButton(f"Update to {modern_name}")
                update_btn.setToolTip(f"Replace with modern equivalent: {modern_name}")
                update_btn.clicked.connect(
                    lambda checked, fn=field_name, mn=modern_name: self._on_update_deprecated(fn, mn)
                )
                layout.addWidget(update_btn)
            
            # Keep button
            keep_btn = QPushButton("Keep as-is")
            keep_btn.setToolTip("Keep the deprecated field name")
            keep_btn.clicked.connect(
                lambda checked, fn=field_name: self._on_keep_deprecated(fn)
            )
            layout.addWidget(keep_btn)
        
        elif category == FieldCategory.REGISTERED_LOCAL:
            # Info only - no actions needed but could allow adding to user allowed
            if prefix:
                allow_prefix_btn = QPushButton(f"Add _{prefix}_ to allowed")
                allow_prefix_btn.setToolTip("Add this registered prefix to your personal allowed list")
                allow_prefix_btn.clicked.connect(
                    lambda checked, fn=field_name, p=prefix: self._on_allow_prefix(fn, p)
                )
                layout.addWidget(allow_prefix_btn)
        
        return container
    
    def _on_allow_prefix(self, field_name: str, prefix: str) -> None:
        """
        Handle allow prefix button click.
        
        Args:
            field_name: The field that triggered this action
            prefix: The prefix to allow
        """
        self._prefixes_to_allow.add(prefix.lower())
        self._pending_actions[field_name.lower()] = FieldAction.ALLOW_PREFIX
        
        # Update UI to show pending action
        self._mark_field_as_handled(field_name, f"Will allow prefix '{prefix}'")
        self._update_apply_button()
        self._update_prefixes_label()
    
    def _on_allow_field(self, field_name: str) -> None:
        """
        Handle allow field button click.
        
        Args:
            field_name: The field to allow
        """
        self._fields_to_allow.add(field_name.lower())
        self._pending_actions[field_name.lower()] = FieldAction.ALLOW_FIELD
        
        # Update UI to show pending action
        self._mark_field_as_handled(field_name, "Will allow this field")
        self._update_apply_button()
    
    def _on_delete_field(self, field_name: str) -> None:
        """
        Mark field for deletion.
        
        Args:
            field_name: The field to delete
        """
        self._fields_to_delete.add(field_name.lower())
        self._pending_actions[field_name.lower()] = FieldAction.DELETE
        
        # Update UI to show pending action
        self._mark_field_as_handled(field_name, "Marked for deletion", color="#c0392b")
        self._update_apply_button()
    
    def _on_ignore_field(self, field_name: str) -> None:
        """
        Add field to session-ignored list.
        
        Args:
            field_name: The field to ignore
        """
        self._pending_actions[field_name.lower()] = FieldAction.IGNORE_SESSION
        
        # Update UI to show pending action
        self._mark_field_as_handled(field_name, "Will ignore for this session")
        self._update_apply_button()
    
    def _on_correct_format(self, field_name: str, suggested_format: str) -> None:
        """
        Mark field for format correction (fix embedded local prefix notation).
        
        Args:
            field_name: The field with incorrect format
            suggested_format: The corrected field name with proper dot notation
        """
        self._format_corrections[field_name.lower()] = suggested_format
        self._pending_actions[field_name.lower()] = FieldAction.CORRECT_FORMAT
        
        # Update UI to show pending action
        self._mark_field_as_handled(
            field_name, 
            f"Will correct to {suggested_format}", 
            color="#27ae60"
        )
        self._update_apply_button()
    
    def _on_update_deprecated(self, field_name: str, modern_name: str) -> None:
        """
        Mark deprecated field for update to modern equivalent.
        
        Args:
            field_name: The deprecated field name
            modern_name: The modern replacement name
        """
        self._deprecated_updates[field_name.lower()] = modern_name
        self._pending_actions[field_name.lower()] = FieldAction.KEEP  # Using KEEP as placeholder
        
        # Update UI to show pending action
        self._mark_field_as_handled(field_name, f"Will update to {modern_name}", color="#27ae60")
        self._update_apply_button()
    
    def _on_keep_deprecated(self, field_name: str) -> None:
        """
        Mark deprecated field to keep as-is.
        
        Args:
            field_name: The field to keep
        """
        self._pending_actions[field_name.lower()] = FieldAction.KEEP
        
        # Update UI to show pending action
        self._mark_field_as_handled(field_name, "Will keep as-is")
        self._update_apply_button()
    
    def _mark_field_as_handled(
        self,
        field_name: str,
        status_text: str,
        color: str = "#27ae60"
    ) -> None:
        """
        Update the tree item to show it has been handled.
        
        Args:
            field_name: The field name
            status_text: Status text to display
            color: Color for the status text
        """
        field_item = self._field_items.get(field_name.lower())
        if field_item:
            # Replace the button widget with a status label
            status_widget = QWidget()
            status_layout = QHBoxLayout(status_widget)
            status_layout.setContentsMargins(4, 2, 4, 2)
            
            status_label = QLabel(f"<span style='color: {color};'>{status_text}</span>")
            status_layout.addWidget(status_label)
            
            # Add undo button
            undo_btn = QPushButton("Undo")
            undo_btn.setToolTip("Undo this action")
            undo_btn.clicked.connect(
                lambda checked, fn=field_name: self._on_undo_action(fn)
            )
            status_layout.addWidget(undo_btn)
            
            status_layout.addStretch()
            
            self.tree.setItemWidget(field_item, 1, status_widget)
    
    def _on_undo_action(self, field_name: str) -> None:
        """
        Undo a pending action on a field.
        
        Args:
            field_name: The field to undo action for
        """
        field_name_lower = field_name.lower()
        
        # Remove from pending actions
        self._pending_actions.pop(field_name_lower, None)
        self._fields_to_delete.discard(field_name_lower)
        self._deprecated_updates.pop(field_name_lower, None)
        self._format_corrections.pop(field_name_lower, None)
        self._fields_to_allow.discard(field_name_lower)
        
        # Find the original field result to restore buttons
        field_result = self._find_field_result(field_name)
        if field_result:
            # Check if we should remove the prefix from pending
            if field_result.prefix and field_result.prefix.lower() in self._prefixes_to_allow:
                # Only remove if no other field with same prefix has pending action
                other_fields_with_prefix = [
                    fn for fn in self._pending_actions.keys()
                    if self._find_field_result(fn) and 
                    self._find_field_result(fn).prefix.lower() == field_result.prefix.lower()
                ]
                if not other_fields_with_prefix:
                    self._prefixes_to_allow.discard(field_result.prefix.lower())
            
            # Restore the action buttons
            field_item = self._field_items.get(field_name_lower)
            if field_item:
                button_widget = self._create_action_buttons(field_result, field_result.category)
                self.tree.setItemWidget(field_item, 1, button_widget)
        
        self._update_apply_button()
        self._update_prefixes_label()
    
    def _find_field_result(self, field_name: str) -> Optional[FieldValidationResult]:
        """
        Find the FieldValidationResult for a given field name.
        
        Args:
            field_name: The field name to find
            
        Returns:
            The FieldValidationResult if found, None otherwise
        """
        field_name_lower = field_name.lower()
        
        all_fields = (
            self.validation_report.unknown_fields +
            self.validation_report.deprecated_fields +
            self.validation_report.registered_local_fields +
            self.validation_report.user_allowed_fields +
            self.validation_report.valid_fields
        )
        
        for result in all_fields:
            if result.field_name.lower() == field_name_lower:
                return result
        
        return None
    
    def _on_filter_changed(self, index: int) -> None:
        """
        Handle filter dropdown change.
        
        Args:
            index: Selected index in the combo box
        """
        selected_category = self.filter_combo.currentData()
        
        for category, item in self._category_items.items():
            if selected_category is None:
                # Show all categories
                item.setHidden(False)
            else:
                # Show only selected category
                item.setHidden(category != selected_category)
    
    def _on_manage_prefixes(self) -> None:
        """Open dialog to manage allowed prefixes and fields."""
        # Get current lists
        allowed_prefixes = self.validator.get_allowed_prefixes()
        allowed_fields = self.validator.get_allowed_fields()
        
        # Build message with current settings
        msg_parts = []
        
        if allowed_prefixes:
            msg_parts.append(f"<b>Allowed Prefixes:</b><br>{'<br>'.join(sorted(allowed_prefixes))}")
        else:
            msg_parts.append("<b>Allowed Prefixes:</b> (none)")
        
        if allowed_fields:
            msg_parts.append(f"<b>Allowed Fields:</b><br>{'<br>'.join(sorted(allowed_fields))}")
        else:
            msg_parts.append("<b>Allowed Fields:</b> (none)")
        
        if self._prefixes_to_allow:
            msg_parts.append(
                f"<b>Pending Prefix Additions:</b><br>{'<br>'.join(sorted(self._prefixes_to_allow))}"
            )
        
        if self._fields_to_allow:
            msg_parts.append(
                f"<b>Pending Field Additions:</b><br>{'<br>'.join(sorted(self._fields_to_allow))}"
            )
        
        msg_parts.append(
            "<br><i>Click 'Apply Changes' to save pending additions, "
            "or use the action buttons on individual fields to add new items.</i>"
        )
        
        QMessageBox.information(
            self,
            "Allowed Prefixes & Fields",
            "<br><br>".join(msg_parts)
        )
    
    def _update_apply_button(self) -> None:
        """Update the apply button state based on pending actions."""
        has_changes = bool(
            self._pending_actions or
            self._fields_to_delete or
            self._deprecated_updates or
            self._format_corrections or
            self._prefixes_to_allow or
            self._fields_to_allow
        )
        
        if has_changes:
            count = len(self._pending_actions)
            self.apply_button.setText(f"Apply Changes ({count})")
            self.apply_button.setEnabled(True)
        else:
            self.apply_button.setText("Apply Changes")
            self.apply_button.setEnabled(False)
    
    def _update_prefixes_label(self) -> None:
        """Update the allowed prefixes label."""
        current = self.validator.get_allowed_prefixes()
        pending = self._prefixes_to_allow
        
        all_prefixes = current | pending
        
        if all_prefixes:
            parts = []
            for p in sorted(all_prefixes):
                if p in pending and p not in current:
                    parts.append(f"<span style='color: #27ae60;'>{p} (pending)</span>")
                else:
                    parts.append(p)
            prefixes_text = ", ".join(parts)
        else:
            prefixes_text = "(none)"
        
        self.prefixes_label.setText(f"Currently allowed: {prefixes_text}")
    
    def _on_apply_changes(self) -> None:
        """Apply all pending changes and close the dialog."""
        # Apply prefix additions
        for prefix in self._prefixes_to_allow:
            self.validator.add_allowed_prefix(prefix)
        
        # Apply field additions
        for field in self._fields_to_allow:
            self.validator.add_allowed_field(field)
        
        # Apply session ignores
        for field_name, action in self._pending_actions.items():
            if action == FieldAction.IGNORE_SESSION:
                self.validator.add_session_ignored(field_name)
        
        self.accept()
    
    def get_pending_actions(self) -> Dict[str, FieldAction]:
        """
        Get all pending actions.
        
        Returns:
            Dict mapping field names to their pending actions
        """
        return self._pending_actions.copy()
    
    def get_fields_to_delete(self) -> List[str]:
        """
        Get list of fields marked for deletion.
        
        Returns:
            List of field names to delete from CIF
        """
        return list(self._fields_to_delete)
    
    def get_deprecated_updates(self) -> Dict[str, str]:
        """
        Get deprecated field update mappings.
        
        Returns:
            Dict mapping old field names to new field names
        """
        return self._deprecated_updates.copy()
    
    def get_format_corrections(self) -> Dict[str, str]:
        """
        Get format correction mappings for embedded local prefixes.
        
        Returns:
            Dict mapping incorrectly formatted field names to corrected names
        """
        return self._format_corrections.copy()
