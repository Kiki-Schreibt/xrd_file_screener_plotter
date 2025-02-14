import sys, os, threading
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QGroupBox, QFormLayout,
    QLineEdit, QListWidget, QListWidgetItem, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, QEvent

# Import backend modules (assumed to be implemented as shown earlier)
from main_backend import MainBackend
from stacked_plot_widget import StackedPlotWidget
from xrd_file_screener import DataScreener  # used to retrieve available categories


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
        self.filter_inputs = {}   # Will be populated with QLineEdits keyed by category.
        self.selected_pth_files = []  # List of selected PTH filenames.
        self.available_categories = []  # To be retrieved after selecting XRD data.
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)

        # Left panel: Control widgets
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
        self.pth_group = QGroupBox("PTH Instances Selection")
        self.pth_layout = QVBoxLayout(self.pth_group)
        self.pth_list_widget = QListWidget()
        self.pth_layout.addWidget(self.pth_list_widget)
        control_layout.addWidget(self.pth_group)

        # --- Process and Plot Button ---
        self.process_button = QPushButton("Process and Plot")
        self.process_button.clicked.connect(self.process_and_plot)
        control_layout.addWidget(self.process_button)
        control_layout.addStretch()

        main_layout.addWidget(control_widget, 1)

        # Right panel: Plot area
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
            # Instantiate a DataScreener to get available categories.
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
                line_edit = QLineEdit()
                line_edit.setPlaceholderText("Leave blank for all")
                self.filter_inputs[category] = line_edit
                self.filter_form.addRow(category, line_edit)

    def select_pth_data(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, "Select PTH Data Folder", options=options)
        if folder:
            self.pth_path = folder
            self.pth_path_label.setText(self.pth_path)
            # Populate the list widget with available PTH filenames.
            from pth_processor import PTHProcessor  # import here to ensure dependency
            processor = PTHProcessor(folder_path=self.pth_path)
            processor.load_pth_files(add_metadata=True)
            self.pth_list_widget.clear()
            for filename in processor.get_available_filenames():
                item = QListWidgetItem(filename)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.pth_list_widget.addItem(item)

    def process_and_plot(self):
        # Build filter dictionary from inputs.
        filters = {}
        for category, widget in self.filter_inputs.items():
            text = widget.text().strip()
            if text:
                filters[category] = text  # For simplicity, using text as exact match

        # Build thresholds mapping for PTH instances.
        thresholds = {}
        selected_files = []
        for i in range(self.pth_list_widget.count()):
            item = self.pth_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                filename = item.text()
                # Prompt user to enter a threshold for each selected file.
                thresh, ok = QInputDialog.getInt(self, "Set Threshold",
                                                 f"Enter y-threshold for {filename}:", 80, 0, 1000)
                if ok:
                    thresholds[filename] = thresh
                    selected_files.append(filename)

        if not self.xrd_path or not self.pth_path:
            QMessageBox.warning(self, "Error", "Please select both XRD and PTH data folders.")
            return

        # Create MainBackend instance.
        vertical_offset = 500  # could be dynamic
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
                # Clear existing plot widget if any.
                while self.plot_layout.count():
                    widget = self.plot_layout.takeAt(0).widget()
                    if widget:
                        widget.setParent(None)
                plot_widget = StackedPlotWidget(df_filtered, vertical_offset=vertical_offset)
                plot_widget.add_vertical_lines(df_lines)
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
