# Slip Extractor

## Description

This is a Flask web application designed to extract information from uploaded slip images. Users can upload images, preview them, process them to extract data (presumably using OCR and bank-specific parsing logic), view the extracted data alongside the image, and delete uploaded images.

## Prerequisites

Before you begin, ensure you have the following installed:

1.  **Python 3.x**: Download from [python.org](https://www.python.org/)
2.  **Pip**: (Usually comes with Python) Used for installing Python packages.
3.  **Tesseract OCR Engine**: This project relies on Tesseract for Optical Character Recognition.
    *   Download from [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki).
    *   **Important**: During installation, make sure to install the language packs for English (`eng`) and Thai (`tha`), or any other languages present in your slips.
    *   Note the installation path of Tesseract OCR, as you will need to configure it in the project.
<!-- 4.  **Git**: (Optional, for cloning the repository) Download from [git-scm.com](https://git-scm.com/) -->

## Setup Instructions

1.  **Chnage root directory of project**:
    ```bash
    cd <project-directory-name>
    ```
    Navigate to the project's root directory.

2.  **Create a Virtual Environment**:
    It's highly recommended to use a virtual environment to manage project dependencies.
    ```bash
    python -m venv .venv
    ```

3.  **Activate the Virtual Environment**:
    *   On Windows:
        ```bash
        .venv\Scripts\activate
        ```
    *   On macOS/Linux:
        ```bash
        source .venv/bin/activate
        ```

4.  **Install Dependencies**:
    Install all required Python packages listed in `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure Tesseract OCR Path**:
    The application needs to know where your Tesseract OCR engine is installed.
    *   Open the file: `function/e_slip/ocr_tesseract.py`
    *   Find the line: `pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"`
    *   **Modify this path** to match your Tesseract OCR installation location. For example, if you installed it in `D:\Tesseract-OCR`, the line should be `pytesseract.pytesseract.tesseract_cmd = r"D:\Tesseract-OCR\tesseract.exe"`.
        *Ensure the path points to the `tesseract.exe` executable.*

6.  **Bank Logo Templates (if applicable)**:
    The bank identification feature (`function/e_slip/bank_annotation.py`) uses image templates.
    *   Ensure you have a folder named `bank_logos` in the root directory of the project.
    *   This folder should contain subfolders for each bank, and those subfolders should contain logo images (e.g., `bank_logos/kbank/kbank_logo.png`).
    *   The `process_image` function in `function/e_slip/extract_info.py` currently expects this `bank_logos` folder at the root.

## Running the Application

1.  **Ensure your virtual environment is activated.**
2.  **Navigate to the project's root directory** (where `app.py` is located).
3.  **Run the Flask application**:
    ```bash
    python app.py
    ```
4.  Open your web browser and go to the address displayed in the terminal (usually `http://127.0.0.1:5000/` or `http://localhost:5000`).

## Features

*   **Upload Images**: Upload slip images (supports common image formats; HEIC files are converted for preview).
*   **File Listing**: View a list of all uploaded images in the `uploads/` folder.
*   **Image Preview**: Click on a filename to see a preview of the image. Click the preview image to zoom in/out (scrollable if image is larger than viewport).
*   **Process Image**: Click the "Process" button next to a file to initiate data extraction.
*   **View Extracted Data**: The processed data is displayed in a table alongside a preview of the image with bank class detection.
*   **Bank Class Display**: Shows detected bank type with color-coded alerts and icons.
*   **Raw OCR Text**: Displays raw OCR output in collapsible sections for debugging.
*   **Delete Image**: Click the "Delete" button to remove an uploaded image from the server (with a confirmation prompt).
*   **Extract All Data**: Bulk extraction feature that processes all uploaded files (both e-slips and physical slips) and exports the results to CSV files with timestamps. The extracted data includes:
    *   Individual CSV files for e-slips and physical slips
    *   Summary report with processing statistics
    *   Metadata including filename, slip type, processing timestamp, detected bank, and confidence scores
    *   Error reporting for files that failed to process
*   **View Extraction Results**: Web interface to view all extraction results with:
    *   Organized display of e-slip and physical slip results
    *   Collapsible data tables for easy viewing
    *   Download links for individual CSV files
    *   Summary statistics and processing timestamps
    *   Color-coded cards for different result types
*   **Loading Spinner**: Visual feedback is provided during file processing and deletion.
*   **Evaluation System**: Comprehensive evaluation tools for analyzing extraction performance.

## Project Structure

```
/
├── app.py                      # Main Flask application file (routes, core logic)
├── requirements.txt            # Python package dependencies
├── README.md                   # Project documentation
├── main-e-slip.ipynb          # Jupyter notebook for e-slip analysis
├── main-physical.ipynb        # Jupyter notebook for physical slip analysis
├── eslip_dataset.csv          # E-slip dataset file
│
├── function/                   # Directory for backend processing logic
│   ├── e_slip/                 # Functions specific to e-slip processing
│   │   ├── bank_annotation.py  # Bank logo detection and annotation
│   │   ├── extract_info.py     # E-slip data extraction logic
│   │   ├── ocr_tesseract.py    # OCR processing functions
│   │   └── preprocess.py       # Image preprocessing utilities
│   └── physical/               # Functions specific to physical slip processing
│       ├── physical_slip.py    # Physical slip YOLO detection and processing
│       └── extract_info.py     # Physical slip data extraction
│
├── templates/                  # HTML templates for the web interface
│   ├── index.html              # Main page (upload, file list, preview)
│   └── display_data.html       # Page to show extracted data and image preview
│
├── uploads/                    # Root folder for uploads (created automatically)
│   ├── e-slips/                # Uploaded e-slip images
│   └── physicals/              # Uploaded physical slip images
│
├── models/                     # Machine learning models
│   └── best.pt                 # YOLO model for physical slip detection
│
├── bank_logos/                 # Folder for bank logo image templates
│   ├── bangkok/                # Bangkok Bank logo templates
│   ├── kbank/                  # KBank logo templates
│   ├── scb/                    # SCB Bank logo templates
│   └── krungthai/              # Krungthai Bank logo templates
│
├── dataset/                    # Dataset files and images
│   └── [various image files]  # Training and testing datasets
│
├── app_extraction_csv/         # CSV results from user app extraction
│   ├── e_slip_extraction_*.csv    # E-slip extraction results with timestamps
│   ├── physical_slip_extraction_*.csv # Physical slip extraction results with timestamps
│   └── extraction_summary_*.csv       # Processing summaries with timestamps
│
├── results_csv/                # CSV results from original research processing
│   ├── eslip_result.csv        # Main e-slip extraction results
│   ├── eslip_ocr.csv           # Raw OCR results
│   └── eslip_classification.csv # Bank classification results
│
├── evaluation/                 # Evaluation and analysis tools
│   ├── detailed_missing_data_by_bank_column.csv  # Detailed missing data analysis
│   ├── comprehensive_evaluation_summary.csv      # Overall summary
│   ├── bank_performance_ranking.csv              # Bank performance ranking
│   ├── field_performance_ranking.csv             # Field extraction ranking
│   ├── overall_statistics.csv                    # Overall statistics
│   ├── summary_missing_data_by_bank.csv          # Summary by bank
│   └── simple_evaluation_summary.txt             # Human-readable summary
│
└── .venv/                      # Python virtual environment (created during setup)
```

## Notes & Potential Issues

*   **Tesseract OCR Path**: The most common setup issue is an incorrect path to `tesseract.exe` in `function/e_slip/ocr_tesseract.py`. Double-check this path.
*   **Tesseract Language Data**: Ensure 'eng' (English) and 'tha' (Thai) language data files are installed for Tesseract OCR. If not, OCR will likely fail or produce poor results for Thai text.
*   **Bank Logo Matching**: The accuracy of bank identification depends on the quality and variety of your logo templates in the `bank_logos/` folder.
*   **YOLO Model**: Physical slip processing requires the `models/best.pt` YOLO model for bank detection.
*   **Upload Folder**: The `uploads/` folder is created automatically if it doesn't exist. Uploaded files are stored here.
*   **Error Messages**: Check the Flask development server console output for detailed error messages if something goes wrong during processing.
*   **Security**: For production use, consider implementing more robust security measures (e.g., using `werkzeug.utils.secure_filename` more consistently, input validation, CSRF protection if forms get more complex). 