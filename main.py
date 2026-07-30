import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import json, io, re
import pandas as pd
from PIL import Image
import fitz

st.set_page_config(page_title="GCash Survey", page_icon="📊", layout="wide")

SPREADSHEET_ID = "1E6S7Bh4R-3LC4XYhIsTqS_9sIxN4WGfDtFXwihlVk84"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"

@st.cache_resource
def init_all():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    creds_dict = dict(st.secrets["gsheets_credentials"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).get_worksheet(0)
    drive_service = build('drive', 'v3', credentials=creds)
    return sheet, drive_service

sheet, drive_service = init_all()

st.title("GCash Survey")

# --- YAN NA YUNG GUSTO MO ---
st.markdown("### GOOGLE DRIVE LINK HERE:")
st.write("Paste mo dito yung GDrive folder link kung saan mo gusto i-extract.")
st.success(f"Connected to Sheet: {SHEET_URL}")

def extract_id(link):
    m = re.search(r'/folders/([a-zA-Z0-9-_]+)', link)
    if m: return m.group(1), "folder"
    m = re.search(r'/file/d/([a-zA-Z0-9-_]+)', link)
    if m: return m.group(1), "file"
    m = re.search(r'id=([a-zA-Z0-9-_]+)', link)
    if m: return m.group(1), "folder"
    if len(link.strip()) > 20 and "/" not in link:
        return link.strip(), "folder"
    return None, None

def pdf_to_images(pdf_bytes):
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        # FIXED: tanggal sobrang )
        images.append(Image.open(io.BytesIO(pix.tobytes("png"))))
    doc.close()
    return images

drive_link = st.text_input(
    "Drive Link:",
    placeholder="https://drive.google.com/drive/folders/1It3yDQk90kowL...",
    label_visibility="collapsed"
)

if drive_link:
    fid, ftype = extract_id(drive_link)
    if not fid:
        st.error("Mali yung link. Dapat Google Drive link.")
    else:
        if st.button("🚀 I-EXTRACT NA FROM DRIVE LINK", type="primary"):
            all_pages = []
            try:
                if ftype == "folder":
                    q = f"'{fid}' in parents and trashed=false"
                    res = drive_service.files().list(q=q, fields="files(id, name, mimeType)", orderBy="name").execute()
                    files = res.get('files', [])
                    if not files:
                        st.error("Walang file sa folder o hindi naka-share sa service account.")
                        st.stop()
                    st.info(f"Nakita sa folder: {len(files)} files - Paired as 1+2 = 1 Row (kahit more or less pages ok)")
                    for f in files:
                        data = drive_service.files().get_media(fileId=f['id']).execute()
                        if f['name'].lower().endswith('.pdf'):
                            all_pages.extend(pdf_to_images(data))
                        else:
                            all_pages.append(Image.open(io.BytesIO(data)))
                else:
                    data = drive_service.files().get_media(fileId=fid).execute()
                    all_pages.extend(pdf_to_images(data))

                st.write(f"Total pages to process: {len(all_pages)}")

                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt = """You have 2 images = 1 person. Image1=Page1 SA WALA PA MAGSUGOD, Image2=Page2 TUBAGON NATO. Name from Ngalan top Image1. Extract ONLY encircled letter A,B,C. For E extract handwritten. Return STRICT JSON only: {"NAME":"","PAGE_1_A_BUDGET_1":"","PAGE_1_A_BUDGET_2":"","PAGE_1_A_BUDGET_3":"","PAGE_1_B_SAVINGS_1":"","PAGE_1_B_SAVINGS_2":"","PAGE_1_B_SAVINGS_3":"","PAGE_1_C_UTANG_1":"","PAGE_1_C_UTANG_2":"","PAGE_1_C_UTANG_3":"","PAGE_1_D_SCAM_1":"","PAGE_1_D_SCAM_2":"","PAGE_1_D_SCAM_3":"","PAGE_2_A_BUDGET_1":"","PAGE_2_A_BUDGET_2":"","PAGE_2_B_SAVINGS_1":"","PAGE_2_B_SAVINGS_2":"","PAGE_2_B_SAVINGS_3":"","PAGE_2_C_UTANG_1":"","PAGE_2_C_UTANG_2":"","PAGE_2_C_UTANG_3":"","PAGE_2_D_SCAM_1":"","PAGE_2_D_SCAM_2":"","PAGE_2_D_SCAM_3":"","PAGE_2_E_1":"","PAGE_2_E_2":"","PAGE_2_E_3":""}"""

                rows = []
                prog = st.progress(0)
                for i in range(0, len(all_pages), 2):
                    if i+1 >= len(all_pages): break
                    resp = model.generate_content([prompt, all_pages[i], all_pages[i+1]])
                    raw = resp.text.strip().replace("```json","").replace("```","").strip()
                    s,e = raw.find("{"), raw.rfind("}")
                    if s!=-1 and e!=-1: raw=raw[s:e+1]
                    data = json.loads(raw)
                    row = [data.get(k,"") for k in ["NAME","PAGE_1_A_BUDGET_1","PAGE_1_A_BUDGET_2","PAGE_1_A_BUDGET_3","PAGE_1_B_SAVINGS_1","PAGE_1_B_SAVINGS_2","PAGE_1_B_SAVINGS_3","PAGE_1_C_UTANG_1","PAGE_1_C_UTANG_2","PAGE_1_C_UTANG_3","PAGE_1_D_SCAM_1","PAGE_1_D_SCAM_2","PAGE_1_D_SCAM_3","PAGE_2_A_BUDGET_1","PAGE_2_A_BUDGET_2","PAGE_2_B_SAVINGS_1","PAGE_2_B_SAVINGS_2","PAGE_2_B_SAVINGS_3","PAGE_2_C_UTANG_1","PAGE_2_C_UTANG_2","PAGE_2_C_UTANG_3","PAGE_2_D_SCAM_1","PAGE_2_D_SCAM_2","PAGE_2_D_SCAM_3","PAGE_2_E_1","PAGE_2_E_2","PAGE_2_E_3"]]
                    rows.append(row)
                    st.write(f"✅ Pair {i//2+1}: {data.get('NAME','')}")
                    prog.progress((i+2)/len(all_pages))

                if rows:
                    sheet.append_rows(rows, value_input_option='USER_ENTERED')
                    st.balloons()
                    st.success(f"TAPOS! {len(rows)} rows na-encode from Drive link.")
                    st.dataframe(pd.DataFrame(rows))

            except Exception as e:
                st.error(f"Error: {e} - Check kung naka-share yung Drive folder sa service account as Viewer")
