import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="GCASH Survey Scanner DEBUG", layout="wide")
st.title("📝 GCASH Survey Form Scanner - DEBUG MODE")

# Setup Gemini API
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

SHEET_ID = "1E6S7Bh4R-3LC4XYhIsTqS_9sIxN4WGfDtFXwihlVk84"

HEADERS = [
    'PANGALAN', 'A1_A', 'A1_B', 'A1_C', 'B1_A', 'B1_B', 'B1_C', 'C1_A', 'C1_B', 'C1_C', 
    'D1_A', 'D1_B', 'D1_C', 'MOBILE_NUMBER', 'NEGOSYO', 'A2_A', 'A2_B', 'B2_A', 'B2_B', 
    'B2_C', 'C2_A', 'C2_B', 'C2_C', 'D2_A', 'D2_B', 'D2_C', 'E1', 'E2', 'E3'
]

def get_gsheet_client():
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
    Look at this survey form. 
    
    STEP 1: List ALL questions you see that have a CIRCLE around letter A, B, or C.
    Format: "Question X: Letter Y is circled"
    
    STEP 2: After listing, create JSON with these keys:
    PANGALAN, MOBILE_NUMBER, NEGOSYO, A1_A, A1_B, A1_C, B1_A, B1_B, B1_C, C1_A, C1_B, C1_C, D1_A, D1_B, D1_C, A2_A, A2_B, B2_A, B2_B, B2_C, C2_A, C2_B, C2_C, D2_A, D2_B, D2_C, E1, E2, E3
    
    Put the circled letter in each key. If no circle, use "".
    
    Return your answer in 2 parts:
    PART1: The list of circled answers
    PART2: The JSON array
    """
    try:
        response = safe_generate_content("gemini-2.5-flash", image, prompt)
    except:
        response = safe_generate_content("gemini-2.5-flash-lite", image, prompt)

    return response.text

if 'df' not in st.session_state:
    st.session_state.df = None
if 'raw_output' not in st.session_state:
    st.session_state.raw_output = ""

uploaded_file = st.file_uploader("Upload Survey Form Photo", type=['png', 'jpg', 'jpeg'])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Ready to scan", use_column_width=True)
    
    if st.button("🔍 Run AI Scan", type="primary"):
        with st.spinner('Gemini AI is reading...'):
            try:
                raw_text = extract_survey_gemini(image)
                st.session_state.raw_output = raw_text
                
                # Try to extract JSON from response
                if "PART2:" in raw_text:
                    json_part = raw_text.split("PART2:")[1].strip()
                else:
                    json_part = raw_text
                
                if json_part.startswith("```json"):
                    json_part = json_part.replace("```json", "").replace("```", "").strip()
                elif json_part.startswith("```"):
                    json_part = json_part.replace("```", "").strip()
                
                table_data = json.loads(json_part)
                st.session_state.df = pd.DataFrame(table_data)
                st.success("✅ Scan done! Check raw output below.")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.code(raw_text)

# Show raw output para makita natin ano nakikita ni Gemini
if st.session_state.raw_output:
    st.subheader("🔍 RAW OUTPUT FROM GEMINI")
    st.code(st.session_state.raw_output, language="text")
    st.divider()

# Show editor
if st.session_state.df is not None:
    st.subheader("📋 Verify Data")
    df = st.session_state.df
    
    for header in HEADERS:
        if header not in df.columns:
            df[header] = ""
    
    df = df[HEADERS]
    
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="editor")
    st.session_state.df = edited_df
    
    col1, col2 = st.columns(2)
    with col1:
        csv = st.session_state.df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, "survey_data.csv", "text/csv", use_container_width=True)
    
    with col2:
        if st.button("🚀 Sync to Google Sheets", use_container_width=True):
            try:
                with st.spinner('Syncing...'):
                    client = get_gsheet_client()
                    sheet = client.open_by_key(SHEET_ID).sheet1
                    if len(sheet.get_all_values()) == 0:
                        sheet.append_row(HEADERS)
                    rows = st.session_state.df.values.tolist()
                    sheet.append_rows(rows, value_input_option='USER_ENTERED')
                    st.success(f"✅ Synced!")
                    st.balloons()
            except Exception as e:
                st.error(f"Sync failed: {str(e)}")
