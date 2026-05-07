#pth_processor.py
import os
import pandas as pd
from plotter.pks_manager import PTHParser, PTHFileData


class PTHProcessor:
    """
    Manages processing of .PTH files (phases). Uses normalized 'X','Y' columns.
    """
    def __init__(self, folder_path: str):
        if not os.path.isdir(folder_path):
            raise ValueError(f"{folder_path} is not a valid directory.")
        self.folder_path = folder_path
        self.pth_instances: list[PTHFileData] = []

    def load_pth_files(self, add_metadata: bool = True) -> list[PTHFileData]:
        parser = PTHParser(folder_path=self.folder_path)
        self.pth_instances = parser.parse(add_metadata=add_metadata)
        return self.pth_instances

    def get_available_filenames(self) -> list[str]:
        return [pth.filename for pth in self.pth_instances]

    def filter_pth_instances(self, criteria: dict = {}) -> list[PTHFileData]:
        if not self.pth_instances:
            self.load_pth_files(add_metadata=True)
        filtered = []
        for pth in self.pth_instances:
            match = True
            for key, expected in criteria.items():
                actual = pth.filename if key.lower() == "filename" else pth.metadata.get(key)
                if actual is None:
                    match = False; break
                if isinstance(expected, (list, tuple, set)):
                    if actual not in expected:
                        match = False; break
                else:
                    if actual != expected:
                        match = False; break
            if match:
                filtered.append(pth)
        return filtered

    def extract_vertical_lines(self) -> pd.DataFrame:
        """
        Returns a wide DataFrame with one column per phase (Series of X positions).
        """
        series_list = []
        for pth in self.pth_instances:
            if pth.df_xy is not None and not pth.df_xy.empty and 'X' in pth.df_xy.columns:
                x_series = pth.df_xy['X'].copy()
                x_series.name = pth.metadata.get('name', pth.filename)
                series_list.append(x_series)
        return pd.concat(series_list, axis=1) if series_list else pd.DataFrame()

    def filter_by_y_threshold(self, thresholds: dict) -> list[PTHFileData]:
        default_threshold = 80
        for pth in self.pth_instances:
            key = pth.filename
            thresh = thresholds.get(key, default_threshold)
            if pth.df_xy is not None and not pth.df_xy.empty and 'Y' in pth.df_xy.columns:
                pth.df_xy = pth.df_xy[pth.df_xy['Y'] >= thresh]
        return self.pth_instances

    def filter_by_y_count(self, max_counts: dict) -> list[PTHFileData]:
        default_max_count = 5
        for pth in self.pth_instances:
            key = pth.filename
            max_count = max_counts.get(key, default_max_count)
            if pth.df_xy is not None and not pth.df_xy.empty and 'Y' in pth.df_xy.columns:
                pth.df_xy = pth.df_xy.sort_values(by='Y', ascending=False).head(max_count)
        return self.pth_instances
