"""Multiline Input Dialog for editing large text fields."""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit


class MultilineInputDialog(QDialog):
    # Define result codes as class attributes
    RESULT_ABORT = 2  # User wants to abort all changes
    RESULT_STOP_SAVE = 3  # User wants to stop but save changes

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Text")
        layout = QVBoxLayout(self)
        
        self.textEdit = QTextEdit()
        self.textEdit.setText(text)
        layout.addWidget(self.textEdit)
        
        buttonBox = QHBoxLayout()
        
        # Save (OK) button
        saveButton = QPushButton("OK")
        saveButton.clicked.connect(self.accept)
        
        # Cancel button
        cancelButton = QPushButton("Cancel Current")
        cancelButton.clicked.connect(self.reject)
        
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
