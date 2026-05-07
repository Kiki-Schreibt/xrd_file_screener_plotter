#xy_manager.py
import pandas as pd


class XYFileReader:

    def __init__(self, filepath):
        """
        Initialize the reader with the path to the .xy file.

        :param filepath: Path to the .xy file
        """
        self.filepath = filepath

    def read(self):
        """
        Reads the .xy file and returns a DataFrame with columns ['x', 'y'].

        :return: pandas.DataFrame with columns 'x' and 'y'
        """
        try:
            # Use delim_whitespace=True to split on any whitespace and no header row.
            df = pd.read_csv(self.filepath, sep=r'\s+', header=None, names=['X', 'Y'])
            return df
        except Exception as e:
            print("An error occurred while reading the file:", e)
            return None


# Example usage:
if __name__ == "__main__":
    # Replace 'data.xy' with the path to your .xy file.
    reader = XYFileReader('data.xy')
    df = reader.read()
    if df is not None:
        print(df.head())
