import streamlit as st
import pdfplumber
import pandas as pd
import re
from pdf2image import convert_from_path
import pytesseract
from io import BytesIO
import tempfile
import os

st.set_page_config(page_title="Form 26AS TDS Summarizer", page_icon="🧾", layout="wide")

st.title("🧾 Form 26AS TDS Summarizer Utility")
st.markdown("Upload your Form 26AS PDF to get automatic section-wise and party-wise TDS summaries.")

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF using pdfplumber with OCR fallback"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_file.getvalue())
            tmp_path = tmp_file.name

        all_text = []

        with pdfplumber.open(tmp_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Try text extraction first
                text = page.extract_text()

                # If no text found or very little text, use OCR
                if not text or len(text.strip()) < 50:
                    st.warning(f"Page {page_num + 1}: Using OCR fallback")
                    images = convert_from_path(tmp_path, first_page=page_num+1, last_page=page_num+1)
                    if images:
                        text = pytesseract.image_to_string(images[0])

                all_text.append(text)

        os.unlink(tmp_path)
        return "\n".join(all_text)

    except Exception as e:
        if "encrypted" in str(e).lower() or "password" in str(e).lower():
            st.error("❌ This PDF is password-protected. Please upload an unprotected version.")
        else:
            st.error(f"❌ Error extracting text: {str(e)}")
        return None

def parse_tds_data(text):
    """Parse TDS data from extracted text"""

    # Initialize data structures
    section_data = {}
    party_data = {}

    # Common TDS sections
    sections_pattern = r'(194[A-Z]|192[A-Z]?|193|195|196[A-Z]?)'

    # Split text into lines for processing
    lines = text.split('\n')

    current_party = None
    current_tan = None

    for i, line in enumerate(lines):
        line = line.strip()

        # Look for TAN (format: XXXX12345X)
        tan_match = re.search(r'[A-Z]{4}\d{5}[A-Z]', line)
        if tan_match:
            current_tan = tan_match.group()

        # Look for party names (typically before TAN or in specific patterns)
        # This is a simplified heuristic - adjust based on actual PDF structure
        if current_tan and len(line) > 10 and not re.search(r'\d{2}/\d{2}/\d{4}', line):
            potential_party = re.sub(r'[A-Z]{4}\d{5}[A-Z]', '', line).strip()
            if len(potential_party) > 5 and not potential_party.isdigit():
                current_party = potential_party[:50]  # Limit length

        # Look for section mentions
        section_match = re.search(sections_pattern, line)
        if section_match:
            section = section_match.group()

            # Extract amounts (look for numbers with commas or decimals)
            amounts = re.findall(r'₹?\s*([\d,]+\.?\d*)', line)

            if amounts:
                # Parse amounts (gross, deducted, deposited)
                cleaned_amounts = [float(amt.replace(',', '')) for amt in amounts if amt]

                # Section-wise aggregation
                if section not in section_data:
                    section_data[section] = {'gross': 0, 'deducted': 0, 'deposited': 0}

                if len(cleaned_amounts) >= 3:
                    section_data[section]['gross'] += cleaned_amounts[0]
                    section_data[section]['deducted'] += cleaned_amounts[1]
                    section_data[section]['deposited'] += cleaned_amounts[2]
                elif len(cleaned_amounts) >= 2:
                    section_data[section]['deducted'] += cleaned_amounts[0]
                    section_data[section]['deposited'] += cleaned_amounts[1]

                # Party-wise aggregation
                if current_party and current_tan:
                    party_key = f"{current_party}|{current_tan}"
                    if party_key not in party_data:
                        party_data[party_key] = {
                            'name': current_party,
                            'tan': current_tan,
                            'gross': 0,
                            'deducted': 0,
                            'deposited': 0,
                            'sections': {}
                        }

                    if section not in party_data[party_key]['sections']:
                        party_data[party_key]['sections'][section] = 0

                    if len(cleaned_amounts) >= 3:
                        party_data[party_key]['gross'] += cleaned_amounts[0]
                        party_data[party_key]['deducted'] += cleaned_amounts[1]
                        party_data[party_key]['deposited'] += cleaned_amounts[2]
                        party_data[party_key]['sections'][section] += cleaned_amounts[1]
                    elif len(cleaned_amounts) >= 2:
                        party_data[party_key]['deducted'] += cleaned_amounts[0]
                        party_data[party_key]['deposited'] += cleaned_amounts[1]
                        party_data[party_key]['sections'][section] += cleaned_amounts[0]

    return section_data, party_data

def create_dataframes(section_data, party_data):
    """Create pandas DataFrames from parsed data"""

    # Section-wise DataFrame
    section_rows = []
    for section, data in section_data.items():
        section_rows.append({
            'Section': section,
            'Total Gross Receipts (₹)': f"{data['gross']:,.2f}",
            'Total TDS Deducted (₹)': f"{data['deducted']:,.2f}",
            'Total TDS Deposited (₹)': f"{data['deposited']:,.2f}"
        })

    df_section = pd.DataFrame(section_rows)

    # Party-wise DataFrame
    party_rows = []
    for party_key, data in party_data.items():
        sections_breakdown = ", ".join([f"{sec}: ₹{amt:,.2f}" for sec, amt in data['sections'].items()])
        party_rows.append({
            'Party Name': data['name'],
            'TAN': data['tan'],
            'Total Gross Receipts (₹)': f"{data['gross']:,.2f}",
            'Total TDS Deducted (₹)': f"{data['deducted']:,.2f}",
            'Total TDS Deposited (₹)': f"{data['deposited']:,.2f}",
            'Section-wise Breakdown': sections_breakdown
        })

    df_party = pd.DataFrame(party_rows)

    return df_section, df_party

def create_excel_download(df_section, df_party):
    """Create Excel file with both sheets"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_section.to_excel(writer, sheet_name='Section Wise', index=False)
        df_party.to_excel(writer, sheet_name='Party Wise', index=False)

    return output.getvalue()

# File upload
uploaded_file = st.file_uploader("Upload Form 26AS PDF", type=['pdf'])

if uploaded_file:
    with st.spinner("Extracting data from PDF..."):
        text = extract_text_from_pdf(uploaded_file)

    if text:
        st.success("✅ Text extraction completed!")

        with st.spinner("Parsing TDS data..."):
            section_data, party_data = parse_tds_data(text)

        if section_data or party_data:
            st.success("✅ Data parsed successfully!")

            df_section, df_party = create_dataframes(section_data, party_data)

            # Display Section-wise Summary
            st.header("📊 Section-wise Summary")
            st.dataframe(df_section, use_container_width=True)

            # Display Party-wise Summary
            st.header("👥 Party-wise Summary")
            st.dataframe(df_party, use_container_width=True)

            # Console output
            st.subheader("🖥️ Console Output")
            with st.expander("View detailed data"):
                st.write("**Section Data:**")
                st.json(section_data)
                st.write("**Party Data:**")
                st.json({k: {**v, 'sections': v['sections']} for k, v in party_data.items()})

            # Excel download
            excel_data = create_excel_download(df_section, df_party)
            st.download_button(
                label="📥 Download Excel Report",
                data=excel_data,
                file_name="26AS_TDS_Summary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ No TDS data found. Please check if the PDF is a valid Form 26AS document.")
    else:
        st.error("⚠️ Could not extract text from PDF. Please check PDF quality and try again.")
else:
    st.info("👆 Please upload a Form 26AS PDF to get started.")
