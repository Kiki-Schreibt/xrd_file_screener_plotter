import os
import re
import pandas as pd
import datetime


from pathlib import Path


#REX245 XRK WAE-WA-049-01, 10dpm, IS 0.25deg, H2, 1bar C17_H2_001_01_0001_0030-0C.xy
                                              #gas, pressure, cycle_optional_gas_optional_measurements in current temp step_current temp step_measurements without interruption_temperatuure-0C

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
        if self.df is None:
            print("No data to save. Run read_files() first.")
            return

        if filename.endswith(".pkl"):
            self.df.to_pickle(filename)
        elif filename.endswith(".csv"):
            self.df.to_csv(filename, index=False)
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

    def filter_by_category(self, category):
        """Returns a DataFrame of files matching the given category in any column."""
        if self.df is None:
            print("No data available. Run read_files() or load_from_file() first.")
            return None

        filtered_df = self.df[self.df.apply(lambda row: category in row.values, axis=1)]

        if filtered_df.empty:
            print(f"No files found for category '{category}'.")
            return None

        return filtered_df

    def filter_by_categories(self, **criteria):
        """
        Filters the DataFrame based on specific category columns.

        Keyword arguments should be provided where the key is the column name
        (e.g., 'Category_1', 'Category_2') and the value is the desired value for that column.

        For example:
            filter_by_categories(Category_1="catA", Category_2="catB")
        will return all rows where Category_1 equals "catA" and Category_2 equals "catB".
        """
        if self.df is None:
            print("No data available. Run read_files() or load_from_file() first.")
            return None

        filtered_df = self.df
        for col, val in criteria.items():
            if col in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[col] == val]
            else:
                print(f"Column {col} not found in the DataFrame.")
                return None

        if filtered_df.empty:
            print("No matching rows found.")
            return None

        return filtered_df

    ### --- HELPER METHODS --- ###

    def _get_files_from_directory(self):
        """Walks through the directory, extracts filenames, categories, and reads (X, Y) data."""
        file_data = []

        for root, _, files in os.walk(self.directory):
            for file in files:
                if file.endswith(".xy"):
                    file_path = os.path.join(root, file)
                    file_path_for_stats = Path(str(file_path))
                    filename, _ = os.path.splitext(file)  # Extract filename without extension
                    creation_time = file_path_for_stats.stat().st_ctime
                    creation_date = datetime.datetime.fromtimestamp(creation_time)
                    print(creation_date)
                    categories = self._extract_categories(filename, creation_date)
                    df_xy = self._read_xy_data(file_path)  # Read (X, Y) data

                    file_data.append([file, *categories, df_xy])  # Store DataFrame in last column

        return file_data

    def _extract_categories(self, filename, creation_date):
        """Extracts categories from a filename (comma-separated)."""
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



        print(filename)
        match = re.search(pattern, filename)
        if match:
            data = match.groupdict()
            print("Gas:", data.get("gas"))
            print("Pressure:", data.get("pressure"))
            print("Cycle:", data.get("cycle"))
            print("Measurements in current temp step:", data.get("numMes"))
            #print("Current temp step:", data.get("currentStep"))
            #print("Measurements without interruption:", data.get("noIntMes"))
            #print("Temperature:", data.get("temperature"))
        else:
            print("The filename did not match the expected format.")



        categories = [cat.strip() for cat in filename.split(",")]
        return categories

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
        max_categories = max(len(row) - 2 for row in file_data)
        column_names = ["Filename"] + [f"Category_{i+1}" for i in range(max_categories)] + ["XY_Data"]
        return pd.DataFrame(file_data, columns=column_names)







data_manager = DataScreener(r"W:\Workgroup Felderhoff\Kiki\Wärmeleitfähigkeit\WAE-WA-030-Mg2NiH4\WAE-WA-031\WAE-WA-031-XRD\In-Situ-2\REX245 XRK WAE-WA-031")
data_manager.read_files()  # Build the DataFrame
#filtered = data_manager.filter_by_categories(Category_1="catA", Category_2="catB")
print("asdfasdf")
print(data_manager.df)



"REX245 XRK WAE-WA-049-01, 10dpm, IS 0.25deg, H2, 5bar C11_001_04_0004_0290-0C"

"REX245 XRK WAE-WA-049-01, 10dpm, IS 0.25deg, H2, 5bar C2_001_01_0001_0289-0C"

