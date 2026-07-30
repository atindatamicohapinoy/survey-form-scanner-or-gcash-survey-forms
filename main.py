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
st.title("GCash Survey")
st.write("Upload up to 5 survey photos. Extracts ONLY encircled/checked letters. [Drive Link Mode]")

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
st.success(f"Connected to: {SHEET_URL}")

def extract_id_from_link(link):
    # Kukunin ID kahit folder o file link pa yan
    m = re.search(r'/folders/([a-zA-Z0-9-_]+)', link)
    if m: return m.group(1), "folder"
    m = re.search(r'/file/d/([a-zA-Z0-9-_]+)', link)
    if m: return m.group(1), "file"
    m = re.search(r'id=([a-zA-Z0-9-_]+)', link)
    if m: return m.group(1), "folder"
    # baka ID lang pinaste
    if len(link.strip()) > 20 and "/" not in link:
        return link.strip(), "folder"
    return None, None

def pdf_to_images(pdf_bytes):
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        images.append(Image.open(io.BytesIO(pix.tobytes("png"))))
    doc.close()
    return images

# --- BAGONG UI: LINK INSTEAD OF UPLOAD ---
drive_link = st.text_input("Paste Google Drive Folder Link dito:", placeholder="https://drive.google.com/drive/folders/1It3yDQk90kowL1Lc6TNRo29hTjhXoxd28gJrIcOL2ml")
st.caption("Pwede Folder link o kahit isang PDF file link. Make sure naka-share sa service account email mo as Viewer.")

if drive_link:
    file_id, link_type = extract_id_from_link(drive_link)

    if not file_id:
        st.error("Hindi ko mabasa yung link. Siguraduhin na Google Drive link yan.")
    else:
        if st.button(f"🚀 Basahin at I-encode from Drive Link", type="primary"):
            all_pages = []

            try:
                if link_type == "folder":
                    # FOLDER MODE
                    query = f"'{file_id}' in parents and trashed=false"
                    results = drive_service.files().list(q=query, fields="files(id, name, mimeType)").execute()
                    files = results.get('files', [])
                    st.info(f"Nakita sa folder: {len(files)} files")

                    for f in files:
                        f_id = f['id']
                        mime = f.get('mimeType','')
                        name = f.get('name','').lower()
                        data = drive_service.files().get_media(fileId=f_id).execute()
                        if 'pdf' in mime or name.endswith('.pdf'):
                            all_pages.extend(pdf_to_images(data))
                        elif 'image' in mime or name.endswith(('.jpg','.jpeg','.png')):
                            all_pages.append(Image.open(io.BytesIO(data)))
                else:
                    # SINGLE FILE MODE (PDF or Image link)
                    meta = drive_service.files().get(fileId=file_id, fields="name, mimeType").execute()
                    data = drive_service.files().get_media(fileId=file_id).execute()
                    st.info(f"Binabasa file: {meta.get('name')}")
                    if 'pdf' in meta.get('mimeType','') or meta.get('name','').lower().endswith('.pdf'):
                        all_pages.extend(pdf_to_images(data))
                    else:
                        all_pages.append(Image.open(io.BytesIO(data)))

                st.success(f"Total na-detect: {len(all_pages)} pages. Magiging {len(all_pages)//2} rows pag pinag-pair (1+2=1 row)")

                # --- GEMINI PAIRING LOGIC ---
                model = genai.GenerativeModel('gemini-2.5-flash')
                pair_prompt = """
                You have 2 survey images of ONE person. Image 1 is Page 1 (SA WALA PA MAGSUGOD), Image 2 is Page 2 (TUBAGON NATO).
                Name is at top of Image 1 under "Ngalan:". If empty, try CONTACT NAME on Image 2.
                Task: Extract ONLY the encircled/checked letter. Answer must be ONLY A, B, or C.
                For Section E on Image 2 bottom, extract handwritten text.
                Return STRICT valid JSON only:
                {"NAME": "", "PAGE_1_A_BUDGET_1": "", "PAGE_1_A_BUDGET_2": "", "PAGE_1_A_BUDGET_3": "", "PAGE_1_B_SAVINGS_1": "", "PAGE_1_B_SAVINGS_2": "", "PAGE_1_B_SAVINGS_3": "", "PAGE_1_C_UTANG_1": "", "PAGE_1_C_UTANG_2": "", "PAGE_1_C_UTANG_3": "", "PAGE_1_D_SCAM_1": "", "PAGE_1_D_SCAM_2": "", "PAGE_1_D_SCAM_3": "", "PAGE_2_A_BUDGET_1": "", "PAGE_2_A_BUDGET_2": "", "PAGE_2_B_SAVINGS_1": "", "PAGE_2_B_SAVINGS_2": "", "PAGE_2_B_SAVINGS_3": "", "PAGE_2_C_UTANG_1": "", "PAGE_2_C_UTANG_2": "", "PAGE_2_C_UTANG_3": "", "PAGE_2_D_SCAM_1": "", "PAGE_2_D_SCAM_2": "", "PAGE_2_D_SCAM_3": "", "PAGE_2_E_1": "", "PAGE_2_E_2": "", "PAGE_2_E_3": ""}
                """

                rows = []
                prog = st.progress(0)
                for i in range(0, len(all_pages), 2):
                    if i+1 >= len(all_pages): break
                    try:
                        resp = model.generate_content([pair_prompt, all_pages[i], all_pages[i+1]])
                        raw = resp.text.strip().replace("```json","").replace("```","").strip()
                        s = raw.find("{"); e = raw.rfind("}")
                        if s!=-1 and e!=-1: raw = raw[s:e+1]
                        data = json.loads(raw)
                        row = [data.get(k,"") for k in ["NAME","PAGE_1_A_BUDGET_1","PAGE_1_A_BUDGET_2","PAGE_1_A_BUDGET_3","PAGE_1_B_SAVINGS_1","PAGE_1_B_SAVINGS_2","PAGE_1_B_SAVINGS_3","PAGE_1_C_UTANG_1","PAGE_1_C_UTANG_2","PAGE_1_C_UTANG_3","PAGE_1_D_SCAM_1","PAGE_1_D_SCAM_2","PAGE_1_D_SCAM_3","PAGE_2_A_BUDGET_1","PAGE_2_A_BUDGET_2","PAGE_2_B_SAVINGS_1","PAGE_2_B_SAVINGS_2","PAGE_2_B_SAVINGS_3","PAGE_2_C_UTANG_1","PAGE_2_C_UTANG_2","PAGE_2_C_UTANG_3","PAGE_2_D_SCAM_1","PAGE_2_D_SCAM_2","PAGE_2_D_SCAM_3","PAGE_2_E_1","PAGE_2_E_2","PAGE_2_E_3"]]
                        rows.append(row)
                        st.write(f"✅ Pair {i//2+1}: {data.get('NAME')}")
                    except Exception as e:
                        st.error(f"Error pair {i//2+1}: {e}")
                    prog.progress((i+2)/len(all_pages))

                if rows:
                    sheet.append_rows(rows, value_input_option='USER_ENTERED')
                    st.balloons()
                    st.success(f"Tapos! {len(rows)} rows na-append from Drive link.")
                    st.dataframe(pd.DataFrame(rows))

            except Exception as e:
                st.error(f"Drive Error: {e}. Siguraduhin na naka-share yung folder/file sa service account email mo.")
