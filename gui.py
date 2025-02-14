#gui.py

import os
import sys
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QGroupBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QMessageBox, QLineEdit
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
        # Use a table widget for PTH files (two columns: filename and threshold).
        self.pth_table_widget = QTableWidget()
        self.init_ui()

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

        # --- PTH Instances Group ---
        self.pth_group = QGroupBox("PTH Instances")
        pth_layout = QVBoxLayout(self.pth_group)
        # Set up the table: two columns ("Filename" and "Threshold")
        self.pth_table_widget.setColumnCount(2)
        self.pth_table_widget.setHorizontalHeaderLabels(["Filename", "Threshold"])
        pth_layout.addWidget(self.pth_table_widget)
        control_layout.addWidget(self.pth_group)

        # --- Process and Plot Button ---
        self.process_button = QPushButton("Process and Plot")
        self.process_button.clicked.connect(self.process_and_plot)
        control_layout.addWidget(self.process_button)
        control_layout.addStretch()

        main_layout.addWidget(control_widget, 1)

        # Right panel: Plot area.
        self.plot_container = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_container)
        # Initially empty; will be filled with the StackedPlotWidget.
        main_layout.addWidget(self.plot_container, 3)

        self.setCentralWidget(central_widget)

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

            # Set up table with 3 columns: Include, Filename, and Threshold.
            self.pth_table_widget.setColumnCount(3)
            self.pth_table_widget.setHorizontalHeaderLabels(["Include", "Filename", "Threshold"])
            self.pth_table_widget.setRowCount(len(filenames))

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

                # Column 2: Threshold (editable, default value "0")
                item_threshold = QTableWidgetItem("0")
                item_threshold.setTextAlignment(Qt.AlignCenter)
                self.pth_table_widget.setItem(row, 2, item_threshold)

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
                    # Convert to float if possible; otherwise keep as string.
                    if '.' in p:
                        parsed_parts.append(float(p))
                    else:
                        parsed_parts.append(int(p))
                except ValueError:
                    parsed_parts.append(p)
            return parsed_parts
        # Try numeric conversion.
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

        # Read thresholds and check which files are selected.
        selected_files = []
        thresholds = {}
        rows = self.pth_table_widget.rowCount()
        for row in range(rows):
            include_item = self.pth_table_widget.item(row, 0)
            if include_item is not None and include_item.checkState() == Qt.Checked:
                filename_item = self.pth_table_widget.item(row, 1)
                threshold_item = self.pth_table_widget.item(row, 2)
                if filename_item is None or threshold_item is None:
                    continue
                filename = filename_item.text()
                try:
                    thresh = int(threshold_item.text())
                except ValueError:
                    thresh = 0
                selected_files.append(filename)
                thresholds[filename] = thresh

        if not self.xrd_path or not self.pth_path:
            QMessageBox.warning(self, "Error", "Please select both XRD and PTH data folders.")
            return

        # Create MainBackend instance.
        vertical_offset = 500  # This could be dynamic.
        group_by = 'cycle'
        agg_by = ("current_temp_step", "max")
        backend = MainBackend(
            xrd_folder=self.xrd_path,
            pkl_path=os.path.join(self.xrd_path, "categorized_data.pkl"),
            pth_folder=self.pth_path,
            filters=filters,
            vertical_offset=vertical_offset,
            group_by=group_by,
            agg_by=agg_by
        )

        # Process data in a background thread.
        def process_data():
            if not backend.load_xrd_data():
                return
            df_filtered = backend.filter_xrd_data()
            if df_filtered.empty:
                print("Filtered XRD data is empty.")
                return
            df_lines = backend.process_pth_data(
                criteria={"filename": selected_files},
                thresholds=thresholds
            )
            # Schedule plot update on the main thread.
            def update_plot():
                # Clear any existing plot widget.
                while self.plot_layout.count():
                    widget = self.plot_layout.takeAt(0).widget()
                    if widget:
                        widget.setParent(None)
                plot_widget = StackedPlotWidget(df_filtered, vertical_offset=vertical_offset)
                plot_widget.add_vertical_lines(df_lines=df_lines)
                self.plot_layout.addWidget(plot_widget)
            self.run_on_main_thread(update_plot)

        threading.Thread(target=process_data).start()

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
