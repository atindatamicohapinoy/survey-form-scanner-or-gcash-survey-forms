import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Survey Form OCR - Gemini AI", layout="wide")
st.title("📝 Survey Form Scanner - Gemini AI")

# Setup Gemini API
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Google Sheets setup - UPDATED SHEET_ID
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
    Extract data from this survey form into a JSON list.
    
    For page 1 "BAGO MAGSIMULA" section and page 2 "SAGUTAN NATIN" section:
    1. Get "Pangalan" at the top if filled out
    2. For each question, return the letter of the selected/checked answer. If multiple answers selected, join with comma. If none, return "".
    3. For "SAGUTAN NATIN" questions with handwritten answers, extract the handwritten text.
    
    Return keys like: "PANGALAN", "1A", "1B", "1C", "2A", "2B", "2C", "2D", "2E", etc. 
    For handwritten parts in section 2, use "2E_1", "2E_2", "2E_3" for the 3 questions.
    
    Only return valid JSON array with 1 object, no other text.
    Example: [{"PANGALAN": "Elaine Y. Legaspi", "1A": "A", "1B": "B", "1C": "C", "2A": "A,B", "2E_1": "hindi magbibigay ng personal info"}]
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
    
    if st.button("🔍 Run AI Scan", type="primary"):
        with st.spinner('Gemini AI is reading... ~3-5 seconds'):
            try:
                table_data = extract_survey_gemini(image)
                
                if table_data:
                    st.success(f"✅ Extracted survey data!")
                    st.session_state.df = pd.DataFrame(table_data)
                else:
                    st.warning("Walang na-detect na data. Try mo mas malinaw na picture.")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Show editor + buttons kung may data na
if st.session_state.df is not None:
    st.subheader("📋 Verify Data - Edit mo kung may mali")
    edited_df = st.data_editor(
        st.session_state.df,
        num_rows="dynamic",
        use_container_width=True,
        key="editor"
    )
    # Update session state with edits
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
        if st.button("🚀 Sync All to Google Sheets", use_container_width=True):
            try:
                with st.spinner('Syncing to Google Sheets...'):
                    client = get_gsheet_client()
                    sheet = client.open_by_key(SHEET_ID).sheet1
                    
                    rows = st.session_state.df.values.tolist()
                    
                    # Add headers kung empty pa yung sheet
                    if len(sheet.get_all_values()) == 0:
                        sheet.append_row(st.session_state.df.columns.tolist())
                    
                    sheet.append_rows(rows, value_input_option='USER_ENTERED')
                    st.success(f"✅ {len(rows)} rows synced sa Google Sheets!")
                    st.balloons()
                    
            except Exception as e:
                st.error(f"Sync failed: {str(e)}")
                st.code(f"Error details: {repr(e)}")
                st.info("Check: 1. Naka-share ba sheet sa service account? 2. Tama ba secrets?")
else:
    st.info("👆 Upload a survey form photo to start")
    st.warning("⚠ REVIEW and EDIT kung may MALI")
