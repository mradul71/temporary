import streamlit as st
import os
import tempfile
import zipfile
import shutil
from test import process_pdf  

st.set_page_config(page_title="PDF Invoice Segregator", layout="centered")
st.title("📂 PDF Invoice Segregator")

# === Upload PDF Files ===
uploaded_files = st.file_uploader("Upload PDF files", type="pdf", accept_multiple_files=True)

# === Initialize persistent temp directory and file map ===
if "tempdir" not in st.session_state:
    st.session_state.tempdir = tempfile.mkdtemp()

if uploaded_files:
    if "file_map" not in st.session_state:
        st.session_state.file_map = {}

        for file in uploaded_files:
            file_path = os.path.join(st.session_state.tempdir, file.name)
            with open(file_path, "wb") as f:
                f.write(file.read())
            st.session_state.file_map[file.name] = file_path

# === Show file selection and processing if files uploaded ===
if "file_map" in st.session_state and st.session_state.file_map:
    file_names = list(st.session_state.file_map.keys())
    selected_file_name = st.selectbox("Select a PDF to process", file_names)

    if st.button("Segregate"):
        with st.spinner("Running OCR and splitting PDF..."):
            selected_path = st.session_state.file_map[selected_file_name]
            output_dir = os.path.join(st.session_state.tempdir, "output")
            os.makedirs(output_dir, exist_ok=True)

            st.write(f"🔍 Starting segregation on: `{selected_file_name}`...")
            saved_files = process_pdf(selected_path, output_dir)
            st.write(f"✅ Segregation complete. {len(saved_files)} PDFs generated.")

           
            zip_path = os.path.join(st.session_state.tempdir, "output.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for pdf_path in saved_files:
                    zipf.write(pdf_path, os.path.basename(pdf_path))

            st.success("🎉 All done! Download your segregated invoices below:")
            with open(zip_path, "rb") as f:
                st.download_button("⬇️ Download ZIP", f, file_name="segregated_pdfs.zip")


st.markdown("---")
if st.button("🧹 Clear session"):
    if "tempdir" in st.session_state:
        shutil.rmtree(st.session_state.tempdir, ignore_errors=True)
    st.session_state.clear()
    st.success("Session cleared.")
    st.rerun()
