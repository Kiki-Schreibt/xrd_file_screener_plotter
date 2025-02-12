import os
import re
import pandas as pd
import datetime
from rasx_reader import RasxDataManager


from pathlib import Path


class DataScreener:

    def __init__(self, directory):
        self.directory = directory
        self.df = None  # DataFrame to store categorized data

    def read_files(self):
        """Public method to read and categorize files, storing the DataFrame."""
        file_data = self._get_files_from_directory()
        self.df = self._create_dataframe(file_data)
        print("Files read and categorized successfully.")

    def save_to_file(self, filename="categorized_data.pkl"):
        """Saves the DataFrame to a file (Pickle or CSV)."""
        file_save_path = os.path.join(self.directory, "..", filename)
        if self.df is None:
            print("No data to save. Run read_files() first.")
            return

        if filename.endswith(".pkl"):
            self.df.to_pickle(file_save_path)
        elif filename.endswith(".csv"):
            self.df.to_csv(file_save_path, index=False)
        else:
            print("Unsupported file format. Use .pkl or .csv")
            return

        print(f"Data saved to {filename}.")

    def load_from_file(self, filename="categorized_data.pkl"):
        """Loads the DataFrame from a saved file."""
        if not os.path.exists(filename):
            print(f"File {filename} not found.")
            return

        if filename.endswith(".pkl"):
            self.df = pd.read_pickle(filename)
        elif filename.endswith(".csv"):
            self.df = pd.read_csv(filename)
        else:
            print("Unsupported file format. Use .pkl or .csv")
            return

        print(f"Data loaded from {filename}.")

    def filter_by_categories(self, group_by=None, max_by=None, **criteria):
        """
        Filters the DataFrame based on specific category columns.

        Keyword arguments should be provided where the key is the column name
        and the value is either:
          - A single value to match exactly, or
          - A tuple or list of two values (min, max) to filter for rows where:
                min <= column_value <= max

        Optionally, you can specify:
          - group_by: a column name to group by (e.g., crit_A)
          - max_by: a column name from which, within each group, the row with the
                    maximum value is selected (e.g., crit_B)

        For example:
            filter_by_categories(pressure=10)
            filter_by_categories(pressure=(5, 10))
            filter_by_categories(gas='Air', group_by='cycle', max_by='pressure')
            available categories: gas, pressure, cycle, measurements_current_step, current_temp_step, measurements_no_interrupt, temperature
        """
        if self.df is None:
            print("No data available. Run read_files() or load_from_file() first.")
            return pd.DataFrame()

        filtered_df = self.df.copy()  # Work on a copy if needed

        # Apply the filtering criteria.
        for col, crit_val in criteria.items():
            if col in filtered_df.columns:
                # Check if crit_val is a tuple or list with exactly two elements.
                if isinstance(crit_val, (tuple, list)) and len(crit_val) == 2:
                    min_val, max_val = crit_val
                    filtered_df = filtered_df[(filtered_df[col] >= min_val) & (filtered_df[col] <= max_val)]
                else:
                    filtered_df = filtered_df[filtered_df[col] == crit_val]
            else:
                print(f"Column {col} not found in the DataFrame.")
                return None

        if filtered_df.empty:
            print("No matching rows found.")
            return None

        # If both group_by and max_by are provided, group the filtered DataFrame
        # and select the row in each group with the maximum value in max_by.
        if group_by is not None and max_by is not None:
            if group_by in filtered_df.columns and max_by in filtered_df.columns:
                # For each group defined by group_by, find the index of the row where max_by is maximum.
                idx = filtered_df.groupby(group_by)[max_by].idxmax()
                filtered_df = filtered_df.loc[idx]
            else:
                print("Group or max column not found in the DataFrame.")
                return None
        filtered_df = filtered_df.reset_index(drop=True)
        return filtered_df

    ### --- HELPER METHODS --- ###

    def _get_files_from_directory(self):
        """Walks through the directory, extracts filenames, categories, and reads (X, Y) data."""
        file_data = []

        for root, _, files in os.walk(self.directory):
            for file in files:
                if file.endswith(".rasx") and not 'temp' in file:
                    file_path = os.path.join(root, file)
                    rasx_manager = RasxDataManager(file_path=file_path)
                    file_path_for_stats = Path(str(file_path))
                    filename, _ = os.path.splitext(file)  # Extract filename without extension

                    try:
                        creation_date = rasx_manager.start_time
                       # print("ok")
                    except:
                        creation_time = file_path_for_stats.stat().st_mtime
                        creation_date = datetime.datetime.fromtimestamp(creation_time)
                        print("not ok")

                    categories = self._extract_categories(filename)
                    if not categories:
                        categories = rasx_manager.categories

                    df_xy = rasx_manager.df_xy
                    #df_xy = self._read_xy_data(file_path)  # Read (X, Y) data

                    file_data.append([file, *categories, creation_date, df_xy])  # Store DataFrame in last column

        return file_data

    def _extract_categories(self, filename):
        """Extracts categories from a filename.
        :returns gas, pressure, cycle, measurements_current_step, current_temp_step, measurements_no_interrupt, temperature """

        pattern = (
                    r"(?:(?P<gas>[A-Z](?:[a-z])?\d*)\s*,\s+)?"  # Optional initial gas
                    r"(?P<pressure>\d+(?:\.\d+)?)bar"             # Pressure
                    r"(?:\s+C(?P<cycle>\d+))?"                    # Optional cycle
                    r"(?:\s*_(?P<gas2>[A-Z](?:[a-z])?\d*))?"       # Optional extra gas field between cycle and numeric block
                    r"\s*_"                                      # The underscore before numMes
                    r"(?P<numMes>\d+)_"                          # numMes digits
                    r"(?P<currentStep>\d+)_"                     # currentStep digits
                    r"(?P<noIntMes>\d+)_"                        # noIntMes digits
                    r"(?P<temperature>\d+)-0C$"                   # temperature then literal -0C at the end
                )

        match = re.search(pattern, filename)
        if match:
            data = match.groupdict()

            gas = data.get("gas") if data.get("gas") else None
            pressure = float(data.get("pressure")) if data.get("pressure") else None
            cycle = int(data.get("cycle")) if data.get("cycle") else 1
            measurements_current_step = int(data.get("numMes")) if data.get("numMes") else None
            current_temp_step = int(data.get("currentStep")) if data.get("currentStep") else None
            measurements_no_interrupt = int(data.get("noIntMes")) if data.get("noIntMes") else None
            temperature = float(data.get("temperature")) if data.get("temperature") else None

            return gas, pressure, cycle, measurements_current_step, current_temp_step, measurements_no_interrupt, temperature

        else:
            print(f"The filename did not match the expected format: {filename}")
            return None, None, None, None, None, None, None

    def _read_xy_data(self, file_path):
        """Reads the (X, Y) data from a CSV file, if valid."""
        try:
            df_xy = pd.read_csv(file_path, sep=r"\s+", header=None)  # Adjust if your files are not CSV

            if len(df_xy.columns) >= 2:  # Ensure at least two columns
                df_xy = df_xy.iloc[:, :2]  # Take only first two columns (assumed X and Y)
                df_xy.columns = ["X", "Y"]  # Standardize column names
                return df_xy
        except Exception as e:
            print(e)
            #pass  # Ignore errors for non-CSV or unreadable files
        return None  # Return None if file is invalid

    def _create_dataframe(self, file_data):
        """Creates a Pandas DataFrame from the collected file data."""
        category_names = [
                                "gas", "pressure", "cycle",
                                "measurements_current_step", "current_temp_step",
                                "measurements_no_interrupt", "temperature"
                         ]
        column_names = ["filename"] + category_names + ["creation_date"] + ["df_xy"]
        df = pd.DataFrame(file_data, columns=column_names)
        df.sort_values(by=['cycle', 'creation_date'], inplace=True)
        return df




if __name__ == "__main__":

    data_manager = DataScreener(r"C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\REX245 XRK WAE-WA-049")
    data_manager.read_files()  # Build the DataFrame
    data_manager.save_to_file(filename="categorized_data.pkl")
    data_manager.save_to_file(filename="categorized_data.csv")

   # print(data_manager.df["creation_date"])


