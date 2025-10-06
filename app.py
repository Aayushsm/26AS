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
st.markdown("Upload your **Form 26AS PDF** to automatically generate section-wise TDS summary.")

# Comprehensive section mapping from Form 26AS
SECTION_DESCRIPTIONS = {
    '192': 'Salary',
    '192A': 'TDS on PF withdrawal',
    '193': 'Interest on Securities',
    '194': 'Dividends',
    '194A': 'Interest other than Interest on securities',
    '194B': 'Winning from lottery or crossword puzzle',
    '194BA': 'Winnings from online games',
    '194BB': 'Winning from horse race',
    '194C': 'Payments to contractors and sub-contractors',
    '194D': 'Insurance commission',
    '194DA': 'Payment in respect of life insurance policy',
    '194E': 'Payments to non-resident sportsmen or sports associations',
    '194EE': 'Payments in respect of deposits under National Savings Scheme',
    '194F': 'Payments on account of repurchase of units by Mutual Fund',
    '194G': 'Commission, price, etc. on sale of lottery tickets',
    '194H': 'Commission or brokerage',
    '194I(a)': 'Rent on hiring of plant and machinery',
    '194I(b)': 'Rent on other than plant and machinery',
    '194IA': 'TDS on Sale of immovable property',
    '194IB': 'Payment of rent by certain individuals or Hindu undivided family',
    '194IC': 'Payment under specified agreement',
    '194J(a)': 'Fees for technical services',
    '194J(b)': 'Fees for professional services or royalty',
    '194JA': 'Fees for technical services',
    '194JB': 'Fees for professional services or royalty',
    '194K': 'Income payable to a resident in respect of units',
    '194LA': 'Payment of compensation on acquisition of immovable property',
    '194LB': 'Income by way of Interest from Infrastructure Debt fund',
    '194LC': 'Income from infrastructure debt fund',
    '194LBA': 'Certain income from units of a business trust',
    '194LBB': 'Income in respect of units of investment fund',
    '194LBC': 'Income in respect of investment in securitization trust',
    '194LD': 'TDS on interest on bonds / government securities',
    '194M': 'Payment of certain sums by certain individuals or HUF',
    '194N': 'Payment of certain amounts in cash',
    '194O': 'Payment of certain sums by e-commerce operator',
    '194P': 'Deduction of tax in case of specified senior citizen',
    '194Q': 'Deduction of tax on payment for purchase of goods',
    '194R': 'Benefits or perquisites of business or profession',
    '194S': 'Payment for transfer of virtual digital asset',
    '195': 'Other sums payable to a non-resident',
    '196A': 'Income in respect of units of non-residents',
    '196B': 'Payments in respect of units to an offshore fund',
    '196C': 'Income from foreign currency bonds or shares',
    '196D': 'Income of foreign institutional investors from securities',
    '196DA': 'Income of specified fund from securities'
}

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using pdfplumber with OCR fallback for image-based pages"""
    full_text = ""
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                
                if not text or len(text.strip()) < 50:
                    st.info(f"Page {page_num + 1}: Using OCR (image-based page detected)")
                    try:
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

# Function to normalize section names
def normalize_section(section_raw):
    """Normalize section names to standard format"""
    section = section_raw.upper().strip()
    
    # Handle variations with parentheses and without
    # 1941(a) -> 194I(a), 1941(b) -> 194I(b)
    section = re.sub(r'1941\(A\)', '194I(a)', section, flags=re.IGNORECASE)
    section = re.sub(r'1941\(B\)', '194I(b)', section, flags=re.IGNORECASE)
    
    # Handle without parentheses: 194Ia -> 194I(a), 194Ib -> 194I(b)
    section = re.sub(r'194IA\b', '194I(a)', section, flags=re.IGNORECASE)
    section = re.sub(r'194IB\b', '194I(b)', section, flags=re.IGNORECASE)
    
    # Handle 194J variations
    section = re.sub(r'194J\(A\)', '194J(a)', section, flags=re.IGNORECASE)
    section = re.sub(r'194J\(B\)', '194J(b)', section, flags=re.IGNORECASE)
    section = re.sub(r'194JA\b', '194J(a)', section, flags=re.IGNORECASE)
    section = re.sub(r'194JB\b', '194J(b)', section, flags=re.IGNORECASE)
    
    # Handle 194LC variations
    section = re.sub(r'194LC\(2\)\(I\)', '194LC(2)(i)', section, flags=re.IGNORECASE)
    section = re.sub(r'194LC\(2\)\(IA\)', '194LC(2)(ia)', section, flags=re.IGNORECASE)
    section = re.sub(r'194LC\(2\)\(IB\)', '194LC(2)(ib)', section, flags=re.IGNORECASE)
    section = re.sub(r'194LC\(2\)\(IC\)', '194LC(2)(ic)', section, flags=re.IGNORECASE)
    
    return section

# Function to parse TDS data from Form 26AS - SECTION-WISE ONLY
def parse_form_26as_sectionwise(text):
    """Parse Form 26AS and extract ONLY section-wise TDS summary, ignoring negative values"""
    
    section_summary = {}
    lines = text.split('\n')
    
    in_tds_section = False
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Detect if we're in PART-I (TDS section)
        if re.search(r'PART[- ]?I\b', line, re.IGNORECASE):
            in_tds_section = True
        
        # Detect end of TDS section
        if re.search(r'PART[- ]?II\b', line, re.IGNORECASE):
            in_tds_section = False
        
        # COMPREHENSIVE REGEX PATTERN for ALL TDS sections
        # Matches: 192, 192A, 193, 194, 194A through 194S, 195, 196A-196DA, 206CA-206CQ, etc.
        section_pattern = r'^(\d+)\s+(' \
                         r'192A?|193|194[A-Z]*(?:\([a-z]\))?|1941?\([ab]\)|' \
                         r'195|196[A-Z]*|' \
                         r'206C[A-Z]|' \
                         r')\s+'
        
        section_match = re.match(section_pattern, line, re.IGNORECASE)
        
        if section_match and in_tds_section:
            section_raw = section_match.group(2)
            section = normalize_section(section_raw)
            
            # Extract all amounts from the line (including potential negatives)
            amounts = re.findall(r'(-?[\d,]+\.\d{2})', line)
            
            if len(amounts) >= 3:
                try:
                    # Last 3 amounts are: Amount Paid/Credited, Tax Deducted, TDS Deposited
                    receipt_amount = float(amounts[-3].replace(',', ''))
                    tds_amount = float(amounts[-1].replace(',', ''))
                    
                    # RULE 1: Ignore negative figures
                    if receipt_amount < 0 or tds_amount < 0:
                        i += 1
                        continue
                    
                    # Update global section summary
                    if section not in section_summary:
                        section_summary[section] = {
                            'total_receipts': 0,
                            'total_tds': 0,
                            'transaction_count': 0
                        }
                    
                    section_summary[section]['total_receipts'] += receipt_amount
                    section_summary[section]['total_tds'] += tds_amount
                    section_summary[section]['transaction_count'] += 1
                    
                except (ValueError, IndexError):
                    pass
        
        i += 1
    
    return section_summary

# Function to create Excel with ONLY section-wise summary
def create_excel_report(section_summary):
    """Create Excel file with ONLY Section-wise Summary"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # ONLY TABLE: SECTION-WISE SUMMARY
        section_data = []
        for idx, (section, data) in enumerate(sorted(section_summary.items()), 1):
            # Get description from mapping
            description = SECTION_DESCRIPTIONS.get(section, 'Description not available')
            
            section_data.append({
                'Sr. No.': idx,
                'TDS Section': section,
                'Description': description,
                'Total Receipts': data['total_receipts'],
                'Total TDS Deposited': data['total_tds'],
                'Transaction Count': data['transaction_count']
            })
        
        df_section = pd.DataFrame(section_data)
        df_section.to_excel(writer, sheet_name='Section-wise Summary', index=False)
        
        # Format the sheet
        workbook = writer.book
        section_sheet = writer.sheets['Section-wise Summary']
        
        # Auto-adjust column widths
        for column in section_sheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 60)
            section_sheet.column_dimensions[column_letter].width = adjusted_width
    
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
                
                # Show extracted text preview
                with st.expander("🔍 View Extracted Text Preview"):
                    st.text(extracted_text[:3000] + "..." if len(extracted_text) > 3000 else extracted_text)
                
                # Parse Form 26AS - SECTION-WISE ONLY
                with st.spinner("🧮 Parsing TDS data (ignoring negative figures)..."):
                    section_summary = parse_form_26as_sectionwise(extracted_text)
                
                if section_summary:
                    st.success(f"✅ Found {len(section_summary)} TDS sections!")
                    
                    # Display Section-wise Summary
                    st.subheader("📊 Section-wise TDS Summary")
                    section_data = []
                    total_receipts = 0
                    total_tds = 0
                    total_transactions = 0
                    
                    for idx, (section, data) in enumerate(sorted(section_summary.items()), 1):
                        description = SECTION_DESCRIPTIONS.get(section, 'Description not available')
                        section_data.append({
                            'Sr. No.': idx,
                            'TDS Section': section,
                            'Description': description,
                            'Total Receipts': f"₹{data['total_receipts']:,.2f}",
                            'Total TDS Deposited': f"₹{data['total_tds']:,.2f}",
                            'Transaction Count': data['transaction_count']
                        })
                        total_receipts += data['total_receipts']
                        total_tds += data['total_tds']
                        total_transactions += data['transaction_count']
                    
                    df_section = pd.DataFrame(section_data)
                    st.dataframe(df_section, use_container_width=True)
                    
                    # Display totals
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Receipts", f"₹{total_receipts:,.2f}")
                    with col2:
                        st.metric("Total TDS Deposited", f"₹{total_tds:,.2f}")
                    with col3:
                        st.metric("Total Transactions", total_transactions)
                    
                    # Create and offer Excel download
                    excel_file = create_excel_report(section_summary)
                    st.download_button(
                        label="📥 Download Excel Report",
                        data=excel_file,
                        file_name="Form_26AS_Section_Summary.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.error("❌ Could not parse TDS data from the PDF. Please check if this is a valid Form 26AS PDF.")
            else:
                st.error("❌ Failed to extract text from PDF.")
        
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            st.exception(e)
        
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

# Footer
st.markdown("---")
st.markdown("**Supported Sections:** 192-196DA (All standard TDS sections)")
st.markdown("**Note:** Ensure Tesseract OCR and Poppler are installed:")
st.code("brew install tesseract poppler  # macOS", language="bash")
st.markdown("**Rules Applied:** ✅ Negative figures ignored | ✅ Section-wise summary only")
