import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="GCASH Survey Scanner", layout="wide")
st.title("📝 GCASH Survey Form Scanner")

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
    
    Use these exact keys for the JSON:
    
    PANGALAN
    MOBILE_NUMBER
    
    Page 1 - BAGO MAGSIMULA:
    A1_A, A1_B, A1_C
    B1_A, B1_B, B1_C  
    C1_A, C1_B, C1_C
    D1_A, D1_B, D1_C
    
    Page 2 - SAGUTAN NATIN:
    A2_A, A2_B
    B2_A, B2_B, B2_C
    C2_A, C2_B, C2_C
    D2_A, D2_B, D2_C
    E1, E2, E3
    
    Example output: [{"PANGALAN": "KRSLYN BALSACAB", "MOBILE_NUMBER": "09468566343", "A1_A": "A", "A1_B": "C", "A2_A": "C", "B2_A": "B"}]
    
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

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = None

uploaded_file = st.file_uploader("Upload Survey Form Photo", type=['png', 'jpg', 'jpeg'])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Ready to scan", use_column_width=True)
    
    if st.button("🔍 Scan Encircles Only", type="primary"):
        with st.spinner('Gemini AI is reading encircled answers... ~3-5 seconds'):
            try:
                table_data = extract_survey_gemini(image)
                
                if table_data:
                    st.success(f"✅ Extracted encircled answers!")
                    st.session_state.df = pd.DataFrame(table_data)
                else:
                    st.warning("Walang na-detect na encircled answers. Try mo mas malinaw na picture.")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Show editor + buttons kung may data na
if st.session_state.df is not None:
    st.subheader("📋 Verify Data - Encircles + Name + Mobile lang")
    st.caption("Edit mo kung may mali sa AI scan")
    
    edited_df = st.data_editor(
        st.session_state.df,
        num_rows="dynamic",
        use_container_width=True,
        key="editor"
    )
    st.session_state.df = edited_df
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = st.session_state.df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download CSV",
            csv,
            "survey_data.csv",
            "text/csv",
            use_container_width=True
        )
    
    with col2:
        if st.button("🚀 Sync to Google Sheets", use_container_width=True):
            try:
                with st.spinner('Syncing to Google Sheets...'):
                    client = get_gsheet_client()
                    sheet = client.open_by_key(SHEET_ID).sheet1
                    
                    rows = st.session_state.df.values.tolist()
                    
                    # Add headers kung empty pa yung sheet
                    if len(sheet.get_all_values()) == 0:
                        sheet.append_row(st.session_state.df.columns.tolist())
                    
                    sheet.append_rows(rows, value_input_option='USER_ENTERED')
                    st.success(f"✅ {len(rows)} rows synced!")
                    st.balloons()
                    
            except Exception as e:
                st.error(f"Sync failed: {str(e)}")
                st.code(f"Error details: {repr(e)}")
                st.info("Check: 1. Naka-share ba sheet sa service account? 2. Tama ba secrets?")
else:
    st.info("👆 Upload a survey form photo to start")
    st.warning("⚠️ Mag-scan lang ng ENcircled answers, Name, at Mobile Number")
