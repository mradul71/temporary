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

# === OCR ===
def extract_text_from_pdf(pdf_path: str) -> List[str]:
    images = convert_from_path(pdf_path, dpi=300)
    return [pytesseract.image_to_string(img.convert("L")) for img in images]

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

    return saved_paths


# === Main Entrypoint ===
def process_pdf(pdf_path: str, output_dir: str) -> List[str]:
    print(f"🔍 Extracting text from {pdf_path}...")
    pages_text = extract_text_from_pdf(pdf_path)

    print("🧠 Parsing metadata strictly with fallback logic...")
    grouped = group_pages_with_fallback(pages_text)

    print("📄 Writing split invoice PDFs...")
    saved = split_and_save(pdf_path, grouped, output_dir)

    print(f"\n✅ Done: {len(saved)} files saved in '{output_dir}'")
    return saved

# === Trigger (not required) === 
# if __name__ == "__main__":
#     process_pdf("Batch3.pdf", "output_invoices2")
