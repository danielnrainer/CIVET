"""Multiline Input Dialog for editing large text fields."""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel
from PyQt6.QtCore import Qt


class MultilineInputDialog(QDialog):
    # Define result codes as class attributes
    RESULT_ABORT = 2  # User wants to abort all changes
    RESULT_STOP_SAVE = 3  # User wants to stop but save changes
    RESULT_USE_DEFAULT = 4  # User wants to use default value

    def __init__(self, text="", parent=None, context_text="", default_value=None, operation_type="edit"):
        super().__init__(parent)
        self.setWindowTitle("Edit Text")
        self.default_value = default_value
        
        layout = QVBoxLayout(self)
        
        # Add operation indicator
        operation_label = QLabel()
        if operation_type == "add":
            operation_label.setText("🆕 ADDING NEW FIELD")
            operation_label.setStyleSheet("font-weight: bold; color: #2E7D32; padding: 5px;")
        elif operation_type == "different":
            operation_label.setText("⚠️ FIELD DIFFERS FROM DEFAULT")
            operation_label.setStyleSheet("font-weight: bold; color: #F57C00; padding: 5px;")
        else:
            operation_label.setText("✏️ EDITING EXISTING FIELD")
            operation_label.setStyleSheet("font-weight: bold; color: #1565C0; padding: 5px;")
        
        operation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(operation_label)
        
        # Add context label if provided
        if context_text:
            context_label = QLabel(context_text)
            context_label.setWordWrap(True)
            context_label.setStyleSheet("padding: 10px; margin: 5px;")
            # Ensure UTF-8 text handling
            if isinstance(context_text, bytes):
                context_label.setText(context_text.decode('utf-8'))
            layout.addWidget(context_label)
        
        self.textEdit = QTextEdit()
        # Ensure UTF-8 text handling
        if isinstance(text, bytes):
            self.textEdit.setText(text.decode('utf-8'))
        else:
            self.textEdit.setText(str(text))
        layout.addWidget(self.textEdit)
        
        buttonBox = QHBoxLayout()
        
        # Save (OK) button
        saveButton = QPushButton("OK")
        saveButton.clicked.connect(self.accept)
        
        # Cancel button
        cancelButton = QPushButton("Cancel Current")
        cancelButton.clicked.connect(self.reject)
        
        # Add "Use Default" button only if default value is provided
        if default_value is not None and str(default_value).strip():
            useDefaultButton = QPushButton(f"Use Default")
            useDefaultButton.clicked.connect(self.use_default)
            buttonBox.addWidget(useDefaultButton)
        
        # Abort button
        abortButton = QPushButton("Abort All Changes")
        abortButton.clicked.connect(self.abort_changes)
        
        # Stop & Save button
        stopSaveButton = QPushButton("Stop && Save")
        stopSaveButton.clicked.connect(self.stop_and_save)
        
        buttonBox.addWidget(saveButton)
        buttonBox.addWidget(cancelButton)
        buttonBox.addWidget(abortButton)
        buttonBox.addWidget(stopSaveButton)
        layout.addLayout(buttonBox)
        
        self.setMinimumWidth(800)  # Increased width to accommodate buttons
        self.setMinimumHeight(400)

    def getText(self):
        return self.textEdit.toPlainText()
        
    def abort_changes(self):
        self.done(self.RESULT_ABORT)
        
    def stop_and_save(self):
        self.done(self.RESULT_STOP_SAVE)
    
    def use_default(self):
        self.done(self.RESULT_USE_DEFAULT)
