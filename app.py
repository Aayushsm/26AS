import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

# ---------------------------
# Text-based extraction
# ---------------------------
def extract_text_pdf(pdf_file):
    records = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split("\n")

            current_deductor, current_tan = None, None

            for line in lines:
                if "Name of Deductor" in line:
                    current_deductor = line.split("Deductor")[-1].strip()
                if "TAN of Deductor" in line:
                    current_tan = line.split("Deductor")[-1].strip()

                cols = re.split(r"\s{2,}", line.strip())
                if len(cols) >= 5 and re.match(r"194", cols[0]):
                    try:
                        records.append({
                            "Deductor": current_deductor,
                            "TAN": current_tan,
                            "Section": cols[0].strip(),
                            "Amount Paid": float(cols[2].replace(",", "")),
                            "Tax Deducted": float(cols[3].replace(",", "")),
                            "TDS Deposited": float(cols[4].replace(",", "")),
                        })
                    except:
                        continue
    return pd.DataFrame(records)

# ---------------------------
# OCR extraction for scanned PDFs
# ---------------------------
def extract_ocr_pdf(uploaded_file):
    images = convert_from_bytes(uploaded_file.read())
    text_all = ""
    for img in images:
        text_all += pytesseract.image_to_string(img) + "\n"

    records = []
    current_deductor, current_tan = None, None
    for line in text_all.splitlines():
        if "Name of Deductor" in line:
            current_deductor = line.split("Deductor")[-1].strip()
        if "TAN of Deductor" in line:
            current_tan = line.split("Deductor")[-1].strip()

        cols = re.split(r"\s{2,}", line.strip())
        if len(cols) >= 5 and re.match(r"194", cols[0]):
            try:
                records.append({
                    "Deductor": current_deductor,
                    "TAN": current_tan,
                    "Section": cols[0].strip(),
                    "Amount Paid": float(cols[2].replace(",", "")),
                    "Tax Deducted": float(cols[3].replace(",", "")),
                    "TDS Deposited": float(cols[4].replace(",", "")),
                })
            except:
                continue
    return pd.DataFrame(records)

# ---------------------------
# Summaries
# ---------------------------
def summarize_26as(df):
    section_summary = df.groupby("Section").agg({
        "Amount Paid": "sum",
        "Tax Deducted": "sum",
        "TDS Deposited": "sum"
    }).reset_index()

    party_summary = df.groupby(["Deductor", "TAN"]).agg({
        "Amount Paid": "sum",
        "Tax Deducted": "sum",
        "TDS Deposited": "sum"
    }).reset_index()

    pivot = df.pivot_table(
        index=["Deductor", "TAN"],
        columns="Section",
        values="Tax Deducted",
        aggfunc="sum",
        fill_value=0
    ).reset_index()

    party_detailed = pd.merge(party_summary, pivot, on=["Deductor", "TAN"], how="left")

    return section_summary, party_detailed

def to_excel(section_summary, party_detailed):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        section_summary.to_excel(writer, sheet_name="Summary", index=False, startrow=0)
        party_detailed.to_excel(writer, sheet_name="Summary", index=False, startrow=len(section_summary)+3)
    return output.getvalue()

# ---------------------------
# Streamlit App
# ---------------------------
st.title("📊 Form 26AS TDS Summarizer")

uploaded_pdf = st.file_uploader("Upload your 26AS PDF", type=["pdf"])

if uploaded_pdf:
    with st.spinner("Extracting data..."):
        try:
            df = extract_text_pdf(uploaded_pdf)
        except Exception:
            df = pd.DataFrame()

        # If text extraction fails → use OCR
        if df.empty:
            st.warning("⚠️ Text extraction failed. Trying OCR...")
            uploaded_pdf.seek(0)  # Reset file pointer
            df = extract_ocr_pdf(uploaded_pdf)

    if not df.empty:
        st.success("✅ Data extracted successfully!")

        with st.expander("🔍 View Raw Extracted Data"):
            st.dataframe(df)

        section_summary, party_detailed = summarize_26as(df)

        st.subheader("📌 Section-wise Summary")
        st.dataframe(section_summary)

        st.subheader("📌 Party-wise Summary")
        st.dataframe(party_detailed)

        excel_data = to_excel(section_summary, party_detailed)
        st.download_button(
            label="📥 Download Excel Report",
            data=excel_data,
            file_name="26AS_Summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("❌ Could not extract data even with OCR. Please check PDF quality.")
