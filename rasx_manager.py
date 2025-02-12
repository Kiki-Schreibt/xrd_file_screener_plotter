# reader.py
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
from datetime import datetime
import re

import pandas as pd


class RasxReader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.metadata = {}
        self.scan_information = {}
        self.x = None  # 2θ values
        self.y = None  # Intensity values
        self.temperature = None  # Parsed temperature as float
        self._parse_file()

    def _parse_file(self):
        try:
            with zipfile.ZipFile(self.file_path, 'r') as zf:
                file_list = zf.namelist()
                # Parse root.xml
                if "root.xml" in file_list:
                    self._parse_root_xml(zf.read("root.xml"))
                # Parse measurement conditions XML
                if "Data0/MesurementConditions0.xml" in file_list:
                    self._parse_measurement_conditions(zf.read("Data0/MesurementConditions0.xml"))
                # Parse diffraction profile data
                if "Data0/Profile0.txt" in file_list:
                    profile_data = zf.read("Data0/Profile0.txt").decode('utf-8', errors='replace')
                    self._parse_profile_txt(profile_data)
        except Exception as e:
            raise IOError(f"Error reading .rasx file {self.file_path}: {e}")

    def _parse_root_xml(self, xml_data):
        root = ET.fromstring(xml_data)
        for child in root:
            tag = child.tag.split("}")[-1]
            self.metadata[tag] = child.text

    def _parse_measurement_conditions(self, xml_data):
        mc_root = ET.fromstring(xml_data)
        for child in mc_root:
            tag = child.tag.split("}")[-1]
            if tag == "ScanInformation":
                self._parse_scan_information(child)
            elif tag == "Axes":
                self._parse_temperature(child)
            else:
                self.metadata[f"MeasurementCondition_{tag}"] = child.text

    def _parse_scan_information(self, scan_info_element):
        for child in scan_info_element:
            tag = child.tag.split("}")[-1]
            self.scan_information[f"ScanInformation_{tag}"] = child.text
        # Example: parse and store start time as a datetime object.
        start_time_str = self.scan_information.get("ScanInformation_StartTime")
        if start_time_str:
            self.metadata["StartTime"] = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%SZ")

    def _parse_temperature(self, axes_element):
        for axis in axes_element.findall('Axis'):
            if axis.get('Name') == 'Temp':
                temp_val = axis.get('Position')
                unit = axis.get('Unit')
                self.metadata['MeasurementCondition_Temperature'] = f"{temp_val} {unit}"
                self.temperature = float(temp_val)
                break

    def _parse_profile_txt(self, text_data):
        lines = text_data.strip().splitlines()
        x_vals, y_vals = [], []
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    x_vals.append(float(parts[0]))
                    y_vals.append(float(parts[1]))
                except ValueError:
                    continue
        if x_vals and y_vals:
            self.x = np.array(x_vals)
            self.y = np.array(y_vals)
        else:
            print("No valid diffraction data found in Profile0.txt.")

    def print_metadata(self):
        print("Metadata:")
        for key, value in self.metadata.items():
            print(f"  {key}: {value}")

    def print_scan_information(self):
        print("Scan Information:")
        for key, value in self.scan_information.items():
            print(f"  {key}: {value}")


class RasxDataManager:

    def __init__(self, file_path):
        self.reader = RasxReader(file_path=file_path)
        # Optionally, you can copy or organize data here.
        self.temperature = self._parse_temperature(self.reader.metadata["MeasurementCondition_Temperature"])
        self.start_time = self.reader.metadata["StartTime"]
        self.df_xy = self._get_xy_df()

    def _parse_temperature(self, temp_str):

        match = re.search(r'\d+', temp_str)
        if match:
            temp_int = int(match.group())
            return temp_int
        else:
            return None

    def filter_data(self, min_2theta, max_2theta):
        # Example function: filter the diffraction data based on a 2θ range.
        mask = (self.reader.x >= min_2theta) & (self.reader.x <= max_2theta)
        return self.reader.x[mask], self.reader.y[mask]

    def _get_xy_df(self):
        df = pd.DataFrame()
        df['X'] = self.reader.x
        df['Y'] = self.reader.y
        return df

    def visualize_xy(self):
        x_filtered, y_filtered = self.filter_data(20, 40)

        # Visualize the filtered data
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 6))
        plt.plot(x_filtered, y_filtered, color='red', lw=2, label='Filtered XRD Pattern')
        plt.xlabel('2θ (degrees)')
        plt.ylabel('Intensity (a.u.)')
        plt.title('Filtered XRD Diffraction Pattern')
        plt.legend()
        plt.show()

    # Add more methods to organize or process your data as needed.

# main_backend.py (example usage)
if __name__ == '__main__':
    file_path = r'C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\REX245 XRK WAE-WA-049\REX245 XRK WAE-WA-049-01, 10dpm, IS 0.25deg, H2, 10bar C17 after 2.5h_001_17_0001_0350-0C.rasx'
    manager = RasxDataManager(file_path=file_path)
    temp = manager.temperature
    time = manager.start_time
    print(temp)
    print(time)
    #try:
        #reader = RasxReader(file_path)
        #reader.print_metadata()
        #reader.print_scan_information()

        # Now use the data manager to further process or organize the data.

        #manager = RasxDataManager(reader)
        # For instance, filter data between 20 and 40 degrees:


   # except Exception as e:
      #  print(f"An error occurred: {e}")


