#xrd_file_screener.py
import os
import re
import pandas as pd
import datetime
from pathlib import Path
from rasx_manager import RasxDataManager

# ----------------------------------
# Category Extractor Base and Classes
# ----------------------------------

class BaseCategoryExtractor:
    """
    Base interface for a category extractor.
    Implementations should extract categories from a file (e.g. from the filename)
    and return a dictionary of {category_name: value}.
    """
    def extract(self, filename: str, rasx_manager: RasxDataManager) -> dict:
        raise NotImplementedError("Must implement extract method.")

    def get_categories(self) -> list:
        raise NotImplementedError("Must implement get_categories method.")


class FilenameCategoryExtractor(BaseCategoryExtractor):
    """
    Dynamically extracts categories from the filename using a regex pattern.
    The regex's named groups determine the keys, so you don't need to predefine them.
    Optionally, you can also provide a conversion mapping to convert values (e.g., to int or float).
    """
    def __init__(self, pattern: str = None, conversion_mapping: dict = None):
        # Default regex pattern if none is provided.
        self.default_pattern = (
            r"(?P<gas>[A-Z](?:[a-z])?\d*)\s*,\s+"
            r"(?P<pressure>\d+(?:\.\d+)?)bar"
            r"(?:\s+C(?P<cycle>\d+))?"
            r"(?:.*?_)"                                         
            r"(?P<numMes>\d+)_"                                  
            r"(?P<currentStep>\d+)_"                             
            r"(?P<noIntMes>\d+)_"                                
            r"(?P<temperature>\d+)-0C$"
        )
        self.pattern = pattern or self.default_pattern
        self.compiled_pattern = re.compile(self.pattern)
        # Dynamically set categories from the regex named groups.
        self.categories = list(self.compiled_pattern.groupindex.keys())
        # Optionally, a mapping of group names to conversion functions.
        self.conversion_mapping = conversion_mapping or {
            'pressure': float,
            'cycle': int,
            'numMes': int,
            'currentStep': int,
            'noIntMes': int,
            'temperature': float,
        }

    def update_pattern(self, new_pattern: str, conversion_mapping: dict = None):
        """Update the regex pattern and optionally the conversion mapping."""
        self.pattern = new_pattern
        self.compiled_pattern = re.compile(new_pattern)
        self.categories = list(self.compiled_pattern.groupindex.keys())
        if conversion_mapping is not None:
            self.conversion_mapping = conversion_mapping

    def extract(self, filename: str, rasx_manager: RasxDataManager) -> dict:
        filename_clean, _ = os.path.splitext(filename)
        match = self.compiled_pattern.search(filename_clean)
        if match:
            raw_data = match.groupdict()
            result = {}
            for key, value in raw_data.items():
                # If a conversion function is provided, apply it.
                if key in self.conversion_mapping and value is not None:
                    try:
                        result[key] = self.conversion_mapping[key](value)
                    except Exception:
                        result[key] = None
                else:
                    result[key] = value
            return result
        else:
            # Return a dictionary with all keys set to None if there's no match.
            return {key: None for key in self.categories}

    def get_categories(self) -> list:
        return self.categories

# ----------------------------------
# DataScreener: File Scanning and Categorization
# ----------------------------------

class DataScreener:
    """
    Reads and categorizes .rasx files based on filename (and optionally content)
    and stores the collected data into a Pandas DataFrame.

    This class supports:
      - Reading from a directory (scanning and building categories)
      - Loading a previously saved DataFrame (pkl or csv)

    It also provides a method to retrieve available category names.
    """
    def __init__(self, source: str, category_extractors: list = None):
        """
        If source is a folder, the DataScreener will scan the folder.
        If source is a file ending with .pkl or .csv, it will load the DataFrame.
        """
        self.source = source
        self.df = None  # DataFrame storing the categorized data

        # Register category extractors (default is FilenameCategoryExtractor).
        self.category_extractors = category_extractors or [FilenameCategoryExtractor()]

        # Determine mode: folder scanning vs. file loading.
        if os.path.isdir(source):
            self.mode = "folder"
        elif os.path.isfile(source) and source.lower().endswith((".pkl", ".csv")):
            self.mode = "file"
        else:
            raise ValueError("Source must be a directory or a .pkl/.csv file.")

    def load(self):
        """
        Main entry: either read files from a directory or load an existing DataFrame.
        """
        if self.mode == "folder":
            self.read_files()
        elif self.mode == "file":
            self.load_from_file(self.source)

    def read_files(self):
        """Scans the directory for .rasx files, categorizes them, and builds the DataFrame."""
        file_records = self._get_files_from_directory()
        self.df = self._create_dataframe(file_records)
        print("Files read and categorized successfully.")

    def save_to_file(self, filename="categorized_data.pkl"):
        """Saves the DataFrame to a file (Pickle or CSV)."""
        if self.df is None:
            print("No data to save. Run load() or read_files() first.")
            return

        # Save file in the same directory as the source folder.
        file_save_path = os.path.join(os.path.dirname(self.source), filename)
        if filename.endswith(".pkl"):
            self.df.to_pickle(file_save_path)
        elif filename.endswith(".csv"):
            self.df.to_csv(file_save_path, index=False)
        else:
            print("Unsupported file format. Use .pkl or .csv")
            return

        print(f"Data saved to {file_save_path}.")

    def load_from_file(self, filepath):
        """Loads the DataFrame from a saved file (pkl or csv)."""
        if not os.path.exists(filepath):
            print(f"File {filepath} not found.")
            return

        if filepath.lower().endswith(".pkl"):
            self.df = pd.read_pickle(filepath)
        elif filepath.lower().endswith(".csv"):
            self.df = pd.read_csv(filepath)
        else:
            print("Unsupported file format. Use .pkl or .csv")
            return

        print(f"Data loaded from {filepath}.")

    def filter_by_categories(self, group_by=None, agg_by=None, **criteria):
        """
        Filters the DataFrame based on specific category columns.
        If a filter value is None, it is ignored.
        Optionally group by a column and then, within each group, select the row with the
        min/max value of a given aggregation column.

        Parameters:
          group_by: The column name to group by.
          agg_by: A tuple in the form (aggregation_column, 'min' or 'max').

        Returns:
          A filtered DataFrame.
        """
        if self.df is None:
            print("No data available. Run load() or read_files() first.")
            return pd.DataFrame()

        filtered_df = self.df.copy()
        # Apply filtering criteria if provided.
        for col, crit_val in criteria.items():
            if crit_val is None:
                continue
            if col in filtered_df.columns:
                if isinstance(crit_val, (tuple, list)) and len(crit_val) == 2:
                    min_val, max_val = crit_val
                    filtered_df = filtered_df[(filtered_df[col] >= min_val) & (filtered_df[col] <= max_val)]
                else:
                    filtered_df = filtered_df[filtered_df[col] == crit_val]
            else:
                print(f"Column {col} not found in the DataFrame. Skipping.")

        # Apply grouping if specified.
        filtered_df = self._group_agg_by(group_by=group_by, agg_by=agg_by, df=filtered_df)
        print('im_executed')
        return filtered_df.reset_index(drop=True)

    def _group_agg_by(self, group_by, agg_by, df):
        # If grouping and aggregation are specified, further filter the data.
        if group_by and agg_by:
            agg_column, agg_func = agg_by
            if group_by not in df.columns:
                print(f"Group by column '{group_by}' not found. Skipping grouping.")
                return df
            elif agg_column not in df.columns:
                print(f"Aggregation column '{agg_column}' not found. Skipping grouping.")
                return df
            else:
                if agg_func.lower() == 'max':
                    idx = df.groupby(group_by)[agg_column].idxmax()
                elif agg_func.lower() == 'min':
                    idx = df.groupby(group_by)[agg_column].idxmin()
                else:
                    print("agg_by function must be 'min' or 'max'. Skipping grouping.")
                    return df
                return df.loc[idx].reset_index(drop=True)
        else:
            # If no grouping is specified, just return the original DataFrame.
            return df

    def get_available_categories(self):
        """
        Returns a list of category names available from all registered extractors.
        """
        categories = set()
        for extractor in self.category_extractors:
            categories.update(extractor.get_categories())
        return list(categories)

    # --- Helper methods for file scanning and DataFrame creation --- #

    def _get_files_from_directory(self):
        """
        Walk through the directory, read .rasx files (ignoring those with 'temp' in the filename),
        extract file-level data (including categories from filename and file content),
        and return a list of dictionaries.
        """
        records = []
        for root_dir, _, files in os.walk(self.source):
            for file in files:
                if file.endswith(".rasx") and 'temp' not in file.lower():
                    file_path = os.path.join(root_dir, file)
                    # Use RasxDataManager to extract file content info.
                    try:
                        rasx_manager = RasxDataManager(file_path=file_path)
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
                        continue

                    # Get creation date from file metadata; fallback to file stats.
                    file_path_obj = Path(file_path)
                    try:
                        creation_date = rasx_manager.start_time

                    except Exception:
                        creation_ts = file_path_obj.stat().st_mtime
                        creation_date = datetime.datetime.fromtimestamp(creation_ts)

                    # Build the record dictionary.
                    record = {
                        "filename": file,
                        "creation_date": creation_date,
                        "start_time": rasx_manager.start_time,
                        "df_xy": rasx_manager.df_xy
                    }
                    # Merge in categories from each registered extractor.
                    for extractor in self.category_extractors:
                        record.update(extractor.extract(file, rasx_manager))
                    records.append(record)
        return records

    def _create_dataframe(self, records: list, sort_key=""):
        """
        Creates and returns a DataFrame from a list of record dictionaries.
        The DataFrame is sorted by 'cycle' and 'creation_date' if these columns exist.
        """
        if not records:
            print("No records to build DataFrame.")
            return pd.DataFrame()
        df = pd.DataFrame(records)

        sort_cols = [col for col in [sort_key, 'cycle', 'creation_date'] if col in df.columns]

        if sort_cols:
            df.sort_values(by=sort_cols, inplace=True)
        return df.reset_index(drop=True)

# ----------------------------------
# Example usage
# ----------------------------------

if __name__ == "__main__":
    # Example: Using a folder path to build the categorized DataFrame.
    folder_path = r"C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\REX245 XRK WAE-WA-049"
    screener = DataScreener(source=folder_path)
    screener.load()  # This calls read_files() internally
    print("Available Categories:", screener.get_available_categories())
    print(screener.df)

    # Save the data in both pickle and CSV formats.
    screener.save_to_file(filename="categorized_data.pkl")
    screener.save_to_file(filename="categorized_data.csv")

    # Example: Loading an existing file
    # screener_file = DataScreener(source=r"C:\path\to\categorized_data.pkl")
    # screener_file.load()
