# xrd_file_screener.py
import os
import re
import pandas as pd
import datetime
from pathlib import Path
from rasx_manager import RasxDataManager
from xy_manager import XYFileReader

# ----------------------------------
# Category Extractor Base and Classes
# ----------------------------------

import os
import re
import pandas as pd
import datetime
from pathlib import Path
from rasx_manager import RasxDataManager
from xy_manager import XYFileReader

# ---------------- Category Extractors ---------------- #

class BaseCategoryExtractor:
    def extract(self, filename: str, manager) -> dict:
        raise NotImplementedError
    def get_categories(self) -> list:
        raise NotImplementedError


class FilenameCategoryExtractor(BaseCategoryExtractor):
    """
    Flexible, token-aware extractor.
    """
    TOKENS = {
        "gas":              (r"(?P<gas>[A-Za-z0-9]+)", str),
        "pressure":         (r"(?P<pressure>\d+(?:\.\d+)?)", float),
        "cycle":            (r"(?P<cycle>\d+)", int),
        "numcurrentstep":   (r"(?P<numcurrentstep>\d+)", int),
        "currenttempstep":  (r"(?P<currenttempstep>\d+)", int),
        "nointerruptmes":   (r"(?P<nointerruptmes>\d+)", int),
        "temperature":      (r"(?P<temperature>\d+(?:\.\d+)?)", float),
    }

    def __init__(self, pattern: str = None, conversion_mapping: dict = None):
        # ✅ Default now includes optional " C<cycle>" before the trailing tokens
        self.default_pattern = (
            r"(?P<gas>[A-Za-z0-9]+)\s*,\s*(?P<pressure>\d+(?:\.\d+)?)bar"
            r"(?:\s*C(?P<cycle>\d+))?"                     # <-- optional cycle like " C17"
            r".*?_"                                       
            r"(?P<numcurrentstep>\d+)_(?P<currenttempstep>\d+)_(?P<nointerruptmes>\d+)_"
            r"(?P<temperature>\d+)-0C$"
        )
        self.update_pattern(pattern or self.default_pattern, conversion_mapping)

    @classmethod
    def from_tokens(cls, tokens: list[str], sep: str = r"[\s,_-]+", suffix: str = r"$"):
        parts, conv = [], {}
        for t in tokens:
            if t not in cls.TOKENS:
                raise ValueError(f"Unknown token: {t}")
            rx, caster = cls.TOKENS[t]
            parts.append(rx)
            name = re.search(r"\?P<([^>]+)>", rx).group(1)
            conv[name] = caster
        pattern = (sep.join(parts)) + suffix
        return cls(pattern=pattern, conversion_mapping=conv)

    def update_pattern(self, new_pattern: str, conversion_mapping: dict = None):
        self.pattern = new_pattern
        self.compiled_pattern = re.compile(new_pattern)
        self.categories = list(self.compiled_pattern.groupindex.keys())
        if conversion_mapping is not None:
            self.conversion_mapping = conversion_mapping
        else:
            self.conversion_mapping = {
                'pressure': float, 'cycle': int,
                'numcurrentstep': int, 'currenttempstep': int,
                'nointerruptmes': int, 'temperature': float,
            }

    def extract(self, filename: str, manager=None) -> dict:
        filename_clean, _ = os.path.splitext(filename)
        m = self.compiled_pattern.search(filename_clean)
        if not m:
            return {k: None for k in self.categories}
        raw = m.groupdict()
        out = {}
        for k, v in raw.items():
            if v is None:
                out[k] = None; continue
            caster = self.conversion_mapping.get(k)
            if caster:
                try: out[k] = caster(v)
                except Exception: out[k] = None
            else:
                out[k] = v
        return out

    def get_categories(self) -> list:
        return list(self.categories)


class CycleExtractor(BaseCategoryExtractor):
    """
    Supplemental extractor that finds 'C<digits>' anywhere in the basename,
    e.g. '... C17 ...' → cycle=17. It ensures 'cycle' is always available
    even when a custom pattern omitted it.
    """
    _rx = re.compile(r'(?<![A-Za-z])C(?P<cycle>\d+)(?!\d)')

    def extract(self, filename: str, manager=None) -> dict:
        name_no_ext = os.path.splitext(filename)[0]
        m = self._rx.search(name_no_ext)
        if not m:
            return {}  # <-- IMPORTANT: do not set {'cycle': None}; that would override earlier values
        try:
            return {'cycle': int(m.group('cycle'))}
        except Exception:
            return {}

    def get_categories(self) -> list:
        return ['cycle']

# ---------------- Data Screener ---------------- #

class DataScreener:
    """
    Scans .rasx/.xy files or loads a saved dataframe (.pkl/.csv),
    annotates rows with categories from one or more extractors,
    and offers powerful filters + optional group/aggregate selection.
    """
    def __init__(self, source: str, category_extractors: list = None):
        self.source = source
        self.df = None
        self.category_extractors = category_extractors or [FilenameCategoryExtractor()]
        if os.path.isdir(source):
            self.mode = "folder"
        elif os.path.isfile(source) and source.lower().endswith((".pkl", ".csv")):
            self.mode = "file"
        else:
            raise ValueError("Source must be a directory or a .pkl/.csv file.")

    def load(self):
        if self.mode == "folder":
            self.read_files()
        else:
            self.load_from_file(self.source)

    def read_files(self):
        records_rasx = self._get_rasx_files_from_directory()
        records_xy = self._get_xy_files_from_directory()

        rasx_basenames = {os.path.splitext(rec["filename"])[0] for rec in records_rasx}
        filtered_records_xy = [rec for rec in records_xy
                               if os.path.splitext(rec["filename"])[0] not in rasx_basenames]

        records = records_rasx + filtered_records_xy
        self.df = self._create_dataframe(records)
        self._normalize_df()
        print("Files read and categorized successfully.")

    def save_to_file(self, filename="categorized_data.pkl"):
        """Save the DataFrame to a file. If filename is an absolute path, respect it."""
        if self.df is None:
            print("No data to save. Run load() or read_files() first.")
            return

        if os.path.isabs(filename):
            file_save_path = filename
        else:
            base_dir = self.source if os.path.isdir(self.source) else os.path.dirname(self.source)
            file_save_path = os.path.join(base_dir, filename)

        if file_save_path.lower().endswith(".pkl"):
            self.df.to_pickle(file_save_path)
        elif file_save_path.lower().endswith(".csv"):
            self.df.to_csv(file_save_path, index=False)
        else:
            print("Unsupported file format. Use .pkl or .csv")
            return

        print(f"Data saved to {file_save_path}.")

    def load_from_file(self, filepath):
        """Load a DataFrame from pkl/csv. If not a DataFrame, leave empty."""
        if not os.path.exists(filepath):
            print(f"File {filepath} not found.")
            self.df = pd.DataFrame()
            return

        try:
            if filepath.lower().endswith(".pkl"):
                obj = pd.read_pickle(filepath)
            elif filepath.lower().endswith(".csv"):
                obj = pd.read_csv(filepath)
            else:
                print("Unsupported file format. Use .pkl or .csv")
                self.df = pd.DataFrame()
                return
        except Exception as e:
            print(f"Failed to read {filepath}: {e}")
            self.df = pd.DataFrame()
            return

        if isinstance(obj, pd.DataFrame):
            self.df = obj
            self._normalize_df()
        else:
            print(f"Loaded object is not a DataFrame (type={type(obj).__name__}).")
            self.df = pd.DataFrame()

        print(f"Data loaded from {filepath}.")

    def filter_by_categories(self, group_by=None, agg_by=None, **criteria):
        """
        Powerful, type-aware filtering:
          - range: (min, max) or [min, max]
          - membership: list/set/tuple
          - callable: lambda row_value -> bool
          - regex: compiled re.Pattern
          - scalar equality
        """
        if self.df is None:
            print("No data available. Run load() or read_files() first.")
            return pd.DataFrame()

        df = self.df
        for col, crit in criteria.items():
            if crit is None or col not in df.columns:
                continue
            s = df[col]
            if callable(crit):
                df = df[s.apply(crit)]
            elif isinstance(crit, (tuple, list)) and len(crit) == 2:
                lo, hi = crit
                df = df[(s >= lo) & (s <= hi)]
            elif isinstance(crit, (list, set, tuple)):
                df = df[s.isin(crit)]
            elif hasattr(crit, "pattern"):  # compiled regex
                df = df[s.astype(str).str.contains(crit)]
            else:
                df = df[s == crit]

        df = self._group_agg_by(group_by=group_by, agg_by=agg_by, df=df)
        return df.reset_index(drop=True)

    def _group_agg_by(self, group_by, agg_by, df):
        if not (group_by and agg_by):
            return df
        agg_column, agg_func = agg_by
        if group_by not in df.columns:
            print(f"Group by column '{group_by}' not found. Skipping grouping.")
            return df
        if agg_column not in df.columns:
            print(f"Aggregation column '{agg_column}' not found. Skipping grouping.")
            return df

        if str(agg_func).lower() == 'max':
            idx = df.groupby(group_by)[agg_column].idxmax()
            return df.loc[idx].reset_index(drop=True)
        elif str(agg_func).lower() == 'min':
            idx = df.groupby(group_by)[agg_column].idxmin()
            return df.loc[idx].reset_index(drop=True)
        elif str(agg_func).lower() == 'minmax':
            idx_min = df.groupby(group_by)[agg_column].idxmin()
            idx_max = df.groupby(group_by)[agg_column].idxmax()
            idx = pd.concat([idx_min, idx_max]).sort_index()
            return df.loc[idx].reset_index(drop=True)
        else:
            print("agg_by function must be 'min', 'max', or 'minmax'. Skipping grouping.")
            return df

    def get_available_categories(self):
        cats = set()
        for extractor in self.category_extractors:
            cats.update(extractor.get_categories())
        return list(cats)

    def list_category_values(self, cat, top_k=None):
        if self.df is None or cat not in self.df.columns:
            return []
        vals = self.df[cat].dropna().unique().tolist()
        return vals[:top_k] if top_k else vals

    # ---- helpers for reading files ---- #

    def _get_rasx_files_from_directory(self):
        records = []
        for root_dir, _, files in os.walk(self.source):
            for file in files:
                if file.endswith(".rasx") and 'temp' not in file.lower():
                    file_path = os.path.join(root_dir, file)
                    try:
                        rasx_manager = RasxDataManager(file_path=file_path)
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
                        continue

                    from datetime import datetime as _dt
                    file_path_obj = Path(file_path)
                    try:
                        creation_date = rasx_manager.start_time
                    except Exception:
                        creation_ts = file_path_obj.stat().st_mtime
                        creation_date = _dt.fromtimestamp(creation_ts)

                    record = {
                        "filename": file,
                        "creation_date": creation_date,
                        "start_time": rasx_manager.start_time,
                        "df_xy": rasx_manager.df_xy  # 'X','Y'
                    }
                    # apply extractors in order; later ones may overwrite same keys
                    for extractor in self.category_extractors:
                        upd = extractor.extract(file, rasx_manager)  # or None for xy manager
                        # Prefer non-None values; do not overwrite existing non-None with None
                        for k, v in upd.items():
                            if v is not None or k not in record:
                                record[k] = v

                    # Default: if cycle is missing or None, treat as cycle=1
                    if 'cycle' not in record or record['cycle'] is None:
                        record['cycle'] = 1
                    records.append(record)
        return records

    def _get_xy_files_from_directory(self):
        records = []
        for root_dir, _, files in os.walk(self.source):
            for file in files:
                if file.endswith(".xy") and 'temp' not in file.lower():
                    file_path = os.path.join(root_dir, file)
                    try:
                        xy_reader = XYFileReader(file_path)
                        df_xy = xy_reader.read()  # returns 'X','Y'
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
                        continue

                    file_path_obj = Path(file_path)
                    try:
                        creation_ts = file_path_obj.stat().st_mtime
                        creation_date = datetime.datetime.fromtimestamp(creation_ts)
                    except Exception as e:
                        print(f"Error obtaining creation date for {file_path}: {e}")
                        creation_date = None

                    record = {
                        "filename": file,
                        "creation_date": creation_date,
                        "start_time": creation_date,
                        "df_xy": df_xy
                    }
                    for extractor in self.category_extractors:
                        upd = extractor.extract(file, None)  # or None for xy manager
                        # Prefer non-None values; do not overwrite existing non-None with None
                        for k, v in upd.items():
                            if v is not None or k not in record:
                                record[k] = v

                    # Default: if cycle is missing or None, treat as cycle=1
                    if 'cycle' not in record or record['cycle'] is None:
                        record['cycle'] = 1
                    records.append(record)
        return records

    def _create_dataframe(self, records: list, sort_key=""):
        if not records:
            print("No records to build DataFrame.")
            return pd.DataFrame()
        df = pd.DataFrame(records)
        sort_cols = [col for col in [sort_key, 'cycle', 'creation_date'] if col in df.columns]
        if sort_cols:
            df.sort_values(by=sort_cols, inplace=True)
        df.reset_index(drop=True)
        return df

    def _normalize_df(self):
        """Ensure critical categories exist and are properly typed."""
        if self.df is None or self.df.empty:
            return
        df = self.df

        # cycle: default to 1 when missing/NaN; ensure int dtype
        if 'cycle' not in df.columns:
            df['cycle'] = 1
        else:
            df['cycle'] = pd.to_numeric(df['cycle'], errors='coerce').fillna(1).astype(int)

        # (optional) pressure/temperature: try to coerce to numeric if present
        for col in ('pressure', 'temperature'):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        self.df = df

# ----------------------------------
# Example usage
# ----------------------------------

if __name__ == "__main__":
    # Example: Using a folder path to build the categorized DataFrame.
    folder_path = r"C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\REX245 XRK WAE-WA-049"
    screener = DataScreener(source=folder_path)
    screener.load()  # This will scan for both .rasx and .xy files.
    print("Available Categories:", screener.get_available_categories())
   # print(screener.df)

    # Save the data in both pickle and CSV formats.
    screener.save_to_file(filename="categorized_data.pkl")
    screener.save_to_file(filename="categorized_data.csv")

    # Example: Loading an existing file
    # screener_file = DataScreener(source=r"C:\path\to\categorized_data.pkl")
    # screener_file.load()
