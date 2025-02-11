import os
import pandas as pd

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
                file_path = os.path.join(root, file)
                filename, _ = os.path.splitext(file)  # Extract filename without extension
                categories = self._extract_categories(filename)
                df_xy = self._read_xy_data(file_path)  # Read (X, Y) data

                file_data.append([file, *categories, df_xy])  # Store DataFrame in last column

        return file_data

    def _extract_categories(self, filename):
        """Extracts categories from a filename (comma-separated)."""
        categories = [cat.strip() for cat in filename.split(",")]
        return categories

    def _read_xy_data(self, file_path):
        """Reads the (X, Y) data from a CSV file, if valid."""
        try:
            df_xy = pd.read_csv(file_path)  # Adjust if your files are not CSV
            if len(df_xy.columns) >= 2:  # Ensure at least two columns
                df_xy = df_xy.iloc[:, :2]  # Take only first two columns (assumed X and Y)
                df_xy.columns = ["X", "Y"]  # Standardize column names
                return df_xy
        except Exception:
            pass  # Ignore errors for non-CSV or unreadable files
        return None  # Return None if file is invalid

    def _create_dataframe(self, file_data):
        """Creates a Pandas DataFrame from the collected file data."""
        max_categories = max(len(row) - 2 for row in file_data)
        column_names = ["Filename"] + [f"Category_{i+1}" for i in range(max_categories)] + ["XY_Data"]
        return pd.DataFrame(file_data, columns=column_names)







data_manager = DataScreener("your/folder/path")
data_manager.read_files()  # Build the DataFrame
filtered = data_manager.filter_by_categories(Category_1="catA", Category_2="catB")
print(filtered)
