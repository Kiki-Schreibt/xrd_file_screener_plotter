#stacked_plot_widget.py
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore

from xrd_file_screener import DataScreener


class StackedPlotWidget(pg.GraphicsLayoutWidget):
    """
    A widget that displays a stacked plot of XY data from a given DataFrame.

    The DataFrame is expected to have at least these columns:
      - 'filename': a label for the curve
      - 'df_xy': a DataFrame with columns "X" and "Y" containing the data
    """
    def __init__(self, data_frame, vertical_offset=10, parent=None):
        """
        :param data_frame: Pandas DataFrame containing the XY data.
        :param vertical_offset: The vertical offset applied between curves.
        :param parent: Optional parent widget.
        """
        super().__init__(parent)
        self.data_frame = data_frame
        self.vertical_offset = vertical_offset

        self._init_ui()
        self._plot_stacked()

    def _init_ui(self):
        """Set up the UI (plot area) of the widget."""
        self.setWindowTitle('Stacked XY Data')
        self.resize(800, 600)
        self.plot_item = self.addPlot(title="Stacked XY Data")
        self.plot_item.setLabel('left', 'Y (offset applied)')
        self.plot_item.setLabel('bottom', 'X')

    def _plot_stacked(self):
        """Plot each XY dataset as a stacked curve in the plot_item."""
        if self.data_frame.empty:
            return
        num_curves = len(self.data_frame)
        for idx, row in self.data_frame.iterrows():
            xy_df = row.get('df_xy')
            if xy_df is None or xy_df.empty:
                continue

            x = xy_df['X'].values
            #y = self._normalize_series(xy_df['Y']) + idx * 0.05
            y = xy_df['Y'].values + idx * self.vertical_offset

            pen = pg.mkPen(color=pg.intColor(idx, hues=num_curves), width=2)
            label = self._create_xy_label(row)


            self.plot_item.plot(x, y, pen=pen, name=[label])
            self.plot_item.addLegend(offset=(0, 1))
            self._add_text_item_to_line(x, y, label, pen)

    def add_vertical_lines(self, df_lines):
        """
        Add vertical lines to the plot with an extra legend using a DataFrame.
        Before adding new vertical lines, remove any existing legend.
        """
        # Remove the existing legend if it exists.
        if hasattr(self, 'vertical_legend') and self.vertical_legend is not None:
            try:
                self.plot_item.removeItem(self.vertical_legend)
            except Exception as e:
                print("Error removing existing legend:", e)

        # Create and store a new legend.
        self.vertical_legend = pg.LegendItem(offset=(50, 50))
        self.vertical_legend.setParentItem(self.plot_item.graphicsItem())

        num_groups = len(df_lines.columns)
        for idx, legend_label in enumerate(df_lines.columns):
            # Choose a color for this group.
            color = pg.intColor(idx, hues=num_groups)
            # Use a dashed line style.
            pen = pg.mkPen(color=color, style=QtCore.Qt.DashLine, width=2)
            # Get the x positions for this legend label and drop NaN values.
            x_positions = df_lines[legend_label].dropna().tolist()
            # Draw a vertical line (angle=90) for each x position.
            for x in x_positions:
                line = pg.InfiniteLine(pos=x, angle=90, pen=pen)
                self.plot_item.addItem(line)
            # Create a dummy plot item to add to the legend.
            dummy_item = pg.PlotDataItem([0], [0], pen=pen)
            self.vertical_legend.addItem(dummy_item, legend_label)



    def add_vertical_lines_from_struct(self, lines_by_legend):
        """
        Add vertical lines to the plot with an extra legend.

        :param lines_by_legend: dict mapping a legend label to a list of x positions.
            For example:
                {
                    "Event A": [1, 2, 3, 4, 5],
                    "Event B": [5, 6, 7, 8]
                }
        Each group of vertical lines will be drawn with the same color.
        """
        # Create a new legend for the vertical lines and add it to the plot.
        vertical_legend = pg.LegendItem(offset=(50, 50))
        vertical_legend.setParentItem(self.plot_item.graphicsItem())

        num_groups = len(lines_by_legend)
        for idx, (legend_label, x_positions) in enumerate(lines_by_legend.items()):
            # Choose a color for this group.
            color = pg.intColor(idx, hues=num_groups)
            # Use a dashed line style.
            pen = pg.mkPen(color=color, style=QtCore.Qt.DashLine, width=2)
            # Draw a vertical line (angle=90) for each x position.
            for x in x_positions:
                line = pg.InfiniteLine(pos=x, angle=90, pen=pen)
                self.plot_item.addItem(line)
            # To add a legend entry, create a dummy plot item.
            dummy_item = pg.PlotDataItem([0], [0], pen=pen)
            vertical_legend.addItem(dummy_item, legend_label)

    def _normalize_series(self, series):
        normed_series = (series - series.min()) / (series.max() - series.min())
        return normed_series

    def _create_xy_label(self, row):
        names_to_exclude = {"filename", "df_xy"}
        labels = []
        label = "Couldn't find info"
        strings_to_delete = ['measurements_', 'current_', 'creation_']
        for index, value in row.items():
            if index not in names_to_exclude:
                for s in strings_to_delete:
                    index = index.replace(s, '')

                labels.append(f"{index}: {value}")
        if labels:
            label = " ".join(labels)
        return label

    def _add_text_item_to_line(self, x, y, label, pen):
        #todo: customize text to show next to line
        x_pos = x[-1]
        y_pos = y[-1]

        # Create a text item for the label.
        # The 'anchor' parameter ensures the text is positioned relative to its bounding box.
        text_item = pg.TextItem(text=label, anchor=(0, 1), color=pen.color())
        # Offset the text slightly from the curve point (adjust offsets as needed).
        offset_x = x.max() * 0.02
        offset_y = 0
        text_item.setPos(x_pos + offset_x, y_pos + offset_y)
        self.plot_item.addItem(text_item)

        # Option 1: Draw a line connecting the curve to the text.
        # You can use plot_item.plot to draw a connecting line.
        self.plot_item.plot([x_pos, x_pos + offset_x], [y_pos, y_pos + offset_y],
                            pen=pg.mkPen(color=pen.color(), style=pg.QtCore.Qt.DashLine))

    def update_plot(self, new_data_frame):
        """
        Clears the existing plot and re-plots using the new DataFrame.
        """
        self.data_frame = new_data_frame
        self.plot_item.clear()  # Clear current items and legend
        self._plot_stacked()

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
