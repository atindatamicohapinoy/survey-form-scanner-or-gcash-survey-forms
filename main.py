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
st.caption("Upload forms. Encircles + Name + Mobile + Negosyo lang ang kukunin.")

# Setup Gemini API
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Google Sheets setup - UPDATED SHEET_ID
SHEET_ID = "1E6S7Bh4R-3LC4XYhIsTqS_9sIxN4WGfDtFXwihlVk84"

# HEADERS - INAYOS NA SEQUENCE: D1 → CONTACT_NUMBER → NEGOSYO → A2
HEADERS = [
    'PANGALAN',
    # BAGO MAGSIMULA - Page 1 Left
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
    # NILIPAT DITO - CONTACT_NUMBER at NEGOSYO after D1
    'MOBILE_NUMBER', 'NEGOSYO',
    # SAGUTAN NATIN - Page 2 Right
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
    Extract ONLY the CIRCLED/SELECTED answers from this GCASH survey form. Return valid JSON array with 1 object.
    
    CRITICAL RULES:
    1. Look for CIRCLES, CHECK MARKS, or SHADED options. These are the selected answers.
    2. Extract "PANGALAN" from handwritten text at top left
    3. Extract "MOBILE_NUMBER" from "CONTACT NUMBER" field at top right
    4. Extract "NEGOSYO" from "NEGOSYO" field below CONTACT NUMBER. If blank, return ""
    5. For ALL multiple choice: return ONLY the letter A, B, or C that is CIRCLED/SELECTED. If multiple circled, join with comma like "A,B". If none circled, return "".
    6. For Section E handwritten: extract the handwritten text. Use keys E1, E2, E3.
    
    Map the answers to these exact keys:
    PANGALAN, MOBILE_NUMBER, NEGOSYO,
    A1_A, A1_B, A1_C, B1_A, B1_B, B1_C, C1_A, C1_B, C1_C, D1_A, D1_B, D1_C,
    A2_A, A2_B, B2_A, B2_B, B2_C, C2_A, C2_B, C2_C, D2_A, D2_B, D2_C, E1, E2, E3
    
    Example: [{"PANGALAN": "LINDA MANZANO DE OCAMPO", "MOBILE_NUMBER": "09468566242", "NEGOSYO": "", "A1_A": "A", "A1_B": "B", "A1_C": "B"}]
    
    Return ONLY valid JSON array with 1 object. No explanation, no markdown, just JSON.
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
    
    return json.loads(json_text)

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = None

uploaded_file = st.file_uploader("Upload Survey Form Photo", type=['png', 'jpg', 'jpeg'])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Ready to scan", use_column_width=True)
    
    if st.button("🔍 Run AI Scan", type="primary"):
        with st.spinner('Gemini AI is reading encircled answers... ~3-5 seconds'):
            try:
                table_data = extract_survey_gemini(image)
                
                if table_data:
                    df = pd.DataFrame(table_data)
                    
                    # Ensure all columns exist at naka-align sa HEADERS
                    for header in HEADERS:
                        if header not in df.columns:
                            df[header] = ""
                    
                    df = df[HEADERS] # Reorder para tugma sa Sheet
                    st.session_state.df = df
                    st.success(f"✅ Extracted encircled answers!")
                else:
                    st.warning("Walang na-detect na data. Try mo mas malinaw na picture.")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Show editor + buttons kung may data na
if st.session_state.df is not None:
    st.subheader("📋 Verify Data - Edit mo kung may mali")
    st.caption("Encircles + Name + Mobile + Negosyo lang ang kukunin")
    
    edited_df = st.data_editor(
        st.session_state.df,
        num_rows="dynamic",
        use_container_width=True,
        key="editor",
        height=400
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
                    
                    # Add headers kung empty pa yung sheet
                    if len(sheet.get_all_values()) == 0:
                        sheet.append_row(HEADERS)
                    
                    rows = st.session_state.df.values.tolist()
                    sheet.append_rows(rows, value_input_option='USER_ENTERED')
                    st.success(f"✅ {len(rows)} rows synced sa Google Sheets!")
                    st.balloons()
                    
            except Exception as e:
                st.error(f"Sync failed: {str(e)}")
                st.code(f"Error details: {repr(e)}")
                st.info("Check: 1. Naka-share ba sheet sa service account? 2. Tama ba secrets?")
else:
    st.info("👆 Upload a survey form photo to start")
    st.warning("⚠ Dapat malinaw yung CIRCLES sa A/B/C options para ma-detect")
