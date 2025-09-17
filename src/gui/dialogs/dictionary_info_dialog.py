"""
Dictionary Information Dialog
============================

Dialog window to display detailed information about loaded CIF dictionaries,
including source locations, field counts, and the ability to load new dictionaries
from files or URLs.
"""

import os
import sys
from typing import List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QPushButton, QLabel, QMessageBox, QFileDialog, QInputDialog, QProgressBar,
    QGroupBox, QTextEdit, QSplitter, QHeaderView, QAbstractItemView, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon
import requests

# Add parent directories to path to import from utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from utils.cif_dictionary_manager import CIFDictionaryManager, DictionaryInfo


class DictionaryDownloadWorker(QThread):
    """Worker thread for downloading dictionaries from URLs"""
    
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(int)  # progress percentage
    
    def __init__(self, url: str, dict_manager: CIFDictionaryManager):
        super().__init__()
        self.url = url
        self.dict_manager = dict_manager
    
    def run(self):
        """Download and add dictionary from URL"""
        try:
            self.progress.emit(10)
            
            # Validate URL
            if not self.url.startswith(('http://', 'https://')):
                self.finished.emit(False, "Invalid URL format. Must start with http:// or https://")
                return
            
            self.progress.emit(30)
            
            # Add dictionary from URL
            success = self.dict_manager.add_dictionary_from_url(self.url)
            
            self.progress.emit(100)
            
            if success:
                self.finished.emit(True, f"Successfully loaded dictionary from {self.url}")
            else:
                self.finished.emit(False, f"Failed to load dictionary from {self.url}")
                
        except requests.RequestException as e:
            self.finished.emit(False, f"Network error: {str(e)}")
        except Exception as e:
            self.finished.emit(False, f"Error loading dictionary: {str(e)}")


class BulkCOMCIFSDownloadWorker(QThread):
    """Worker thread for downloading all COMCIFS dictionaries"""
    
    finished = pyqtSignal(dict)  # results dictionary
    progress = pyqtSignal(int)  # progress percentage
    status_update = pyqtSignal(str)  # current status message
    
    def __init__(self, dict_manager: CIFDictionaryManager):
        super().__init__()
        self.dict_manager = dict_manager
    
    def run(self):
        """Download all COMCIFS dictionaries"""
        try:
            self.progress.emit(10)
            self.status_update.emit("Starting COMCIFS downloads...")
            
            # Use the dictionary manager's method to load all COMCIFS dictionaries
            results = self.dict_manager.load_all_comcifs_dictionaries(timeout=30)
            
            self.progress.emit(100)
            self.status_update.emit("Download complete")
            self.finished.emit(results)
            
        except Exception as e:
            self.status_update.emit(f"Error: {str(e)}")
            # Return empty results dict to indicate failure
            self.finished.emit({})


class DictionaryInfoDialog(QDialog):
    """
    Dialog for displaying and managing CIF dictionary information
    """
    
    def __init__(self, dict_manager: CIFDictionaryManager, parent=None):
        super().__init__(parent)
        self.dict_manager = dict_manager
        self.download_worker = None
        
        self.setWindowTitle("Dictionary Information")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        self.setup_ui()
        self.load_dictionary_data()
        
        # Apply some styling
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: #fafafa;
                alternate-background-color: #f0f0f0;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #3875d7;
                color: white;
            }
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
        """)
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout()
        
        # Summary section
        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout()
        
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)
        
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        # Create splitter for table and details
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Dictionaries table section
        table_group = QGroupBox("Loaded Dictionaries")
        table_layout = QVBoxLayout()
        
        self.dict_table = QTableWidget()
        self.dict_table.setColumnCount(6)
        self.dict_table.setHorizontalHeaderLabels([
            "Name", "Source", "Type", "Fields", "Size", "Loaded"
        ])
        
        # Set table properties
        self.dict_table.setAlternatingRowColors(True)
        self.dict_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dict_table.horizontalHeader().setStretchLastSection(True)
        self.dict_table.verticalHeader().setVisible(False)
        
        # Connect selection change
        self.dict_table.itemSelectionChanged.connect(self.on_selection_changed)
        
        table_layout.addWidget(self.dict_table)
        table_group.setLayout(table_layout)
        splitter.addWidget(table_group)
        
        # Dictionary details section
        details_group = QGroupBox("Dictionary Details")
        details_layout = QVBoxLayout()
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)
        
        details_group.setLayout(details_layout)
        splitter.addWidget(details_group)
        
        # Set splitter proportions
        splitter.setSizes([400, 150])
        layout.addWidget(splitter)
        
        # Action buttons section
        buttons_group = QGroupBox("Actions")
        buttons_layout = QVBoxLayout()
        
        # First row: Load dictionaries
        load_layout = QHBoxLayout()
        
        self.load_file_btn = QPushButton("Load from File...")
        self.load_file_btn.clicked.connect(self.load_dictionary_from_file)
        load_layout.addWidget(self.load_file_btn)
        
        self.load_url_btn = QPushButton("Load from URL...")
        self.load_url_btn.clicked.connect(self.load_dictionary_from_url)
        load_layout.addWidget(self.load_url_btn)
        
        self.load_comcif_btn = QPushButton("Load COMCIFS Dictionary...")
        self.load_comcif_btn.clicked.connect(self.load_comcifs_dictionary)
        load_layout.addWidget(self.load_comcif_btn)
        
        self.load_all_comcif_btn = QPushButton("Load All COMCIFS")
        self.load_all_comcif_btn.clicked.connect(self.load_all_comcifs_dictionaries)
        load_layout.addWidget(self.load_all_comcif_btn)
        
        load_layout.addStretch()
        buttons_layout.addLayout(load_layout)
        
        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        buttons_layout.addWidget(self.progress_bar)
        
        # Second row: Refresh, Remove, and Close
        action_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)
        action_layout.addWidget(self.refresh_btn)
        
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected_dictionary)
        self.remove_btn.setEnabled(False)  # Initially disabled
        action_layout.addWidget(self.remove_btn)
        
        action_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        action_layout.addWidget(self.close_btn)
        
        buttons_layout.addLayout(action_layout)
        buttons_group.setLayout(buttons_layout)
        layout.addWidget(buttons_group)
        
        self.setLayout(layout)
    
    def load_dictionary_data(self):
        """Load and display dictionary information"""
        try:
            detailed_info = self.dict_manager.get_detailed_dictionary_info()
            dict_summary = self.dict_manager.get_dictionary_info()
            
            # Update summary
            total_dicts = len(detailed_info)
            total_fields = dict_summary.get('total_cif1_mappings', 0)
            
            summary_text = f"""
            <b>Total Dictionaries:</b> {total_dicts}<br>
            <b>Total Field Mappings:</b> {total_fields} CIF1→CIF2, {dict_summary.get('total_cif2_mappings', 0)} CIF2→CIF1<br>
            <b>Primary Dictionary:</b> {detailed_info[0].name if detailed_info else 'None'}
            """
            if total_dicts > 1:
                summary_text += f"<br><b>Additional Dictionaries:</b> {total_dicts - 1}"
            
            self.summary_label.setText(summary_text)
            
            # Clear and update table
            self.dict_table.clearContents()
            self.dict_table.setRowCount(len(detailed_info))
            
            for row, dict_info in enumerate(detailed_info):
                # Name
                self.dict_table.setItem(row, 0, QTableWidgetItem(dict_info.name))
                
                # Source (show just filename for files, full URL for web)
                if dict_info.source_type == 'url':
                    source_text = dict_info.path
                elif dict_info.source_type == 'file':
                    source_text = os.path.dirname(dict_info.path) or "Current directory"
                else:
                    source_text = dict_info.source_type.capitalize()
                    
                self.dict_table.setItem(row, 1, QTableWidgetItem(source_text))
                
                # Type
                type_text = dict_info.source_type.upper()
                if row == 0:
                    type_text += " (Primary)"
                self.dict_table.setItem(row, 2, QTableWidgetItem(type_text))
                
                # Fields
                self.dict_table.setItem(row, 3, QTableWidgetItem(str(dict_info.field_count)))
                
                # Size
                size_text = self.format_file_size(dict_info.size_bytes)
                self.dict_table.setItem(row, 4, QTableWidgetItem(size_text))
                
                # Loaded time
                if dict_info.loaded_time:
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(dict_info.loaded_time)
                        time_text = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        time_text = dict_info.loaded_time
                else:
                    time_text = "Unknown"
                self.dict_table.setItem(row, 5, QTableWidgetItem(time_text))
            
            # Resize columns
            header = self.dict_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Name
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # Source
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Type  
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Fields
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Size
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Loaded
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load dictionary information: {str(e)}")
    
    def on_selection_changed(self):
        """Handle table selection changes"""
        current_row = self.dict_table.currentRow()
        if current_row >= 0:
            try:
                detailed_info = self.dict_manager.get_detailed_dictionary_info()
                if current_row < len(detailed_info):
                    dict_info = detailed_info[current_row]
                    
                    details_html = f"""
                    <h3>{dict_info.name}</h3>
                    <b>Description:</b> {dict_info.description or 'No description available'}<br><br>
                    <b>Full Path:</b> {dict_info.path}<br>
                    <b>Source Type:</b> {dict_info.source_type.upper()}<br>
                    <b>File Size:</b> {self.format_file_size(dict_info.size_bytes)}<br>
                    <b>Field Count:</b> {dict_info.field_count}<br>
                    <b>Loaded:</b> {dict_info.loaded_time or 'Unknown'}
                    """
                    
                    if dict_info.version:
                        details_html += f"<br><b>Version:</b> {dict_info.version}"
                    
                    self.details_text.setHtml(details_html)
                
            except Exception as e:
                self.details_text.setPlainText(f"Error loading details: {str(e)}")
        else:
            self.details_text.clear()
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def load_dictionary_from_file(self):
        """Load a dictionary from a local file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select CIF Dictionary File", 
            "", 
            "CIF Dictionary Files (*.dic);;All Files (*)"
        )
        
        if file_path:
            try:
                success = self.dict_manager.add_dictionary(file_path)
                if success:
                    QMessageBox.information(
                        self, 
                        "Success", 
                        f"Successfully loaded dictionary from {os.path.basename(file_path)}"
                    )
                    self.refresh_data()
                else:
                    QMessageBox.warning(
                        self, 
                        "Error", 
                        f"Failed to load dictionary from {file_path}"
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Error", 
                    f"Error loading dictionary: {str(e)}"
                )
    
    def load_dictionary_from_url(self):
        """Load a dictionary from a URL"""
        url, ok = QInputDialog.getText(
            self, 
            "Load Dictionary from URL", 
            "Enter the URL of the CIF dictionary file:",
            text="https://github.com/COMCIFS/cif_core/raw/master/"
        )
        
        if ok and url:
            self.start_url_download(url)
    
    def load_comcifs_dictionary(self):
        """Show dialog to load common COMCIFS dictionaries"""
        # Get available COMCIFS dictionaries from the manager
        available_dicts = self.dict_manager.get_available_comcifs_dictionaries()
        
        # Create display names with descriptions
        display_options = []
        dict_mapping = {}
        
        for dict_id, dict_info in available_dicts.items():
            display_name = f"{dict_info['name']} - {dict_info['description']}"
            display_options.append(display_name)
            dict_mapping[display_name] = dict_info['url']
        
        dict_name, ok = QInputDialog.getItem(
            self,
            "Load COMCIFS Dictionary",
            "Select a dictionary to load:",
            display_options,
            0,
            False
        )
        
        if ok and dict_name:
            url = dict_mapping[dict_name]
            self.start_url_download(url)
    
    def load_all_comcifs_dictionaries(self):
        """Load all available COMCIFS dictionaries"""
        # Get available dictionaries dynamically
        available_dicts = self.dict_manager.get_available_comcifs_dictionaries()
        dict_count = len(available_dicts)
        
        # Build dictionary list for display
        dict_list = ""
        for dict_info in available_dicts.values():
            dict_list += f"• {dict_info['name']}\n"
        
        reply = QMessageBox.question(
            self,
            "Load All COMCIFS Dictionaries",
            f"This will download and load all {dict_count} available COMCIFS dictionaries:\n\n"
            f"{dict_list}\n"
            "This may take a few moments. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_bulk_comcifs_download()
    
    def start_bulk_comcifs_download(self):
        """Start downloading all COMCIFS dictionaries"""
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Disable buttons during download
        self.load_file_btn.setEnabled(False)
        self.load_url_btn.setEnabled(False) 
        self.load_comcif_btn.setEnabled(False)
        self.load_all_comcif_btn.setEnabled(False)
        
        # Create and start bulk download worker
        self.bulk_download_worker = BulkCOMCIFSDownloadWorker(self.dict_manager)
        self.bulk_download_worker.progress.connect(self.progress_bar.setValue)
        self.bulk_download_worker.finished.connect(self.on_bulk_download_finished)
        self.bulk_download_worker.status_update.connect(self.show_status_message)
        self.bulk_download_worker.start()
    
    def on_bulk_download_finished(self, results: dict):
        """Handle bulk download completion"""
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Re-enable buttons
        self.load_file_btn.setEnabled(True)
        self.load_url_btn.setEnabled(True)
        self.load_comcif_btn.setEnabled(True)
        self.load_all_comcif_btn.setEnabled(True)
        
        # Show results
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        if successful == total:
            QMessageBox.information(
                self,
                "Download Complete",
                f"Successfully loaded all {total} COMCIFS dictionaries!"
            )
        elif successful > 0:
            failed_dicts = [name for name, success in results.items() if not success]
            QMessageBox.warning(
                self,
                "Partial Success",
                f"Loaded {successful} of {total} dictionaries.\n\n"
                f"Failed to load: {', '.join(failed_dicts)}"
            )
        else:
            QMessageBox.critical(
                self,
                "Download Failed",
                "Failed to load any COMCIFS dictionaries. Please check your internet connection."
            )
        
        # Refresh the dictionary list
        self.refresh_data()
    
    def show_status_message(self, message: str):
        """Show status message in the UI"""
        # Could be used to show current dictionary being downloaded
        # For now, just update the window title temporarily
        original_title = self.windowTitle()
        self.setWindowTitle(f"{original_title} - {message}")
        QTimer.singleShot(2000, lambda: self.setWindowTitle(original_title))
    
    def start_url_download(self, url: str):
        """Start downloading dictionary from URL"""
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Disable buttons during download
        self.load_file_btn.setEnabled(False)
        self.load_url_btn.setEnabled(False) 
        self.load_comcif_btn.setEnabled(False)
        self.load_all_comcif_btn.setEnabled(False)
        
        # Start download worker
        self.download_worker = DictionaryDownloadWorker(url, self.dict_manager)
        self.download_worker.progress.connect(self.progress_bar.setValue)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.start()
    
    def on_download_finished(self, success: bool, message: str):
        """Handle download completion"""
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Re-enable buttons
        self.load_file_btn.setEnabled(True)
        self.load_url_btn.setEnabled(True)
        self.load_comcif_btn.setEnabled(True)
        self.load_all_comcif_btn.setEnabled(True)
        
        # Show result message
        if success:
            QMessageBox.information(self, "Success", message)
            self.refresh_data()
        else:
            QMessageBox.warning(self, "Error", message)
        
        # Clean up worker
        if self.download_worker:
            self.download_worker.deleteLater()
            self.download_worker = None
    
    def refresh_data(self):
        """Refresh the displayed dictionary information"""
        try:
            # Temporarily disable the refresh button to prevent multiple clicks
            self.refresh_btn.setEnabled(False)
            self.refresh_btn.setText("Refreshing...")
            
            # Process events to update UI
            QApplication.processEvents()
            
            # Reload dictionary data
            self.load_dictionary_data()
            
            # Update parent dictionary status if available
            try:
                if self.parent() and hasattr(self.parent(), 'update_dictionary_status'):
                    self.parent().update_dictionary_status()
            except Exception as e:
                print(f"Warning: Failed to update parent dictionary status: {e}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh dictionary data: {str(e)}")
        finally:
            # Re-enable the refresh button
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("Refresh")
    
    def on_selection_changed(self):
        """Handle table selection changes"""
        selected_rows = self.dict_table.selectionModel().selectedRows()
        
        if not selected_rows:
            self.remove_btn.setEnabled(False)
            self.details_text.clear()
            return
        
        # Enable remove button only for non-primary dictionaries (not row 0)
        selected_row = selected_rows[0].row()
        is_primary = (selected_row == 0)
        self.remove_btn.setEnabled(not is_primary)
        
        # Show details for selected dictionary
        try:
            detailed_info = self.dict_manager.get_detailed_dictionary_info()
            if selected_row < len(detailed_info):
                dict_info = detailed_info[selected_row]
                self.show_dictionary_details(dict_info)
        except Exception as e:
            self.details_text.setText(f"Error loading details: {str(e)}")
    
    def show_dictionary_details(self, dict_info):
        """Show detailed information for a dictionary"""
        details = []
        details.append(f"<b>Dictionary Details</b><br>")
        details.append(f"<b>Name:</b> {dict_info.name}")
        details.append(f"<b>Path/URL:</b> {dict_info.path}")
        details.append(f"<b>Source Type:</b> {dict_info.source_type}")
        details.append(f"<b>Field Count:</b> {dict_info.field_count:,}")
        
        if dict_info.size_bytes > 0:
            size_kb = dict_info.size_bytes / 1024
            details.append(f"<b>Size:</b> {size_kb:.1f} KB")
        
        if dict_info.loaded_time:
            details.append(f"<b>Loaded:</b> {dict_info.loaded_time}")
        
        if dict_info.description:
            details.append(f"<br><b>Description:</b><br>{dict_info.description}")
        
        self.details_text.setHtml("<br>".join(details))
    
    def remove_selected_dictionary(self):
        """Remove the selected dictionary"""
        selected_rows = self.dict_table.selectionModel().selectedRows()
        
        if not selected_rows:
            return
        
        selected_row = selected_rows[0].row()
        
        # Don't allow removal of primary dictionary (row 0)
        if selected_row == 0:
            QMessageBox.information(self, "Cannot Remove", 
                                  "The primary CIF core dictionary cannot be removed.")
            return
        
        try:
            detailed_info = self.dict_manager.get_detailed_dictionary_info()
            if selected_row >= len(detailed_info):
                return
            
            dict_info = detailed_info[selected_row]
            
            # Confirm removal
            reply = QMessageBox.question(self, "Remove Dictionary", 
                                       f"Are you sure you want to remove the dictionary:\n\n"
                                       f"{dict_info.name}\n"
                                       f"({dict_info.field_count:,} fields)\n\n"
                                       f"This action cannot be undone.",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                # Remove the dictionary
                success = self.dict_manager.remove_dictionary(dict_info.name)
                
                if success:
                    QMessageBox.information(self, "Dictionary Removed", 
                                          f"Dictionary '{dict_info.name}' has been removed successfully.")
                    # Refresh the display
                    self.refresh_data()
                else:
                    QMessageBox.warning(self, "Removal Failed", 
                                      f"Failed to remove dictionary '{dict_info.name}'.")
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", 
                               f"An error occurred while removing the dictionary:\n{str(e)}")