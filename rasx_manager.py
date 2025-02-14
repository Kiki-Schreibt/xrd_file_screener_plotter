#rasx_manager.py
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
from datetime import datetime
import re
import pandas as pd

# ---------------------------
# Extractor Base and Classes
# ---------------------------


class BaseExtractor:
    """Abstract base class for file extractors."""
    def extract(self, file_content):
        raise NotImplementedError("Must implement extract method.")


class RootXMLExtractor(BaseExtractor):
    """Extractor for root.xml file."""
    def extract(self, file_content):
        result = {}
        try:
            root = ET.fromstring(file_content)
            for child in root:
                tag = child.tag.split("}")[-1]
                result[tag] = child.text
        except Exception as e:
            raise ValueError(f"Error parsing root XML: {e}")
        return result


class MeasurementConditionsExtractor(BaseExtractor):
    """Extractor for MesurementConditions0.xml file."""
    def extract(self, file_content):
        result = {}
        try:
            root = ET.fromstring(file_content)
            for child in root:
                tag = child.tag.split("}")[-1]
                if tag == "ScanInformation":
                    scan_info = self._extract_scan_information(child)
                    result.update(scan_info)
                elif tag == "Axes":
                    temperature = self._extract_temperature(child)
                    if temperature is not None:
                        result["MeasurementCondition_Temperature"] = temperature
                else:
                    result[f"MeasurementCondition_{tag}"] = child.text
        except Exception as e:
            raise ValueError(f"Error parsing measurement conditions XML: {e}")
        return result

    def _extract_scan_information(self, scan_info_element):
        scan_info = {}
        for child in scan_info_element:
            tag = child.tag.split("}")[-1]
            scan_info[f"ScanInformation_{tag}"] = child.text
        # Example: parse start time into a datetime object.
        if "ScanInformation_StartTime" in scan_info:
            try:
                scan_info["StartTime"] = datetime.strptime(
                    scan_info["ScanInformation_StartTime"], "%Y-%m-%dT%H:%M:%SZ"
                )
            except Exception:
                pass
        return scan_info

    def _extract_temperature(self, axes_element):
        for axis in axes_element.findall('Axis'):
            if axis.get('Name') == 'Temp':
                temp_val = axis.get('Position')
                unit = axis.get('Unit')
                try:
                    return f"{float(temp_val)} {unit}"
                except Exception:
                    return None
        return None


class ProfileExtractor(BaseExtractor):
    """Extractor for Profile0.txt file containing diffraction data."""
    def extract(self, file_content):
        x_vals, y_vals = [], []
        lines = file_content.strip().splitlines()
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    x_vals.append(float(parts[0]))
                    y_vals.append(float(parts[1]))
                except ValueError:
                    continue
        return {'x': np.array(x_vals) if x_vals else None,
                'y': np.array(y_vals) if y_vals else None}


# ---------------------------
# RasxReader using extractors
# ---------------------------


class RasxReader:
    """
    Reads a .rasx file and uses registered extractors to parse different components.

    Available extractors (categories):
      - root.xml (metadata)
      - Data0/MesurementConditions0.xml (measurement conditions, scan info, temperature)
      - Data0/Profile0.txt (diffraction profile data)

    To add a new category, define a new extractor (subclass of BaseExtractor) and
    add it to the 'extractors' dictionary.
    """
    def __init__(self, file_path, extractors=None):
        self.file_path = file_path
        self.metadata = {}
        self.x = None  # Diffraction 2θ values
        self.y = None  # Intensity values

        # Register extractors with their corresponding file names
        self.extractors = extractors or {
            'root.xml': RootXMLExtractor(),
            'Data0/MesurementConditions0.xml': MeasurementConditionsExtractor(),
            'Data0/Profile0.txt': ProfileExtractor(),
        }
        self._parse_file()

    def _parse_file(self):
        try:
            with zipfile.ZipFile(self.file_path, 'r') as zf:
                file_list = zf.namelist()
                for file_name, extractor in self.extractors.items():
                    if file_name in file_list:
                        content = zf.read(file_name)
                        # Decode XML or TXT content
                        if file_name.endswith('.xml') or file_name.endswith('.txt'):
                            content = content.decode('utf-8', errors='replace')
                        result = extractor.extract(content)
                        # Store results accordingly
                        if file_name == 'Data0/Profile0.txt':
                            self.x = result.get('x')
                            self.y = result.get('y')
                        else:
                            self.metadata.update(result)
        except Exception as e:
            raise IOError(f"Error reading .rasx file {self.file_path}: {e}")

    def print_metadata(self):
        print("Metadata:")
        for key, value in self.metadata.items():
            print(f"  {key}: {value}")


# ---------------------------
# RasxDataManager for data handling
# ---------------------------


class RasxDataManager:
    """
    Provides higher-level data operations using RasxReader.
    This includes filtering diffraction data, converting data to DataFrames,
    and visualization.
    """
    def __init__(self, file_path):
        self.reader = RasxReader(file_path=file_path)
        self.temperature = self._parse_temperature(
            self.reader.metadata.get("MeasurementCondition_Temperature")
        )
        self.start_time = self.reader.metadata.get("StartTime")
        self.df_xy = self._get_xy_df()

    def _parse_temperature(self, temp_str):
        if not temp_str:
            return None
        match = re.search(r'\d+\.?\d*', temp_str)
        if match:
            return float(match.group())
        return None

    def filter_data(self, min_2theta, max_2theta):
        if self.reader.x is None or self.reader.y is None:
            return None, None
        mask = (self.reader.x >= min_2theta) & (self.reader.x <= max_2theta)
        return self.reader.x[mask], self.reader.y[mask]

    def _get_xy_df(self):
        if self.reader.x is None or self.reader.y is None:
            return pd.DataFrame()
        return pd.DataFrame({'X': self.reader.x, 'Y': self.reader.y})

    def visualize_xy(self):
        x_filtered, y_filtered = self.filter_data(20, 40)
        if x_filtered is None or y_filtered is None:
            print("No diffraction data available.")
            return

        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 6))
        plt.plot(x_filtered, y_filtered, color='red', lw=2, label='Filtered XRD Pattern')
        plt.xlabel('2θ (degrees)')
        plt.ylabel('Intensity (a.u.)')
        plt.title('Filtered XRD Diffraction Pattern')
        plt.legend()
        plt.show()

# ---------------------------
# Example usage (main)
# ---------------------------

if __name__ == '__main__':
    file_path = r'C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\REX245 XRK WAE-WA-049\REX245 XRK WAE-WA-049-01, 10dpm, IS 0.25deg, H2, 10bar C17 after 2.5h_001_17_0001_0350-0C.rasx'

    try:
        manager = RasxDataManager(file_path=file_path)
        print("Extracted Metadata:")
        print(manager.reader.metadata)
        print("Start Time:", manager.start_time)
        print("Temperature:", manager.temperature)
        # Optionally, visualize the diffraction data:
        # manager.visualize_xy()
    except Exception as e:
        print(f"An error occurred: {e}")


