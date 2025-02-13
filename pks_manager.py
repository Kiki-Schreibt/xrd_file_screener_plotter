import os
from codecs import ignore_errors

import pandas as pd
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

@dataclass
class PTHFileData:
    filename: str
    metadata: Dict[str, Any]
    df: pd.DataFrame
    df_xy: pd.DataFrame

class PTHParser:
    """
    A class to parse .PTH files from XRD measurements.

    It separates the metadata (header comments and key–value pairs)
    from the tabular peaklist data and stores them separately.

    Parameters
    ----------
    file_path : str
        Path to the .PTH file.
    """
    def __init__(self, file_path: str = None, folder_path=None):
        self.folder_path = folder_path
        self.metadata: Dict[str, Any] = {}  # Dictionary for metadata
        self.df: pd.DataFrame = pd.DataFrame()  # DataFrame for peaklist data

        self.all_data = None

    def parse(self, add_metadata: bool = False, file_path=""):
        if self.folder_path and not file_path:
            return self.parse_folder(add_metadata=add_metadata)
        elif file_path:
            return self.parse_file(add_metadata=add_metadata, file_path=file_path)

    def parse_file(self, add_metadata: bool = False, file_path="", filename="") -> Tuple[Dict[str, Any], pd.DataFrame]:
        """
        Parse the .PTH file, separating metadata and table data.

        Parameters
        ----------
        add_metadata : bool, optional
            If True, add the metadata as extra columns in the DataFrame,
            by default False.

        Returns
        -------
        metadata : dict
            Parsed metadata from the file.
        df : pd.DataFrame
            DataFrame containing the numerical peaklist data.
        """
        with open(file_path, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]

        meta_lines, table_lines = self._split_lines(lines)
        self.metadata = self._parse_metadata(meta_lines)

        header, data_rows = self._parse_table_lines(table_lines)

        # Adjust rows so that all rows have the same number of columns.
        header, data_rows = self._adjust_rows(header, data_rows)

        if header and data_rows:
            df = pd.DataFrame(data_rows, columns=header)
        elif data_rows:
            df = pd.DataFrame(data_rows)
        else:
            df = pd.DataFrame()

        # Convert columns to numeric where possible.
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception:
                # If conversion fails, leave the column as is.
                pass
        df.rename(columns={"2Theta": "x", "I(rel)": "y"}, inplace=True)
        if add_metadata:
            for key, value in self.metadata.items():
                df[key] = value

        self.df = df
        result = PTHFileData(filename=filename, metadata=self.metadata, df=self.df, df_xy=self.df[['x', 'y']])
        return result

    def _split_lines(self, lines: List[str]) -> Tuple[List[str], List[str]]:
        """
        Separate the lines into two parts:
          - meta_lines: lines that come before the table data.
          - table_lines: lines starting from the first occurrence of "Peaklist".
        """
        meta_lines = []
        table_lines = []
        table_start_index = None
        for i, line in enumerate(lines):
            if line.startswith("Peaklist"):
                table_start_index = i
                break
            meta_lines.append(line)
        if table_start_index is not None:
            table_lines = lines[table_start_index:]
        return meta_lines, table_lines

    def _parse_metadata(self, meta_lines: List[str]) -> Dict[str, Any]:
        """
        Parse metadata from a list of lines.
        Lines starting with '!' are considered comments.
        If a line contains a colon, split into key and value.
        """
        metadata = {}
        for line in meta_lines:
            clean_line = line.lstrip("!").strip() if line.startswith("!") else line
            if ":" in clean_line:
                key, val = clean_line.split(":", 1)
                metadata[key.strip()] = val.strip()
            else:
                metadata.setdefault("comments", []).append(clean_line)
        metadata['name'] = metadata['STOE Peak File'].partition('_')[0]
        print(metadata['name'])
        return metadata

    def _parse_table_lines(self, table_lines: List[str]) -> Tuple[List[str], List[List[str]]]:
        """
        Parse the table section to extract a header and data rows.
        The first comment line after 'Peaklist' is assumed to be the header.
        Any further non-comment lines are treated as data rows.
        """
        header = None
        data_rows = []
        data_start = 0

        for j, line in enumerate(table_lines):
            if line.startswith("Peaklist"):
                continue
            if line.startswith("!"):
                header_line = line.lstrip("!").strip()
                header = header_line.split()
                data_start = j + 1
                break

        for line in table_lines[data_start:]:
            if line.startswith("!"):
                continue
            row_values = line.split()
            data_rows.append(row_values)
        return header, data_rows

    def _adjust_rows(self, header: List[str], data_rows: List[List[str]]) -> Tuple[List[str], List[List[str]]]:
        """
        Adjust the header and data rows so that every row has the same number of columns.
        If any data row has more tokens than the header, extend the header with generic names.
        If a row has fewer tokens, pad it with None.
        """
        # Determine maximum column count from header and all rows.
        header_len = len(header) if header is not None else 0
        max_cols = header_len
        for row in data_rows:
            if len(row) > max_cols:
                max_cols = len(row)

        # Adjust header: if header is None, create generic names; if shorter than max_cols, extend it.
        if header is None or len(header) == 0:
            header = [f"Col_{i+1}" for i in range(max_cols)]
        elif len(header) < max_cols:
            extra_cols = [f"Col_{i+1}" for i in range(len(header), max_cols)]
            header.extend(extra_cols)

        # Adjust each data row: pad if too short, or truncate if too long.
        adjusted_rows = []
        for row in data_rows:
            if len(row) < max_cols:
                # Pad the row with None values.
                row = row + [None] * (max_cols - len(row))
            elif len(row) > max_cols:
                row = row[:max_cols]
            adjusted_rows.append(row)
        return header, adjusted_rows

    def parse_folder(self, add_metadata: bool = False) -> List[PTHFileData]:
        """
        Parse all .PTH files in the specified folder.

        Parameters
        ----------
        folder_path : str
            Path to the folder containing .PTH files.
        add_metadata : bool, optional
            If True, add the metadata as extra columns in each DataFrame,
            by default False.

        Returns
        -------
        List[PTHFileData]
            A list of PTHFileData objects for each .PTH file in the folder.
        """
        results = []

        for file in os.listdir(self.folder_path):
            if file.lower().endswith('.pth'):
                file_path = os.path.join(self.folder_path, file)

                data = self.parse_file(add_metadata=add_metadata, file_path=file_path, filename=file)

                results.append(data)
            self.all_data = results
        return results

    def save_to_file(self, filename="pks_files.pkl"):
        """Saves the DataFrame to a file (Pickle or CSV)."""
        if not self.folder_path:
            return
        file_save_path = os.path.join(self.folder_path, "..", filename)
        if self.all_data is None:
            print("No data to save. Run read_files() first.")
            return

        if filename.endswith(".pkl"):
            self.all_data.to_pickle(file_save_path)
        elif filename.endswith(".csv"):
            self.all_data.to_csv(file_save_path, index=False)
        else:
            print("Unsupported file format. Use .pkl or .csv")
            return

        print(f"Data saved to {filename}.")

# Example usage:
if __name__ == "__main__":
    folder_path = r'C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\pks_files'
    file_path = os.path.join(folder_path, 'Mg_642654_Cu_borad.PTH')

    # Parse a single file.
    parser = PTHParser(folder_path=folder_path)
    data = parser.parse(add_metadata=True)

    print(f"\nParsed {len(data)} .PTH files in folder '{folder_path}'.")
    for file_data in data:
        print(f"\nFile: {file_data.filename}")
        print("Metadata:", file_data.metadata)
        print("DataFrame shape:", file_data.df.shape)
        print("DataFrame:")
        print(file_data.df_xy)

    #parser.save_to_file()
