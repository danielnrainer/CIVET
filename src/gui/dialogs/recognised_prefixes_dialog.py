"""
Recognised Prefixes Dialog
==========================

Dialog for displaying all CIF data name prefixes that CIVET recognises as allowed.
This includes:
- Officially registered prefixes from the IUCr registry
- User-allowed prefixes (added via validation dialog or manually)
"""

from typing import Dict, Set, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QPushButton, QGroupBox,
    QWidget, QHeaderView, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from utils.registered_prefixes import (
    get_registered_prefixes, get_prefix_info, get_prefix_data_source,
    get_all_prefix_info, fetch_and_cache_official_prefixes,
    IUCR_RESERVED_PREFIXES_URL
)
from utils.data_name_validator import DataNameValidator


class PrefixUpdateWorker(QThread):
    """Worker thread for fetching the official IUCr reserved-prefixes registry."""

    finished = pyqtSignal(bool, str)  # success, message

    def run(self):
        try:
            source = fetch_and_cache_official_prefixes()
            self.finished.emit(True, source)
        except Exception as e:
            self.finished.emit(False, str(e))


class RecognisedPrefixesDialog(QDialog):
    """
    Dialog for viewing and managing recognised CIF data name prefixes.
    
    Shows all prefixes that CIVET will accept without flagging as unknown:
    - IUCr registered prefixes (fetched from the official registry and cached)
    - User-allowed prefixes (stored in user preferences)
    """
    
    def __init__(self, validator: DataNameValidator, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.validator = validator
        self._setup_ui()
        self._populate_tree()
    
    def _setup_ui(self) -> None:
        """Build the dialog UI."""
        self.setWindowTitle("Recognised CIF Data Name Prefixes")
        self.setModal(True)
        self.setMinimumSize(600, 500)
        self.resize(700, 600)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        header_label = QLabel(
            "<b>Recognised Prefixes</b><br>"
            "These prefixes are accepted by CIVET and will not be flagged as unknown."
        )
        header_label.setWordWrap(True)
        layout.addWidget(header_label)
        
        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type to filter prefixes...")
        self.search_edit.textChanged.connect(self._filter_tree)
        self.search_edit.setClearButtonEnabled(True)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Prefix", "Description", "Source"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setSortingEnabled(True)
        
        # Set column widths
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.tree)
        
        # Summary label
        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)
        
        # Source info
        source_group = QGroupBox("Prefix Data Source")
        source_layout = QVBoxLayout(source_group)
        self.source_label = QLabel()
        self.source_label.setWordWrap(True)
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._refresh_source_label()
        source_layout.addWidget(self.source_label)
        layout.addWidget(source_group)
        
        # Button row
        button_layout = QHBoxLayout()

        # Add user prefix button
        add_prefix_btn = QPushButton("Add User Prefix...")
        add_prefix_btn.setToolTip("Add a custom prefix to your allowed list")
        add_prefix_btn.clicked.connect(self._on_add_prefix)
        button_layout.addWidget(add_prefix_btn)

        # Update registered prefixes from the official IUCr registry
        self.update_btn = QPushButton("Update from IUCr Registry")
        self.update_btn.setToolTip(f"Fetch the latest reserved-prefix list from {IUCR_RESERVED_PREFIXES_URL}")
        self.update_btn.clicked.connect(self._on_update_from_iucr)
        button_layout.addWidget(self.update_btn)

        button_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _refresh_source_label(self) -> None:
        """Update the source-info label with the current prefix data source."""
        self.source_label.setText(f"<code>{get_prefix_data_source()}</code>")

    def _on_update_from_iucr(self) -> None:
        """Fetch the latest reserved-prefix registry from IUCr in a background thread."""
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Updating...")

        self._update_worker = PrefixUpdateWorker()
        self._update_worker.finished.connect(self._on_update_finished)
        self._update_worker.start()

    def _on_update_finished(self, success: bool, message: str) -> None:
        """Handle completion of the IUCr registry update."""
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Update from IUCr Registry")

        if success:
            self.validator.clear_cache()
            self._refresh_source_label()
            self._populate_tree()
            QMessageBox.information(
                self, "Prefixes Updated",
                f"Successfully updated registered prefixes from IUCr.\n\nSource: {message}"
            )
        else:
            QMessageBox.warning(
                self, "Update Failed",
                f"Could not fetch the official prefix registry:\n\n{message}\n\n"
                "The previously loaded prefixes are unchanged."
            )

    def _populate_tree(self) -> None:
        """Populate the tree with prefix data."""
        self.tree.clear()
        
        # Get all prefixes
        registered_prefixes = get_all_prefix_info()
        user_prefixes = self.validator.get_allowed_prefixes()
        
        # Create category items
        registered_item = QTreeWidgetItem(["IUCr Registered Prefixes", "", ""])
        registered_item.setFont(0, QFont("", -1, QFont.Weight.Bold))
        registered_item.setForeground(0, QColor("#2980b9"))
        self.tree.addTopLevelItem(registered_item)
        
        user_item = QTreeWidgetItem(["User-Allowed Prefixes", "", ""])
        user_item.setFont(0, QFont("", -1, QFont.Weight.Bold))
        user_item.setForeground(0, QColor("#27ae60"))
        self.tree.addTopLevelItem(user_item)
        
        # Add registered prefixes
        for prefix in sorted(registered_prefixes.keys(), key=str.lower):
            description = registered_prefixes[prefix]
            child = QTreeWidgetItem([f"_{prefix}_", description, "IUCr Registry"])
            child.setData(0, Qt.ItemDataRole.UserRole, prefix)  # Store original prefix
            child.setData(2, Qt.ItemDataRole.UserRole, "registered")  # Category marker
            registered_item.addChild(child)
        
        # Add user-allowed prefixes
        for prefix in sorted(user_prefixes, key=str.lower):
            # Check if also registered (shouldn't be, but show if so)
            if prefix.lower() in {p.lower() for p in registered_prefixes.keys()}:
                note = "(also IUCr registered)"
            else:
                note = "User preference"
            
            child = QTreeWidgetItem([f"_{prefix}_", "Custom user-allowed prefix", note])
            child.setData(0, Qt.ItemDataRole.UserRole, prefix)
            child.setData(2, Qt.ItemDataRole.UserRole, "user")
            
            # Add remove button context
            child.setToolTip(0, "Right-click to remove from allowed list")
            user_item.addChild(child)
        
        # Expand both categories
        registered_item.setExpanded(True)
        user_item.setExpanded(True)
        
        # Update summary
        total = len(registered_prefixes) + len(user_prefixes)
        self.summary_label.setText(
            f"<b>Total recognised:</b> {total} prefixes "
            f"({len(registered_prefixes)} registered, {len(user_prefixes)} user-allowed)"
        )
        
        # Enable context menu for user prefixes
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
    
    def _filter_tree(self, search_text: str) -> None:
        """Filter the tree based on search text."""
        search_lower = search_text.lower().strip()
        
        # Get top-level items (categories)
        for i in range(self.tree.topLevelItemCount()):
            category_item = self.tree.topLevelItem(i)
            visible_children = 0
            
            # Check each child
            for j in range(category_item.childCount()):
                child = category_item.child(j)
                prefix = child.data(0, Qt.ItemDataRole.UserRole) or ""
                description = child.text(1)
                
                # Match against prefix or description
                matches = (
                    not search_lower or
                    search_lower in prefix.lower() or
                    search_lower in description.lower()
                )
                
                child.setHidden(not matches)
                if matches:
                    visible_children += 1
            
            # Hide category if no visible children
            category_item.setHidden(visible_children == 0)
    
    def _on_context_menu(self, position) -> None:
        """Handle right-click context menu."""
        item = self.tree.itemAt(position)
        if not item:
            return
        
        # Only allow removal of user prefixes
        category = item.data(2, Qt.ItemDataRole.UserRole)
        if category != "user":
            return
        
        prefix = item.data(0, Qt.ItemDataRole.UserRole)
        if not prefix:
            return
        
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        remove_action = menu.addAction(f"Remove '{prefix}' from allowed list")
        
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        if action == remove_action:
            self._remove_user_prefix(prefix)
    
    def _remove_user_prefix(self, prefix: str) -> None:
        """Remove a user prefix from the allowed list."""
        reply = QMessageBox.question(
            self,
            "Remove Prefix",
            f"Remove '{prefix}' from your allowed prefixes list?\n\n"
            "Fields using this prefix will be flagged as unknown.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.validator.remove_allowed_prefix(prefix)
            self._populate_tree()  # Refresh
    
    def _on_add_prefix(self) -> None:
        """Add a new user prefix."""
        prefix, ok = QInputDialog.getText(
            self,
            "Add User Prefix",
            "Enter a prefix to add to your allowed list:\n"
            "(without leading/trailing underscores)",
            QLineEdit.EchoMode.Normal
        )
        
        if ok and prefix:
            # Clean up the prefix
            prefix = prefix.strip().strip('_')
            
            if not prefix:
                QMessageBox.warning(self, "Invalid Prefix", "Please enter a valid prefix.")
                return
            
            # Check if already registered
            registered = get_registered_prefixes()
            if prefix.lower() in {p.lower() for p in registered}:
                QMessageBox.information(
                    self,
                    "Already Registered",
                    f"The prefix '{prefix}' is already an IUCr registered prefix."
                )
                return
            
            # Check if already in user list
            user_prefixes = self.validator.get_allowed_prefixes()
            if prefix.lower() in {p.lower() for p in user_prefixes}:
                QMessageBox.information(
                    self,
                    "Already Allowed",
                    f"The prefix '{prefix}' is already in your allowed list."
                )
                return
            
            # Add to allowed list
            self.validator.add_allowed_prefix(prefix)
            self._populate_tree()  # Refresh
            
            QMessageBox.information(
                self,
                "Prefix Added",
                f"The prefix '{prefix}' has been added to your allowed list.\n\n"
                f"Fields like _{prefix}_* will now be recognised."
            )
