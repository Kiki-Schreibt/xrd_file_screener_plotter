#main_backen.py
import os
import sys
import logging
import threading
import pandas as pd
from pyqtgraph.Qt import QtWidgets

# Import your custom classes.
from xrd_file_screener import DataScreener, FilenameCategoryExtractor  # Reads raw .rasx files and builds a DataFrame
from stacked_plot_widget import StackedPlotWidget  # Widget for plotting
from pth_processor import PTHProcessor         # New class to handle PTH file processing

# Configure logging for better debugging and traceability.
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


class MainBackend:
    def __init__(self,
                 xrd_folder: str,
                 pkl_path: str,
                 pth_folder: str,
                 filters: dict,
                 vertical_offset: int,
                 group_by: str,
                 agg_by: tuple,
                 custom_filename_pattern: str = None):
        """
        Initialize backend paths and filtering/aggregation criteria.
        """
        self.xrd_folder = xrd_folder
        self.pkl_path = pkl_path
        self.pth_folder = pth_folder
        self.filters = filters
        self.vertical_offset = vertical_offset
        self.group_by = group_by
        self.agg_by = agg_by

         # Use a custom FilenameCategoryExtractor if a custom pattern is provided.
        if custom_filename_pattern:
            extractor = FilenameCategoryExtractor(pattern=custom_filename_pattern)
            self.data_screener = DataScreener(self.xrd_folder, category_extractors=[extractor])
        else:
            self.data_screener = DataScreener(self.xrd_folder)

        if self.pth_folder:
            from pth_processor import PTHProcessor
            self.pth_processor = PTHProcessor(folder_path=self.pth_folder)

        # Initialize data screener and PTH processor.
        self.data_screener = DataScreener(self.xrd_folder)
        if self.pth_folder:
            self.pth_processor = PTHProcessor(folder_path=self.pth_folder)

    def load_xrd_data(self) -> bool:
        """
        Load XRD data from a pickle file if available; otherwise, read raw data
        and save the processed results.
        """
        if self.pkl_path and os.path.exists(self.pkl_path):
            logging.info(f"Loading categorized XRD data from {self.pkl_path}...")
            self.data_screener.load()
        else:
            logging.info(f"Reading raw XRD data from directory {self.xrd_folder}...")
            self.data_screener.read_files()
            if self.pkl_path:
                self.data_screener.save_to_file(filename=self.pkl_path)

        if self.data_screener.df is None or self.data_screener.df.empty:
            logging.error("No XRD data loaded.")
            return False
        return True

    def filter_xrd_data(self) -> pd.DataFrame:
        """
        Apply user-specified filters to the XRD data. If no filter value is set,
        the data remains unfiltered for that category; however, if grouping (group_by
        and agg_by) is specified, that grouping is applied even if filters are empty.
        """
        df = self.data_screener.df
        # Apply filtering if either filters exist or grouping options are provided.
        if self.filters or (self.group_by and self.agg_by):
            logging.info("Applying filters to XRD data...")
            if self.group_by and self.agg_by:
                print('im filtering')
                df_filtered = self.data_screener.filter_by_categories(
                    group_by=self.group_by,
                    agg_by=self.agg_by,
                    **self.filters
                )
            else:
                df_filtered = self.data_screener.filter_by_categories(**self.filters)
            if df_filtered is None or df_filtered.empty:
                logging.warning("No matching rows found for the given filters.")
                return pd.DataFrame()
            return df_filtered.reset_index(drop=True)
        return df

    def process_pth_data(self, criteria: dict = {}, thresholds: dict = None, max_counts: dict = None) -> pd.DataFrame:
        """
        Load and process PTH files, then extract vertical line data.
        Accepts an optional thresholds dict mapping filenames to individual y thresholds.
        """
        logging.info(f"Processing PTH files from folder: {self.pth_folder}")
        self.pth_processor.load_pth_files(add_metadata=True)
        available_files = self.pth_processor.get_available_filenames()
        logging.info(f"Available PTH filenames: {available_files}")

        # Filter based on criteria (e.g. specific filenames)
        filtered_pth = self.pth_processor.filter_pth_instances(criteria=criteria)
        self.pth_processor.pth_instances = filtered_pth

        # Use individual thresholds (or default if not provided)
        if thresholds is None:
            thresholds = {}  # If none provided, the filter method will use the default threshold.
        self.pth_processor.filter_by_y_threshold(thresholds=thresholds)
        # Use individual max_counts (or default if not provided)
        if max_counts is None:
            max_counts = {}
        self.pth_processor.filter_by_y_count(max_counts=max_counts)
        return self.pth_processor.extract_vertical_lines()

    def show_plot(self, df_filtered: pd.DataFrame, df_lines: pd.DataFrame):
        """
        Launch a Qt application to display a stacked plot of filtered XRD data
        with vertical lines derived from PTH files.
        """
        app = QtWidgets.QApplication(sys.argv)
        widget = StackedPlotWidget(df_filtered, vertical_offset=self.vertical_offset)
        widget.add_vertical_lines(df_lines=df_lines)
        widget.show()
        sys.exit(app.exec())

    def run(self):
        """
        Main run method: loads XRD data, applies filters, processes PTH data, and shows the plot.
        """
        if not self.load_xrd_data():
            return

        df_filtered = self.filter_xrd_data()
        if df_filtered.empty:
            logging.error("Filtered XRD data is empty. Exiting.")
            return

        # Process PTH data (synchronously here, but could be done asynchronously as needed).
        individual_thresholds = {
                    "Mg_642654_Cu_borad.PTH": 75,
                    "MgH2_155807_Cu.PTH": 80,
                    "MgO_Periclase_77821_Cu.PTH": 85
                    }
        df_lines = self.process_pth_data(
                    criteria={"filename": ["Mg_642654_Cu_borad.PTH",
                                             "MgH2_155807_Cu.PTH",
                                             "MgO_Periclase_77821_Cu.PTH"]},
                    thresholds=individual_thresholds
                )
        logging.info("Displaying stacked plot with vertical PTH lines.")
        self.show_plot(df_filtered, df_lines)


def main():
    """
    Main method for testing functionality.
    It uses background threads for asynchronous processing of XRD and PTH data.
    """
    # Example folder paths (adjust these paths to match your test data)
    xrd_folder = r"test_data/REX245 XRK WAE-WA-049"
    pkl_path = r"test_data/categorized_data.pkl"
    pth_folder = r"test_data/pks_files"

    # Define filter criteria.
    filters = {
        "temperature": [285, 305],
        "cycle": [0, 20]
    }
    vertical_offset = 500
    group_by = 'cycle'
    agg_by = ("current_temp_step", 'max')

    backend = MainBackend(xrd_folder, pkl_path, pth_folder, filters, vertical_offset, group_by, agg_by)

    # Load XRD data asynchronously.
    xrd_thread = threading.Thread(target=backend.load_xrd_data)
    xrd_thread.start()
    xrd_thread.join()

    # Apply filtering and print out the resulting DataFrame.
    df_filtered = backend.filter_xrd_data()
    if df_filtered.empty:
        logging.error("Filtered XRD data is empty.")
        return
    logging.info("Filtered XRD Data:")
    print(df_filtered)

    # Process PTH data asynchronously.
    def process_and_print_pth():
        df_lines = backend.process_pth_data(criteria={"filename": ["Mg_642654_Cu_borad.PTH"]})
        logging.info("Processed PTH vertical lines:")
        print(df_lines)
    pth_thread = threading.Thread(target=process_and_print_pth)
    pth_thread.start()
    pth_thread.join()


    # For testing the GUI plotting, uncomment the following line.
    # Note that this will block the thread and requires a proper Qt environment.
    backend.run()


if __name__ == '__main__':
    main()
