import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets

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
        num_curves = len(self.data_frame)
        for idx, row in self.data_frame.iterrows():
            xy_df = row.get('df_xy')
            if xy_df is None or xy_df.empty:
                continue

            x = xy_df['X'].values
            y = xy_df['Y'].values + idx * self.vertical_offset

            pen = pg.mkPen(color=pg.intColor(idx, hues=num_curves), width=2)
            self.plot_item.plot(x, y, pen=pen, name=[row.get('filename', f'Curve {idx}'), row.get('creation_date')])
            self.plot_item.addLegend(offset=(0, 1))





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
    df = data_manager.filter_by_categories(temperature=350, cycle=[5, 10], )

    # Create the Qt application.
    app = QtWidgets.QApplication([])

    # Create and show the stacked plot widget.
    widget = StackedPlotWidget(df, vertical_offset=500)
    widget.show()

    # Start the Qt event loop.
    app.exec()
