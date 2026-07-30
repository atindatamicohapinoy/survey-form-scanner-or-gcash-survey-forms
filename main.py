import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
import json
import pandas as pd
from PIL import Image
import fitz
import io

st.set_page_config(page_title="GCash Survey", page_icon="📊", layout="wide")
st.title("GCash Survey - Paired Mode (1+2 = 1 Row)")

SPREADSHEET_ID = "1E6S7Bh4R-3LC4XYhIsTqS_9sIxN4WGfDtFXwihlVk84"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"

@st.cache_resource
def init_connections():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    credentials_dict = dict(st.secrets["gsheets_credentials"])
    credentials_dict["private_key"] = credentials_dict["private_key"].replace(r"\n", "\n")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).get_worksheet(0)
    return sheet

sheet = init_connections()
st.success(f"Connected to: {sheet.title}")

def pdf_to_images(pdf_bytes):
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=250) # mas malinaw para sa bilog
        images.append(Image.open(io.BytesIO(pix.tobytes("png"))))
    return images

uploaded_files = st.file_uploader("Upload PDF (kahit 72 pages) o images", type=["jpg","jpeg","png","pdf"], accept_multiple_files=True)

if uploaded_files:
    all_pages = []
    for f in uploaded_files:
        if f.type == "application/pdf":
            all_pages.extend(pdf_to_images(f.getvalue()))
        else:
            all_pages.append(Image.open(f))

    st.info(f"Na-detect: {len(all_pages)} pages. Kapag pinag-pair, magiging {len(all_pages)//2} rows yan.")
    st.write("Preview ng unang 2 pages (isang tao):")
    c1, c2 = st.columns(2)
    if len(all_pages) > 0: c1.image(all_pages[0], caption="Page 1 - SA WALA PA MAGSUGOD")
    if len(all_pages) > 1: c2.image(all_pages[1], caption="Page 2 - TUBAGON NATO")

    if st.button(f"🚀 I-encode na lahat", type="primary"):
        model = genai.GenerativeModel('gemini-2.5-flash')

        pair_prompt = """
        You have 2 survey images of ONE person. Image 1 is marked with number 1 (SA WALA PA MAGSUGOD), Image 2 is marked with number 2 (TUBAGON NATO).
        The name is at the top of Image 1 under "Ngalan:".
        Task: Extract ONLY the encircled letter (A, B, or C) for each question.
        For Section E on Image 2 (questions 1,2,3 at bottom), extract the short handwritten text if any.

        Return STRICT JSON only, no markdown:
        {
         "NAME": "from Ngalan in Image 1",
         "PAGE_1_A_BUDGET_1": "A/B/C", "PAGE_1_A_BUDGET_2": "A/B/C", "PAGE_1_A_BUDGET_3": "A/B/C",
         "PAGE_1_B_SAVINGS_1": "A/B/C", "PAGE_1_B_SAVINGS_2": "A/B/C", "PAGE_1_B_SAVINGS_3": "A/B/C",
         "PAGE_1_C_UTANG_1": "A/B/C", "PAGE_1_C_UTANG_2": "A/B/C", "PAGE_1_C_UTANG_3": "A/B/C",
         "PAGE_1_D_SCAM_1": "A/B/C", "PAGE_1_D_SCAM_2": "A/B/C", "PAGE_1_D_SCAM_3": "A/B/C",
         "PAGE_2_A_BUDGET_1": "A/B/C", "PAGE_2_A_BUDGET_2": "A/B/C",
         "PAGE_2_B_SAVINGS_1": "A/B/C", "PAGE_2_B_SAVINGS_2": "A/B/C", "PAGE_2_B_SAVINGS_3": "A/B/C",
         "PAGE_2_C_UTANG_1": "A/B/C", "PAGE_2_C_UTANG_2": "A/B/C", "PAGE_2_C_UTANG_3": "A/B/C",
         "PAGE_2_D_SCAM_1": "A/B/C", "PAGE_2_D_SCAM_2": "A/B/C", "PAGE_2_D_SCAM_3": "A/B/C",
         "PAGE_2_E_1": "text", "PAGE_2_E_2": "text", "PAGE_2_E_3": "text"
        }
        """

        rows = []
        prog = st.progress(0)
        # Pair by 2
        for i in range(0, len(all_pages), 2):
            if i+1 >= len(all_pages):
                st.warning(f"May sobrang 1 page sa dulo (page {i+1}), nilaktawan.")
                break

            img1 = all_pages[i]
            img2 = all_pages[i+1]
            try:
                resp = model.generate_content([pair_prompt, img1, img2])
                raw = resp.text.strip().replace("```json","").replace("```","").strip()
                data = json.loads(raw)

                row = [data.get(k,"") for k in ["NAME","PAGE_1_A_BUDGET_1","PAGE_1_A_BUDGET_2","PAGE_1_A_BUDGET_3","PAGE_1_B_SAVINGS_1","PAGE_1_B_SAVINGS_2","PAGE_1_B_SAVINGS_3","PAGE_1_C_UTANG_1","PAGE_1_C_UTANG_2","PAGE_1_C_UTANG_3","PAGE_1_D_SCAM_1","PAGE_1_D_SCAM_2","PAGE_1_D_SCAM_3","PAGE_2_A_BUDGET_1","PAGE_2_A_BUDGET_2","PAGE_2_B_SAVINGS_1","PAGE_2_B_SAVINGS_2","PAGE_2_B_SAVINGS_3","PAGE_2_C_UTANG_1","PAGE_2_C_UTANG_2","PAGE_2_C_UTANG_3","PAGE_2_D_SCAM_1","PAGE_2_D_SCAM_2","PAGE_2_D_SCAM_3","PAGE_2_E_1","PAGE_2_E_2","PAGE_2_E_3"]]
                rows.append(row)
                st.write(f"✅ Pair {i//2+1}: {data.get('NAME')} -> {row[1:5]}...")
            except Exception as e:
                st.error(f"Error sa pair {i//2+1}: {e}")
            prog.progress((i+2)/len(all_pages))

        if rows:
            sheet.append_rows(rows)
            st.balloons()
            st.success(f"Tapos na! {len(rows)} tao / rows ang na-append. Kahit more or less pages, auto-pair pa rin.")
            st.dataframe(pd.DataFrame(rows))
