"""CIF Input Dialog for field editing."""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette


class CIFInputDialog(QDialog):
    # Define result codes as class attributes
    RESULT_ABORT = 2  # User wants to abort all changes
    RESULT_STOP_SAVE = 3  # User wants to stop but save changes
    RESULT_USE_DEFAULT = 4  # User wants to use default value

    def __init__(self, title, text, value="", default_value=None, parent=None, operation_type="edit"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.default_value = default_value
        
        # Set background color based on operation type
        self.set_dialog_color(operation_type)
        
        layout = QVBoxLayout(self)
        
        # Add operation indicator
        operation_label = QLabel()
        if operation_type == "add":
            operation_label.setText("🆕 ADDING NEW FIELD")
            operation_label.setStyleSheet("font-weight: bold; color: #1565C0; padding: 5px;")
        elif operation_type == "different":
            operation_label.setText("✏️ EDITING EXISTING FIELD, DIFFERENT FROM DEFAULT")
            operation_label.setStyleSheet("font-weight: bold; color: #F57C00; padding: 5px;")
        else:
            operation_label.setText("✏️ EDITING EXISTING FIELD, SAME AS DEFAULT")
            operation_label.setStyleSheet("font-weight: bold; color: #2E7D32; padding: 5px;")
        
        operation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(operation_label)
        
        # Add text label
        label = QLabel(text)
        label.setWordWrap(True)
        # Ensure UTF-8 text handling
        if isinstance(text, bytes):
            label.setText(text.decode('utf-8'))
        layout.addWidget(label)
        
        # Add input field
        self.inputField = QLineEdit(self)
        # Ensure UTF-8 text handling
        if isinstance(value, bytes):
            self.inputField.setText(value.decode('utf-8'))
        else:
            self.inputField.setText(str(value))
        layout.addWidget(self.inputField)
        
        # Add buttons
        buttonBox = QHBoxLayout()
        
        okButton = QPushButton("OK")
        okButton.clicked.connect(self.accept)
        
        cancelButton = QPushButton("Cancel Current")
        cancelButton.clicked.connect(self.reject)
        
        # Add "Use Default" button only if default value is provided
        if default_value is not None and default_value.strip():
            useDefaultButton = QPushButton(f"Use suggested (default) value")
            useDefaultButton.clicked.connect(self.use_default)
            buttonBox.addWidget(useDefaultButton)
        
        abortButton = QPushButton("Abort All Changes")
        abortButton.clicked.connect(self.abort_changes)
        
        stopSaveButton = QPushButton("Stop && Save")
        stopSaveButton.clicked.connect(self.stop_and_save)
        
        buttonBox.addWidget(okButton)
        buttonBox.addWidget(cancelButton)
        buttonBox.addWidget(abortButton)
        buttonBox.addWidget(stopSaveButton)
        
        layout.addLayout(buttonBox)
        self.setMinimumWidth(600)

    def set_dialog_color(self, operation_type):
        """Set dialog background color based on operation type."""
        if operation_type == "add":
            # Light blue background for adding new fields
            self.setStyleSheet("""
                QDialog {
                    background-color: #E3F2FD;
                    border: 2px solid #2196F3;
                }
                QLabel {
                    background-color: transparent;
                }
                QLineEdit {
                    background-color: white;
                    border: 1px solid #2196F3;
                    padding: 5px;
                }
            """)
        elif operation_type == "different":
            # Light orange background for editing fields that differ from default
            self.setStyleSheet("""
                QDialog {
                    background-color: #FFF3E0;
                    border: 2px solid #FF9800;
                }
                QLabel {
                    background-color: transparent;
                }
                QLineEdit {
                    background-color: white;
                    border: 1px solid #FF9800;
                    padding: 5px;
                }
            """)
        else:
            # Light green background for editing existing fields that are the same as default
            self.setStyleSheet("""
                QDialog {
                    background-color: #E8F5E8;
                    border: 2px solid #4CAF50;
                }
                QLabel {
                    background-color: transparent;
                }
                QLineEdit {
                    background-color: white;
                    border: 1px solid #4CAF50;
                    padding: 5px;
                }
            """)

    def getValue(self):
        return self.inputField.text()
        
    def abort_changes(self):
        self.done(self.RESULT_ABORT)
        
    def stop_and_save(self):
        self.done(self.RESULT_STOP_SAVE)
    
    def use_default(self):
        self.done(self.RESULT_USE_DEFAULT)

    @staticmethod
    def getText(parent, title, text, value="", default_value=None, operation_type="edit"):
        # Check if the value contains newlines (multiline)
        if '\n' in str(value):
            # Use multiline dialog for multiline values
            from .multiline_dialog import MultilineInputDialog
            
            # Update title to indicate operation type
            if operation_type == "add":
                title = f"🆕 {title}"
            elif operation_type == "different":
                title = f"⚠️ {title}"
            else:
                title = f"✏️ {title}"
            
            dialog = MultilineInputDialog(str(value), parent, text, default_value, operation_type)
            dialog.setWindowTitle(title)
            
            # Set background color based on operation type
            if operation_type == "add":
                dialog.setStyleSheet("""
                    QDialog {
                        background-color: #E3F2FD;
                        border: 2px solid #2196F3;
                    }
                    QTextEdit {
                        background-color: white;
                        border: 1px solid #2196F3;
                        padding: 5px;
                    }
                """)
            elif operation_type == "different":
                dialog.setStyleSheet("""
                    QDialog {
                        background-color: #FFF3E0;
                        border: 2px solid #FF9800;
                    }
                    QTextEdit {
                        background-color: white;
                        border: 1px solid #FF9800;
                        padding: 5px;
                    }
                """)
            else:
                dialog.setStyleSheet("""
                    QDialog {
                        background-color: #E8F5E8;
                        border: 2px solid #4CAF50;
                    }
                    QTextEdit {
                        background-color: white;
                        border: 1px solid #4CAF50;
                        padding: 5px;
                    }
                """)
            
            result = dialog.exec()
            
            if result == QDialog.DialogCode.Accepted:
                return dialog.getText(), QDialog.DialogCode.Accepted
            elif result == MultilineInputDialog.RESULT_ABORT:
                return None, CIFInputDialog.RESULT_ABORT
            elif result == MultilineInputDialog.RESULT_STOP_SAVE:
                return dialog.getText(), CIFInputDialog.RESULT_STOP_SAVE
            elif result == MultilineInputDialog.RESULT_USE_DEFAULT:
                return default_value, QDialog.DialogCode.Accepted
            else:
                return None, QDialog.DialogCode.Rejected
        else:
            # Use single-line dialog for single-line values
            dialog = CIFInputDialog(title, text, value, default_value, parent, operation_type)
            result = dialog.exec()
            
            if result == QDialog.DialogCode.Accepted:
                return dialog.getValue(), QDialog.DialogCode.Accepted
            elif result == CIFInputDialog.RESULT_ABORT:
                return None, CIFInputDialog.RESULT_ABORT
            elif result == CIFInputDialog.RESULT_STOP_SAVE:
                return dialog.getValue(), CIFInputDialog.RESULT_STOP_SAVE
            elif result == CIFInputDialog.RESULT_USE_DEFAULT:
                return default_value, QDialog.DialogCode.Accepted
            else:
                return None, QDialog.DialogCode.Rejected
