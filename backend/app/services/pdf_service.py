from pathlib import Path
import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract plain text from a PDF using PyMuPDF."""
    text_parts = []
    with fitz.open(pdf_path) as doc:
        for page_number, page in enumerate(doc, start=1):
            page_text = page.get_text("text")
            if page_text:
                text_parts.append(f"\n--- Page {page_number} ---\n{page_text}")
    return "\n".join(text_parts).strip()
