# 🧾 Form 26AS TDS Summarizer Utility

A Streamlit web application that automatically summarizes TDS data from Form 26AS PDFs (downloaded from TRACES) with section-wise and party-wise breakdowns.

## 🎯 Features

- **Smart PDF Processing**: Handles both text-based and scanned (image-based) PDFs
- **Dual Extraction**: Uses pdfplumber for text extraction with OCR fallback (pytesseract)
- **Section-wise Summary**: Aggregates TDS data by section (194A, 194C, 194J, etc.)
- **Party-wise Summary**: Groups TDS by deductor with TAN details
- **Excel Export**: Download summaries in a clean Excel file with two sheets
- **Error Handling**: Detects password-protected PDFs and extraction failures

## 📋 Prerequisites

### System Dependencies (macOS)

Install Poppler and Tesseract using Homebrew:

```bash
brew install poppler
brew install tesseract
```

### For Linux:
```bash
sudo apt-get install poppler-utils
sudo apt-get install tesseract-ocr
```

### For Windows:
- Download and install [Poppler for Windows](http://blog.alivate.com.au/poppler-windows/)
- Download and install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)

## 🚀 Installation

1. **Clone or download this project**

2. **Create a virtual environment** (recommended):

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Python dependencies**:

```bash
pip install -r requirements.txt
```

## 🎮 Usage

1. **Run the Streamlit app**:

```bash
streamlit run app.py
```

2. **Open your browser** (usually opens automatically at `http://localhost:8501`)

3. **Upload your Form 26AS PDF** using the file uploader

4. **View the summaries**:
   - Section-wise summary table
   - Party-wise summary table with TDS breakdowns
   - Console output for detailed data inspection

5. **Download Excel report** using the download button

## 📊 Output Format

### Section-wise Summary
| Section | Total Gross Receipts | Total TDS Deducted | Total TDS Deposited |
|---------|---------------------|-------------------|---------------------|

### Party-wise Summary
| Party Name | TAN | Total Gross Receipts | Total TDS Deducted | Total TDS Deposited | Section-wise Breakdown |
|------------|-----|---------------------|-------------------|---------------------|----------------------|

## 🛠️ Technical Stack

- **Framework**: Streamlit
- **PDF Processing**: pdfplumber, pdf2image, pytesseract
- **Data Handling**: pandas, openpyxl
- **Language**: Python 3.8+

## ⚙️ Configuration

The app uses intelligent OCR triggering:
- Primary extraction via pdfplumber
- OCR fallback only for pages with <50 characters
- Supports both scanned and digital PDFs

## 🧭 Error Handling

- **Password-protected PDFs**: Shows clear error message
- **Extraction failures**: Prompts user to check PDF quality
- **No data found**: Warns if no valid TDS data is detected

## 📝 Notes

- Optimized for **TRACES Form 26AS format**
- Supports standard TDS sections (194A, 194C, 194J, etc.)
- Tested on macOS (Apple Silicon)
- Works with both text-based and image-based PDFs

## 🐛 Troubleshooting

### OCR not working:
- Verify Tesseract installation: `tesseract --version`
- Check Tesseract path in system PATH

### PDF conversion fails:
- Verify Poppler installation: `pdftoppm -v`
- Ensure poppler binaries are in system PATH

### Dependencies error:
```bash
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

## 📄 License

This project is provided as-is for educational and utility purposes.

## 🤝 Contributing

Feel free to submit issues or pull requests for improvements!
