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
st.title("📝 GCASH Survey Form Scanner - Vertical")
st.caption("Questions sa Column A, Answers sa Column B")

# Setup Gemini API
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Google Sheets setup
SHEET_ID = "1E6S7Bh4R-3LC4XYhIsTqS_9sIxN4WGfDtFXwihlVk84"

# QUESTION LABELS - Eto yung lalabas sa Column A
QUESTIONS = [
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
    Look at this GCASH survey form. Answer each question below.
    
    For multiple choice A, B, C: Look for which letter has a CIRCLE around it. Return only A or B or C.
    If no circle, return blank.
    
    Answer these questions:
    1. PANGALAN: What is the name written at top left?
    2. A1_A: For "Anong pakiramdam mo kapag pinag-uusapan ang pera at budget?" which letter A/B/C is circled?
    3. A1_B: For "Paano mo hinahati ang pera mo kapag may kita ka?" which letter is circled?
    4. A1_C: For "Anong ginagawa mo kapag may sobra sa kita mo?" which letter is circled?
    5. B1_A: For "Ano ang ginagawa mo sa pera mo?" which letter is circled?
    6. B1_B: For "Saan mo nilalagay ang ipon mo?" which letter is circled?
    7. B1_C: For "Ano ang gusto mong pag-ipunan?" which letter is circled?
    8. C1_A: For "Ano ang naiisip mo kapag sinabing utang?" which letter is circled?
    9. C1_B: For "Bakit ka umuutang?" which letter is circled?
    10. C1_C: For "Anong ginagawa mo para mabayaran ang utang?" which letter is circled?
    11. D1_A: For "Ano ang gagawin mo kapag may text na nagsasabing Nanalo ka ng P50,000?" which letter is circled?
    12. D1_B: For "Paano mo pinu-protektahan ang password mo?" which letter is circled?
    13. D1_C: For "Ano ang pwede mong gawin para makaiwas sa scam?" which letter is circled?
    14. MOBILE_NUMBER: What is written in CONTACT NUMBER field?
    15. NEGOSYO: What is written in NEGOSYO field? If blank, return empty.
    16. A2_A: For "Anong pakiramdam mo ngayon kapag pinag-uusapan ang pera at budget?" which letter is circled?
    17. A2_B: For "Kailan mo sisimulan ang pag-badyet?" which letter is circled?
    18. B2_A: For "Ano ang plano mong gawin sa pera mo ngayon?" which letter is circled?
    19. B2_B: For "Saan mo gustong ilagay ang ipon mo?" which letter is circled?
    20. B2_C: For "Ano ang pinag-iipunan mo ngayon?" which letter is circled?
    21. C2_A: For "Ano ang masasabi mo ngayon tungkol sa utang?" which letter is circled?
    22. C2_B: For "Paano mo babayaran ang utang mo?" which letter is circled?
    23. C2_C: For "Ano ang gagawin mo para umiwas sa mabigat na utang?" which letter is circled?
    24. D2_A: For "Ano ang gagawin mo kapag may text tungkol sa investment na kikita ka ng 50% kada buwan?" which letter is circled?
    25. D2_B: For "Paano ka mag-iingat sa online shopping?" which letter is circled?
    26. D2_C: For "Ano ang gagawin mo kung nabiktima ka ng scam?" which letter is circled?
    27. E1: What is the handwritten answer for E1?
    28. E2: What is the handwritten answer for E2?
    29. E3: What is the handwritten answer for E3?
    
    Return ONLY valid JSON object with keys: PANGALAN, A1_A, A1_B, A1_C, B1_A, B1_B, B1_C, C1_A, C1_B, C1_C, D1_A, D1_B, D1_C, MOBILE_NUMBER, NEGOSYO, A2_A, A2_B, B2_A, B2_B, B2_C, C2_A, C2_B, C2_C, D2_A, D2_B, D2_C, E1, E2, E3
    
    Example: {"PANGALAN": "LINDA MANZANO DE OCAMPO", "A1_A": "A", "A1_B": "B", "MOBILE_NUMBER": "09468566342"}
    
    No markdown, just JSON.
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
if 'vertical_df' not in st.session_state:
    st.session_state.vertical_df = None
if 'raw_output' not in st.session_state:
    st.session_state.raw_output = ""

uploaded_file = st.file_uploader("Upload Survey Form Photo", type=['png', 'jpg', 'jpeg'])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Ready to scan", use_column_width=True)
    
    if st.button("🔍 Run AI Scan", type="primary"):
        with st.spinner('Reading encircled answers...'):
            try:
                table_data, raw_text = extract_survey_gemini(image)
                st.session_state.raw_output = raw_text
                
                if table_data:
                    # Convert to vertical format: Column A = Questions, Column B = Answers
                    answers = []
                    for q in QUESTIONS:
                        key = q.split('.')[0] if '.' in q else q
                        answers.append(table_data.get(key, ""))
                    
                    vertical_df = pd.DataFrame({
                        'QUESTION': QUESTIONS,
                        'ANSWER': answers
                    })
                    
                    st.session_state.vertical_df = vertical_df
                    st.success("✅ Extracted answers!")
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

# Show vertical table
if st.session_state.vertical_df is not None:
    st.subheader("📋 Verify Data - Vertical Format")
    st.caption("Column A = Questions, Column B = Answers")
    
    edited_df = st.data_editor(
        st.session_state.vertical_df,
        num_rows="dynamic",
        use_container_width=True,
        key="editor",
        height=600,
        column_config={
            "QUESTION": st.column_config.TextColumn("QUESTION", width="large"),
            "ANSWER": st.column_config.TextColumn("ANSWER", width="small"),
        }
    )
    st.session_state.vertical_df = edited_df
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = st.session_state.vertical_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download CSV",
            csv,
            "survey_data_vertical.csv",
            "text/csv",
            use_container_width=True
        )
    
    with col2:
        if st.button("🚀 Sync to Google Sheets", use_container_width=True):
            try:
                with st.spinner('Syncing vertical format to Google Sheets...'):
                    client = get_gsheet_client()
                    sheet = client.open_by_key(SHEET_ID).sheet1
                    
                    # Clear sheet first para fresh
                    sheet.clear()
                    
                    # Upload vertical data: Question sa Col A, Answer sa Col B
                    rows = st.session_state.vertical_df.values.tolist()
                    sheet.append_rows(rows, value_input_option='USER_ENTERED')
                    
                    st.success(f"✅ Synced {len(rows)} rows vertically!")
                    st.balloons()
                    
            except Exception as e:
                st.error(f"Sync failed: {str(e)}")
                st.code(f"Error details: {repr(e)}")
else:
    st.info("👆 Upload a survey form photo to start")
    st.warning("⚠️ Dapat malinaw ang BILOG sa A, B, C para ma-detect")
