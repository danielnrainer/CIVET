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
    QSizePolicy, QMessageBox, QInputDialog, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from utils.data_name_validator import (
    ValidationReport, FieldValidationResult, FieldCategory, FieldAction, DataNameValidator
)


class ManagePrefixesDialog(QDialog):
    """Dialog for managing allowed prefixes and fields."""
    
    def __init__(
        self,
        validator: DataNameValidator,
        pending_prefixes: Set[str],
        pending_fields: Set[str],
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.validator = validator
        self.pending_prefixes = pending_prefixes.copy()
        self.pending_fields = pending_fields.copy()
        
        # Track additions and removals
        self.prefixes_to_add: Set[str] = set()
        self.prefixes_to_remove: Set[str] = set()
        self.fields_to_add: Set[str] = set()
        self.fields_to_remove: Set[str] = set()
        
        self._setup_ui()
        self._populate_lists()
    
    def _setup_ui(self) -> None:
        """Build the dialog UI."""
        self.setWindowTitle("Manage Allowed Prefixes & Fields")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Prefixes section
        prefixes_group = QGroupBox("Allowed Prefixes")
        prefixes_layout = QVBoxLayout(prefixes_group)
        
        self.prefixes_list = QListWidget()
        self.prefixes_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        prefixes_layout.addWidget(self.prefixes_list)
        
        prefix_btn_layout = QHBoxLayout()
        add_prefix_btn = QPushButton("Add Prefix...")
        add_prefix_btn.clicked.connect(self._on_add_prefix)
        prefix_btn_layout.addWidget(add_prefix_btn)
        
        self.remove_prefix_btn = QPushButton("Remove Selected")
        self.remove_prefix_btn.clicked.connect(self._on_remove_prefix)
        self.remove_prefix_btn.setEnabled(False)
        prefix_btn_layout.addWidget(self.remove_prefix_btn)
        
        prefix_btn_layout.addStretch()
        prefixes_layout.addLayout(prefix_btn_layout)
        
        layout.addWidget(prefixes_group)
        
        # Fields section
        fields_group = QGroupBox("Allowed Fields")
        fields_layout = QVBoxLayout(fields_group)
        
        self.fields_list = QListWidget()
        self.fields_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        fields_layout.addWidget(self.fields_list)
        
        field_btn_layout = QHBoxLayout()
        add_field_btn = QPushButton("Add Field...")
        add_field_btn.clicked.connect(self._on_add_field)
        field_btn_layout.addWidget(add_field_btn)
        
        self.remove_field_btn = QPushButton("Remove Selected")
        self.remove_field_btn.clicked.connect(self._on_remove_field)
        self.remove_field_btn.setEnabled(False)
        field_btn_layout.addWidget(self.remove_field_btn)
        
        field_btn_layout.addStretch()
        fields_layout.addLayout(field_btn_layout)
        
        layout.addWidget(fields_group)
        
        # Connect selection changes
        self.prefixes_list.itemSelectionChanged.connect(self._on_prefix_selection_changed)
        self.fields_list.itemSelectionChanged.connect(self._on_field_selection_changed)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _populate_lists(self) -> None:
        """Populate the lists with current and pending items."""
        # Prefixes
        self.prefixes_list.clear()
        current_prefixes = self.validator.get_allowed_prefixes()
        
        for prefix in sorted(current_prefixes):
            item = QListWidgetItem(prefix)
            item.setData(Qt.ItemDataRole.UserRole, ("current", prefix))
            self.prefixes_list.addItem(item)
        
        for prefix in sorted(self.pending_prefixes - current_prefixes):
            item = QListWidgetItem(f"{prefix} (pending)")
            item.setForeground(QColor("#27ae60"))
            item.setData(Qt.ItemDataRole.UserRole, ("pending", prefix))
            self.prefixes_list.addItem(item)
        
        # Fields
        self.fields_list.clear()
        current_fields = self.validator.get_allowed_fields()
        
        for field in sorted(current_fields):
            item = QListWidgetItem(field)
            item.setData(Qt.ItemDataRole.UserRole, ("current", field))
            self.fields_list.addItem(item)
        
        for field in sorted(self.pending_fields - current_fields):
            item = QListWidgetItem(f"{field} (pending)")
            item.setForeground(QColor("#27ae60"))
            item.setData(Qt.ItemDataRole.UserRole, ("pending", field))
            self.fields_list.addItem(item)
    
    def _on_prefix_selection_changed(self) -> None:
        """Enable/disable remove button based on selection."""
        self.remove_prefix_btn.setEnabled(bool(self.prefixes_list.selectedItems()))
    
    def _on_field_selection_changed(self) -> None:
        """Enable/disable remove button based on selection."""
        self.remove_field_btn.setEnabled(bool(self.fields_list.selectedItems()))
    
    def _on_add_prefix(self) -> None:
        """Add a new prefix."""
        text, ok = QInputDialog.getText(
            self,
            "Add Prefix",
            "Enter prefix name (without underscores):",
            text=""
        )
        if ok and text.strip():
            prefix = text.strip().lower().strip('_')
            if prefix:
                self.prefixes_to_add.add(prefix)
                self.prefixes_to_remove.discard(prefix)
                self.pending_prefixes.add(prefix)
                self._populate_lists()
    
    def _on_remove_prefix(self) -> None:
        """Remove the selected prefix."""
        items = self.prefixes_list.selectedItems()
        if items:
            data = items[0].data(Qt.ItemDataRole.UserRole)
            if data:
                status, prefix = data
                if status == "current":
                    self.prefixes_to_remove.add(prefix)
                else:
                    self.pending_prefixes.discard(prefix)
                    self.prefixes_to_add.discard(prefix)
                self._populate_lists()
    
    def _on_add_field(self) -> None:
        """Add a new field."""
        text, ok = QInputDialog.getText(
            self,
            "Add Field",
            "Enter field name (e.g., _my_custom_field):",
            text="_"
        )
        if ok and text.strip():
            field = text.strip().lower()
            if not field.startswith('_'):
                field = '_' + field
            self.fields_to_add.add(field)
            self.fields_to_remove.discard(field)
            self.pending_fields.add(field)
            self._populate_lists()
    
    def _on_remove_field(self) -> None:
        """Remove the selected field."""
        items = self.fields_list.selectedItems()
        if items:
            data = items[0].data(Qt.ItemDataRole.UserRole)
            if data:
                status, field = data
                if status == "current":
                    self.fields_to_remove.add(field)
                else:
                    self.pending_fields.discard(field)
                    self.fields_to_add.discard(field)
                self._populate_lists()
    
    def get_prefix_changes(self) -> tuple[Set[str], Set[str]]:
        """Get prefix additions and removals."""
        return self.prefixes_to_add, self.prefixes_to_remove
    
    def get_field_changes(self) -> tuple[Set[str], Set[str]]:
        """Get field additions and removals."""
        return self.fields_to_add, self.fields_to_remove
    
    def get_updated_pending(self) -> tuple[Set[str], Set[str]]:
        """Get updated pending sets."""
        return self.pending_prefixes, self.pending_fields


class DataNameValidationDialog(QDialog):
    """
    Dialog for displaying CIF data name validation results.
    
    This dialog shows categorized validation results (valid, registered local,
    unknown, deprecated fields) and allows users to take actions on each field
    such as allowing prefixes, deleting fields, or updating deprecated fields.
    
    The dialog supports applying changes without closing - it emits the
    changes_requested signal, and the caller should apply changes and call
    refresh_validation() with the new report to update the dialog contents.
    """
    
    # Emitted when user clicks "Apply Changes" - caller should apply and call refresh_validation()
    changes_requested = pyqtSignal()
    
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
            'icon': 'ℹ️',
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
            'icon': '✅',
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
        
        # Track whether any changes have been applied
        self._changes_applied = False
        
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
        
        # Total count - store reference for updates
        self.summary_total_label = QLabel(
            f"<b>Summary:</b> {self.validation_report.total_fields} fields checked"
        )
        summary_layout.addWidget(self.summary_total_label)
        
        summary_layout.addStretch()
        
        # Category counts with icons - store references for updates
        self.count_labels: Dict[FieldCategory, QLabel] = {}
        counts = [
            (FieldCategory.VALID, len(self.validation_report.valid_fields)),
            (FieldCategory.REGISTERED_LOCAL, len(self.validation_report.registered_local_fields)),
            (FieldCategory.USER_ALLOWED, len(self.validation_report.user_allowed_fields)),
            (FieldCategory.UNKNOWN, len(self.validation_report.unknown_fields)),
            (FieldCategory.DEPRECATED, len(self.validation_report.deprecated_fields)),
        ]
        
        for category, count in counts:
            config = self.CATEGORY_CONFIG[category]
            count_label = QLabel(
                f"<span style='color: {config['color']};'>{config['icon']}</span> {count}"
            )
            count_label.setToolTip(f"{count} {config['label'].lower()}")
            if count == 0:
                count_label.hide()
            summary_layout.addWidget(count_label)
            self.count_labels[category] = count_label
        
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
                f"ℹ️ Registered Local ({len(self.validation_report.registered_local_fields)})",
                FieldCategory.REGISTERED_LOCAL
            )
        if self.validation_report.user_allowed_fields:
            self.filter_combo.addItem(
                f"👤 User Allowed ({len(self.validation_report.user_allowed_fields)})",
                FieldCategory.USER_ALLOWED
            )
        if self.validation_report.valid_fields:
            self.filter_combo.addItem(
                f"✅ Valid ({len(self.validation_report.valid_fields)})",
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
        self.tree.setColumnWidth(0, 250)
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
        dialog = ManagePrefixesDialog(
            self.validator,
            self._prefixes_to_allow,
            self._fields_to_allow,
            self
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get changes from the dialog
            prefixes_to_add, prefixes_to_remove = dialog.get_prefix_changes()
            fields_to_add, fields_to_remove = dialog.get_field_changes()
            updated_prefixes, updated_fields = dialog.get_updated_pending()
            
            # Apply removals immediately (these affect saved settings)
            for prefix in prefixes_to_remove:
                self.validator.remove_allowed_prefix(prefix)
            for field in fields_to_remove:
                self.validator.remove_allowed_field(field)
            
            # Update pending sets
            self._prefixes_to_allow = updated_prefixes
            self._fields_to_allow = updated_fields
            
            # Update UI
            self._update_prefixes_label()
            self._update_apply_button()
    
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
        """Apply all pending changes without closing the dialog.
        
        Emits changes_requested signal for the caller to apply changes.
        The caller should then call refresh_validation() with new results.
        """
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
        
        # Mark that changes have been applied
        self._changes_applied = True
        
        # Emit signal for caller to apply CIF modifications and refresh
        self.changes_requested.emit()
    
    def refresh_validation(self, new_report: ValidationReport) -> None:
        """
        Refresh the dialog with new validation results.
        
        Call this after applying changes to update the dialog contents in place.
        
        Args:
            new_report: New ValidationReport after changes have been applied
        """
        self.validation_report = new_report
        
        # Clear pending actions (they've been applied)
        self._pending_actions.clear()
        self._fields_to_delete.clear()
        self._deprecated_updates.clear()
        self._format_corrections.clear()
        self._prefixes_to_allow.clear()
        self._fields_to_allow.clear()
        
        # Refresh UI
        self._update_summary_section()
        self._update_filter_section()
        self._populate_tree()
        self._update_prefixes_label()
        self._update_apply_button()
    
    def _update_summary_section(self) -> None:
        """Update the summary frame with current counts."""
        # Find and update the total label
        if hasattr(self, 'summary_total_label'):
            self.summary_total_label.setText(
                f"<b>Summary:</b> {self.validation_report.total_fields} fields checked"
            )
        
        # Update count labels
        counts = [
            (FieldCategory.VALID, len(self.validation_report.valid_fields)),
            (FieldCategory.REGISTERED_LOCAL, len(self.validation_report.registered_local_fields)),
            (FieldCategory.USER_ALLOWED, len(self.validation_report.user_allowed_fields)),
            (FieldCategory.UNKNOWN, len(self.validation_report.unknown_fields)),
            (FieldCategory.DEPRECATED, len(self.validation_report.deprecated_fields)),
        ]
        
        # Update or rebuild count labels
        if hasattr(self, 'count_labels'):
            for category, label in list(self.count_labels.items()):
                # Find new count for this category
                count = next((c for cat, c in counts if cat == category), 0)
                if count > 0:
                    config = self.CATEGORY_CONFIG[category]
                    label.setText(
                        f"<span style='color: {config['color']};'>{config['icon']}</span> {count}"
                    )
                    label.setToolTip(f"{count} {config['label'].lower()}")
                    label.show()
                else:
                    label.hide()
    
    def _update_filter_section(self) -> None:
        """Update the filter dropdown with current category counts."""
        # Remember current selection
        current_data = self.filter_combo.currentData()
        
        # Update items with new counts
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("All Categories", None)
        
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
                f"ℹ️ Registered Local ({len(self.validation_report.registered_local_fields)})",
                FieldCategory.REGISTERED_LOCAL
            )
        if self.validation_report.user_allowed_fields:
            self.filter_combo.addItem(
                f"👤 User Allowed ({len(self.validation_report.user_allowed_fields)})",
                FieldCategory.USER_ALLOWED
            )
        if self.validation_report.valid_fields:
            self.filter_combo.addItem(
                f"✅ Valid ({len(self.validation_report.valid_fields)})",
                FieldCategory.VALID
            )
        
        # Try to restore selection
        for i in range(self.filter_combo.count()):
            if self.filter_combo.itemData(i) == current_data:
                self.filter_combo.setCurrentIndex(i)
                break
        
        self.filter_combo.blockSignals(False)
    
    def has_changes_applied(self) -> bool:
        """
        Check if any changes have been applied during this dialog session.
        
        Returns:
            True if changes were applied, False otherwise
        """
        return self._changes_applied
    
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
