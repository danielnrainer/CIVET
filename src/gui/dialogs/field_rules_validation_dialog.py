"""
Field Rules Validation Dialog
=============================

Dialog for displaying and resolving field rules validation issues.
Provides categorized issue display with options for automatic fixes and 
manual resolution similar to the field conflict dialog.
"""

import os
import sys
from typing import Dict, List, Optional, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, 
    QGroupBox, QScrollArea, QWidget, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QFileDialog, QCheckBox, QSplitter, QFrame, QTreeWidgetItemIterator,
    QTabWidget, QPlainTextEdit, QComboBox, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

# Add parent directories to path to import from utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from utils.field_rules_validator import ValidationResult, ValidationIssue, IssueCategory, AutoFixType, CIFFormatAnalyzer


class IssueTreeWidget(QTreeWidget):
    """Custom tree widget for displaying validation issues by category"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["CIF Field", "Explanation", "Auto-Fix"])
        self.setRootIsDecorated(True)
        self.setAlternatingRowColors(True)
        self.itemChanged.connect(self.on_item_changed)
        self.selected_issues = set()
        
    def populate_issues(self, validation_result: ValidationResult):
        """Populate tree with validation issues organized by category"""
        self.clear()
        self.selected_issues.clear()
        
        # Group issues by category
        issues_by_category = validation_result.issues_by_category
        
        for category, issues in issues_by_category.items():
            # Create category item
            category_item = QTreeWidgetItem([f"{category.value} ({len(issues)})", "", ""])
            
            # Style category item
            font = QFont()
            font.setBold(True)
            category_item.setFont(0, font)
            
            # Color code by category
            if category == IssueCategory.MIXED_FORMAT:
                category_item.setBackground(0, self.palette().color(self.palette().ColorRole.AlternateBase))
            elif category == IssueCategory.DUPLICATE_ALIAS:
                category_item.setBackground(0, self.palette().color(self.palette().ColorRole.Base))
            elif category == IssueCategory.UNKNOWN_FIELD:
                category_item.setBackground(0, self.palette().color(self.palette().ColorRole.AlternateBase))
            
            self.addTopLevelItem(category_item)
            
            # Add individual issues
            for i, issue in enumerate(issues):
                field_text, explanation_text = self._format_issue_text(issue)
                auto_fix_text = self._format_auto_fix_text(issue.auto_fix_type)
                
                issue_item = QTreeWidgetItem([field_text, explanation_text, auto_fix_text])
                issue_item.setData(0, Qt.ItemDataRole.UserRole, (category, i))  # Store issue reference
                
                # Add checkbox for selection - only for fixable issues
                issue_item.setFlags(issue_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                if issue.auto_fix_type != AutoFixType.NO:
                    issue_item.setCheckState(0, Qt.CheckState.Checked)  # Pre-select fixable issues
                    issue_item.setToolTip(0, "This issue can be automatically fixed - check to include in fixes")
                    # Add to selected issues
                    issue_id = f"{category.value}_{i}"
                    self.selected_issues.add(issue_id)
                else:
                    issue_item.setCheckState(0, Qt.CheckState.Unchecked)
                    issue_item.setFlags(issue_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                    issue_item.setToolTip(0, "This issue cannot be automatically fixed and requires manual attention")
                
                # Color code by auto-fixable status
                if issue.auto_fix_type != AutoFixType.NO:
                    issue_item.setForeground(0, self.palette().color(self.palette().ColorRole.WindowText))
                else:
                    issue_item.setForeground(0, self.palette().color(self.palette().ColorRole.Mid))
                
                # Color code auto-fix type in third column
                if issue.auto_fix_type == AutoFixType.YES:
                    issue_item.setForeground(2, self.palette().color(self.palette().ColorRole.Dark))
                else:
                    issue_item.setForeground(2, self.palette().color(self.palette().ColorRole.Mid))
                
                category_item.addChild(issue_item)
            
            # Set collapsed AFTER children are added
            category_item.setExpanded(False)  # Start collapsed for better readability
        
        # Resize columns
        self.resizeColumnToContents(0)
        self.resizeColumnToContents(1)
        self.resizeColumnToContents(2)
    
    def _format_issue_text(self, issue: ValidationIssue) -> Tuple[str, str]:
        """Format issue for display in tree - returns (field_text, explanation_text)"""
        if len(issue.field_names) == 1:
            field_text = issue.field_names[0]
            explanation_text = issue.description
        else:
            fields_text = ", ".join(issue.field_names[:3])
            if len(issue.field_names) > 3:
                fields_text += f" (and {len(issue.field_names) - 3} more)"
            field_text = fields_text
            explanation_text = issue.description
        
        return field_text, explanation_text
    
    def _format_auto_fix_text(self, auto_fix_type: AutoFixType) -> str:
        """Format auto-fix type for display"""
        if auto_fix_type == AutoFixType.YES:
            return "yes"
        else:
            return "no"
    
    def on_item_changed(self, item, column):
        """Handle item check state changes"""
        if item.parent() is not None:  # Only for issue items, not category items
            category_data = item.data(0, Qt.ItemDataRole.UserRole)
            if category_data:
                category, index = category_data
                issue_id = f"{category.value}_{index}"
                
                if item.checkState(0) == Qt.CheckState.Checked:
                    self.selected_issues.add(issue_id)
                else:
                    self.selected_issues.discard(issue_id)
                
                # Emit signal to update selection count in parent dialog
                if hasattr(self.parent(), 'update_selection_count'):
                    self.parent().update_selection_count()
    
    def get_selected_issues(self, validation_result: ValidationResult) -> List[ValidationIssue]:
        """Get list of selected issues for fixing"""
        selected = []
        issues_by_category = validation_result.issues_by_category
        
        for category, issues in issues_by_category.items():
            for i, issue in enumerate(issues):
                issue_id = f"{category.value}_{i}"
                if issue_id in self.selected_issues:
                    selected.append(issue)
        
        return selected
    
    def select_all_auto_fixable(self):
        """Select all auto-fixable issues (both official and modern manual mappings)"""
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.parent() is not None and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(0, Qt.CheckState.Checked)
            iterator += 1
    
    def select_none(self):
        """Deselect all issues"""
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.parent() is not None and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(0, Qt.CheckState.Unchecked)
            iterator += 1


class FieldRulesValidationDialog(QDialog):
    """Dialog for validating and fixing field rules files"""
    
    # Signal emitted when validation is completed with fixes
    validation_completed = pyqtSignal(str, list)  # (fixed_content, changes_made)
    
    def __init__(self, validation_result: ValidationResult, 
                 field_rules_content: str, field_rules_path: str = "",
                 validator=None, parent=None):
        super().__init__(parent)
        
        self.validation_result = validation_result
        self.field_rules_content = field_rules_content
        self.field_rules_path = field_rules_path
        self.validator = validator
        self.fixed_content = None
        self.changes_made = []
        
        self.setWindowTitle("Field Rules Validation")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        self.setup_ui()
        self.populate_data()
        
        # Apply styling
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin: 5px 0;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTreeWidget {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #3875d7;
                color: white;
            }
        """)
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout()
        
        # Header with summary and instructions
        header_group = QGroupBox("Validation Summary")
        header_layout = QVBoxLayout()
        
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        header_layout.addWidget(self.summary_label)
        
        # Add instructions
        instructions_frame = QFrame()
        instructions_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        instructions_frame.setStyleSheet("QFrame { background-color: #f0f8ff; border: 1px solid #d0d0d0; border-radius: 4px; padding: 8px; }")
        instructions_layout = QVBoxLayout(instructions_frame)
        
        instructions_title = QLabel("<b>How to use this validation dialog:</b>")
        instructions_layout.addWidget(instructions_title)
        
        instructions_text = QLabel(
            "1. Review the validation issues below, organized by category<br>"
            "2. Check the boxes next to the issues you want to fix automatically<br>"
            "3. Click 'Apply Selected Fixes' to fix the checked issues<br>"
            "4. Use 'Preview Changes' to see what will be changed<br>"
            "5. Save or replace your field definition file with the fixes"
        )
        instructions_text.setWordWrap(True)
        instructions_text.setStyleSheet("margin-left: 10px;")
        instructions_layout.addWidget(instructions_text)
        
        header_layout.addWidget(instructions_frame)
        
        # Format selection for automatic fixes
        format_selection_frame = QFrame()
        format_selection_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        format_selection_frame.setStyleSheet("QFrame { background-color: #f8f8f8; border: 1px solid #d0d0d0; border-radius: 4px; padding: 8px; }")
        format_layout = QHBoxLayout(format_selection_frame)
        
        format_label = QLabel("<b>Automatic fix format:</b>")
        format_layout.addWidget(format_label)
        
        self.format_button_group = QButtonGroup()
        
        self.cif1_radio = QRadioButton("Legacy format (e.g., _cell_length_a)")
        self.cif1_radio.setToolTip("Convert mixed formats to legacy style with underscores")
        self.format_button_group.addButton(self.cif1_radio, 1)
        format_layout.addWidget(self.cif1_radio)
        
        self.cif2_radio = QRadioButton("Modern format (e.g., _cell.length_a)")
        self.cif2_radio.setToolTip("Convert mixed formats to modern style with dots")
        self.format_button_group.addButton(self.cif2_radio, 2)
        format_layout.addWidget(self.cif2_radio)
        
        format_layout.addStretch()
        header_layout.addWidget(format_selection_frame)
        
        header_group.setLayout(header_layout)
        layout.addWidget(header_group)
        
        # Main content with tabs
        self.tab_widget = QTabWidget()
        
        # Tab 1: Validation Issues
        issues_tab = QWidget()
        self.setup_issues_tab(issues_tab)
        self.tab_widget.addTab(issues_tab, "🔍 Validation Issues")
        
        # Tab 2: Manual Editor
        editor_tab = QWidget()
        self.setup_editor_tab(editor_tab)
        self.tab_widget.addTab(editor_tab, "✏️ Manual Editor")
        
        layout.addWidget(self.tab_widget)
        
        # Action buttons
        buttons_group = QGroupBox("Actions")
        buttons_layout = QVBoxLayout()
        
        # Main fix button - more prominent
        fix_layout = QHBoxLayout()
        
        self.apply_fixes_btn = QPushButton("🔧 Apply Selected Fixes")
        self.apply_fixes_btn.setToolTip("Apply automatic fixes for all checked issues")
        self.apply_fixes_btn.clicked.connect(self.apply_selected_fixes)
        self.apply_fixes_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        fix_layout.addWidget(self.apply_fixes_btn)
        
        fix_layout.addStretch()
        buttons_layout.addLayout(fix_layout)
        
        # File handling
        file_layout = QHBoxLayout()
        
        self.preview_changes_btn = QPushButton("👁 Preview Changes")
        self.preview_changes_btn.setToolTip("Show what changes will be made to the file")
        self.preview_changes_btn.clicked.connect(self.preview_changes)
        file_layout.addWidget(self.preview_changes_btn)
        
        file_layout.addStretch()
        
        self.save_as_btn = QPushButton("💾 Save As New File...")
        self.save_as_btn.setToolTip("Save the fixed field definitions to a new file")
        self.save_as_btn.clicked.connect(self.save_as_new_file)
        self.save_as_btn.setEnabled(False)
        file_layout.addWidget(self.save_as_btn)
        
        self.replace_file_btn = QPushButton("🔄 Replace Original File")
        self.replace_file_btn.setToolTip("Replace the original file with the fixed version (backup will be created)")
        self.replace_file_btn.clicked.connect(self.replace_original_file)
        self.replace_file_btn.setEnabled(False)
        file_layout.addWidget(self.replace_file_btn)
        
        buttons_layout.addLayout(file_layout)
        
        # Close buttons
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        self.skip_btn = QPushButton("Skip Validation")
        self.skip_btn.clicked.connect(self.reject)
        close_layout.addWidget(self.skip_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        close_layout.addWidget(self.close_btn)
        
        buttons_layout.addLayout(close_layout)
        
        buttons_group.setLayout(buttons_layout)
        layout.addWidget(buttons_group)
        
        # Connect radio button signals after UI is fully set up
        self.cif1_radio.toggled.connect(self.on_format_changed)
        self.cif2_radio.toggled.connect(self.on_format_changed)
        
        # Set default format based on validation result or analyze rules content
        if hasattr(self.validation_result, 'target_format_used'):
            if self.validation_result.target_format_used == "legacy":
                self.cif1_radio.setChecked(True)
            else:
                self.cif2_radio.setChecked(True)
        else:
            # Analyze the provided rules content to choose a sensible default
            try:
                rules_format = CIFFormatAnalyzer.analyze_cif_format(self.field_rules_content)
                if rules_format == "legacy":
                    self.cif1_radio.setChecked(True)
                else:
                    self.cif2_radio.setChecked(True)
            except Exception:
                # Fallback if analysis fails
                self.cif2_radio.setChecked(True)
        
        self.setLayout(layout)
        
        # Set the "Close" button as the default button instead of "Apply Selected Fixes"
        self.close_btn.setDefault(True)
    
    def setup_issues_tab(self, tab_widget):
        """Setup the validation issues tab"""
        layout = QVBoxLayout(tab_widget)
        
        # Issues tree section
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Issues tree
        issues_group = QGroupBox("Validation Issues")
        issues_layout = QVBoxLayout()
        
        # Quick conversion buttons
        conversion_layout = QHBoxLayout()
        
        self.convert_official_btn = QPushButton("🔄 Convert Official Mappings")
        self.convert_official_btn.setToolTip("Select and convert all fields with official dictionary mappings (\"yes\" items)")
        self.convert_official_btn.clicked.connect(self.convert_official_mappings)
        conversion_layout.addWidget(self.convert_official_btn)

        self.convert_all_fixable_btn = QPushButton("⚡ Convert All Fixable")
        self.convert_all_fixable_btn.setToolTip("Select and convert all fixable fields")
        self.convert_all_fixable_btn.clicked.connect(self.convert_all_fixable)
        conversion_layout.addWidget(self.convert_all_fixable_btn)
        
        issues_layout.addLayout(conversion_layout)
        
        # Selection controls with clearer labels
        selection_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("✓ Check All Fixable Issues")
        self.select_all_btn.setToolTip("Select all issues that can be automatically fixed")
        self.select_all_btn.clicked.connect(self.select_all_auto_fixable)
        selection_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton("✗ Uncheck All Issues")
        self.select_none_btn.setToolTip("Deselect all issues")
        self.select_none_btn.clicked.connect(self.select_none)
        selection_layout.addWidget(self.select_none_btn)
        
        # Selection count display
        self.selection_count_label = QLabel("0 issues selected")
        self.selection_count_label.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        selection_layout.addStretch()
        selection_layout.addWidget(self.selection_count_label)
        issues_layout.addLayout(selection_layout)
        
        # Issues tree widget
        self.issues_tree = IssueTreeWidget()
        self.issues_tree.itemSelectionChanged.connect(self.on_issue_selection_changed)
        issues_layout.addWidget(self.issues_tree)
        
        issues_group.setLayout(issues_layout)
        splitter.addWidget(issues_group)
        
        # Issue details
        details_group = QGroupBox("Issue Details")
        details_layout = QVBoxLayout()
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)
        
        details_group.setLayout(details_layout)
        splitter.addWidget(details_group)
        
        # Set splitter sizes
        splitter.setSizes([400, 150])
        layout.addWidget(splitter)
    
    def setup_editor_tab(self, tab_widget):
        """Setup the manual editor tab"""
        layout = QVBoxLayout(tab_widget)
        
        # Instructions for manual editing
        editor_instructions = QLabel(
            "<b>Manual Editor:</b> Edit field definitions directly. "
            "Changes made here will be used instead of automatic fixes. "
            "You can manually resolve the issues that cannot be automatically fixed."
        )
        editor_instructions.setWordWrap(True)
        editor_instructions.setStyleSheet("padding: 8px; background-color: #fff8dc; border: 1px solid #ddd; border-radius: 4px;")
        layout.addWidget(editor_instructions)
        
        # Editor controls
        editor_controls = QHBoxLayout()
        
        self.reset_editor_btn = QPushButton("🔄 Reset to Original")
        self.reset_editor_btn.setToolTip("Reset editor content to the original field definitions")
        self.reset_editor_btn.clicked.connect(self.reset_editor_content)
        editor_controls.addWidget(self.reset_editor_btn)
        
        self.apply_auto_fixes_to_editor_btn = QPushButton("🔧 Apply Auto-Fixes to Editor")
        self.apply_auto_fixes_to_editor_btn.setToolTip("Apply selected automatic fixes to the editor content")
        self.apply_auto_fixes_to_editor_btn.clicked.connect(self.apply_auto_fixes_to_editor)
        editor_controls.addWidget(self.apply_auto_fixes_to_editor_btn)
        
        editor_controls.addStretch()
        
        # Manual validation button
        self.validate_editor_btn = QPushButton("✅ Validate Editor Content")
        self.validate_editor_btn.setToolTip("Re-validate the manually edited content")
        self.validate_editor_btn.clicked.connect(self.validate_editor_content)
        editor_controls.addWidget(self.validate_editor_btn)
        
        layout.addLayout(editor_controls)
        
        # Text editor
        editor_group = QGroupBox("Field Definitions Editor")
        editor_layout = QVBoxLayout()
        
        self.manual_editor = QPlainTextEdit()
        self.manual_editor.setFont(QFont("Courier New", 10))
        self.manual_editor.setPlainText(self.field_rules_content)
        self.manual_editor.textChanged.connect(self.on_editor_content_changed)
        editor_layout.addWidget(self.manual_editor)
        
        # Editor status
        self.editor_status_label = QLabel("Ready for manual editing")
        self.editor_status_label.setStyleSheet("color: #666; font-style: italic;")
        editor_layout.addWidget(self.editor_status_label)
        
        editor_group.setLayout(editor_layout)
        layout.addWidget(editor_group)
    
    def populate_data(self):
        """Populate the dialog with validation data"""
        # Update summary
        total_issues = len(self.validation_result.issues)
        auto_fixable = sum(1 for issue in self.validation_result.issues if issue.auto_fix_type != AutoFixType.NO)
        
        if self.field_rules_path:
            file_info = f"<b>File:</b> {os.path.basename(self.field_rules_path)}<br>"
        else:
            file_info = "<b>File:</b> Field Definition Content<br>"
        
        summary_text = f"""
        {file_info}
        <b>Total Issues:</b> {total_issues}<br>
        <b>Auto-Fixable:</b> {auto_fixable}<br>
        <b>CIF Format Detected:</b> {self.validation_result.cif_format_detected}<br>
        <b>Fields:</b> {self.validation_result.unique_fields} unique out of {self.validation_result.total_fields} total
        """
        
        if total_issues == 0:
            summary_text += "<br><br><span style='color: green; font-weight: bold;'>✅ No issues found!</span>"
        
        self.summary_label.setText(summary_text)
        
        # Populate issues tree (only if it exists)
        if hasattr(self, 'issues_tree'):
            self.issues_tree.populate_issues(self.validation_result)
        
        # Update conversion button counts
        self.update_conversion_button_counts()
        
        # Update button states
        if total_issues == 0:
            self.apply_fixes_btn.setEnabled(False)
            self.select_all_btn.setEnabled(False)
            self.select_none_btn.setEnabled(False)
        else:
            # Enable selection buttons when there are issues
            self.select_all_btn.setEnabled(True)
            self.select_none_btn.setEnabled(True)
            # Apply fixes button will be enabled/disabled in update_selection_count()
        
        # Update selection count
        self.update_selection_count()
    
    def on_issue_selection_changed(self):
        """Handle issue selection changes to update details"""
        current_item = self.issues_tree.currentItem()
        
        if current_item and current_item.parent() is not None:
            # Get issue data
            category_data = current_item.data(0, Qt.ItemDataRole.UserRole)
            if category_data:
                category, index = category_data
                issues_by_category = self.validation_result.issues_by_category
                
                if category in issues_by_category and index < len(issues_by_category[category]):
                    issue = issues_by_category[category][index]
                    self.show_issue_details(issue)
        else:
            self.details_text.clear()
    
    def show_issue_details(self, issue: ValidationIssue):
        """Show detailed information for a specific issue"""
        details_html = f"""
        <h3>{issue.category.value}</h3>
        <p><b>Description:</b> {issue.description}</p>
        <p><b>Affected Fields:</b> {', '.join(issue.field_names)}</p>
        <p><b>Suggested Fix:</b> {issue.suggested_fix}</p>
        <p><b>Auto-Fix Type:</b> {self._format_auto_fix_text(issue.auto_fix_type)}</p>
        """
        
        self.details_text.setHtml(details_html)
    
    def _format_auto_fix_text(self, auto_fix_type: AutoFixType) -> str:
        """Format auto-fix type for display"""
        if auto_fix_type == AutoFixType.YES:
            return "yes"
        else:
            return "no"
    
    def update_selection_count(self):
        """Update the selection count display"""
        if (hasattr(self, 'selection_count_label') and hasattr(self, 'issues_tree') and 
            hasattr(self, 'validation_result')):
            selected_count = len(self.issues_tree.selected_issues)
            total_fixable = sum(1 for issue in self.validation_result.issues if issue.auto_fix_type != AutoFixType.NO)
            
            if selected_count == 0:
                self.selection_count_label.setText("No issues selected")
                self.apply_fixes_btn.setEnabled(False)
            else:
                self.selection_count_label.setText(f"{selected_count} of {total_fixable} fixable issues selected")
                self.apply_fixes_btn.setEnabled(True)

    def select_all_auto_fixable(self):
        """Select all auto-fixable issues"""
        if hasattr(self, 'issues_tree'):
            self.issues_tree.select_all_auto_fixable()
            self.update_selection_count()
    
    def select_none(self):
        """Deselect all issues"""
        if hasattr(self, 'issues_tree'):
            self.issues_tree.select_none()
            self.update_selection_count()
    
    def on_format_changed(self):
        """Handle format radio button changes - refresh the validation table"""
        if (hasattr(self, 'validation_result') and hasattr(self, 'field_rules_content') and 
            hasattr(self, 'validator') and hasattr(self, 'issues_tree')):
            # Re-run validation with the new target format
            target_format = "modern" if self.cif2_radio.isChecked() else "legacy"
            
            # Create a new validation result with the new target format
            new_validation_result = self.validator.validate_field_rules(
                self.field_rules_content, cif_content=None, target_format=target_format
            )
            
            # Update the validation result and refresh the display
            self.validation_result = new_validation_result
            self.populate_data()
    
    def convert_official_mappings(self):
        """Select and convert all fields with official dictionary mappings"""
        self._select_by_auto_fix_type([AutoFixType.YES])
        self.apply_selected_fixes()
    
    def convert_all_fixable(self):
        """Select and convert all auto-fixable fields"""
        self._select_by_auto_fix_type([AutoFixType.YES])
        self.apply_selected_fixes()
    
    def _select_by_auto_fix_type(self, auto_fix_types):
        """Select issues with the specified auto-fix types"""
        # Clear current selection
        self.issues_tree.selected_issues.clear()
        
        # Select issues with matching auto-fix types
        issues_by_category = self.validation_result.issues_by_category
        
        for category, issues in issues_by_category.items():
            for i, issue in enumerate(issues):
                if issue.auto_fix_type in auto_fix_types:
                    issue_id = f"{category.value}_{i}"
                    self.issues_tree.selected_issues.add(issue_id)
        
        # Update the UI checkboxes
        self._update_tree_checkboxes()
        self.update_selection_count()
    
    def _update_tree_checkboxes(self):
        """Update the checkbox states in the tree to match selected_issues"""
        iterator = QTreeWidgetItemIterator(self.issues_tree)
        while iterator.value():
            item = iterator.value()
            if item.parent() is not None:  # Only for issue items, not category items
                category_data = item.data(0, Qt.ItemDataRole.UserRole)
                if category_data:
                    category, index = category_data
                    issue_id = f"{category.value}_{index}"
                    
                    if issue_id in self.issues_tree.selected_issues:
                        item.setCheckState(0, Qt.CheckState.Checked)
                    else:
                        item.setCheckState(0, Qt.CheckState.Unchecked)
            iterator += 1
    
    def update_conversion_button_counts(self):
        """Update the conversion button texts with current counts"""
        # Count issues by auto-fix type
        fixable_count = sum(1 for issue in self.validation_result.issues if issue.auto_fix_type == AutoFixType.YES)
        
        # Update button texts with counts
        self.convert_official_btn.setText(f"🔄 Convert Official Mappings ({fixable_count})")
        self.convert_all_fixable_btn.setText(f"⚡ Convert All Auto-Fixable ({fixable_count})")
        
        # Enable/disable buttons based on counts
        self.convert_official_btn.setEnabled(fixable_count > 0)
        self.convert_all_fixable_btn.setEnabled(fixable_count > 0)
    
    def apply_selected_fixes(self):
        """Apply fixes for all selected issues"""
        if not self.validator:
            QMessageBox.warning(self, "Error", "No validator available for fixing issues.")
            return
        
        selected_issues = self.issues_tree.get_selected_issues(self.validation_result)
        
        if not selected_issues:
            QMessageBox.information(self, "No Issues Selected", 
                                  "Please select issues to fix by checking the boxes next to them.")
            return
        
        # Show confirmation dialog
        fixable_count = len([issue for issue in selected_issues if issue.auto_fix_type != AutoFixType.NO])
        non_fixable_count = len(selected_issues) - fixable_count
        
        msg = f"Apply automatic fixes for {fixable_count} selected issues?"
        if non_fixable_count > 0:
            msg += f"\n\nNote: {non_fixable_count} issues cannot be automatically fixed and will be skipped."
        
        reply = QMessageBox.question(self, "Apply Fixes", msg, 
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Only fix the auto-fixable selected issues
            fixable_issues = [issue for issue in selected_issues if issue.auto_fix_type != AutoFixType.NO]
            
            if fixable_issues:
                # Determine target format from radio buttons
                target_format = "modern" if self.cif2_radio.isChecked() else "legacy"
                
                self.fixed_content, self.changes_made = self.validator.apply_automatic_fixes(
                    self.field_rules_content, fixable_issues, target_format=target_format
                )
                
                if self.changes_made:
                    self._enable_save_buttons()
                    QMessageBox.information(self, "Fixes Applied", 
                                          f"Applied {len(self.changes_made)} fixes using {target_format} format!\n\n"
                                          "Use 'Preview Changes' to review or save the fixed file.")
                else:
                    QMessageBox.information(self, "No Changes", "No changes were needed.")
            else:
                QMessageBox.information(self, "No Fixable Issues", 
                                      "None of the selected issues can be automatically fixed.")
                
        except Exception as e:
            QMessageBox.critical(self, "Fix Error", f"Error applying fixes: {str(e)}")
    
    def reset_editor_content(self):
        """Reset manual editor to original content"""
        self.manual_editor.setPlainText(self.field_rules_content)
        self.editor_status_label.setText("Editor reset to original content")
        self.editor_status_label.setStyleSheet("color: #2e8b57; font-style: italic;")
    
    def apply_auto_fixes_to_editor(self):
        """Apply selected automatic fixes to the manual editor"""
        if not self.validator:
            QMessageBox.warning(self, "Error", "No validator available for fixing issues.")
            return
        
        selected_issues = self.issues_tree.get_selected_issues(self.validation_result)
        fixable_issues = [issue for issue in selected_issues if issue.auto_fix_type != AutoFixType.NO]
        
        if not fixable_issues:
            QMessageBox.information(self, "No Fixable Issues", 
                                  "No auto-fixable issues are selected.")
            return
        
        try:
            # Get the current editor content as base
            current_content = self.manual_editor.toPlainText()
            
            # Determine target format from radio buttons
            target_format = "modern" if self.cif2_radio.isChecked() else "legacy"
            
            # Apply fixes with selected format
            fixed_content, changes_made = self.validator.apply_automatic_fixes(
                current_content, fixable_issues, target_format=target_format
            )
            
            if changes_made:
                self.manual_editor.setPlainText(fixed_content)
                self.editor_status_label.setText(f"Applied {len(changes_made)} automatic fixes to editor")
                self.editor_status_label.setStyleSheet("color: #2e8b57; font-style: italic;")
                
                # Show what was changed
                changes_text = "\\n".join(changes_made[:5])  # Show first 5 changes
                if len(changes_made) > 5:
                    changes_text += f"\\n... and {len(changes_made) - 5} more changes"
                    
                QMessageBox.information(self, "Fixes Applied to Editor", 
                                      f"Applied {len(changes_made)} fixes using {target_format} format:\\n\\n{changes_text}")
            else:
                self.editor_status_label.setText("No changes were needed")
                self.editor_status_label.setStyleSheet("color: #666; font-style: italic;")
                
        except Exception as e:
            QMessageBox.critical(self, "Fix Error", f"Error applying fixes to editor: {str(e)}")
    
    def validate_editor_content(self):
        """Re-validate the content in the manual editor"""
        if not self.validator:
            QMessageBox.warning(self, "Error", "No validator available for validation.")
            return
        
        try:
            editor_content = self.manual_editor.toPlainText()
            
            # Use original CIF content for validation
            test_cif_content = getattr(self, 'original_cif_content', "")
            
            # Re-validate with editor content
            new_validation_result = self.validator.validate_field_rules(
                editor_content, test_cif_content
            )
            
            # Update the issues tree with new results
            self.validation_result = new_validation_result
            self.issues_tree.populate_issues(new_validation_result)
            self.update_selection_count()
            
            # Update summary
            self.populate_data()
            
            # Switch to issues tab to show results
            self.tab_widget.setCurrentIndex(0)
            
            total_issues = len(new_validation_result.issues)
            if total_issues == 0:
                QMessageBox.information(self, "Validation Complete", 
                                      "✅ No validation issues found in the manual editor content!")
                self.editor_status_label.setText("✅ Editor content is valid!")
                self.editor_status_label.setStyleSheet("color: #2e8b57; font-weight: bold;")
            else:
                QMessageBox.information(self, "Validation Results", 
                                      f"Found {total_issues} issues in the editor content. "
                                      "Check the Validation Issues tab for details.")
                self.editor_status_label.setText(f"⚠️ {total_issues} issues found in editor content")
                self.editor_status_label.setStyleSheet("color: #d2691e; font-style: italic;")
                
        except Exception as e:
            QMessageBox.critical(self, "Validation Error", f"Error validating editor content: {str(e)}")
    
    def on_editor_content_changed(self):
        """Handle changes in the manual editor"""
        self.editor_status_label.setText("Manual changes made - click 'Validate Editor Content' to re-check")
        self.editor_status_label.setStyleSheet("color: #666; font-style: italic;")
    
    def get_final_content(self):
        """Get the final content - either from manual editor or fixed content"""
        if hasattr(self, 'manual_editor'):
            # If manual editor exists and has been modified, use its content
            editor_content = self.manual_editor.toPlainText().strip()
            original_content = self.field_rules_content.strip()
            
            if editor_content != original_content:
                return editor_content
        
        # Otherwise use the fixed content from automatic fixes
        return getattr(self, 'fixed_content', self.field_rules_content)
    
    def _enable_save_buttons(self):
        """Enable save buttons after fixes are applied"""
        self.save_as_btn.setEnabled(True)
        if self.field_rules_path:
            self.replace_file_btn.setEnabled(True)
    
    def preview_changes(self):
        """Show preview of changes that would be made"""
    def preview_changes(self):
        """Show preview of changes that would be made"""
        final_content = self.get_final_content()
        
        if final_content == self.field_rules_content:
            QMessageBox.information(self, "No Changes", 
                                  "No changes have been made to preview.")
            return
        
        # Create preview dialog
        preview_dialog = QDialog(self)
        preview_dialog.setWindowTitle("Preview Changes")
        preview_dialog.setMinimumSize(700, 500)
        
        layout = QVBoxLayout()
        
        # Changes summary
        changes_description = []
        if hasattr(self, 'changes_made') and self.changes_made:
            changes_description.extend(self.changes_made)
        if final_content != getattr(self, 'fixed_content', self.field_rules_content):
            changes_description.append("Manual edits applied")
            
        changes_label = QLabel(f"<b>Changes summary ({len(changes_description)}):</b>")
        layout.addWidget(changes_label)
        
        if changes_description:
            changes_list = QTextEdit()
            changes_list.setPlainText("\n".join(f"• {change}" for change in changes_description))
            changes_list.setMaximumHeight(120)
            changes_list.setReadOnly(True)
            layout.addWidget(changes_list)
        
        # Side-by-side comparison
        comparison_label = QLabel("<b>Content Comparison:</b>")
        layout.addWidget(comparison_label)
        
        # Create splitter for side-by-side view
        comparison_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Original content
        original_group = QGroupBox("Original Content")
        original_layout = QVBoxLayout()
        original_preview = QPlainTextEdit()
        original_preview.setFont(QFont("Courier New", 9))
        original_preview.setPlainText(self.field_rules_content)
        original_preview.setReadOnly(True)
        original_layout.addWidget(original_preview)
        original_group.setLayout(original_layout)
        comparison_splitter.addWidget(original_group)
        
        # Final content
        final_group = QGroupBox("Final Content (with fixes)")
        final_layout = QVBoxLayout()
        final_preview = QPlainTextEdit()
        final_preview.setFont(QFont("Courier New", 9))
        final_preview.setPlainText(final_content)
        final_preview.setReadOnly(True)
        final_layout.addWidget(final_preview)
        final_group.setLayout(final_layout)
        comparison_splitter.addWidget(final_group)
        
        comparison_splitter.setSizes([350, 350])
        layout.addWidget(comparison_splitter)
        
        # Close button
        close_btn = QPushButton("Close Preview")
        close_btn.clicked.connect(preview_dialog.accept)
        layout.addWidget(close_btn)
        
        preview_dialog.setLayout(layout)
        preview_dialog.exec()
    
    def save_as_new_file(self):
        """Save fixed content as a new file"""
        final_content = self.get_final_content()
        
        if final_content == self.field_rules_content:
            QMessageBox.information(self, "No Changes", 
                                  "No changes have been made. The content is identical to the original.")
            return
        
        # Suggest filename based on original
        if self.field_rules_path:
            base_name = os.path.splitext(self.field_rules_path)[0]
            extension = os.path.splitext(self.field_rules_path)[1] or '.cif_rules'
            suggested_name = f"{base_name}_fixed{extension}"
        else:
            suggested_name = "field_rules_fixed.cif_rules"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Field Rules", suggested_name,
            "Field Rules Files (*.cif_rules);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(final_content)
                
                QMessageBox.information(self, "File Saved", 
                                      f"Field definitions saved to:\n{file_path}")
                
                # Emit signal with the final content
                changes_description = []
                if hasattr(self, 'changes_made') and self.changes_made:
                    changes_description.extend(self.changes_made)
                if final_content != getattr(self, 'fixed_content', self.field_rules_content):
                    changes_description.append("Manual edits applied")
                
                self.validation_completed.emit(final_content, changes_description)
                
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Error saving file: {str(e)}")
    
    def replace_original_file(self):
        """Replace the original file with fixed content"""
        final_content = self.get_final_content()
        
        if not self.field_rules_path:
            QMessageBox.warning(self, "Cannot Replace", "No original file specified.")
            return
            
        if final_content == self.field_rules_content:
            QMessageBox.information(self, "No Changes", 
                                  "No changes have been made. The content is identical to the original.")
            return
        
        # Count changes
        change_count = 0
        if hasattr(self, 'changes_made') and self.changes_made:
            change_count += len(self.changes_made)
        if final_content != getattr(self, 'fixed_content', self.field_rules_content):
            change_count += 1  # Manual changes
        
        # Ask for confirmation
        reply = QMessageBox.question(
            self, "Replace Original File",
            f"Are you sure you want to replace the original file?\n\n"
            f"{self.field_rules_path}\n\n"
            f"This will apply changes to the file. "
            f"A backup will be created automatically.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Create backup
                backup_path = f"{self.field_rules_path}.backup"
                with open(self.field_rules_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                
                # Write final content
                with open(self.field_rules_path, 'w', encoding='utf-8') as f:
                    f.write(final_content)
                
                QMessageBox.information(self, "File Replaced", 
                                      f"Original file replaced with fixed version.\n"
                                      f"Backup created: {backup_path}")
                
                # Emit signal with the fixed content
                self.validation_completed.emit(self.fixed_content, self.changes_made)
                
            except Exception as e:
                QMessageBox.critical(self, "Replace Error", f"Error replacing file: {str(e)}")
