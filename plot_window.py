import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        # Create a matplotlib Figure and add a subplot.
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        # Initialize the canvas with the figure.
        super().__init__(self.fig)
        # Optionally, set the parent widget.
        self.setParent(parent)
        # Plot some sample data.
        self.plot_sample()

    def plot_sample(self):
        # Clear the axes and plot example data.
        self.axes.clear()
        x = [0, 1, 2, 3, 4]
        y = [10, 1, 20, 3, 15]
        self.axes.plot(x, y, marker='o', linestyle='-', color='blue')
        self.axes.set_title("Sample Plot")
        self.axes.set_xlabel("X-axis")
        self.axes.set_ylabel("Y-axis")
        # Draw the canvas again.
        self.draw()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Plot Window Example")
        # Create a central widget and a vertical layout.
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        # Create an instance of PlotCanvas and add it to the layout.
        self.plot_canvas = PlotCanvas(self, width=5, height=4, dpi=100)
        self.plot_canvas.show()
        # Set the central widget for the main window.
        #self.setCentralWidget(central_widget)

if __name__ == '__main__':
    # Create the application instance.
    app = QApplication(sys.argv)
    # Create and show the main window.
    window = MainWindow()
    window.show()
    # Start the event loop.
    sys.exit(app.exec())
