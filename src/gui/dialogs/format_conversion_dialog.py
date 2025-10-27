"""
Format Conversion Suggestion Dialog
==================================

Dialog for suggesting and previewing CIF format conversion to modern format
when loading legacy or mixed format files.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QPushButton, QTextEdit, QFrame, QGroupBox, QScrollArea,
                           QSizePolicy, QTabWidget, QWidget, QMessageBox)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QFontMetrics
from typing import List, Optional
from utils.cif_dictionary_manager import CIFVersion


class FormatConversionDialog(QDialog):
    """Dialog for suggesting conversion to modern CIF format"""
    
    def __init__(self, original_content: str, detected_version: CIFVersion, 
                 format_converter, parent=None):
        super().__init__(parent)
        self.original_content = original_content
        self.detected_version = detected_version
        self.format_converter = format_converter
        self.converted_content = None
        self.conversion_changes = []
        self.user_choice = None  # 'convert', 'keep_original', 'cancel'
        
        self.setWindowTitle("CIF Format Modernization Suggestion")
        self.setModal(True)
        self.resize(800, 600)
        
        self.init_ui()
        self.generate_conversion_preview()
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        
        # Header section
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        header_frame.setStyleSheet("""
            QFrame { 
                background-color: #e8f4f8; 
                border: 1px solid #bee5eb; 
                border-radius: 6px; 
                padding: 12px; 
                margin-bottom: 10px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        
        # Title
        title = QLabel("🔄 Convert to Modern CIF Format?")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        # Version detection info
        version_text = {
            CIFVersion.CIF1: "Legacy CIF format detected",
            CIFVersion.MIXED: "Mixed CIF format detected",
            CIFVersion.UNKNOWN: "Unknown CIF format detected"
        }
        
        detection_label = QLabel(f"📋 {version_text.get(self.detected_version, 'Unknown format')}")
        detection_label.setStyleSheet("color: #0c5460; font-weight: bold;")
        header_layout.addWidget(detection_label)
        
        # Recommendation
        recommendation_text = (
            "We recommend converting to modern CIF format:\n"
            "• Field name clarity with hierarchical dot notation\n"
            "• Standards compliance with current specifications\n" 
            "• Compatibility with modern crystallographic software"
        )
        recommendation_label = QLabel(recommendation_text)
        recommendation_label.setWordWrap(True)
        recommendation_label.setStyleSheet("color: #0c5460; margin-top: 5px;")
        header_layout.addWidget(recommendation_label)
        
        layout.addWidget(header_frame)
        
        # Preview section with tabs
        preview_tabs = QTabWidget()
        
        # Changes summary tab
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        
        summary_label = QLabel("Conversion Summary")
        summary_font = QFont()
        summary_font.setBold(True)
        summary_label.setFont(summary_font)
        summary_layout.addWidget(summary_label)
        
        self.changes_text = QTextEdit()
        self.changes_text.setMaximumHeight(150)
        self.changes_text.setReadOnly(True)
        self.changes_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
            }
        """)
        summary_layout.addWidget(self.changes_text)
        
        preview_tabs.addTab(summary_tab, "📋 Changes Summary")
        
        # Content preview tab
        content_tab = QWidget()
        content_layout = QVBoxLayout(content_tab)
        
        content_label = QLabel("Preview of Converted Content")
        content_label.setFont(summary_font)
        content_layout.addWidget(content_label)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        content_layout.addWidget(self.preview_text)
        
        preview_tabs.addTab(content_tab, "👁 Content Preview")
        
        layout.addWidget(preview_tabs)
        
        # Warning for mixed format
        if self.detected_version == CIFVersion.MIXED:
            warning_frame = QFrame()
            warning_frame.setStyleSheet("""
                QFrame { 
                    background-color: #fff3cd; 
                    border: 1px solid #ffeaa7; 
                    border-radius: 4px; 
                    padding: 8px; 
                    margin: 5px 0px;
                }
            """)
            warning_layout = QVBoxLayout(warning_frame)
            warning_label = QLabel("⚠️ Mixed format detected: Your file contains both legacy and modern field names. Converting will standardize all fields to modern format.")
            warning_label.setWordWrap(True)
            warning_label.setStyleSheet("color: #856404; font-weight: bold;")
            warning_layout.addWidget(warning_label)
            layout.addWidget(warning_frame)
        
        # Button section
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Convert button (recommended)
        self.convert_btn = QPushButton("✅ Convert to Modern Format")
        self.convert_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.convert_btn.clicked.connect(self.accept_conversion)
        button_layout.addWidget(self.convert_btn)
        
        # Keep original button
        self.keep_btn = QPushButton("📄 Keep Original Format")
        self.keep_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        self.keep_btn.clicked.connect(self.keep_original)
        button_layout.addWidget(self.keep_btn)
        
        # Cancel button
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Set default focus
        self.convert_btn.setDefault(True)
        self.convert_btn.setFocus()
    
    def generate_conversion_preview(self):
        """Generate the conversion preview and changes summary"""
        try:
            # Perform the conversion
            self.converted_content, self.conversion_changes = self.format_converter.convert_to_cif2(self.original_content)
            
            # Update changes summary
            if self.conversion_changes:
                changes_summary = f"Conversion will make {len(self.conversion_changes)} changes:\n\n"
                # Show first 10 changes, summarize the rest
                display_changes = self.conversion_changes[:10]
                changes_summary += "\n".join(display_changes)
                
                if len(self.conversion_changes) > 10:
                    remaining = len(self.conversion_changes) - 10
                    changes_summary += f"\n\n... and {remaining} more changes"
                
                self.changes_text.setPlainText(changes_summary)
            else:
                self.changes_text.setPlainText("No changes required - file is already in modern format.")
                # Disable convert button if no changes needed
                self.convert_btn.setEnabled(False)
                self.convert_btn.setText("✅ Already Modern Format")
            
            # Update content preview (show first 50 lines to avoid overwhelming UI)
            preview_lines = self.converted_content.split('\n')[:50]
            preview_content = '\n'.join(preview_lines)
            if len(self.converted_content.split('\n')) > 50:
                preview_content += f"\n\n... ({len(self.converted_content.split('\n')) - 50} more lines)"
            
            self.preview_text.setPlainText(preview_content)
            
        except Exception as e:
            error_msg = f"Error generating conversion preview: {str(e)}"
            self.changes_text.setPlainText(error_msg)
            self.preview_text.setPlainText("Preview unavailable due to conversion error.")
            self.convert_btn.setEnabled(False)
    
    def accept_conversion(self):
        """User chose to convert to modern format"""
        self.user_choice = 'convert'
        self.accept()
    
    def keep_original(self):
        """User chose to keep original format"""
        self.user_choice = 'keep_original'
        self.accept()
    
    def get_result(self):
        """Get the result of the user's choice"""
        if self.user_choice == 'convert':
            return self.converted_content, self.conversion_changes
        elif self.user_choice == 'keep_original':
            return self.original_content, []
        else:
            return None, []  # Cancelled
    
    def get_user_choice(self):
        """Get the user's choice"""
        return self.user_choice


def suggest_format_conversion(content: str, detected_version: CIFVersion, 
                            format_converter, parent=None):
    """
    Show format conversion suggestion dialog if content is not in modern format.
    
    Args:
        content: CIF file content
        detected_version: Detected CIF version
        format_converter: CIF format converter instance
        parent: Parent widget
    
    Returns:
        Tuple of (final_content, user_choice, changes_made)
        user_choice: 'convert', 'keep_original', or 'cancel'
    """
    # Only suggest conversion for non-modern formats
    if detected_version in [CIFVersion.CIF1, CIFVersion.MIXED, CIFVersion.UNKNOWN]:
        dialog = FormatConversionDialog(content, detected_version, format_converter, parent)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            final_content, changes = dialog.get_result()
            return final_content, dialog.get_user_choice(), changes
        else:
            return content, 'cancel', []
    else:
        # Already modern format, no suggestion needed
        return content, 'no_suggestion', []