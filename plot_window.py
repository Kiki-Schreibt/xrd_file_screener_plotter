import sys
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets

from xrd_file_screener import DataScreener

class StackedPlotter:


    def __init__(self, data_frame, vertical_offset=10):
        """
        :param data_frame: A pandas DataFrame with at least the following columns:
                           - 'filename': a string (for labeling)
                           - 'df_xy': a DataFrame holding the measurement data with columns "X" and "Y"
        :param vertical_offset: The amount of vertical shift to apply between consecutive curves.
        """
        self.df = data_frame
        self.vertical_offset = vertical_offset

    def plot_stacked(self):
        """
        Creates a pyqtgraph window and plots each (X, Y) curve from the DataFrame,
        applying a vertical offset to each subsequent curve.
        """
        # Create the Qt application
        app = QtWidgets.QApplication(sys.argv)

        # Create a GraphicsLayoutWidget (a convenient container for plots)
        win = pg.GraphicsLayoutWidget(title="Stacked Plot of XY Data")
        win.resize(800, 600)
        win.setWindowTitle('Stacked XY Data')

        # Add a PlotItem to the layout
        plot_item = win.addPlot(title="Stacked XY Data")
        plot_item.setLabel('left', 'Y (offset applied)')
        plot_item.setLabel('bottom', 'X')

        # Determine the number of curves to help set up a color cycle
        num_curves = len(self.df)

        # Loop over the rows of the DataFrame and plot each curve
        for idx, row in self.df.iterrows():
            # Extract the XY data (ensure it's not None and not empty)
            xy_df = row.get('df_xy')
            if xy_df is None or xy_df.empty:
                continue  # Skip if no valid data

            # Get X and Y values and apply a vertical offset (based on the index)
            x = xy_df['X'].values
            y = xy_df['Y'].values + idx * self.vertical_offset

            # Create a pen with a unique color for each curve (using pyqtgraph's built-in color helper)
            pen = pg.mkPen(color=pg.intColor(idx, hues=num_curves), width=2)

            # Plot the curve; you can also add a name for a legend if needed
            plot_item.plot(x, y, pen=pen, name=row.get('filename', f'Curve {idx}'))

        # Show the window and start the Qt event loop.
        win.show()
        sys.exit(app.exec())



# ------------------------------
# Example usage of StackedPlotter
# ------------------------------
if __name__ == '__main__':
    # For demonstration, let's create a dummy filtered DataFrame similar to what your DataScreener produces.
    # In your actual usage, you would obtain 'filtered_df' from:
    #    filtered_df = data_manager.filter_by_categories(pressure=10)

    # Create dummy data (5 curves) with a "df_xy" column containing a DataFrame with X and Y data.
    dummy_data = []
    data_manager = DataScreener(r"C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\REX245 XRK WAE-WA-049")
    data_manager.load_from_file(r"C:\Daten\Kiki\ProgrammingStuff\in_situ_xrd_plotter\test_data\categorized_data.pkl")
    #df = data_manager.df
    df = data_manager.filter_by_categories()

    plotter = StackedPlotter(df, vertical_offset=500)
    plotter.plot_stacked()
