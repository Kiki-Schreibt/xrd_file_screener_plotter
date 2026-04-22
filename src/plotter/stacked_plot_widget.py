#stacked_plot_widget.py
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore, QtGui

from xrd_file_screener import DataScreener

import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore, QtGui

class StackedPlotWidget(pg.GraphicsLayoutWidget):
    """
    Displays stacked XY curves from a DataFrame:
      columns: 'filename', 'df_xy' (with 'X','Y'), plus any category columns.
    """
    def __init__(self, data_frame, vertical_offset=10, parent=None):
        super().__init__(parent)
        self.data_frame = data_frame
        self.vertical_offset = vertical_offset
        self.filter_params = {}
        self.grouping_params = {}
        self.standard_params = {}

        self.name_mapping = {
            'nointerruptmes': 'Without interruption: ',
            'pressure': 'Pressure: ',
            'cycle': 'Cycle ',
            'numcurrentstep': 'Step program #: ',
            'currenttempstep': 'Meas. @program step: ',
            'gas': "Gas: ",
            'temperature': 'Temperature: ',
            'GroupBy': 'Grouped by: ',
            'AggBy': 'Sorted in group by: ',
            'AggFunc': 'Shown each group: '
        }
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle('Stacked XY Data')
        self.resize(800, 600)
        self.plot_item = self.addPlot(title="Diffractograms")
        font = QtGui.QFont("Arial", 16)
        self.plot_item.setLabel('left', 'Intensity (a.u.)')
        self.plot_item.setLabel('bottom', '2 Theta (°)')
        tick_font = QtGui.QFont("Arial", 14)
        left_axis = self.plot_item.getAxis('left')
        bottom_axis = self.plot_item.getAxis('bottom')
        left_axis.setStyle(tickFont=tick_font)
        bottom_axis.setStyle(tickFont=tick_font)
        left_axis.label.setFont(font)
        bottom_axis.label.setFont(font)

    def plot_stacked(self):
        if self.data_frame.empty:
            return
        num_curves = len(self.data_frame)
        self.plot_item.addLegend(offset=(0, 1))
        for idx, row in self.data_frame.iterrows():
            xy_df = row.get('df_xy')
            if xy_df is None or xy_df.empty:
                continue
            x = xy_df['X'].values
            y = xy_df['Y'].values + idx * self.vertical_offset
            pen = pg.mkPen(color=pg.intColor(idx, hues=num_curves), width=2)
            label = self._create_xy_label(row)
            self.plot_item.plot(x, y, pen=pen, name=label)
            self._add_text_item_to_line(x, y, label, pen)

    def add_vertical_lines(self, df_lines):
        if hasattr(self, 'vertical_legend') and self.vertical_legend is not None:
            try:
                self.vertical_legend.setParentItem(None)
            except Exception:
                pass
            self.vertical_legend = None

        self.vertical_legend = pg.LegendItem(offset=(50, 50))
        self.vertical_legend.setParentItem(self.plot_item.graphicsItem())

        num_groups = len(df_lines.columns)
        for idx, legend_label in enumerate(df_lines.columns):
            color = pg.intColor(idx, hues=num_groups)
            pen = pg.mkPen(color=color, style=QtCore.Qt.DashLine, width=2)
            x_positions = df_lines[legend_label].dropna().tolist()
            for x in x_positions:
                line = pg.InfiniteLine(pos=x, angle=90, pen=pen)
                self.plot_item.addItem(line)
            dummy_item = pg.PlotDataItem([0], [0], pen=pen)
            self.vertical_legend.addItem(dummy_item, legend_label)
        custom_font = QtGui.QFont("Arial", 16)
        if hasattr(self.vertical_legend, 'items'):
            for sample, label in getattr(self.vertical_legend, 'items', []):
                try:
                    label.setFont(custom_font)
                except Exception:
                    pass

    def _normalize_series(self, series):
        return (series - series.min()) / (series.max() - series.min())

    def _create_xy_label(self, row):
        names_to_exclude = {"filename", "df_xy", "creation_date", "start_time"}
        parts = []
        for k, v in row.items():
            if k in names_to_exclude or v is None:
                continue
            disp = self.name_mapping.get(k, k)
            parts.append(f"{disp}{v}")
        return " | ".join(parts) if parts else "Curve"

    def _add_text_item_to_line(self, x, y, base_label, pen):
        final_label = base_label
        custom = self._create_text_item_for_line()
        if custom:
            final_label = custom
        x_pos = x[-1]; y_pos = y[-1]
        text_item = pg.TextItem(text=final_label, anchor=(0, 1), color=pen.color())
        text_item.setFont(QtGui.QFont("Arial", 12))
        offset_x = (x.max() - x.min()) * 0.02 if len(x) else 0.5
        self.plot_item.addItem(text_item)
        text_item.setPos(x_pos + offset_x, y_pos)

    def update_plot(self, new_data_frame):
        self.data_frame = new_data_frame
        self.plot_item.clear()
        self.plot_stacked()

    def set_filter_params(self, params: dict):
        self.filter_params = params or {}

    def set_grouping_params(self, params: dict):
        self.grouping_params = params or {}

    def set_standard_params(self, params: dict):
        self.standard_params = params or {}

    def _create_text_item_for_line(self):
        segments = []
        if self.standard_params:
            segments += [f"{self.name_mapping.get(k, k)}{v}" for k, v in self.standard_params.items()]
        if self.filter_params:
            segments += [f"{self.name_mapping.get(k, k)}{v}" for k, v in self.filter_params.items()]
        if self.grouping_params:
            segments += [f"{self.name_mapping.get(k, k)}{v}" for k, v in self.grouping_params.items()]
        return " , ".join(segments) if segments else None


# ------------------------------
# Example usage of StackedPlotWidget
# ------------------------------
if __name__ == '__main__':
    # Create a DataScreener instance and load/filter the data.
    data_manager = DataScreener(
        r"C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\REX245 XRK WAE-WA-049"
    )
    data_manager.load_from_file(
        r"C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\categorized_data.pkl"
    )

    # Filter for a specific temperature and cycle range.

    cycle_number = [1, 20]
    temperature = [285, 300]
    pressure = [9.5, 10.5]
    group_by = 'cycle'
    agg_by = ("current_temp_step", "max")
    df = data_manager.filter_by_categories(cycle=cycle_number, temperature=temperature, group_by=group_by, agg_by=agg_by)
    #df = data_manager.df
    # Create the Qt application.
    app = QtWidgets.QApplication([])

    # Create and show the stacked plot widget.
    widget = StackedPlotWidget(df, vertical_offset=500)
    line = {"A": [20, 30, 40],
            "B": [15, 35, 45]}
    line = pd.DataFrame(line)
    widget.add_vertical_lines(df_lines=line)
    widget.show()

    # Start the Qt event loop.
    app.exec()
