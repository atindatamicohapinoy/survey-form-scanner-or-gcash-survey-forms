import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
import json
import pandas as pd
from PIL import Image

st.set_page_config(page_title="GCash Survey - 5X Batch", page_icon="📊", layout="wide")
st.title("GCash Survey - Batch 5 Pics")
st.write("Upload up to 5 survey photos at once. Auto-detect bilog at i-append as rows sa Google Sheet.")

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
        st.error(f"Secrets Error: {e}")
        st.info(f"Share mo muna sheet {SHEET_URL} sa service account email as Editor.")
        st.stop()

sheet = init_connections()
st.success(f"Connected to: {sheet.title} | [{SPREADSHEET_ID}]({SHEET_URL})")

# --- BAGONG MULTI UPLOAD HANGGANG 5 ---
uploaded_files = st.file_uploader(
    "Choose up to 5 survey form images...",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if uploaded_files:
    if len(uploaded_files) > 5:
        st.warning("Hanggang 5 pics lang per batch para di ma-rate limit si Gemini. First 5 lang ipo-process.")
        uploaded_files = uploaded_files[:5]

    st.write(f"**{len(uploaded_files)} files selected:**")
    cols = st.columns(len(uploaded_files))
    for i, file in enumerate(uploaded_files):
        with cols[i]:
            st.image(Image.open(file), caption=file.name, use_container_width=True)

    if st.button(f"🚀 Scan & Sync {len(uploaded_files)} Pics to Sheet", type="primary"):
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = (
            "Analyze the survey image and extract data matching this specific horizontal order. "
            "For multiple-choice questions, provide ONLY the encircled/checked letter (A, B, or C). If no encircle, leave blank. "
            "For handwritten questions under Section E, extract the short text written.\n\n"
            "Return strictly as valid JSON object, no markdown:\n"
            "{\n"
            " \"NAME\": \"Full name or CONTACT NUMBER from the form\",\n"
            " \"PAGE_1_A_BUDGET_1\": \"A/B/C or blank\",\n"
            " \"PAGE_1_A_BUDGET_2\": \"\",\n"
            " \"PAGE_1_A_BUDGET_3\": \"\",\n"
            " \"PAGE_1_B_SAVINGS_1\": \"\",\n"
            " \"PAGE_1_B_SAVINGS_2\": \"\",\n"
            " \"PAGE_1_B_SAVINGS_3\": \"\",\n"
            " \"PAGE_1_C_UTANG_1\": \"\",\n"
            " \"PAGE_1_C_UTANG_2\": \"\",\n"
            " \"PAGE_1_C_UTANG_3\": \"\",\n"
            " \"PAGE_1_D_SCAM_1\": \"\",\n"
            " \"PAGE_1_D_SCAM_2\": \"\",\n"
            " \"PAGE_1_D_SCAM_3\": \"\",\n"
            " \"PAGE_2_A_BUDGET_1\": \"\",\n"
            " \"PAGE_2_A_BUDGET_2\": \"\",\n"
            " \"PAGE_2_B_SAVINGS_1\": \"\",\n"
            " \"PAGE_2_B_SAVINGS_2\": \"\",\n"
            " \"PAGE_2_B_SAVINGS_3\": \"\",\n"
            " \"PAGE_2_C_UTANG_1\": \"\",\n"
            " \"PAGE_2_C_UTANG_2\": \"\",\n"
            " \"PAGE_2_C_UTANG_3\": \"\",\n"
            " \"PAGE_2_D_SCAM_1\": \"\",\n"
            " \"PAGE_2_D_SCAM_2\": \"\",\n"
            " \"PAGE_2_D_SCAM_3\": \"\",\n"
            " \"PAGE_2_E_1\": \"text\",\n"
            " \"PAGE_2_E_2\": \"text\",\n"
            " \"PAGE_2_E_3\": \"text\"\n"
            "}"
        )

        all_rows = []
        progress = st.progress(0)
        status = st.empty()

        for idx, file in enumerate(uploaded_files):
            try:
                status.text(f"Scanning {idx+1}/{len(uploaded_files)}: {file.name}...")
                image = Image.open(file)
                response = model.generate_content([prompt, image])

                raw_text = response.text.strip()
                if "```" in raw_text:
                    raw_text = raw_text.split("```")[1].replace("json","").strip()
                data = json.loads(raw_text.strip("`").strip())

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
                all_rows.append(row_values)
            except Exception as e:
                st.error(f"Failed {file.name}: {e}")

            progress.progress((idx+1)/len(uploaded_files))

        if all_rows:
            # Batch append - mas mabilis kaysa isa-isa, iwas Column N error
            sheet.append_rows(all_rows)
            st.success(f"🎉 Success! {len(all_rows)} rows appended to {SHEET_URL}")
            st.dataframe(pd.DataFrame(all_rows))
        else:
            st.error("Walang na-process.")
