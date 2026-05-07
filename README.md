# In-Situ XRD Plotter
## Disclaimer

I am not a professional programmer. I built this project during my doctoral work because I needed a faster way to inspect large batches 
of in-situ XRD measurements together with phase reference data. Its a small tool but quite helpful. 

The main purpose of this software is to load diffraction scans from a measurement folder, 
extract useful metadata from the filenames, and make it practical to compare many patterns at once. 
It can also overlay phase positions from `.PTH` files and export the currently visible stacked plot to Origin.

The repository mainly exists so the code behind the plots in my research is available and reproducible. 
If you are working with similar in-situ diffraction datasets, I hope it is useful as a starting point for your own workflow.

Some parts of the implementation are still rough around the edges. The program grew out of actual lab work, 
so the focus was getting reliable plots and filtering tools rather than polishing every detail of the code structure.

Feel free to extend the functionality for your own work. Please do not redistribute it as your own. 
A substantial amount of time went into developing and testing it against my data.

If you have questions, you can contact me at Christian.Wagner.420@gmail.com and I will try to help when I can.

## Overview
In-Situ XRD Plotter is a PySide6 desktop application for screening and plotting batches of XRD measurements. 
It reads `.rasx` and `.xy` diffraction files, categorizes them from filename patterns, lets you filter and group scans by extracted metadata, 
and displays the result as stacked diffractograms.

The repository also includes support for `.PTH` peak lists, so characteristic phase positions can be added as vertical reference lines. 
On Windows, the current plot can be sent directly to Origin through `originpro`.

Main features in the current codebase:

- **Batch loading of XRD files** from folders containing `.rasx` and/or `.xy` files.
- **Metadata extraction from filenames** such as gas, pressure, cycle number, step indices, and temperature.
- **Filtering and grouping** of scans before plotting.
- **Stacked plotting** with adjustable vertical offsets.
- **Phase marker overlays** from `.PTH` peak files.
- **Cached categorized datasets** via `.pkl` or `.csv` to avoid rebuilding metadata every time.
- **Origin export** for the currently displayed plot on Windows systems with Origin installed.

## Project Structure
```text
.
|-- src/
|   `-- plotter/
|       |-- gui.py                  # Main PySide6 application
|       |-- main_backend.py         # Data loading, filtering, PTH processing
|       |-- xrd_file_screener.py    # File scanning and filename-based categorization
|       |-- rasx_manager.py         # .rasx reader and metadata extraction
|       |-- xy_manager.py           # Plain .xy reader
|       |-- pks_manager.py          # .PTH parser
|       |-- pth_processor.py        # PTH filtering and vertical line extraction
|       `-- stacked_plot_widget.py  # Stacked diffractogram plotting widget
|-- test_data/                      # Example XRD, XY, PTH, and cached data
|-- docs/                           # Documentation scaffolding, still incomplete
|-- requirements.txt                # Python dependencies
|-- README.md
|-- LICENSE.md
|-- COMMERCIAL-LICENSE.md
`-- NOTICE.md
```

## Prerequisites
- **Python 3.12** is recommended.
- **Windows** is the primary target environment.
- **Origin** is only required if you want to use the export-to-Origin feature.
- XRD input data should be available as **`.rasx`** or whitespace-separated **`.xy`** files.
- Phase reference data should be available as **`.PTH`** files if you want vertical markers.

The project depends on `PySide6`, `pyqtgraph`, `pandas`, `numpy`, `scipy`, and `originpro` among others. These are listed in `requirements.txt`.

## Setup
1. **Clone the repository**
   ```bash
   git clone https://github.com/Kiki-Schreibt/xrd_file_screener_plotter.git
   cd xrd_file_screener_plotter
   ```
2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. **Install dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

If you do not need Origin export, the rest of the application is still usable without an active Origin session. 
The export feature itself is Windows-specific and expects a working Origin installation.

## Running the Application
Start the GUI from the repository root with:

```bash
python src/plotter/gui.py
```

This opens the main window for selecting XRD and optional PTH data, configuring filters, and generating stacked plots.

## Typical Workflow
1. Select an XRD folder or a previously saved categorized dataset (`.pkl` or `.csv`).
2. Optionally select a folder containing `.PTH` peak files.
3. Load the XRD data so available filename categories can be detected.
4. Apply filters such as gas, pressure, cycle, step number, or temperature.
5. Optionally group the scans and choose a min/max aggregation column.
6. Adjust the vertical offset for the stacked plot.
7. Select PTH entries and define threshold / maximum peak count if phase lines should be overlaid.
8. Plot the result and optionally send it to Origin.

## Filename Parsing
The default filename parser expects filenames that contain information like gas, pressure, optional cycle number, step identifiers, and temperature. If your naming scheme differs, the GUI includes a token-based pattern builder for constructing a custom extraction pattern.

In practice, the code is built around filename conventions similar to the example data under `test_data/`. If your files follow a different naming scheme, some adjustment of the pattern will likely be necessary.

## Cached Data
When raw XRD files are read, the categorized DataFrame can be stored as a pickle or CSV file and reloaded later. This is useful when a folder contains many scans and you do not want to rebuild the metadata table every time.


## Notes and Limitations
- The codebase currently uses direct module imports inside `src/plotter`, so running `python src/plotter/gui.py` from the repository root is the intended entry point.
- Origin export is only available on Windows and only when `originpro` can connect to an installed Origin instance.
- The documentation setup (`mkdocs.yml`, `docs/`) is present, but the written user manual is not complete yet.
- The repository includes sample data for experimentation, but it is still tailored to the file structures and naming conventions used during development.

## License

This project is licensed under the **PolyForm Noncommercial License 1.0.0**.

That means you may use, modify, and redistribute this software only for permitted noncommercial purposes under that license.

Commercial use is not granted under this repository license. If you want to use this software commercially, you must obtain a separate written commercial license from the copyright holder.

For commercial licensing inquiries, contact:

Christian Wagner  
Christian.Wagner.420@gmail.com

For further information, see `LICENSE.md`, `COMMERCIAL-LICENSE.md`, and `NOTICE.md`.
