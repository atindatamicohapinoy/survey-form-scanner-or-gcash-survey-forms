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
    You are an expert OCR for GCASH survey forms. Extract ONLY the CIRCLED answers.
    
    FORM LAYOUT:
    LEFT PAGE "BAGO MAGSIMULA" has questions A1 to D1.
    RIGHT PAGE "SAGUTAN NATIN" has CONTACT NUMBER, NEGOSYO, then questions A2 to E3.
    
    EXTRACTION RULES:
    1. Find PANGALAN at top left of page 1
    2. Find MOBILE_NUMBER at top right of page 2 under "CONTACT NUMBER"
    3. Find NEGOSYO below MOBILE_NUMBER. If blank return ""
    4. For each multiple choice question below, find which letter A, B, or C has a CIRCLE, CHECK, or SHADE around it. Return ONLY that letter.
    
    PAGE 1 QUESTIONS - Map to these keys:
    "Anong pakiramdam mo kapag pinag-uusapan ang pera at budget?" = A1_A
    "Paano mo hinahati ang pera mo kapag may kita ka?" = A1_B
    "Anong ginagawa mo kapag may sobra sa kita mo?" = A1_C
    "Ano ang ginagawa mo sa pera mo?" = B1_A
    "Saan mo nilalagay ang ipon mo?" = B1_B
    "Ano ang gusto mong pag-ipunan?" = B1_C
    "Ano ang naiisip mo kapag sinabing utang?" = C1_A
    "Bakit ka umuutang?" = C1_B
    "Anong ginagawa mo para mabayaran ang utang?" = C1_C
    "Ano ang gagawin mo kapag may text na nagsasabing Nanalo ka ng P50,000?" = D1_A
    "Paano mo pinu-protektahan ang password mo?" = D1_B
    "Ano ang pwede mong gawin para makaiwas sa scam?" = D1_C
    
    PAGE 2 QUESTIONS - Map to these keys:
    "Anong pakiramdam mo ngayon kapag pinag-uusapan ang pera at budget?" = A2_A
    "Kailan mo sisimulan ang pag-badyet?" = A2_B
    "Ano ang plano mong gawin sa pera mo ngayon?" = B2_A
    "Saan mo gustong ilagay ang ipon mo?" = B2_B
    "Ano ang pinag-iipunan mo ngayon?" = B2_C
    "Ano ang masasabi mo ngayon tungkol sa utang?" = C2_A
    "Paano mo babayaran ang utang mo?" = C2_B
    "Ano ang gagawin mo para umiwas sa mabigat na utang?" = C2_C
    "Ano ang gagawin mo kapag may text tungkol sa investment na kikita ka ng 50% kada buwan?" = D2_A
    "Paano ka mag-iingat sa online shopping?" = D2_B
    "Ano ang gagawin mo kung nabiktima ka ng scam?" = D2_C
    
    SECTION E - Extract handwritten text:
    E1, E2, E3
    
    CRITICAL:
    - If NO circle on a question, return "" for that key
    - If multiple circles on one question, return "A,B" 
    - Look carefully at EVERY question
    
    Return ONLY valid JSON array with 1 object. Example:
    [{"PANGALAN": "LINDA MANZANO DE OCAMPO", "MOBILE_NUMBER": "09468566242", "NEGOSYO": "", "A1_A": "A", "A1_B": "B", "A1_C": "B", "D1_C": "C", "A2_A": "A"}]
    
    No markdown, no explanation, just JSON.
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
if 'all_data' not in st.session_state:
    st.session_state.all_data = []

# Multiple file uploader
uploaded_files = st.file_uploader(
    "Upload Survey Form Photos", 
    type=['png', 'jpg', 'jpeg'], 
    accept_multiple_files=True,
    help="Dapat malinaw yung mga BILOG sa A, B, C options"
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
    
    # Ensure all columns exist
    for header in HEADERS:
        if header not in df.columns:
            df[header] = ""
    
    df = df[HEADERS]
    
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key="editor",
        height=500
    )
    
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
                    
                    # Auto-add headers kung empty
                    existing = sheet.get_all_values()
                    if len(existing) == 0:
                        sheet.append_row(HEADERS)
                    
                    df_to_sync = pd.DataFrame(st.session_state.all_data)[HEADERS]
                    rows = df_to_sync.values.tolist()
                    sheet.append_rows(rows, value_input_option='USER_ENTERED')
                    
                    st.success(f"✅ {len(rows)} rows synced sa Google Sheets!")
                    st.balloons()
                    
                    if st.checkbox("Clear data after successful sync"):
                        st.session_state.all_data = []
                        st.rerun()
                    
            except Exception as e:
                st.error(f"Sync failed: {str(e)}")
                st.code(f"Error details: {repr(e)}")
else:
    st.info("👆 Upload survey form photos to start")
    st.warning("⚠️ Siguraduhing malinaw ang BILOG sa A, B, C para ma-detect")
