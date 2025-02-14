#pks_manager.py
import os
import datetime
import pandas as pd
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Set

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
    """
    def __init__(self, file_path: str = None, folder_path: str = None):
        self.file_path = file_path
        self.folder_path = folder_path
        self.metadata: Dict[str, Any] = {}
        self.df: pd.DataFrame = pd.DataFrame()
        self.all_data: List[PTHFileData] = []

    def parse(self, add_metadata: bool = False, file_path: str = "") -> List[PTHFileData]:
        """
        Main entry point. If a folder path is given, parse all files;
        if a single file is specified, return a list with one PTHFileData object.
        """
        if self.folder_path and not file_path:
            return self.parse_folder(add_metadata=add_metadata)
        elif file_path:
            return [self.parse_file(add_metadata=add_metadata, file_path=file_path, filename=os.path.basename(file_path))]
        else:
            raise ValueError("Either folder_path or file_path must be provided.")

    def parse_file(self, add_metadata: bool = False, file_path: str = "", filename: str = "") -> PTHFileData:
        """
        Parse a single .PTH file, separating metadata and table data.
        """
        try:
            with open(file_path, 'r', encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            raise IOError(f"Error reading file {file_path}: {e}")

        meta_lines, table_lines = self._split_lines(lines)
        metadata = self._parse_metadata(meta_lines)
        header, data_rows = self._parse_table_lines(table_lines)
        header, data_rows = self._adjust_rows(header, data_rows)

        if header and data_rows:
            df = pd.DataFrame(data_rows, columns=header)
        elif data_rows:
            df = pd.DataFrame(data_rows)
        else:
            df = pd.DataFrame()

        # Attempt numeric conversion for each column.
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception:
                pass

        # Rename columns if they exist.
        if "2Theta" in df.columns and "I(rel)" in df.columns:
            df.rename(columns={"2Theta": "x", "I(rel)": "y"}, inplace=True)

        if add_metadata:
            for key, value in metadata.items():
                df[key] = value

        # Create a df_xy only if the expected columns exist.
        if "x" in df.columns and "y" in df.columns:
            df_xy = df[['x', 'y']]
        else:
            df_xy = pd.DataFrame()

        # Optionally extract a simplified name from metadata.
        if "STOE Peak File" in metadata:
            metadata['name'] = metadata['STOE Peak File'].partition('_')[0]
            print(f"Parsed file name: {metadata['name']}")  # Consider using logging instead.

        return PTHFileData(filename=filename, metadata=metadata, df=df, df_xy=df_xy)

    def _split_lines(self, lines: List[str]) -> Tuple[List[str], List[str]]:
        """
        Split lines into metadata lines and table lines.
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
        Parse metadata from the given lines.
        Lines starting with '!' are considered comments; lines with ':' are key–value pairs.
        """
        metadata = {}
        for line in meta_lines:
            clean_line = line.lstrip("!").strip() if line.startswith("!") else line
            if ":" in clean_line:
                key, val = clean_line.split(":", 1)
                metadata[key.strip()] = val.strip()
            else:
                metadata.setdefault("comments", []).append(clean_line)
        return metadata

    def _parse_table_lines(self, table_lines: List[str]) -> Tuple[List[str], List[List[str]]]:
        """
        Parse the table section to extract a header and the data rows.
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
        Ensure every row has the same number of columns by adjusting header and data rows.
        """
        header_len = len(header) if header is not None else 0
        max_cols = header_len
        for row in data_rows:
            max_cols = max(max_cols, len(row))

        if header is None or len(header) == 0:
            header = [f"Col_{i+1}" for i in range(max_cols)]
        elif len(header) < max_cols:
            header.extend([f"Col_{i+1}" for i in range(len(header), max_cols)])

        adjusted_rows = []
        for row in data_rows:
            if len(row) < max_cols:
                row = row + [None] * (max_cols - len(row))
            elif len(row) > max_cols:
                row = row[:max_cols]
            adjusted_rows.append(row)
        return header, adjusted_rows

    def parse_folder(self, add_metadata: bool = False) -> List[PTHFileData]:
        """
        Parse all .PTH files in the specified folder.
        """
        results: List[PTHFileData] = []
        if not os.path.isdir(self.folder_path):
            raise ValueError("Provided folder path does not exist or is not a directory.")

        for file in os.listdir(self.folder_path):
            if file.lower().endswith('.pth'):
                file_path = os.path.join(self.folder_path, file)
                try:
                    file_data = self.parse_file(add_metadata=add_metadata, file_path=file_path, filename=file)
                    results.append(file_data)
                except Exception as e:
                    print(f"Error parsing file {file}: {e}")
        self.all_data = results
        return results

    def save_to_file(self, filename: str = "pth_files.pkl"):
        """
        Saves the list of PTHFileData objects to a pickle file.
        If you need a CSV representation, you'll have to decide on how to flatten the data.
        """
        if not self.folder_path:
            print("No folder path provided.")
            return
        if not self.all_data:
            print("No data to save. Run parse_folder() first.")
            return

        file_save_path = os.path.join(os.path.dirname(self.folder_path), filename)
        try:
            # Saving using pandas.to_pickle works fine on arbitrary objects.
            pd.to_pickle(self.all_data, file_save_path)
            print(f"Data saved to {file_save_path}.")
        except Exception as e:
            print(f"Error saving data: {e}")


class PTHFilterManager:
    """
    A manager class to inspect and filter PTHFileData objects based on
    metadata or filename criteria.
    """
    def __init__(self, pth_file_data_list: List[PTHFileData]):
        self.pth_files = pth_file_data_list

    def list_metadata_fields(self) -> Set[str]:
        """
        Returns a set of all metadata fields present across all PTHFileData objects.
        """
        fields: Set[str] = set()
        for pth in self.pth_files:
            fields.update(pth.metadata.keys())
        return fields

    def unique_values_for_field(self, field: str) -> Set[Any]:
        """
        Returns a set of unique values for the specified metadata field.
        """
        values: Set[Any] = set()
        for pth in self.pth_files:
            if field in pth.metadata:
                values.add(pth.metadata[field])
        return values

    def filter(self, criteria: Dict[str, Any]) -> List[PTHFileData]:
        """
        Filters the PTHFileData objects based on the provided criteria.
        """
        filtered_files: List[PTHFileData] = []
        for pth in self.pth_files:
            match = True
            for key, expected in criteria.items():
                # Special handling for filename
                actual = pth.filename if key.lower() == "filename" else pth.metadata.get(key)
                if actual is None:
                    match = False
                    break

                if isinstance(expected, tuple) and len(expected) == 2:
                    try:
                        numeric_value = float(actual)
                        lower, upper = expected
                        if not (lower <= numeric_value <= upper):
                            match = False
                            break
                    except (ValueError, TypeError):
                        if actual != expected:
                            match = False
                            break
                elif isinstance(expected, (list, tuple, set)):
                    if actual not in expected:
                        match = False
                        break
                else:
                    if actual != expected:
                        match = False
                        break
            if match:
                filtered_files.append(pth)
        return filtered_files

# Example usage:
if __name__ == '__main__':
    folder_path = r'C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\pks_files'
    parser = PTHParser(folder_path=folder_path)
    pth_file_data_list = parser.parse(add_metadata=True)

    # Create a filter manager instance.
    filter_manager = PTHFilterManager(pth_file_data_list)

    # List available metadata fields.
    metadata_fields = filter_manager.list_metadata_fields()
    print("Available metadata fields:", metadata_fields)

    # Get unique values for a specific metadata field.
    unique_names = filter_manager.unique_values_for_field('STOE Peak File')
    print("Unique 'STOE Peak File' values:", unique_names)

    # Define filtering criteria.
    criteria = {
        "filename": ["Mg_642654_Cu_borad.PTH"],
        "SomeNumericField": (0, 100)  # Replace with an actual numeric field if available.
    }
    filtered_pth_files = filter_manager.filter(criteria)
    print(f"Found {len(filtered_pth_files)} files matching the criteria.")
    for file_data in filtered_pth_files:
        print(f"Filename: {file_data.filename}, Metadata: {file_data.metadata}")

    # Optionally save the parsed data.
    parser.save_to_file(filename="pth_files.pkl")
