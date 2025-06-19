import os
import re
import fitz  
import pytesseract
import datetime
from pdf2image import convert_from_path
from typing import List, Tuple, Dict
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

# === Configure Tesseract for Streamlit Cloud ===
def configure_tesseract():
    """Configure Tesseract path for different environments"""
    try:
        # Try to find tesseract executable
        import subprocess
        result = subprocess.run(['which', 'tesseract'], capture_output=True, text=True)
        if result.returncode == 0:
            tesseract_path = result.stdout.strip()
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            print(f"✅ Tesseract found at: {tesseract_path}")
        else:
            # Common paths for different systems
            possible_paths = [
                '/usr/bin/tesseract',
                '/usr/local/bin/tesseract',
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',  # Windows
                r'C:\Users\AppData\Local\Tesseract-OCR\tesseract.exe'  # Windows alt
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    print(f"✅ Tesseract configured at: {path}")
                    return
            
            print("⚠️ Tesseract not found in common locations")
            
    except Exception as e:
        print(f"⚠️ Error configuring Tesseract: {e}")

# Configure Tesseract when module is imported
configure_tesseract()

# === OCR ===
def extract_text_from_pdf(pdf_path: str) -> List[str]:
    try:
        # Add error handling for PDF conversion
        images = convert_from_path(pdf_path, dpi=300)
        texts = []
        
        for i, img in enumerate(images):
            try:
                # Convert to grayscale and extract text
                text = pytesseract.image_to_string(img.convert("L"), config='--psm 6')
                texts.append(text)
                print(f"✅ Processed page {i+1}/{len(images)}")
            except Exception as e:
                print(f"⚠️ OCR failed for page {i+1}: {e}")
                texts.append("")  # Add empty string for failed pages
                
        return texts
        
    except Exception as e:
        print(f"❌ PDF conversion failed: {e}")
        raise Exception(f"Failed to process PDF: {str(e)}")

# === Extracting Top-Right Bill Date (strict format) & Account Number ===
def extract_metadata(page_text: str) -> Dict[str, str]:
    bill_date = "0000"
    account_number = "0000"

    bill_date_match = re.search(
        r'Bill\s*date[^a-zA-Z0-9]{0,10}(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}',
        page_text,
        re.IGNORECASE
    )

    if bill_date_match:
        try:
            date_part_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}', bill_date_match.group(0))
            if date_part_match:
                dt = datetime.datetime.strptime(date_part_match.group(0), "%b %d, %Y")
                bill_date = f"{dt.month:02d}{str(dt.year)[-2:]}"
        except Exception as e:
            print(f"[Date Parse Error] {e}")

    # Account Number
    acc_match = re.search(r'\b\d{4} \d{4} \d{4}\b', page_text)
    if acc_match:
        account_number = acc_match.group(0).replace(" ", "")[-4:]

    return {"bill_date": bill_date, "account_number": account_number}

# === Group Pages with ±1 fallback for missing bill date ===
def group_pages_with_fallback(pages_text: List[str]) -> Dict[Tuple[str, str], List[int]]:
    metadata = [extract_metadata(text) for text in pages_text]
    grouped = defaultdict(list)
    used = set()

    for i, meta in enumerate(metadata):
        if i in used:
            continue
        acc = meta["account_number"]
        date = meta["bill_date"]

        if date != "0000":
            key = (acc, date)
            grouped[key].append(i)
            used.add(i)
            for j in [i - 1, i + 1]:
                if 0 <= j < len(metadata):
                    meta_j = metadata[j]
                    if j not in used and meta_j["account_number"] == acc and meta_j["bill_date"] == "0000":
                        grouped[key].append(j)
                        used.add(j)
        else:
            matched = False
            for j in [i - 1, i + 1]:
                if 0 <= j < len(metadata):
                    meta_j = metadata[j]
                    if meta_j["account_number"] == acc and meta_j["bill_date"] != "0000":
                        key = (acc, meta_j["bill_date"])
                        grouped[key].append(i)
                        used.add(i)
                        matched = True
                        break
            if not matched:
                grouped[(acc, "0000")].append(i)
                used.add(i)

    return grouped

# === Saving Grouped PDFs ===
def split_and_save(pdf_path: str, grouped: Dict[Tuple[str, str], List[int]], output_dir: str) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    saved_paths = []

    pages_text = extract_text_from_pdf(pdf_path)

    for (acc, _), pages in grouped.items():
        new_pdf = fitz.open()
        pages = sorted(set(pages))
        true_date = "0000"

        for idx in pages:
            meta = extract_metadata(pages_text[idx])
            if meta["bill_date"] != "0000":
                true_date = meta["bill_date"]
                break

        for p in pages:
            new_pdf.insert_pdf(doc, from_page=p, to_page=p)

        filename = f"{true_date}_{acc}.pdf"
        path = os.path.join(output_dir, filename)
        new_pdf.save(path)
        saved_paths.append(path)
        new_pdf.close()

    doc.close()
    return saved_paths

# === Main Entrypoint ===
def process_pdf(pdf_path: str, output_dir: str) -> List[str]:
    print(f"🔍 Extracting text from {pdf_path}...")
    
    try:
        pages_text = extract_text_from_pdf(pdf_path)
        print(f"✅ Extracted text from {len(pages_text)} pages")

        print("🧠 Parsing metadata strictly with fallback logic...")
        grouped = group_pages_with_fallback(pages_text)
        print(f"✅ Grouped into {len(grouped)} invoice sets")

        print("📄 Writing split invoice PDFs...")
        saved = split_and_save(pdf_path, grouped, output_dir)

        print(f"\n✅ Done: {len(saved)} files saved in '{output_dir}'")
        return saved
        
    except Exception as e:
        print(f"❌ Error processing PDF: {e}")
        raise e