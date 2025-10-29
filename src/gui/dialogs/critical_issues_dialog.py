"""
Critical Issues and Deprecated Fields Dialog

Dialog for displaying critical issues (duplicates/aliases) and deprecated fields
with proper scrolling to handle large numbers of issues.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QLabel, QTextEdit, QScrollArea, QWidget, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class CriticalIssuesDialog(QDialog):
    """Dialog for displaying critical issues and deprecated fields with scrolling"""
    
    def __init__(self, conflicts, deprecated_fields, parent=None):
        super().__init__(parent)
        self.conflicts = conflicts
        self.deprecated_fields = deprecated_fields
        self.has_critical_issues = bool(conflicts)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the dialog UI with scrollable content"""
        # Determine title based on what issues we have
        if self.has_critical_issues and self.deprecated_fields:
            title = "Critical Issues and Deprecated Fields Found"
        elif self.has_critical_issues:
            title = "Critical: Duplicate/Alias Conflicts"
        else:
            title = "Deprecated Fields Found"
            
        self.setWindowTitle(title)
        
        # Set size constraints to prevent oversized dialogs
        self.setMinimumSize(700, 400)
        self.setMaximumSize(900, 700)
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Header label
        header = QLabel(f"<h2>{title}</h2>")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Create scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(10)
        
        # Build the report
        report_text = self._build_report()
        
        # Use QTextEdit for rich text with proper formatting
        text_display = QTextEdit()
        text_display.setReadOnly(True)
        text_display.setPlainText(report_text)
        
        # Set font for better readability
        font = QFont("Courier New", 9)
        text_display.setFont(font)
        
        content_layout.addWidget(text_display)
        content_widget.setLayout(content_layout)
        scroll_area.setWidget(content_widget)
        
        layout.addWidget(scroll_area)
        
        # Action text
        action_label = QLabel(self._get_action_text())
        action_label.setWordWrap(True)
        action_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border: 1px solid #ccc;")
        layout.addWidget(action_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Yes button
        yes_button = QPushButton("Yes - Fix Issues")
        yes_button.clicked.connect(self.accept)
        yes_button.setDefault(True)
        yes_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 8px 20px; font-weight: bold; }")
        button_layout.addWidget(yes_button)
        
        # No button
        no_button = QPushButton("No - Keep Issues")
        no_button.clicked.connect(self.reject)
        no_button.setStyleSheet("QPushButton { background-color: #ff9800; color: white; padding: 8px 20px; }")
        button_layout.addWidget(no_button)
        
        # Cancel button
        cancel_button = QPushButton("Cancel - Abort")
        cancel_button.clicked.connect(lambda: self.done(2))  # Custom return code for cancel
        cancel_button.setStyleSheet("QPushButton { padding: 8px 20px; }")
        button_layout.addWidget(cancel_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _build_report(self) -> str:
        """Build the report text showing all issues"""
        report = ""
        
        if self.conflicts:
            report += "⚠️  CRITICAL: DUPLICATE/ALIAS CONFLICTS DETECTED\n\n"
            report += f"Found {len(self.conflicts)} field conflict(s) that should be resolved:\n\n"
            
            for canonical, details in self.conflicts.items():
                report += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                report += f"Conflict: {canonical}\n"
                report += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                for alias_info in details:
                    report += f"  • Line {alias_info['line_num']}: {alias_info['alias']}\n"
                    report += f"    Value: {alias_info['value']}\n"
                    if alias_info.get('is_deprecated'):
                        report += f"    (DEPRECATED field)\n"
                    report += "\n"
                
                report += f"These fields are aliases and represent the SAME data.\n"
                report += f"Database submission may fail unless consolidated to a single field.\n\n"
            
            report += "These conflicts should be resolved before database submission.\n\n"
        
        if self.deprecated_fields:
            if report:
                report += "─────────────────────────────────────────────────────────\n\n"
            
            report += "📅 DEPRECATED FIELDS DETECTED\n\n"
            report += f"Found {len(self.deprecated_fields)} deprecated field(s) that can be modernized:\n\n"
            
            for dep_field in self.deprecated_fields:
                report += f"• Line {dep_field['line_num']}: {dep_field['field']}\n"
                if dep_field['modern']:
                    report += f"  → Modern equivalent: {dep_field['modern']}\n"
                else:
                    report += f"  → No modern equivalent (consider removal)\n"
                report += "\n"
            
            report += "Modernizing these fields improves CIF compatibility and reduces validation warnings.\n\n"
        
        return report
    
    def _get_action_text(self) -> str:
        """Get the action text based on what issues exist"""
        if self.has_critical_issues and self.deprecated_fields:
            return ("How would you like to proceed?\n\n" +
                   "• Yes: Resolve conflicts AND modernize deprecated fields (RECOMMENDED)\n" +
                   "• No: Continue with all issues (NOT RECOMMENDED)\n" +
                   "• Cancel: Abort checks and revert all changes")
        elif self.has_critical_issues:
            return ("How would you like to resolve these conflicts?\n\n" +
                   "• Yes: Resolve conflicts now (RECOMMENDED)\n" +
                   "• No: Continue with conflicts (NOT RECOMMENDED - file may be rejected)\n" +
                   "• Cancel: Abort checks and revert all changes")
        else:  # Only deprecated fields
            return ("How would you like to proceed?\n\n" +
                   "• Yes: Modernize deprecated fields (RECOMMENDED)\n" +
                   "• No: Continue with deprecated fields (compatibility warnings may occur)\n" +
                   "• Cancel: Abort checks and revert all changes")
    
    @staticmethod
    def show_dialog(conflicts, deprecated_fields, parent=None):
        """
        Show the dialog and return the user's choice.
        
        Returns:
            0: Cancel (abort)
            1: Yes (fix issues)
            2: No (keep issues)
        """
        dialog = CriticalIssuesDialog(conflicts, deprecated_fields, parent)
        result = dialog.exec()
        
        if result == 2:  # Custom cancel code
            return 0
        elif result == QDialog.DialogCode.Accepted:
            return 1
        else:
            return 2
