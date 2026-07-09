import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="Survey Form OCR - Gemini AI", layout="wide")
st.title("📝 Survey Form Scanner - Gemini AI")
st.caption("Upload multiple forms. Lahat maiipon sa table bago i-sync.")

# Setup Gemini API
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Google Sheets setup
SHEET_ID = "1E6S7Bh4R-3LC4XYhIsTqS_9sIxN4WGfDtFXwihlVk84"

def get_gsheet_client():
    """Connect to Google Sheets using service account"""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client

def safe_generate_content(model_name, img, prompt):
    model = genai.GenerativeModel(model_name)
    response = model.generate_content([prompt, img])
    return response

def extract_survey_gemini(image):
    prompt = """
    Extract ONLY the following from this GCASH survey form. Return valid JSON array with 1 object.
    
    RULES:
    1. Extract "PANGALAN" from the top left
    2. Extract "MOBILE_NUMBER" from "CONTACT NUMBER" on top right  
    3. For all multiple choice questions, return ONLY the letter of the CIRCLED/SELECTED answer. If multiple circled, join with comma. If none circled, return "".
    4. Ignore questions with no circled answer.
    5. For Section E "SAGUTAN NATIN" handwritten answers, extract text if written. Use keys E1, E2, E3.
    
    Use these exact keys:
    PANGALAN, MOBILE_NUMBER
    A1_A, A1_B, A1_C, B1_A, B1_B, B1_C, C1_A, C1_B, C1_C, D1_A, D1_B, D1_C
    A2_A, A2_B, B2_A, B2_B, B2_C, C2_A, C2_B, C2_C, D2_A, D2_B, D2_C, E1, E2, E3
    
    Example: [{"PANGALAN": "KRSLYN BALSACAB", "MOBILE_NUMBER": "09468566343", "A1_A": "A", "B1_B": "B"}]
    
    Only return JSON, no other text.
    """
    try:
        response = safe_generate_content("gemini-2.5-flash", image, prompt)
    except:
        response = safe_generate_content("gemini-2.5-flash-lite", image, prompt)

    json_text = response.text.strip()
    if json_text.startswith("```json"):
        json_text = json_text.replace("```json", "").replace("```", "").strip()
    
    return json.loads(json_text)

# Initialize session state - ngayon list of dataframes na
if 'all_data' not in st.session_state:
    st.session_state.all_data = []

# Multiple file uploader
uploaded_files = st.file_uploader(
    "Upload Survey Form Photos", 
    type=['png', 'jpg', 'jpeg'], 
    accept_multiple_files=True,  # ← MULTIPLE FILES NA TO
    help="Piliin lahat ng pics na i-scan mo. Pwede mag-add ulit mamaya."
)

if uploaded_files:
    st.info(f"📁 {len(uploaded_files)} file(s) selected")
    
    col1, col2 = st.columns([1,3])
    with col1:
        if st.button("🔍 Run AI Scan All", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, uploaded_file in enumerate(uploaded_files):
                status_text.text(f'Scanning {idx+1}/{len(uploaded_files)}: {uploaded_file.name}')
                
                try:
                    image = Image.open(uploaded_file)
                    table_data = extract_survey_gemini(image)
                    
                    if table_data:
                        # Add timestamp at filename
                        for row in table_data:
                            row['TIMESTAMP'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            row['FILENAME'] = uploaded_file.name
                        
                        st.session_state.all_data.extend(table_data)
                        st.success(f"✅ {uploaded_file.name} - Scanned!")
                    else:
                        st.warning(f"⚠️ {uploaded_file.name} - Walang na-detect")
                        
                except Exception as e:
                    st.error(f"❌ {uploaded_file.name} - Error: {str(e)}")
                
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            status_text.text("Done!")
            st.rerun()
    
    with col2:
        if st.button("🗑️ Clear All Data", use_container_width=True):
            st.session_state.all_data = []
            st.rerun()

# Show combined table
if st.session_state.all_data:
    st.subheader(f"📋 All Scanned Data - {len(st.session_state.all_data)} forms")
    
    df = pd.DataFrame(st.session_state.all_data)
    
    # Reorder columns para mauna yung important
    priority_cols = ['TIMESTAMP', 'FILENAME', 'PANGALAN', 'MOBILE_NUMBER']
    other_cols = [col for col in df.columns if col not in priority_cols]
    df = df[priority_cols + other_cols]
    
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key="editor"
    )
    
    # Update session state
    st.session_state.all_data = edited_df.to_dict('records')
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download All CSV",
            csv,
            f"survey_data_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv",
            use_container_width=True
        )
    
    with col2:
        if st.button("🚀 Sync All to Google Sheets", use_container_width=True, type="primary"):
            try:
                with st.spinner(f'Syncing {len(st.session_state.all_data)} rows...'):
                    client = get_gsheet_client()
                    sheet = client.open_by_key(SHEET_ID).sheet1
                    
                    # Convert to list of lists
                    df_to_sync = pd.DataFrame(st.session_state.all_data)
                    rows = df_to_sync.values.tolist()
                    
                    # Add headers kung empty pa yung sheet
                    if len(sheet.get_all_values()) == 0:
                        sheet.append_row(df_to_sync.columns.tolist())
                    
                    sheet.append_rows(rows, value_input_option='USER_ENTERED')
                    st.success(f"✅ {len(rows)} rows synced sa Google Sheets!")
                    st.balloons()
                    
                    # Optional: Clear data after sync
                    if st.checkbox("Clear data after successful sync"):
                        st.session_state.all_data = []
                        st.rerun()
                    
            except Exception as e:
                st.error(f"Sync failed: {str(e)}")
                st.code(f"Error details: {repr(e)}")
else:
    st.info("👆 Upload multiple survey form photos to start")
    st.warning("⚠️ Encircles + Name + Mobile lang ang kukunin")
