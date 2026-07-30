import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
import json
import pandas as pd
from PIL import Image
import fitz # PyMuPDF - for PDF handling
import io

# Page Configuration
st.set_page_config(page_title="GCash Survey", page_icon="📊", layout="wide")

st.title("GCash Survey")
st.write("Upload up to 5 survey photos. Extracts ONLY encircled/checked letters.")

SPREADSHEET_ID = "1E6S7Bh4R-3LC4XYhIsTqS_9sIxN4WGfDtFXwihlVk84"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"

@st.cache_resource
def init_connections():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        credentials_dict = dict(st.secrets["gsheets_credentials"])
        credentials_dict["private_key"] = credentials_dict["private_key"].replace(r"\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).get_worksheet(0)
        return sheet
    except Exception as e:
        st.error(f"Configuration/Secrets Error: {e}")
        st.info(f"Make sure you shared the sheet {SHEET_URL} with your service account email as Editor.")
        st.stop()

sheet = init_connections()
st.success(f"Connected to: [{SHEET_URL}]({SHEET_URL}) - Tab: {sheet.title} (gid=0)")

def pdf_to_images(pdf_bytes):
    """Convert PDF bytes to list of PIL Images"""
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=200) # higher DPI for clearer scan
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        images.append(img)
    return images

# --- UPDATED UPLOADER ---
uploaded_files = st.file_uploader(
    "Choose up to 5 survey form images...",
    type=["jpg", "jpeg", "png", "pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    if len(uploaded_files) > 5:
        st.warning("Hanggang 5 files lang. Yung unang 5 lang ang i-process ko.")
        uploaded_files = uploaded_files[:5]

    all_pil_images = []
    for uploaded_file in uploaded_files:
        if uploaded_file.type == "application/pdf":
            st.info(f"📄 Reading PDF: {uploaded_file.name}")
            pdf_images = pdf_to_images(uploaded_file.getvalue())
            all_pil_images.extend(pdf_images)
        else:
            all_pil_images.append(Image.open(uploaded_file))

    # Preview
    st.write(f"**Total pages/images to scan: {len(all_pil_images)}**")
    cols = st.columns(3)
    for i, img in enumerate(all_pil_images):
        with cols[i % 3]:
            st.image(img, caption=f"Image {i+1}", use_container_width=True)

    if st.button(f"🚀 Scan & Sync {len(all_pil_images)} Image(s) to Sheet", type="primary"):
        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = (
            "Analyze the survey image and extract data matching this specific horizontal order. "
            "Extracts ONLY encircled/checked letters. "
            "For multiple-choice questions, provide only the selected letter (A, B, or C). "
            "For handwritten questions under Section E, extract the short text written.\n\n"
            "Return your response strictly as a valid JSON object with the following keys. "
            "Do not include markdown tags or ```json wrappers.\n\n"
            "{\n"
            " \"NAME\": \"Full name from the form\",\n"
            " \"PAGE_1_A_BUDGET_1\": \"Selected letter\",\n"
            " \"PAGE_1_A_BUDGET_2\": \"Selected letter\",\n"
            " \"PAGE_1_A_BUDGET_3\": \"Selected letter\",\n"
            " \"PAGE_1_B_SAVINGS_1\": \"Selected letter\",\n"
            " \"PAGE_1_B_SAVINGS_2\": \"Selected letter\",\n"
            " \"PAGE_1_B_SAVINGS_3\": \"Selected letter\",\n"
            " \"PAGE_1_C_UTANG_1\": \"Selected letter\",\n"
            " \"PAGE_1_C_UTANG_2\": \"Selected letter\",\n"
            " \"PAGE_1_C_UTANG_3\": \"Selected letter\",\n"
            " \"PAGE_1_D_SCAM_1\": \"Selected letter\",\n"
            " \"PAGE_1_D_SCAM_2\": \"Selected letter\",\n"
            " \"PAGE_1_D_SCAM_3\": \"Selected letter\",\n"
            " \"PAGE_2_A_BUDGET_1\": \"Selected letter\",\n"
            " \"PAGE_2_A_BUDGET_2\": \"Selected letter\",\n"
            " \"PAGE_2_B_SAVINGS_1\": \"Selected letter\",\n"
            " \"PAGE_2_B_SAVINGS_2\": \"Selected letter\",\n"
            " \"PAGE_2_B_SAVINGS_3\": \"Selected letter\",\n"
            " \"PAGE_2_C_UTANG_1\": \"Selected letter\",\n"
            " \"PAGE_2_C_UTANG_2\": \"Selected letter\",\n"
            " \"PAGE_2_C_UTANG_3\": \"Selected letter\",\n"
            " \"PAGE_2_D_SCAM_1\": \"Selected letter\",\n"
            " \"PAGE_2_D_SCAM_2\": \"Selected letter\",\n"
            " \"PAGE_2_D_SCAM_3\": \"Selected letter\",\n"
            " \"PAGE_2_E_1\": \"Extracted text answer\",\n"
            " \"PAGE_2_E_2\": \"Extracted text answer\",\n"
            " \"PAGE_2_E_3\": \"Extracted text answer\"\n"
            "}"
        )

        progress = st.progress(0)
        for idx, image in enumerate(all_pil_images):
            with st.spinner(f"Scanning image {idx+1}/{len(all_pil_images)}..."):
                try:
                    response = model.generate_content([prompt, image])
                    raw_text = response.text.strip()
                    if raw_text.startswith("```"):
                        raw_text = raw_text.split("\n", 1)[1]
                    if raw_text.endswith("```"):
                        raw_text = raw_text.rsplit("\n", 1)[0]
                    raw_text = raw_text.strip("`").strip()
                    data = json.loads(raw_text)

                    row_values = [
                        data.get("NAME", ""),
                        data.get("PAGE_1_A_BUDGET_1", ""), data.get("PAGE_1_A_BUDGET_2", ""), data.get("PAGE_1_A_BUDGET_3", ""),
                        data.get("PAGE_1_B_SAVINGS_1", ""), data.get("PAGE_1_B_SAVINGS_2", ""), data.get("PAGE_1_B_SAVINGS_3", ""),
                        data.get("PAGE_1_C_UTANG_1", ""), data.get("PAGE_1_C_UTANG_2", ""), data.get("PAGE_1_C_UTANG_3", ""),
                        data.get("PAGE_1_D_SCAM_1", ""), data.get("PAGE_1_D_SCAM_2", ""), data.get("PAGE_1_D_SCAM_3", ""),
                        data.get("PAGE_2_A_BUDGET_1", ""), data.get("PAGE_2_A_BUDGET_2", ""),
                        data.get("PAGE_2_B_SAVINGS_1", ""), data.get("PAGE_2_B_SAVINGS_2", ""), data.get("PAGE_2_B_SAVINGS_3", ""),
                        data.get("PAGE_2_C_UTANG_1", ""), data.get("PAGE_2_C_UTANG_2", ""), data.get("PAGE_2_C_UTANG_3", ""),
                        data.get("PAGE_2_D_SCAM_1", ""), data.get("PAGE_2_D_SCAM_2", ""), data.get("PAGE_2_D_SCAM_3", ""),
                        data.get("PAGE_2_E_1", ""), data.get("PAGE_2_E_2", ""), data.get("PAGE_2_E_3", "")
                    ]
                    sheet.append_row(row_values)
                    st.success(f"✅ {data.get('NAME','No Name')} - na-sync na!")
                    st.dataframe(pd.DataFrame([row_values]))

                except Exception as e:
                    st.error(f"Error on image {idx+1}: {e}")
            progress.progress((idx+1)/len(all_pil_images))
