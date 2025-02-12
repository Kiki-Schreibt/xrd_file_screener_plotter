import os
import sys
import pandas as pd
from pyqtgraph.Qt import QtWidgets  # or from pyqtgraph.Qt import QtWidgets, QtCore
from datetime import datetime

# Import your custom classes.
from xrd_file_screener import DataScreener  # Class that reads raw .rasx files and builds a DataFrame
from stacked_plot_widget import StackedPlotWidget  # The widget for plotting

class XRDFileScreenerController:
    def __init__(self, folder_path=None, pkl_path=None, filters=None, vertical_offset=500,
                 group_by=None, agg_by=()):
        """
        :param folder_path: Path to the directory containing .rasx files.
                            Required if a pkl file is not provided.
        :param pkl_path: Path to a pre-saved pickle file containing the categorized DataFrame.
                        If provided and exists, data will be loaded from this file.
        :param filters: Dictionary of filters to apply. For example:
                        {"cycle": [1, 20], "temperature": [285, 300], "pressure": [9.5, 10.5]}
        :param vertical_offset: Vertical offset applied between curves in the stacked plot.
        :param group_by: Column name to group the filtered data (for example, "cycle").
        :param agg_by: tuple (col_name, max/min) from which to select the row with the maximum/minimum value within each group.
        """
        self.folder_path = folder_path
        self.pkl_path = pkl_path
        self.filters = filters or {}
        self.vertical_offset = vertical_offset
        self.group_by = group_by
        self.agg_by = agg_by
        self.data_screener = DataScreener(self.folder_path) if folder_path else None

    def run(self):
        # If a pickle path is provided and the file exists, load from it.
        if self.pkl_path and os.path.exists(self.pkl_path):
            print(f"Loading categorized data from {self.pkl_path}...")
            if self.data_screener is None:
                # Create a dummy instance just to use its load_from_file method.
                self.data_screener = DataScreener(self.folder_path or os.path.dirname(self.pkl_path))
            self.data_screener.load_from_file(filename=self.pkl_path)
        else:
            # Otherwise, read raw files from the folder.
            if self.folder_path is None:
                print("Error: You must provide a folder path if no pickle file is given.")
                return
            print(f"Reading raw data from directory {self.folder_path}...")
            self.data_screener.read_files()
            # Save the DataFrame if a pickle path is provided.
            if self.pkl_path:
                self.data_screener.save_to_file(filename=self.pkl_path)

        df = self.data_screener.df
        if df is None or df.empty:
            print("No data loaded.")
            return

        # Apply filters if provided.
        if self.filters:
            print("Applying filters...")
            # Pass the additional group_by and agg_by parameters if they are provided.
            if self.group_by and self.agg_by:
                df_filtered = self.data_screener.filter_by_categories(group_by=self.group_by,
                                                                      agg_by=self.agg_by,
                                                                      **self.filters)
            else:
                df_filtered = self.data_screener.filter_by_categories(**self.filters)
            if df_filtered is None or df_filtered.empty:
                print("No matching rows found for the given filters.")
                return
        else:
            df_filtered = df

        # Create and show the stacked plot widget.
        app = QtWidgets.QApplication(sys.argv)
        print("Plotting data")
        widget = StackedPlotWidget(df_filtered, vertical_offset=self.vertical_offset)
        line = {"A": [20, 30, 40],
            "B": [15, 35, 45]}
        line = pd.DataFrame(line)
        widget.add_vertical_lines(df_lines=line)
        widget.show()
        sys.exit(app.exec())

# -------------------------
# Example usage:
# -------------------------
if __name__ == '__main__':
    # Path to the folder containing .rasx files.
    folder_path = r"C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\REX245 XRK WAE-WA-049"

    # Optionally, specify the path to a pre-saved pickle file.
    pkl_path = r"C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\categorized_data.pkl"

    category_names = [
                                "gas", "pressure", "cycle",
                                "measurements_current_step", "current_temp_step",
                                "measurements_no_interrupt", "temperature"
                         ]
    filters = { "temperature": [0,500],
                "cycle": [0, 30]



                }

    # Group by the "cycle" column and select, within each group, the row with maximum "current_temp_step"
    group_by = 'cycle'
    agg_by = ("current_temp_step", 'min')

    controller = XRDFileScreenerController(folder_path=folder_path,
                                             pkl_path=pkl_path,
                                             filters=filters,
                                             vertical_offset=500,
                                             group_by=group_by,
                                             agg_by=agg_by
                                            )
    controller.run()
#todo: legende an linien heften
