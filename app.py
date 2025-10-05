import streamlit as st
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
import pandas as pd
import re
from io import BytesIO
import tempfile
import os

# Set page configuration
st.set_page_config(page_title="Form 26AS TDS Summarizer", page_icon="🧾", layout="wide")

# Title and description
st.title("🧾 Form 26AS TDS Summarizer Utility")
st.markdown("Upload your **Form 26AS PDF** to automatically generate section-wise and party-wise TDS summaries.")

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using pdfplumber with OCR fallback for image-based pages"""
    full_text = ""
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Try text extraction first
                text = page.extract_text()
                
                # If no text found (image-based page), use OCR
                if not text or len(text.strip()) < 50:
                    st.info(f"Page {page_num + 1}: Using OCR (image-based page detected)")
                    try:
                        # Convert specific page to image
                        images = convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1)
                        if images:
                            text = pytesseract.image_to_string(images[0])
                    except Exception as e:
                        st.warning(f"OCR failed for page {page_num + 1}: {str(e)}")
                        text = ""
                
                full_text += text + "\n"
        
        return full_text
    
    except Exception as e:
        if "password" in str(e).lower():
            st.error("❌ The PDF is password-protected. Please upload an unlocked PDF.")
        else:
            st.error(f"❌ Error reading PDF: {str(e)}")
        return None

# Function to parse TDS data from extracted text
def parse_tds_data(text):
    """Parse TDS data from Form 26AS text"""
    
    # Initialize data structures
    section_data = {}
    party_data = {}
    
    # Common TDS sections in Form 26AS
    tds_sections = ['194A', '194C', '194J', '194H', '194I', '194IA', '194IB', '194M', '192', '193', '194', '194D']
    
    # Split text into lines
    lines = text.split('\n')
    
    current_party = None
    current_tan = None
    current_section = None
    
    for i, line in enumerate(lines):
        # Look for TDS section patterns (e.g., "Section 194A", "194J", etc.)
        for section in tds_sections:
            if re.search(rf'\b{section}\b', line, re.IGNORECASE):
                current_section = section
                break
        
        # Look for TAN pattern (e.g., "DELC12345F")
        tan_match = re.search(r'\b[A-Z]{4}\d{5}[A-Z]\b', line)
        if tan_match:
            current_tan = tan_match.group()
        
        # Look for party/deductor name (typically appears before TAN)
        if current_tan and i > 0:
            potential_name = lines[i-1].strip()
            if len(potential_name) > 3 and not re.search(r'\d{2}/\d{2}/\d{4}', potential_name):
                current_party = potential_name
        
        # Extract monetary values (amounts in Indian format)
        amounts = re.findall(r'₹?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', line)
        
        if amounts and current_section:
            # Convert amounts to float - FIX: Handle empty strings and validation
            clean_amounts = []
            for amt in amounts:
                try:
                    # Remove commas and strip whitespace
                    cleaned = amt.replace(',', '').strip()
                    # Only convert if string is not empty and contains digits
                    if cleaned and cleaned.replace('.', '').isdigit():
                        clean_amounts.append(float(cleaned))
                except (ValueError, AttributeError):
                    # Skip invalid amounts
                    continue
            
            # Heuristic: typically Gross Receipt, TDS Deducted, TDS Deposited appear in sequence
            if len(clean_amounts) >= 3:
                gross_receipt = clean_amounts[0]
                tds_deducted = clean_amounts[1]
                tds_deposited = clean_amounts[2] if len(clean_amounts) > 2 else clean_amounts[1]
                
                # Update section-wise data
                if current_section not in section_data:
                    section_data[current_section] = {
                        'gross_receipts': 0,
                        'tds_deducted': 0,
                        'tds_deposited': 0
                    }
                
                section_data[current_section]['gross_receipts'] += gross_receipt
                section_data[current_section]['tds_deducted'] += tds_deducted
                section_data[current_section]['tds_deposited'] += tds_deposited
                
                # Update party-wise data
                if current_party and current_tan:
                    party_key = f"{current_party}_{current_tan}"
                    
                    if party_key not in party_data:
                        party_data[party_key] = {
                            'name': current_party,
                            'tan': current_tan,
                            'gross_receipts': 0,
                            'tds_deducted': 0,
                            'tds_deposited': 0,
                            'section_breakdown': {}
                        }
                    
                    party_data[party_key]['gross_receipts'] += gross_receipt
                    party_data[party_key]['tds_deducted'] += tds_deducted
                    party_data[party_key]['tds_deposited'] += tds_deposited
                    
                    # Section breakdown for party
                    if current_section not in party_data[party_key]['section_breakdown']:
                        party_data[party_key]['section_breakdown'][current_section] = 0
                    party_data[party_key]['section_breakdown'][current_section] += tds_deducted
    
    return section_data, party_data

# Function to create DataFrames
def create_dataframes(section_data, party_data):
    """Convert parsed data to pandas DataFrames"""
    
    # Section-wise DataFrame
    section_rows = []
    for section, data in section_data.items():
        section_rows.append({
            'Section': f'TDS {section}',
            'Total Gross Receipts (₹)': f"{data['gross_receipts']:,.2f}",
            'Total TDS Deducted (₹)': f"{data['tds_deducted']:,.2f}",
            'Total TDS Deposited (₹)': f"{data['tds_deposited']:,.2f}"
        })
    
    df_section = pd.DataFrame(section_rows)
    
    # Party-wise DataFrame
    party_rows = []
    for party_key, data in party_data.items():
        # Create section breakdown string
        breakdown = ', '.join([f"TDS {sec} – ₹{amt:,.2f}" 
                               for sec, amt in data['section_breakdown'].items()])
        
        party_rows.append({
            'Party Name': data['name'],
            'TAN': data['tan'],
            'Total Gross Receipts (₹)': f"{data['gross_receipts']:,.2f}",
            'Total TDS Deducted (₹)': f"{data['tds_deducted']:,.2f}",
            'Total TDS Deposited (₹)': f"{data['tds_deposited']:,.2f}",
            'TDS Breakdown by Section': breakdown
        })
    
    df_party = pd.DataFrame(party_rows)
    
    return df_section, df_party

# Function to create Excel file
def create_excel(df_section, df_party):
    """Create Excel file with two sheets"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_section.to_excel(writer, sheet_name='Section Wise', index=False)
        df_party.to_excel(writer, sheet_name='Party Wise', index=False)
    
    output.seek(0)
    return output

# Main app logic
uploaded_file = st.file_uploader("📁 Upload Form 26AS PDF", type=['pdf'])

if uploaded_file:
    with st.spinner("📄 Processing PDF..."):
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.read())
            tmp_path = tmp_file.name
        
        try:
            # Extract text
            extracted_text = extract_text_from_pdf(tmp_path)
            
            if extracted_text:
                st.success("✅ PDF text extracted successfully!")
                
                # Show extracted text preview (optional debug)
                with st.expander("🔍 View Extracted Text Preview"):
                    st.text(extracted_text[:2000] + "..." if len(extracted_text) > 2000 else extracted_text)
                
                # Parse TDS data
                with st.spinner("🧮 Parsing TDS data..."):
                    section_data, party_data = parse_tds_data(extracted_text)
                
                if section_data or party_data:
                    # Create DataFrames
                    df_section, df_party = create_dataframes(section_data, party_data)
                    
                    # Display section-wise summary
                    st.subheader("📊 Section-wise TDS Summary")
                    if not df_section.empty:
                        st.dataframe(df_section, use_container_width=True)
                    else:
                        st.warning("No section-wise data found.")
                    
                    # Display party-wise summary
                    st.subheader("👥 Party-wise TDS Summary")
                    if not df_party.empty:
                        st.dataframe(df_party, use_container_width=True)
                    else:
                        st.warning("No party-wise data found.")
                    
                    # Console output
                    print("\n=== SECTION-WISE SUMMARY ===")
                    print(df_section.to_string(index=False))
                    print("\n=== PARTY-WISE SUMMARY ===")
                    print(df_party.to_string(index=False))
                    
                    # Download Excel button
                    if not df_section.empty or not df_party.empty:
                        excel_file = create_excel(df_section, df_party)
                        st.download_button(
                            label="📥 Download Excel Report",
                            data=excel_file,
                            file_name="Form_26AS_TDS_Summary.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                else:
                    st.error("❌ Could not parse TDS data from the PDF. Please check if this is a valid Form 26AS PDF.")
            else:
                st.error("❌ Failed to extract text from PDF. Please check PDF quality and try again.")
        
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            st.exception(e)
        
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

# Footer
st.markdown("---")
st.markdown("**Note:** Ensure Tesseract OCR and Poppler are installed on macOS via Homebrew:")
st.code("brew install tesseract poppler", language="bash")
