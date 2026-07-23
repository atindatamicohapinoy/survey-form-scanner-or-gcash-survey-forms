import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
import json
import pandas as pd
from PIL import Image

# Page Configuration
st.set_page_config(page_title="GCash Survey", page_icon="📊", layout="wide")

st.title("GCash Survey")
st.write("Upload a survey photo to automatically append a single structured row matching your Google Sheet layout.")

# --- UPDATED: Changed to your requested link ---
# Link: https://docs.google.com/spreadsheets/d/1E6S7Bh4R-3LC4XYhIsTqS_9sIxN4WGfDtFXwihlVk84/edit?gid=0#gid=0
SPREADSHEET_ID = "1E6S7Bh4R-3LC4XYhIsTqS_9sIxN4WGfDtFXwihlVk84"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"

# Authenticate with Google Sheets & Gemini securely using Streamlit Secrets
@st.cache_resource
def init_connections():
    try:
        # 1. Setup Gemini API
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

        # 2. Extract the complete credentials dictionary
        credentials_dict = dict(st.secrets["gsheets_credentials"])

        # Repair escaped newline strings inside the private key
        credentials_dict["private_key"] = credentials_dict["private_key"].replace(r"\n", "\n")

        # Authenticate Scopes
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)

        # Open Google Sheet - gid=0 means first worksheet/tab
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).get_worksheet(0)
        return sheet
    except Exception as e:
        st.error(f"Configuration/Secrets Error: {e}")
        st.info(f"Make sure you shared the sheet {SHEET_URL} with your service account email as Editor.")
        st.stop()

# Initialize sheet connection
sheet = init_connections()

st.success(f"Connected to: [{SPREADSHEET_ID}]({SHEET_URL}) - Tab: {sheet.title} (gid=0)")

uploaded_file = st.file_uploader("Choose a survey form image...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Survey Form", use_container_width=True)

    if st.button("🚀 Scan & Sync to New Sheet", type="primary"):
        with st.spinner("AI is parsing the layout into a horizontal row..."):
            try:
                model = genai.GenerativeModel('gemini-2.5-flash')

                prompt = (
                    "Analyze the survey image and extract data matching this specific horizontal order. "
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

                response = model.generate_content([prompt, image])

                # JSON Cleaning
                raw_text = response.text.strip()
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("\n", 1)[1]
                if raw_text.endswith("```"):
                    raw_text = raw_text.rsplit("\n", 1)[0]
                raw_text = raw_text.strip("`").strip()

                data = json.loads(raw_text)

                # Strict 27-column mapping layout order matching your spreadsheet grid
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

                # Directly append values as a horizontal row
                sheet.append_row(row_values)

                st.success(f"🎉 Success! Row appended for: {data.get('NAME')} to sheet {SHEET_URL}")

                # Render UI Preview Table
                preview_df = pd.DataFrame([row_values])
                st.dataframe(preview_df)

            except Exception as e:
                st.error(f"Error parsing or writing row: {e}")
