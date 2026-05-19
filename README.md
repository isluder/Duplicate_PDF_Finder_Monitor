# Duplicate PDF Finder Monitor

A lightweight, highly efficient Python command-line tool that monitors a specified folder and immediately deletes any duplicate PDFs added to it. 

This tool is designed to prioritize the actual *content* of the PDFs rather than just their filenames. It calculates a SHA-256 digital signature (hash) for each PDF, ensuring 100% accuracy in detecting identical files even if they have been renamed (e.g., `Report.pdf` and `Report (1).pdf`).

## Features

- **Content-Based Detection**: Uses SHA-256 hashing to compare the actual binary contents of files, ensuring identical files are caught regardless of filename.
- **Initial Scan**: Automatically scans the target folder upon startup, catalogs existing PDFs, and cleans up any existing duplicates.
- **Efficient Monitoring**: Utilizes the `watchdog` library to listen for file system events asynchronously with a minimal CPU footprint.
- **Graceful Shutdown**: Safely exits and cleans up background processes when `Ctrl + C` is pressed.

## Prerequisites

- Python 3.7 or higher

## Setup Instructions

We recommend running this application within a Python virtual environment to keep its dependencies isolated.

1. **Clone or Download the Repository**
   Navigate to the directory where you downloaded or cloned this project:
   ```bash
   cd /path/to/Duplicate_PDF_Finder_Monitor
   ```

2. **Create a Virtual Environment**
   Run the following command to create a virtual environment named `.venv` in the project directory:
   ```bash
   python3 -m venv .venv
   ```

3. **Activate the Virtual Environment**
   - On **macOS and Linux**:
     ```bash
     source .venv/bin/activate
     ```
   - On **Windows**:
     ```bash
     .venv\Scripts\activate
     ```

4. **Install Requirements**
   Once the virtual environment is activated (you will usually see `(.venv)` in your terminal prompt), install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the application by executing the `monitor.py` script and passing the path of the folder you want to monitor.

```bash
python monitor.py /path/to/your/folder
```

For example, to watch your Downloads folder on a Mac:
```bash
python monitor.py ~/Downloads
```

If you run the script without any arguments, it will default to monitoring the current directory:
```bash
python monitor.py
```

### Stopping the Monitor
To stop the application, press `Ctrl + C` in your terminal. The script will catch the interrupt, cleanly shut down the file observer, and exit gracefully.

## Credits

Created by Isluder in collaboration with Gemini 3.1 Pro (as a human must always take responsibility for the code).
