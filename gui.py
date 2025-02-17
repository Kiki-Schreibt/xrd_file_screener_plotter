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

# Import backend modules (assumed to be defined elsewhere)
from main_backend import MainBackend
from xrd_file_screener import DataScreener
from stacked_plot_widget import StackedPlotWidget

# A custom event for safely scheduling functions on the main thread
class FunctionEvent(QEvent):
    def __init__(self, func):
        super().__init__(QEvent.User)
        self.func = func

# ----------------------------
# Panel Classes (each a QGroupBox)
# ----------------------------

class DataSelectionWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Data Selection", parent)
        self.xrd_select_button = QPushButton("Select XRD Folder/File")
        self.xrd_path_label = QLabel("No XRD data selected")
        self.pth_select_button = QPushButton("Select PTH Folder/File")
        self.pth_path_label = QLabel("No PTH data selected")

        layout = QVBoxLayout(self)
        layout.addWidget(self.xrd_select_button)
        layout.addWidget(self.xrd_path_label)
        layout.addWidget(self.pth_select_button)
        layout.addWidget(self.pth_path_label)


class FilterWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("XRD Data Filters", parent)
        self.form_layout = QFormLayout(self)
        self.filter_inputs = {}  # Will be populated once data is loaded

    def update_filters(self, available_categories):
        # Clear previous filter inputs
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.filter_inputs.clear()
        for cat in available_categories:
            le = QLineEdit()
            le.setPlaceholderText("Leave blank for all")
            self.filter_inputs[cat] = le
            self.form_layout.addRow(cat, le)


class GroupingOptionsWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Grouping Options", parent)
        layout = QHBoxLayout(self)
        self.group_by_combo = QComboBox()
        self.group_by_combo.addItem("None")
        self.agg_column_combo = QComboBox()
        self.agg_column_combo.addItem("None")
        self.agg_func_combo = QComboBox()
        self.agg_func_combo.addItems(["min", "max", "minmax"])

        layout.addWidget(QLabel("Group by:"))
        layout.addWidget(self.group_by_combo)
        layout.addWidget(QLabel("Agg. Column:"))
        layout.addWidget(self.agg_column_combo)
        layout.addWidget(QLabel("Agg. Func:"))
        layout.addWidget(self.agg_func_combo)


class PTHInstancesWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("PTH Instances", parent)
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(["Include", "Filename", "Threshold", "Max Count"])
        layout = QVBoxLayout(self)
        layout.addWidget(self.table_widget)

    def populate_table(self, filenames):
        self.table_widget.setRowCount(len(filenames))
        for row, filename in enumerate(filenames):
            # Column 0: Checkbox
            item_checkbox = QTableWidgetItem()
            item_checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item_checkbox.setCheckState(Qt.Unchecked)
            self.table_widget.setItem(row, 0, item_checkbox)
            # Column 1: Filename (non-editable)
            item_filename = QTableWidgetItem(filename)
            item_filename.setFlags(item_filename.flags() ^ Qt.ItemIsEditable)
            self.table_widget.setItem(row, 1, item_filename)
            # Column 2: Threshold (default "0")
            item_threshold = QTableWidgetItem("0")
            item_threshold.setTextAlignment(Qt.AlignCenter)
            self.table_widget.setItem(row, 2, item_threshold)
            # Column 3: Max Count (default "5")
            item_max = QTableWidgetItem("5")
            item_max.setTextAlignment(Qt.AlignCenter)
            self.table_widget.setItem(row, 3, item_max)
        self.table_widget.resizeColumnsToContents()


class PatternBuilderWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Filename Pattern Builder", parent)
        layout = QVBoxLayout(self)
        self.use_default_pattern_checkbox = QCheckBox("Use Default Pattern")
        self.use_default_pattern_checkbox.setChecked(True)
        self.use_default_pattern_checkbox.stateChanged.connect(self.toggle_custom_pattern)
        layout.addWidget(self.use_default_pattern_checkbox)

        self.custom_pattern_lineedit = QLineEdit()
        self.custom_pattern_lineedit.setPlaceholderText("Custom regex pattern (e.g., use Add Token to build)")
        self.custom_pattern_lineedit.setEnabled(False)
        layout.addWidget(self.custom_pattern_lineedit)

        self.token_combo = QComboBox()
        self.token_combo.addItems(["gas", "pressure", "cycle", "numMes", "currentStep", "noIntMes", "temperature"])
        self.token_combo.setEnabled(False)
        layout.addWidget(self.token_combo)

        self.add_token_button = QPushButton("Add Token")
        self.add_token_button.setEnabled(False)
        self.add_token_button.clicked.connect(self.add_token_to_pattern)
        layout.addWidget(self.add_token_button)

    def toggle_custom_pattern(self, state):
        use_default = self.use_default_pattern_checkbox.isChecked()
        self.custom_pattern_lineedit.setEnabled(not use_default)
        self.token_combo.setEnabled(not use_default)
        self.add_token_button.setEnabled(not use_default)

    def add_token_to_pattern(self):
        token = self.token_combo.currentText()
        token_pattern = f"(?P<{token}>\\S+)"
        current_text = self.custom_pattern_lineedit.text().strip()
        new_text = current_text + " " + token_pattern if current_text else token_pattern
        self.custom_pattern_lineedit.setText(new_text)

# ----------------------------
# MainWindow that composes the panels
# ----------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XRD Data GUI")
        self.resize(1200, 800)

        # Variables to store paths and data
        self.xrd_path = ""
        self.pth_path = ""
        self.available_categories = []
        self.current_df_filtered = None
        self.backend = None
        self.current_plot_widget = None

        # Main layout containers
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)

        # Left panel: Control widgets
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)

        # Instantiate each control panel
        self.data_selection = DataSelectionWidget()
        self.data_selection.xrd_select_button.clicked.connect(self.select_xrd_data)
        self.data_selection.pth_select_button.clicked.connect(self.select_pth_data)
        control_layout.addWidget(self.data_selection)

        self.filter_widget = FilterWidget()
        control_layout.addWidget(self.filter_widget)

        self.grouping_options = GroupingOptionsWidget()
        control_layout.addWidget(self.grouping_options)

        self.pth_instances = PTHInstancesWidget()
        control_layout.addWidget(self.pth_instances)

        self.pattern_builder = PatternBuilderWidget()
        control_layout.addWidget(self.pattern_builder)

        self.process_button = QPushButton("Process and Plot")
        self.process_button.clicked.connect(self.process_and_plot)
        control_layout.addWidget(self.process_button)
        control_layout.addStretch()

        # Right panel: Plot area
        self.plot_container = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_container)

        main_layout.addWidget(control_widget, 1)
        main_layout.addWidget(self.plot_container, 3)
        self.setCentralWidget(central_widget)

        # Connect change events from the PTH table
        self.pth_instances.table_widget.itemChanged.connect(self.on_pth_table_item_changed)

    def select_xrd_data(self):
        folder = QFileDialog.getExistingDirectory(self, "Select XRD Data Folder")
        if folder:
            self.xrd_path = folder
            self.data_selection.xrd_path_label.setText(folder)
            screener = DataScreener(source=self.xrd_path)
            screener.load()
            self.available_categories = screener.get_available_categories()
            self.filter_widget.update_filters(self.available_categories)
            # Update grouping combo boxes
            self.grouping_options.group_by_combo.clear()
            self.grouping_options.group_by_combo.addItem("None")
            self.grouping_options.agg_column_combo.clear()
            self.grouping_options.agg_column_combo.addItem("None")
            for col in self.available_categories:
                self.grouping_options.group_by_combo.addItem(col)
                self.grouping_options.agg_column_combo.addItem(col)

    def select_pth_data(self):
        folder = QFileDialog.getExistingDirectory(self, "Select PTH Data Folder")
        if folder:
            self.pth_path = folder
            self.data_selection.pth_path_label.setText(folder)
            from pth_processor import PTHProcessor  # assumed to be defined elsewhere
            processor = PTHProcessor(folder_path=self.pth_path)
            processor.load_pth_files(add_metadata=True)
            filenames = processor.get_available_filenames()
            self.pth_instances.populate_table(filenames)

    @staticmethod
    def parse_filter_value(text):
        text = text.strip()
        if '-' in text and not text.startswith('-'):
            parts = text.split('-')
            if len(parts) == 2:
                try:
                    lower = float(parts[0].strip())
                    upper = float(parts[1].strip())
                    return (lower, upper)
                except ValueError:
                    pass
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
        # Build filters dictionary from the filter widget
        filters = {}
        for category, widget in self.filter_widget.filter_inputs.items():
            text = widget.text().strip()
            if text:
                filters[category] = MainWindow.parse_filter_value(text)

        # Process PTH table data
        selected_files = []
        thresholds = {}
        max_counts = {}
        table = self.pth_instances.table_widget
        for row in range(table.rowCount()):
            include_item = table.item(row, 0)
            if include_item and include_item.checkState() == Qt.Checked:
                filename_item = table.item(row, 1)
                threshold_item = table.item(row, 2)
                max_count_item = table.item(row, 3)
                if not (filename_item and threshold_item and max_count_item):
                    continue
                filename = filename_item.text()
                try:
                    thresh = int(threshold_item.text())
                except ValueError:
                    thresh = 0
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
        if not self.pattern_builder.use_default_pattern_checkbox.isChecked():
            pattern_text = self.pattern_builder.custom_pattern_lineedit.text().strip()
            if pattern_text:
                custom_pattern = pattern_text

        vertical_offset = 500
        # Create backend instance
        self.backend = MainBackend(
            xrd_folder=self.xrd_path,
            pkl_path=os.path.join(self.xrd_path, "categorized_data.pkl"),
            pth_folder=self.pth_path if self.pth_path else None,
            filters=filters,
            vertical_offset=vertical_offset,
            group_by=(self.grouping_options.group_by_combo.currentText() if self.grouping_options.group_by_combo.currentText() != "None" else None),
            agg_by=((self.grouping_options.agg_column_combo.currentText(), self.grouping_options.agg_func_combo.currentText())
                    if self.grouping_options.agg_column_combo.currentText() != "None" else None),
            custom_filename_pattern=custom_pattern
        )

        def process_data():
            df_lines = pd.DataFrame()
            if not self.backend.load_xrd_data():
                return
            self.current_df_filtered = self.backend.filter_xrd_data()
            if self.current_df_filtered.empty:
                print("Filtered XRD data is empty.")
                return
            if self.backend.pth_folder:
                df_lines = self.backend.process_pth_data(
                    criteria={"filename": selected_files},
                    thresholds=thresholds,
                    max_counts=max_counts
                )
            def update_plot():
                # Clear existing plot widget
                while self.plot_layout.count():
                    widget = self.plot_layout.takeAt(0).widget()
                    if widget:
                        widget.setParent(None)
                self.current_plot_widget = StackedPlotWidget(self.current_df_filtered, vertical_offset=vertical_offset)
                if not df_lines.empty:
                    self.current_plot_widget.add_vertical_lines(df_lines=df_lines)
                self.plot_layout.addWidget(self.current_plot_widget)
            self.run_on_main_thread(update_plot)
        threading.Thread(target=process_data).start()

    def on_pth_table_item_changed(self, item):
        if item.column() == 0:
            self.update_vertical_lines()

    def update_vertical_lines(self):
        if not self.backend or self.current_df_filtered.empty or not self.current_plot_widget:
            return
        selected_files = []
        thresholds = {}
        max_counts = {}
        table = self.pth_instances.table_widget
        for row in range(table.rowCount()):
            include_item = table.item(row, 0)
            if include_item and include_item.checkState() == Qt.Checked:
                filename_item = table.item(row, 1)
                threshold_item = table.item(row, 2)
                max_count_item = table.item(row, 3)
                if not (filename_item and threshold_item and max_count_item):
                    continue
                filename = filename_item.text()
                try:
                    thresh = int(threshold_item.text())
                except ValueError:
                    thresh = 0
                try:
                    max_count = int(max_count_item.text())
                except ValueError:
                    max_count = 5
                selected_files.append(filename)
                thresholds[filename] = thresh
                max_counts[filename] = max_count
        df_lines = self.backend.process_pth_data(
            criteria={"filename": selected_files},
            thresholds=thresholds,
            max_counts=max_counts
        )
        plot_item = self.current_plot_widget.plot_item
        # Remove existing vertical lines
        for item in plot_item.items[:]:
            if isinstance(item, pg.InfiniteLine):
                plot_item.removeItem(item)
        self.current_plot_widget.add_vertical_lines(df_lines=df_lines)

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
