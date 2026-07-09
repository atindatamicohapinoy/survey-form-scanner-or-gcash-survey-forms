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
st.caption("Upload forms. Encircles + Name + Mobile + Negosyo lang ang kukunin.")

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
    Look at this GCASH survey form. It has 2 columns: LEFT is "BAGO MAGSIMULA", RIGHT is "SAGUTAN NATIN".
    
    Extract answers into JSON with these EXACT keys. Look for CIRCLED letters A, B, or C.
    
    LEFT COLUMN "BAGO MAGSIMULA":
    PANGALAN: from top left
    A1_A: "Anong pakiramdam mo kapag pinag-uusapan ang pera at budget?" - which letter A/B/C is circled?
    A1_B: "Paano mo hinahati ang pera mo kapag may kita ka?" - which letter is circled?
    A1_C: "Anong ginagawa mo kapag may sobra sa kita mo?" - which letter is circled?
    B1_A: "Ano ang ginagawa mo sa pera mo?" - which letter is circled?
    B1_B: "Saan mo nilalagay ang ipon mo?" - which letter is circled?
    B1_C: "Ano ang gusto mong pag-ipunan?" - which letter is circled?
    C1_A: "Ano ang naiisip mo kapag sinabing utang?" - which letter is circled?
    C1_B: "Bakit ka umuutang?" - which letter is circled?
    C1_C: "Anong ginagawa mo para mabayaran ang utang?" - which letter is circled?
    D1_A: "Ano ang gagawin mo kapag may text na nagsasabing Nanalo ka ng P50,000?" - which letter is circled?
    D1_B: "Paano mo pinu-protektahan ang password mo?" - which letter is circled?
    D1_C: "Ano ang pwede mong gawin para makaiwas sa scam?" - which letter is circled?
    
    RIGHT COLUMN "SAGUTAN NATIN":
    MOBILE_NUMBER: from "CONTACT NUMBER" field
    NEGOSYO: from "NEGOSYO" field, blank = ""
    A2_A: "Anong pakiramdam mo ngayon kapag pinag-uusapan ang pera at budget?" - which letter is circled?
    A2_B: "Kailan mo sisimulan ang pag-badyet?" - which letter is circled?
    B2_A: "Ano ang plano mong gawin sa pera mo ngayon?" - which letter is circled?
    B2_B: "Saan mo gustong ilagay ang ipon mo?" - which letter is circled?
    B2_C: "Ano ang pinag-iipunan mo ngayon?" - which letter is circled?
    C2_A: "Ano ang masasabi mo ngayon tungkol sa utang?" - which letter is circled?
    C2_B: "Paano mo babayaran ang utang mo?" - which letter is circled?
    C2_C: "Ano ang gagawin mo para umiwas sa mabigat na utang?" - which letter is circled?
    D2_A: "Ano ang gagawin mo kapag may text tungkol sa investment na kikita ka ng 50% kada buwan?" - which letter is circled?
    D2_B: "Paano ka mag-iingat sa online shopping?" - which letter is circled?
    D2_C: "Ano ang gagawin mo kung nabiktima ka ng scam?" - which letter is circled?
    E1: Handwritten answer
    E2: Handwritten answer 
    E3: Handwritten answer
    
    RULES:
    - For A/B/C questions: Return ONLY the letter A or B or C that is circled. If none circled, return ""
    - If multiple circled in one question, return "A,B"
    - Return ONLY valid JSON object, not array. No markdown.
    
    Example: {"PANGALAN": "LINDA MANZANO DE OCAMPO", "MOBILE_NUMBER": "09468566342", "NEGOSYO": "", "A1_A": "A", "A1_B": "B", "A1_C": "B"}
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
        with st.spinner('Gemini AI is reading encircled answers...'):
            try:
                table_data, raw_text = extract_survey_gemini(image)
                st.session_state.raw_output = raw_text
                
                if table_data:
                    # FIX: Wrap sa list para maging 1 row dataframe
                    df = pd.DataFrame([table_data])
                    
                    # Ensure all columns exist
                    for header in HEADERS:
                        if header not in df.columns:
                            df[header] = ""
                    
                    df = df[HEADERS]
                    st.session_state.df = df
                    st.success("✅ Extracted encircled answers!")
                else:
                    st.warning("Walang na-detect na data.")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                if st.session_state.raw_output:
                    st.code(st.session_state.raw_output)

# Show raw output para ma-debug
if st.session_state.raw_output:
    with st.expander("🔍 RAW OUTPUT FROM GEMINI - Click to see"):
        st.code(st.session_state.raw_output, language="text")

# Show editor
if st.session_state.df is not None:
    st.subheader("📋 Verify Data - Edit mo kung may mali")
    st.caption("Encircles + Name + Mobile + Negosyo lang ang kukunin")
    
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
    st.warning("⚠️ Dapat malinaw ang BILOG sa A, B, C para ma-detect")
