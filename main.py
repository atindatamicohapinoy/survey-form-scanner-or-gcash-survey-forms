import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="GCASH Survey Scanner", layout="wide")
st.title("📝 GCASH Survey Form Scanner")
st.caption("Encircles + Name + Mobile + Negosyo lang. Blank pag walang bilog.")

# Setup Gemini API
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Google Sheets setup
SHEET_ID = "1E6S7Bh4R-3LC4XYhIsTqS_9sIxN4WGfDtFXwihlVk84"

# HEADERS - D1 → MOBILE_NUMBER → NEGOSYO → A2 ang sequence
HEADERS = [
    'PANGALAN',
    'A1_A. Anong pakiramdam mo kapag pinag-uusapan ang pera at budget?',
    'A1_B. Paano mo hinahati ang pera mo kapag may kita ka?',
    'A1_C. Anong ginagawa mo kapag may sobra sa kita mo?',
    'B1_A. Ano ang ginagawa mo sa pera mo?',
    'B1_B. Saan mo nilalagay ang ipon mo?',
    'B1_C. Ano ang gusto mong pag-ipunan?',
    'C1_A. Ano ang naiisip mo kapag sinabing utang?',
    'C1_B. Bakit ka umuutang?',
    'C1_C. Anong ginagawa mo para mabayaran ang utang?',
    'D1_A. Ano ang gagawin mo kapag may text na nagsasabing Nanalo ka ng P50,000?',
    'D1_B. Paano mo pinu-protektahan ang password mo?',
    'D1_C. Ano ang pwede mong gawin para makaiwas sa scam?',
    'MOBILE_NUMBER',
    'NEGOSYO',
    'A2_A. Anong pakiramdam mo ngayon kapag pinag-uusapan ang pera at budget?',
    'A2_B. Kailan mo sisimulan ang pag-badyet?',
    'B2_A. Ano ang plano mong gawin sa pera mo ngayon?',
    'B2_B. Saan mo gustong ilagay ang ipon mo?',
    'B2_C. Ano ang pinag-iipunan mo ngayon?',
    'C2_A. Ano ang masasabi mo ngayon tungkol sa utang?',
    'C2_B. Paano mo babayaran ang utang mo?',
    'C2_C. Ano ang gagawin mo para umiwas sa mabigat na utang?',
    'D2_A. Ano ang gagawin mo kapag may text tungkol sa investment na kikita ka ng 50% kada buwan?',
    'D2_B. Paano ka mag-iingat sa online shopping?',
    'D2_C. Ano ang gagawin mo kung nabiktima ka ng scam?',
    'E1. Ano ang gagawin mong paraan para hindi maghalo ang pera ng pamilya at pera ng negosyo?',
    'E2. Bago mangutang para sa negosyo, ano ang unang dapat mong isipin para masiguradong kaya mo itong bayaran?',
    'E3. Ano ang red flag o babala para masabing ang isang transaksyon ay isang scam at paano ito maiiwasan?'
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
    Analyze this GCASH survey form image. This form has 24 multiple choice questions + 3 handwritten.
    
    CRITICAL INSTRUCTION: ONLY return a letter if you SEE a CLEAR CIRCLE around A, B, or C. 
    If you DO NOT see any circle on a question, you MUST return empty string "" for that question.
    DO NOT GUESS. DO NOT INVENT. Empty string if no visible circle.
    
    Extract to JSON with these exact keys:
    
    PANGALAN: handwritten name at top left
    MOBILE_NUMBER: from CONTACT NUMBER field at top right
    NEGOSYO: from NEGOSYO field. If blank, return ""
    
    For each question below, check if A, B, or C has a VISIBLE CIRCLE:
    
    A1_A: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    A1_B: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    A1_C: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    B1_A: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    B1_B: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    B1_C: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    C1_A: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    C1_B: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    C1_C: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    D1_A: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    D1_B: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    D1_C: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    A2_A: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    A2_B: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    B2_A: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    B2_B: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    B2_C: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    C2_A: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    C2_B: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    C2_C: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    D2_A: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    D2_B: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    D2_C: Is there a circle around A, B, or C? If yes, which letter? If no circle, return ""
    E1: Handwritten text. If blank, return ""
    E2: Handwritten text. If blank, return ""
    E3: Handwritten text. If blank, return ""
    
    FINAL RULE: If you are not 100% sure you see a circle, return "". Never guess.
    
    Return ONLY valid JSON object. No markdown, no explanation.
    
    Example: {"PANGALAN": "LINDA MANZANO DE OCAMPO", "MOBILE_NUMBER": "09468566342", "NEGOSYO": "", "A1_A": "A", "A1_B": "", "A1_C": "B"}
    """
    try:
        response = safe_generate_content("gemini-2.5-flash", image, prompt)
    except:
        response = safe_generate_content("gemini-2.5-flash-lite", image, prompt)

    json_text = response.text.strip()
    if json_text.startswith("```json"):
        json_text = json_text.replace("```json", "").replace("```", "").strip()
    elif json_text.startswith("```"):
        json_text = json_text.replace("```", "").strip()
    
    return json.loads(json_text), response.text

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = None
if 'raw_output' not in st.session_state:
    st.session_state.raw_output = ""

uploaded_file = st.file_uploader("Upload Survey Form Photo", type=['png', 'jpg', 'jpeg'])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Ready to scan", use_column_width=True)
    
    if st.button("🔍 Run AI Scan", type="primary"):
        with st.spinner('Reading encircled answers... DO NOT GUESS mode'):
            try:
                table_data, raw_text = extract_survey_gemini(image)
                st.session_state.raw_output = raw_text
                
                if table_data:
                    df = pd.DataFrame([table_data])
                    
                    # Ensure all columns exist
                    for header in HEADERS:
                        if header not in df.columns:
                            df[header] = ""
                    
                    df = df[HEADERS]
                    st.session_state.df = df
                    st.success("✅ Scan complete! Blank = walang bilog na nakita")
                else:
                    st.warning("Walang na-detect na data.")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                if st.session_state.raw_output:
                    st.code(st.session_state.raw_output)

# Show raw output para ma-verify
if st.session_state.raw_output:
    with st.expander("🔍 RAW GEMINI OUTPUT - Check mo kung tama"):
        st.code(st.session_state.raw_output, language="json")

# Show editor
if st.session_state.df is not None:
    st.subheader("📋 Verify Data - Edit mo kung may mali")
    st.caption("⚠️ Blank = Walang bilog na nakita si AI. Wag mag-assume.")
    
    edited_df = st.data_editor(
        st.session_state.df,
        num_rows="dynamic",
        use_container_width=True,
        key="editor",
        height=500
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
                    
                    if len(sheet.get_all_values()) == 0:
                        sheet.append_row(HEADERS)
                    
                    rows = st.session_state.df.values.tolist()
                    sheet.append_rows(rows, value_input_option='USER_ENTERED')
                    st.success(f"✅ {len(rows)} rows synced!")
                    st.balloons()
                    
            except Exception as e:
                st.error(f"Sync failed: {str(e)}")
                st.code(f"Error details: {repr(e)}")
else:
    st.info("👆 Upload a survey form photo to start")
    st.warning("⚠️ Malinaw dapat ang BILOG. Pag walang bilog, blank ang lalabas.")
