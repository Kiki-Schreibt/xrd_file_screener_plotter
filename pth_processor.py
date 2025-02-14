#pth_processor.py
import os
import pandas as pd
from pks_manager import PTHParser, PTHFileData  # Assuming these classes are defined in pks_manager.py


class PTHProcessor:
    """
    Class to manage the processing of .PTH files where reflex positions of xrd database for different phases are stored.

    This class encapsulates logic for:
      - Loading and parsing PTH files from a specified folder.
      - Filtering the parsed PTHFileData objects based on user-defined criteria.
      - Extracting vertical line data (e.g., the 'x' values) from the parsed data,
        which can then be used in a stacked plot.
    """
    def __init__(self, folder_path: str):
        if not os.path.isdir(folder_path):
            raise ValueError(f"{folder_path} is not a valid directory.")
        self.folder_path = folder_path
        self.pth_instances: list[PTHFileData] = []

    def load_pth_files(self, add_metadata: bool = True) -> list[PTHFileData]:
        """
        Load and parse PTH files from the folder.

        :param add_metadata: Whether to add metadata columns to the DataFrame.
        :return: List of parsed PTHFileData objects.
        """
        parser = PTHParser(folder_path=self.folder_path)
        self.pth_instances = parser.parse(add_metadata=add_metadata)
        return self.pth_instances

    def get_available_filenames(self) -> list[str]:
        """
        Returns a list of all filenames available in the loaded PTH instances.
        """
        return [pth.filename for pth in self.pth_instances]

    def filter_pth_instances(self, criteria: dict = {}) -> list[PTHFileData]:
        """
        Filter the loaded PTHFileData objects based on provided criteria.

        The criteria dictionary can include keys such as "filename" or any metadata key.
        For the "filename" key, you can pass a single value or a list of allowed filenames.

        :param criteria: Dictionary of filtering criteria.
        :return: Filtered list of PTHFileData objects.
        """
        if not self.pth_instances:
            self.load_pth_files(add_metadata=True)

        filtered = []
        for pth in self.pth_instances:
            match = True
            for key, expected in criteria.items():
                if key.lower() == "filename":
                    actual = pth.filename
                else:
                    actual = pth.metadata.get(key)

                if actual is None:
                    match = False
                    break

                # If expected is a collection, check membership
                if isinstance(expected, (list, tuple, set)):
                    if actual not in expected:
                        match = False
                        break
                else:
                    if actual != expected:
                        match = False
                        break
            if match:
                filtered.append(pth)
        return filtered

    def extract_vertical_lines(self) -> pd.DataFrame:
        """
        Extract vertical line data (the 'x' values) from the loaded PTH instances.
        Each column in the returned DataFrame corresponds to the x-values of one PTH file.

        :return: DataFrame with vertical line data.
        """
        series_list = []
        for pth in self.pth_instances:
            if not pth.df_xy.empty and 'x' in pth.df_xy.columns:
                x_series = pth.df_xy['x'].copy()
                # Name the series using metadata 'name' or fallback to the filename.
                x_series.name = pth.metadata.get('name', pth.filename)
                series_list.append(x_series)
        if series_list:
            return pd.concat(series_list, axis=1)
        else:
            return pd.DataFrame()

    def filter_by_y_threshold(self, thresholds: dict) -> list[PTHFileData]:
        """
        For each loaded PTHFileData instance, filter its df_xy DataFrame by removing rows
        where the 'y' value is below a threshold specific to that instance.
        `thresholds` is a dict mapping each pth instance's identifier (e.g. filename) to its threshold.
        If an instance's key is not in the dictionary, a default threshold is used.
        """
        default_threshold = 80  # You can adjust the default as needed.
        for pth in self.pth_instances:
            key = pth.filename  # assuming filename is a unique identifier
            thresh = thresholds.get(key, default_threshold)
            if not pth.df_xy.empty and 'y' in pth.df_xy.columns:
                pth.df_xy = pth.df_xy[pth.df_xy['y'] >= thresh]
        return self.pth_instances

    def filter_by_y_count(self, max_counts: dict) -> list[PTHFileData]:
        """
        For each loaded PTHFileData instance, filter its df_xy DataFrame to keep only
        the top N rows with the highest 'y' intensity.

        :param max_counts: Dict mapping each instance's identifier (e.g. filename) to the maximum number of x values to show.
        :return: The list of PTHFileData instances with their df_xy filtered.
        """
        default_max_count = 5  # Default number if none is provided.
        for pth in self.pth_instances:
            key = pth.filename  # assuming filename is unique.
            max_count = max_counts.get(key, default_max_count)
            if not pth.df_xy.empty and 'y' in pth.df_xy.columns:
                # Sort descending by y and take the top max_count rows.
                pth.df_xy = pth.df_xy.sort_values(by='y', ascending=False).head(max_count)
        return self.pth_instances
