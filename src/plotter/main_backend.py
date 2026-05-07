#main_backen.py
import os
import sys
import logging
import threading
import pandas as pd
from pyqtgraph.Qt import QtWidgets

from plotter.xrd_file_screener import DataScreener, FilenameCategoryExtractor, CycleExtractor
from plotter.stacked_plot_widget import StackedPlotWidget
from plotter.pth_processor import PTHProcessor

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
        self.filters = filters or {}
        self.vertical_offset = vertical_offset
        self.group_by = group_by
        self.agg_by = agg_by

        # Build extractor chain: custom first (if provided), then default fallback.
        category_extractors = []
        if custom_filename_pattern:
            category_extractors.append(FilenameCategoryExtractor(pattern=custom_filename_pattern))
        category_extractors.append(FilenameCategoryExtractor())  # default with optional cycle
        category_extractors.append(CycleExtractor())             # belt-and-suspenders cycle finder

        self.data_screener = DataScreener(self.xrd_folder, category_extractors=category_extractors)
        self.pth_processor = PTHProcessor(folder_path=self.pth_folder) if self.pth_folder else None

    def load_xrd_data(self) -> bool:
        """
        Try loading from pickle. If missing/empty/invalid, rebuild from raw and
        save to self.pkl_path (absolute). Return True only if df is non-empty.
        """
        # 1) Try pickle if present
        if self.pkl_path and os.path.exists(self.pkl_path):
            logging.info(f"Loading categorized XRD data from {self.pkl_path}...")
            self.data_screener.load_from_file(self.pkl_path)
            try:
                self.data_screener.save_to_file(self.pkl_path)
            except Exception:
                pass
            if isinstance(self.data_screener.df, pd.DataFrame) and not self.data_screener.df.empty:
                return True
            logging.warning("Pickle load yielded empty/invalid DataFrame; rebuilding from raw...")

        # 2) Rebuild from raw
        logging.info(f"Reading raw XRD data from directory {self.xrd_folder}...")
        self.data_screener.read_files()

        # 3) Save exactly to the requested pickle path (absolute or inside folder)
        if self.pkl_path:
            self.data_screener.save_to_file(self.pkl_path)

        # 4) Final guard
        if self.data_screener.df is None or self.data_screener.df.empty:
            logging.error("No XRD data loaded.")
            return False
        return True

    def filter_xrd_data(self) -> pd.DataFrame:
        """
        Apply filters and optional grouping/aggregation.
        Accepts ranges (tuple/list len 2), sets/lists, callables, regex (compiled), or scalars.
        """
        df = self.data_screener.df
        if self.filters or (self.group_by and self.agg_by):
            logging.info("Applying filters to XRD data...")
            df_filtered = self.data_screener.filter_by_categories(
                group_by=self.group_by,
                agg_by=self.agg_by,
                **self.filters
            )
            if df_filtered is None or df_filtered.empty:
                logging.warning("No matching rows found for the given filters.")
                return pd.DataFrame()
            return df_filtered.reset_index(drop=True)
        return df

    def process_pth_data(self, criteria: dict = {}, thresholds: dict = None, max_counts: dict = None) -> pd.DataFrame:
        """
        Load and process PTH files, then extract vertical line data.
        Columns normalized to 'X','Y' in PTH parser; this returns a wide df with column per phase.
        """
        if not self.pth_processor:
            return pd.DataFrame()
        logging.info(f"Processing PTH files from folder: {self.pth_folder}")
        self.pth_processor.load_pth_files(add_metadata=True)
        filtered_pth = self.pth_processor.filter_pth_instances(criteria=criteria)
        self.pth_processor.pth_instances = filtered_pth

        # Thresholds and max_counts may be per-filename; defaults inside helper methods.
        self.pth_processor.filter_by_y_threshold(thresholds=thresholds or {})
        self.pth_processor.filter_by_y_count(max_counts=max_counts or {})
        return self.pth_processor.extract_vertical_lines()

    def show_plot(self, df_filtered: pd.DataFrame, df_lines: pd.DataFrame):
        app = QtWidgets.QApplication(sys.argv)
        widget = StackedPlotWidget(df_filtered, vertical_offset=self.vertical_offset)
        if df_lines is not None and not df_lines.empty:
            widget.add_vertical_lines(df_lines=df_lines)
        widget.show()
        sys.exit(app.exec())

    def run(self):
        if not self.load_xrd_data():
            return
        df_filtered = self.filter_xrd_data()
        if df_filtered.empty:
            logging.error("Filtered XRD data is empty. Exiting.")
            return
        df_lines = pd.DataFrame()
        if self.pth_processor:
            df_lines = self.process_pth_data()
        logging.info("Displaying stacked plot.")
        self.show_plot(df_filtered, df_lines)


def main():
    """
    Main method for testing functionality.
    It uses background threads for asynchronous processing of XRD and PTH data.
    """
    # Example folder paths (adjust these paths to match your test data)
    xrd_folder = r"test_data/REX245 XRK WAE-WA-049"
    pkl_path = r"../../test_data/categorized_data.pkl"
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
