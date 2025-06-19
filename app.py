import streamlit as st
import os
import tempfile
import zipfile
import shutil
import traceback
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

        try:
            for file in uploaded_files:
                file_path = os.path.join(st.session_state.tempdir, file.name)
                with open(file_path, "wb") as f:
                    f.write(file.read())
                st.session_state.file_map[file.name] = file_path
            st.success(f"✅ Uploaded {len(uploaded_files)} file(s) successfully")
        except Exception as e:
            st.error(f"❌ Error uploading files: {str(e)}")

# === Show file selection and processing if files uploaded ===
if "file_map" in st.session_state and st.session_state.file_map:
    file_names = list(st.session_state.file_map.keys())
    selected_file_name = st.selectbox("Select a PDF to process", file_names)

    if st.button("Segregate"):
        try:
            with st.spinner("Running OCR and splitting PDF..."):
                selected_path = st.session_state.file_map[selected_file_name]
                output_dir = os.path.join(st.session_state.tempdir, "output")
                os.makedirs(output_dir, exist_ok=True)

                st.write(f"🔍 Starting segregation on: `{selected_file_name}`...")
                
                # Add progress indicator
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.text("Processing PDF...")
                progress_bar.progress(25)
                
                saved_files = process_pdf(selected_path, output_dir)
                
                progress_bar.progress(75)
                status_text.text("Creating ZIP file...")
                
                st.write(f"✅ Segregation complete. {len(saved_files)} PDFs generated.")

                # Create ZIP file
                zip_path = os.path.join(st.session_state.tempdir, "output.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for pdf_path in saved_files:
                        zipf.write(pdf_path, os.path.basename(pdf_path))

                progress_bar.progress(100)
                status_text.text("Complete!")
                
                st.success("🎉 All done! Download your segregated invoices below:")
                with open(zip_path, "rb") as f:
                    st.download_button("⬇️ Download ZIP", f, file_name="segregated_pdfs.zip")

        except Exception as e:
            st.error(f"❌ Error during processing: {str(e)}")
            
            # Show detailed error in expander for debugging
            with st.expander("🔍 View detailed error"):
                st.code(traceback.format_exc())
            
            st.info("💡 This might be due to:")
            st.write("- Tesseract OCR not being properly configured")
            st.write("- PDF format not supported")
            st.write("- Memory limitations on Streamlit Cloud")
            st.write("- File corruption during upload")

# === Debug Information ===
with st.expander("🔧 Debug Information"):
    st.write("**Environment Info:**")
    st.write(f"- Python version: {st.__version__}")
    st.write(f"- Temp directory: {st.session_state.get('tempdir', 'Not set')}")
    
    # Check if Tesseract is available
    try:
        import pytesseract
        import subprocess
        result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            st.write("- ✅ Tesseract OCR: Available")
            st.code(result.stdout.split('\n')[0])
        else:
            st.write("- ❌ Tesseract OCR: Not found")
    except Exception as e:
        st.write(f"- ❌ Tesseract OCR: Error checking - {str(e)}")

st.markdown("---")
if st.button("🧹 Clear session"):
    if "tempdir" in st.session_state:
        shutil.rmtree(st.session_state.tempdir, ignore_errors=True)
    st.session_state.clear()
    st.success("Session cleared.")
    st.rerun()