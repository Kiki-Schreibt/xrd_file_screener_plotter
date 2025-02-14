#gui.py
import os
import sys
import threading

import pandas as pd
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QGroupBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QMessageBox, QLineEdit, QComboBox, QCheckBox
)
from PySide6.QtCore import Qt, QEvent

# Import backend modules.
from main_backend import MainBackend
from xrd_file_screener import DataScreener
from stacked_plot_widget import StackedPlotWidget


# Custom event to safely schedule a function to run on the main GUI thread.
class FunctionEvent(QEvent):
    def __init__(self, func):
        super().__init__(QEvent.User)
        self.func = func


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XRD and PTH Data GUI")
        self.resize(1200, 800)
        # Variables to store paths, filters, etc.
        self.xrd_path = ""
        self.pth_path = ""
        self.filter_inputs = {}   # QLineEdits keyed by category.
        self.available_categories = []  # To be set after selecting XRD data.
        # Use a table widget for PTH files (4 columns: Include, Filename, Threshold, Max Count).
        self.pth_table_widget = QTableWidget()

        # New grouping widgets:
        self.group_by_combo = QComboBox()
        self.agg_column_combo = QComboBox()  # For selecting the aggregation column.
        self.agg_func_combo = QComboBox()      # For choosing 'min' or 'max'.

        self.init_ui()

        self.pth_table_widget.itemChanged.connect(self.on_pth_table_item_changed)
        self.current_plot_widget = None  # Will hold the current StackedPlotWidget instance.
        self.backend = None  # Will be created in process_and_plot
        self.current_df_filtered = None  # To store filtered XRD data for reuse.

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)

        # Left panel: Control widgets.
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)

        # --- Data Selection Group ---
        data_group = QGroupBox("Data Selection")
        data_layout = QVBoxLayout(data_group)
        self.xrd_select_button = QPushButton("Select XRD Folder/File")
        self.xrd_select_button.clicked.connect(self.select_xrd_data)
        self.xrd_path_label = QLabel("No XRD data selected")
        self.pth_select_button = QPushButton("Select PTH Folder/File")
        self.pth_select_button.clicked.connect(self.select_pth_data)
        self.pth_path_label = QLabel("No PTH data selected")
        data_layout.addWidget(self.xrd_select_button)
        data_layout.addWidget(self.xrd_path_label)
        data_layout.addWidget(self.pth_select_button)
        data_layout.addWidget(self.pth_path_label)
        control_layout.addWidget(data_group)

        # --- Filter Group ---
        self.filter_group = QGroupBox("XRD Data Filters")
        self.filter_form = QFormLayout(self.filter_group)
        # (Will be populated after selecting XRD data.)
        control_layout.addWidget(self.filter_group)

        # --- Grouping Options Group ---
        grouping_group = QGroupBox("Grouping Options")
        grouping_layout = QHBoxLayout(grouping_group)
        # Group-by Combo Box.
        self.group_by_combo.addItem("None")
        # Aggregation Column Combo Box.
        self.agg_column_combo.addItem("None")
        # Aggregation Function Combo Box.
        self.agg_func_combo.addItems(["min", "max"])
        grouping_layout.addWidget(QLabel("Group by:"))
        grouping_layout.addWidget(self.group_by_combo)
        grouping_layout.addWidget(QLabel("Agg. Column:"))
        grouping_layout.addWidget(self.agg_column_combo)
        grouping_layout.addWidget(QLabel("Agg. Func:"))
        grouping_layout.addWidget(self.agg_func_combo)
        control_layout.addWidget(grouping_group)

        # --- PTH Instances Group ---
        self.pth_group = QGroupBox("PTH Instances")
        pth_layout = QVBoxLayout(self.pth_group)
        # Set up the table: 4 columns ("Include", "Filename", "Threshold", "Max Count")
        self.pth_table_widget.setColumnCount(4)
        self.pth_table_widget.setHorizontalHeaderLabels(
            ["Include", "Filename", "Threshold", "Max Count"]
        )
        pth_layout.addWidget(self.pth_table_widget)
        control_layout.addWidget(self.pth_group)

        # --- Process and Plot Button ---
        self.process_button = QPushButton("Process and Plot")
        self.process_button.clicked.connect(self.process_and_plot)
        control_layout.addWidget(self.process_button)
        control_layout.addStretch()

        self.init_pattern_constructor()
        control_layout.addWidget(self.pattern_group)

        main_layout.addWidget(control_widget, 1)

        # Right panel: Plot area.
        self.plot_container = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_container)
        # Initially empty; will be filled with the StackedPlotWidget.
        main_layout.addWidget(self.plot_container, 3)

        self.setCentralWidget(central_widget)

    def init_pattern_constructor(self):
         # NEW: Filename Pattern Builder Group
        self.pattern_group = QGroupBox("Filename Pattern Builder")
        pattern_layout = QVBoxLayout(self.pattern_group)

        self.use_default_pattern_checkbox = QCheckBox("Use Default Pattern")
        self.use_default_pattern_checkbox.setChecked(True)
        self.use_default_pattern_checkbox.stateChanged.connect(self.toggle_custom_pattern)
        pattern_layout.addWidget(self.use_default_pattern_checkbox)

        self.custom_pattern_lineedit = QLineEdit()
        self.custom_pattern_lineedit.setPlaceholderText("Custom regex pattern (e.g., use Add Token to build)")
        self.custom_pattern_lineedit.setEnabled(False)
        pattern_layout.addWidget(self.custom_pattern_lineedit)

        # A combobox with token names and a button to add the token's regex group.
        self.token_combo = QComboBox()
        self.token_combo.addItems(["gas", "pressure", "cycle", "numMes", "currentStep", "noIntMes", "temperature"])
        self.token_combo.setEnabled(False)
        pattern_layout.addWidget(self.token_combo)

        self.add_token_button = QPushButton("Add Token")
        self.add_token_button.setEnabled(False)
        self.add_token_button.clicked.connect(self.add_token_to_pattern)
        pattern_layout.addWidget(self.add_token_button)

        return pattern_layout

    def select_xrd_data(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, "Select XRD Data Folder", options=options)
        if folder:
            self.xrd_path = folder
            self.xrd_path_label.setText(self.xrd_path)
            # Use DataScreener to get available categories.
            screener = DataScreener(source=self.xrd_path)
            screener.load()
            self.available_categories = screener.get_available_categories()
            # Rebuild the filter form.
            while self.filter_form.count():
                child = self.filter_form.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            self.filter_inputs = {}
            for category in self.available_categories:
                le = QLineEdit()
                le.setPlaceholderText("Leave blank for all")
                self.filter_inputs[category] = le
                self.filter_form.addRow(category, le)
            # Populate the group_by and aggregation column combo boxes.
            self.group_by_combo.clear()
            self.group_by_combo.addItem("None")
            self.agg_column_combo.clear()
            self.agg_column_combo.addItem("None")
            for col in self.available_categories:
                self.group_by_combo.addItem(col)
                self.agg_column_combo.addItem(col)

    def select_pth_data(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, "Select PTH Data Folder", options=options)
        if folder:
            self.pth_path = folder
            self.pth_path_label.setText(self.pth_path)
            # Populate the table with available PTH filenames.
            from pth_processor import PTHProcessor
            processor = PTHProcessor(folder_path=self.pth_path)
            processor.load_pth_files(add_metadata=True)
            filenames = processor.get_available_filenames()
            self.pth_table_widget.setRowCount(len(filenames))
            self.pth_table_widget.setColumnCount(4)
            self.pth_table_widget.setHorizontalHeaderLabels(
                ["Include", "Filename", "Threshold", "Max Count"]
            )
            for row, filename in enumerate(filenames):
                # Column 0: Checkbox (default unchecked)
                item_checkbox = QTableWidgetItem()
                item_checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                item_checkbox.setCheckState(Qt.Unchecked)
                self.pth_table_widget.setItem(row, 0, item_checkbox)

                # Column 1: Filename (non-editable)
                item_filename = QTableWidgetItem(filename)
                item_filename.setFlags(item_filename.flags() ^ Qt.ItemIsEditable)
                self.pth_table_widget.setItem(row, 1, item_filename)

                # Column 2: Threshold (editable, default value "80")
                item_threshold = QTableWidgetItem("80")
                item_threshold.setTextAlignment(Qt.AlignCenter)
                self.pth_table_widget.setItem(row, 2, item_threshold)

                # Column 3: Max Count (editable, default value "5")
                item_max = QTableWidgetItem("5")
                item_max.setTextAlignment(Qt.AlignCenter)
                self.pth_table_widget.setItem(row, 3, item_max)
            self.pth_table_widget.resizeColumnsToContents()

    @staticmethod
    def parse_filter_value(text):
        """
        Convert a filter string into an appropriate type.
          - "0-100" becomes a tuple (0, 100)
          - "A, B, C" becomes a list ["A", "B", "C"] (with numeric conversion if possible)
          - Numeric strings are converted to int or float.
          - Otherwise, returns the string.
        """
        text = text.strip()
        # Check for a range input.
        if '-' in text and not text.startswith('-'):
            parts = text.split('-')
            if len(parts) == 2:
                try:
                    lower = float(parts[0].strip())
                    upper = float(parts[1].strip())
                    return (lower, upper)
                except ValueError:
                    pass
        # Check for a comma-separated list.
        if ',' in text:
            parts = [p.strip() for p in text.split(',')]
            parsed_parts = []
            for p in parts:
                try:
                    if '.' in p:
                        parsed_parts.append(float(p))
                    else:
                        parsed_parts.append(int(p))
                except ValueError:
                    parsed_parts.append(p)
            return parsed_parts
        try:
            if text.isdigit():
                return int(text)
            return float(text)
        except ValueError:
            return text

    def process_and_plot(self):
        # Build filter dictionary from inputs.
        filters = {}
        for category, widget in self.filter_inputs.items():
            text = widget.text().strip()
            if text:
                filters[category] = MainWindow.parse_filter_value(text)

        # Process PTH table: only if there are any rows in the table.
        selected_files = []
        thresholds = {}
        max_counts = {}
        if self.pth_table_widget.rowCount() > 0:
            rows = self.pth_table_widget.rowCount()
            for row in range(rows):
                include_item = self.pth_table_widget.item(row, 0)
                if include_item is not None and include_item.checkState() == Qt.Checked:
                    filename_item = self.pth_table_widget.item(row, 1)
                    threshold_item = self.pth_table_widget.item(row, 2)
                    max_count_item = self.pth_table_widget.item(row, 3)
                    if filename_item is None or threshold_item is None or max_count_item is None:
                        continue
                    filename = filename_item.text()
                    try:
                        thresh = int(threshold_item.text())
                    except ValueError:
                        thresh = 80
                    try:
                        max_count = int(max_count_item.text())
                    except ValueError:
                        max_count = 5
                    selected_files.append(filename)
                    thresholds[filename] = thresh
                    max_counts[filename] = max_count

        if not self.xrd_path:
            QMessageBox.warning(self, "Error", "Please select an XRD data folder.")
            return
        custom_pattern = None
        if not self.use_default_pattern_checkbox.isChecked():
            pattern_text = self.custom_pattern_lineedit.text().strip()
            if pattern_text:
                custom_pattern = pattern_text

        vertical_offset = 500  # This could be dynamic.
        # Create MainBackend instance. pth_folder is set only if provided.
        self.backend = MainBackend(
                        xrd_folder=self.xrd_path,
                        pkl_path=os.path.join(self.xrd_path, "categorized_data.pkl"),
                        pth_folder=self.pth_path if self.pth_path else None,
                        filters=filters,
                        vertical_offset=vertical_offset,
                        group_by=(self.group_by_combo.currentText() if self.group_by_combo.currentText() != "None" else None),
                        agg_by=((self.agg_column_combo.currentText(), self.agg_func_combo.currentText())
                                if self.agg_column_combo.currentText() != "None" else None),
                        custom_filename_pattern=custom_pattern  # New parameter
                    )

        def process_data():
            df_lines = pd.DataFrame()
            if not self.backend.load_xrd_data():
                return
            self.current_df_filtered = self.backend.filter_xrd_data()
            if self.current_df_filtered.empty:
                print("Filtered XRD data is empty.")
                return

            # Process PTH data only if a PTH folder is provided.
            if self.backend.pth_folder:
                df_lines = self.backend.process_pth_data(
                    criteria={"filename": selected_files},
                    thresholds=thresholds,
                    max_counts=max_counts
                )

            def update_plot():
                # Clear any existing plot widget.
                while self.plot_layout.count():
                    widget = self.plot_layout.takeAt(0).widget()
                    if widget:
                        widget.setParent(None)
                self.current_plot_widget = StackedPlotWidget(self.current_df_filtered, vertical_offset=vertical_offset)
                # Add vertical lines only if df_lines is not empty.
                if not df_lines.empty:
                    self.current_plot_widget.add_vertical_lines(df_lines=df_lines)
                self.plot_layout.addWidget(self.current_plot_widget)
            self.run_on_main_thread(update_plot)
        threading.Thread(target=process_data).start()

    # Slot to be called when an item in the pth_table_widget changes.
    def on_pth_table_item_changed(self, item):
        # Only update if the changed item is in the "Include" column.
        if item.column() == 0:
            self.update_vertical_lines()

    # Method to update vertical lines based on current PTH table state.
    def update_vertical_lines(self):
        # If no PTH folder is provided, do nothing.
        if not self.backend or not self.backend.pth_folder:
            return

        # Gather selected files, thresholds, and max counts.
        selected_files = []
        thresholds = {}
        max_counts = {}
        rows = self.pth_table_widget.rowCount()
        for row in range(rows):
            include_item = self.pth_table_widget.item(row, 0)
            if include_item is not None and include_item.checkState() == Qt.Checked:
                filename_item = self.pth_table_widget.item(row, 1)
                threshold_item = self.pth_table_widget.item(row, 2)
                max_count_item = self.pth_table_widget.item(row, 3)
                if filename_item is None or threshold_item is None or max_count_item is None:
                    continue
                filename = filename_item.text()
                try:
                    thresh = int(threshold_item.text())
                except ValueError:
                    thresh = 80
                try:
                    max_count = int(max_count_item.text())
                except ValueError:
                    max_count = 5
                selected_files.append(filename)
                thresholds[filename] = thresh
                max_counts[filename] = max_count

        # Recompute vertical lines.
        if self.backend and self.current_df_filtered is not None and self.current_plot_widget is not None:
            df_lines = self.backend.process_pth_data(
                criteria={"filename": selected_files},
                thresholds=thresholds,
                max_counts=max_counts
            )
            plot_item = self.current_plot_widget.plot_item
            # Remove existing vertical lines.
            for item in plot_item.items[:]:
                if isinstance(item, pg.InfiniteLine):
                    plot_item.removeItem(item)
            # Add new vertical lines.
            self.current_plot_widget.add_vertical_lines(df_lines=df_lines)

    def toggle_custom_pattern(self):
        use_default = self.use_default_pattern_checkbox.isChecked()
        # When using default, disable custom pattern editing.
        self.custom_pattern_lineedit.setEnabled(not use_default)
        self.token_combo.setEnabled(not use_default)
        self.add_token_button.setEnabled(not use_default)

    def add_token_to_pattern(self):
        token = self.token_combo.currentText()
        # Create a simple named group for the token (adjust the inner pattern as needed).
        token_pattern = f"(?P<{token}>\\S+)"
        current_text = self.custom_pattern_lineedit.text().strip()
        if current_text:
            new_text = current_text + " " + token_pattern
        else:
            new_text = token_pattern
        self.custom_pattern_lineedit.setText(new_text)


    def run_on_main_thread(self, func):
        QApplication.instance().postEvent(self, FunctionEvent(func))

    def customEvent(self, event):
        if isinstance(event, FunctionEvent):
            event.func()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
