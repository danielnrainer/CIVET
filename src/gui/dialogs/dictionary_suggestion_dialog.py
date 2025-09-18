"""
Dictionary Suggestion Dialog

Dialog to display suggested COMCIFS dictionaries based on CIF content analysis
and allow users to load them automatically.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QCheckBox, QScrollArea, QWidget, QGroupBox,
    QProgressBar, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from typing import List, Dict, Optional, Callable
import requests
import os

from utils.dictionary_suggestion_manager import DictionarySuggestion


class DictionaryDownloadWorker(QThread):
    """Worker thread for downloading dictionaries without blocking UI."""
    
    progress = pyqtSignal(int)
    finished = pyqtSignal(str, bool, str)  # url, success, message
    
    def __init__(self, url: str, save_path: str):
        super().__init__()
        self.url = url
        self.save_path = save_path
    
    def run(self):
        """Download dictionary file."""
        try:
            response = requests.get(self.url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
            
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress.emit(progress)
            
            self.finished.emit(self.url, True, "Dictionary downloaded successfully!")
            
        except requests.RequestException as e:
            self.finished.emit(self.url, False, f"Download failed: {str(e)}")
        except Exception as e:
            self.finished.emit(self.url, False, f"Error: {str(e)}")


class DictionarySuggestionDialog(QDialog):
    """Dialog for displaying and managing dictionary suggestions."""
    
    def __init__(self, suggestions: List[DictionarySuggestion], 
                 cif_format: str = "CIF1",
                 load_dictionary_callback: Optional[Callable[[str], bool]] = None,
                 dictionary_manager=None,
                 update_status_callback: Optional[Callable[[str], None]] = None,
                 parent=None):
        super().__init__(parent)
        self.suggestions = suggestions
        self.cif_format = cif_format
        self.load_dictionary_callback = load_dictionary_callback
        self.dictionary_manager = dictionary_manager
        self.update_status_callback = update_status_callback
        self.selected_suggestions = {}  # url -> (suggestion, checkbox)
        
        self.setWindowTitle("Dictionary Suggestions")
        self.setModal(True)
        self.resize(600, 500)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Header
        header_label = QLabel("Recommended Dictionaries")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)
        
        # Format info
        format_label = QLabel(f"Detected CIF Format: {self.cif_format}")
        format_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(format_label)
        
        # Explanation
        if self.suggestions:
            explanation = QLabel(
                "Based on your CIF content, these specialized dictionaries "
                "could improve field validation. Select dictionaries to download and load automatically:"
            )
        else:
            explanation = QLabel(
                "Based on your CIF content analysis, no specialized dictionaries are recommended. "
                "Your CIF appears to use standard field definitions only."
            )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("margin: 10px 0px;")
        layout.addWidget(explanation)
        
        if not self.suggestions:
            no_suggestions = QLabel("No specialized dictionaries suggested for this CIF file.")
            no_suggestions.setStyleSheet("color: #888; font-style: italic; padding: 20px;")
            no_suggestions.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_suggestions)
        else:
            # Scrollable suggestions area
            scroll_area = QScrollArea()
            scroll_widget = QWidget()
            scroll_layout = QVBoxLayout()
            
            for suggestion in self.suggestions:
                suggestion_widget = self.create_suggestion_widget(suggestion)
                scroll_layout.addWidget(suggestion_widget)
            
            scroll_widget.setLayout(scroll_layout)
            scroll_area.setWidget(scroll_widget)
            scroll_area.setWidgetResizable(True)
            scroll_area.setMinimumHeight(250)
            layout.addWidget(scroll_area)
        
        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        if self.suggestions:
            self.load_selected_btn = QPushButton("Load Selected Dictionaries")
            self.load_selected_btn.clicked.connect(self.load_selected_dictionaries)
            self.load_selected_btn.setEnabled(False)  # Enabled when something is selected
            button_layout.addWidget(self.load_selected_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def create_suggestion_widget(self, suggestion: DictionarySuggestion) -> QWidget:
        """Create a widget for a single dictionary suggestion."""
        group_box = QGroupBox()
        layout = QVBoxLayout()
        
        # Header with checkbox and name
        header_layout = QHBoxLayout()
        
        checkbox = QCheckBox(suggestion.name)
        checkbox.setStyleSheet("font-weight: bold;")
        checkbox.stateChanged.connect(self.on_selection_changed)
        header_layout.addWidget(checkbox)
        
        # Confidence indicator
        confidence_label = QLabel(f"Match: {suggestion.confidence:.0%}")
        confidence_color = "#4CAF50" if suggestion.confidence > 0.7 else "#FF9800" if suggestion.confidence > 0.4 else "#9E9E9E"
        confidence_label.setStyleSheet(f"color: {confidence_color}; font-size: 11px;")
        header_layout.addWidget(confidence_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Description
        desc_label = QLabel(suggestion.description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-left: 20px;")
        layout.addWidget(desc_label)
        
        # Trigger fields
        if suggestion.trigger_fields:
            trigger_text = "Triggered by: " + ", ".join(suggestion.trigger_fields[:3])
            if len(suggestion.trigger_fields) > 3:
                trigger_text += f" (and {len(suggestion.trigger_fields) - 3} more)"
            
            trigger_label = QLabel(trigger_text)
            trigger_label.setStyleSheet("color: #888; font-size: 11px; margin-left: 20px; font-family: monospace;")
            layout.addWidget(trigger_label)
        
        # Local file info or download info
        if suggestion.local_file and os.path.exists(suggestion.local_file):
            local_label = QLabel("✓ Available locally")
            local_label.setStyleSheet("color: #4CAF50; font-size: 11px; margin-left: 20px;")
            layout.addWidget(local_label)
        else:
            # Show that it will be downloaded
            download_label = QLabel(f"🌐 Will download from: {suggestion.url}")
            download_label.setStyleSheet("color: #2196F3; font-size: 11px; margin-left: 20px;")
            download_label.setWordWrap(True)
            layout.addWidget(download_label)
        
        group_box.setLayout(layout)
        
        # Store reference
        self.selected_suggestions[suggestion.url] = (suggestion, checkbox)
        
        return group_box
    
    def on_selection_changed(self):
        """Handle checkbox selection changes."""
        selected_count = sum(1 for _, checkbox in self.selected_suggestions.values() 
                           if checkbox.isChecked())
        
        if hasattr(self, 'load_selected_btn'):
            self.load_selected_btn.setEnabled(selected_count > 0)
            self.load_selected_btn.setText(
                f"Load Selected Dictionaries ({selected_count})" if selected_count > 0
                else "Load Selected Dictionaries"
            )
    
    def load_selected_dictionaries(self):
        """Load the selected dictionaries by downloading them if necessary."""
        if not self.dictionary_manager:
            QMessageBox.information(self, "Info", 
                                  "Dictionary manager not available for downloading.")
            return
        
        selected = [(suggestion, checkbox) for suggestion, checkbox 
                   in self.selected_suggestions.values() if checkbox.isChecked()]
        
        if not selected:
            return
        
        self.load_selected_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(selected))
        self.progress_bar.setValue(0)
        self.status_label.setText("Loading dictionaries...")
        
        success_count = 0
        total_count = len(selected)
        
        for i, (suggestion, checkbox) in enumerate(selected):
            self.progress_bar.setValue(i)
            self.status_label.setText(f"Loading {suggestion.name}...")
            
            success = False
            try:
                # Try local file first
                if suggestion.local_file and os.path.exists(suggestion.local_file):
                    success = self.dictionary_manager.add_dictionary(suggestion.local_file)
                    if success:
                        success_count += 1
                        checkbox.setText(f"{suggestion.name} ✓")
                        checkbox.setStyleSheet("color: #4CAF50; font-weight: bold;")
                        if self.update_status_callback:
                            self.update_status_callback(f"Loaded local dictionary: {suggestion.name}")
                    else:
                        checkbox.setText(f"{suggestion.name} ✗")
                        checkbox.setStyleSheet("color: #f44336; font-weight: bold;")
                else:
                    # Download from URL
                    self.status_label.setText(f"Downloading {suggestion.name}...")
                    success = self.dictionary_manager.add_dictionary_from_url(suggestion.url)
                    
                    if success:
                        success_count += 1
                        checkbox.setText(f"{suggestion.name} ✓")
                        checkbox.setStyleSheet("color: #4CAF50; font-weight: bold;")
                        if self.update_status_callback:
                            self.update_status_callback(f"Downloaded and loaded dictionary: {suggestion.name}")
                    else:
                        checkbox.setText(f"{suggestion.name} ✗")
                        checkbox.setStyleSheet("color: #f44336; font-weight: bold;")
                        
            except Exception as e:
                checkbox.setText(f"{suggestion.name} ✗")
                checkbox.setStyleSheet("color: #f44336; font-weight: bold;")
                QMessageBox.warning(self, "Dictionary Error",
                    f"Failed to load dictionary '{suggestion.name}':\n{str(e)}")
        
        self.progress_bar.setValue(total_count)
        
        # Final status message
        if success_count == total_count:
            self.status_label.setText(f"✓ All {success_count} dictionaries loaded successfully!")
            self.status_label.setStyleSheet("color: #4CAF50;")
        elif success_count > 0:
            self.status_label.setText(f"✓ {success_count}/{total_count} dictionaries loaded successfully.")
            self.status_label.setStyleSheet("color: #FF9800;")
        else:
            self.status_label.setText("❌ No dictionaries could be loaded.")
            self.status_label.setStyleSheet("color: #f44336;")
        
        self.load_selected_btn.setEnabled(True)
        
        # Update parent window status if callback provided
        if self.update_status_callback and success_count > 0:
            self.update_status_callback(f"Dictionary status updated - {success_count} new dictionaries loaded")
    
    def get_selected_suggestions(self) -> List[DictionarySuggestion]:
        """Get list of selected suggestions."""
        return [suggestion for suggestion, checkbox 
                in self.selected_suggestions.values() if checkbox.isChecked()]


def show_dictionary_suggestions(suggestions: List[DictionarySuggestion], 
                              cif_format: str = "CIF1",
                              load_callback: Optional[Callable] = None,
                              dictionary_manager=None,
                              update_status_callback: Optional[Callable] = None,
                              parent=None) -> List[DictionarySuggestion]:
    """
    Convenience function to show dictionary suggestions dialog.
    
    Args:
        suggestions: List of dictionary suggestions
        cif_format: Detected CIF format
        load_callback: Function to call for loading dictionaries (deprecated - use dictionary_manager)
        dictionary_manager: CIF dictionary manager instance for downloading/loading
        update_status_callback: Function to call for status updates
        parent: Parent widget
    
    Returns:
        List of selected suggestions
    """
    dialog = DictionarySuggestionDialog(
        suggestions, cif_format, load_callback, dictionary_manager, 
        update_status_callback, parent
    )
    dialog.exec()
    return dialog.get_selected_suggestions()