"""Read a locally supplied syllabus into page-level records."""

import hashlib
import json
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]

PDF_PATH = (
    ROOT
    / "data"
    / "raw"
    / "syllabi"
    / "csci526_20263_friday.pdf"
)

OUTPUT_PATH = (
    ROOT
    / "data"
    / "processed"
    / "syllabi"
    / "csci526_20263_friday.json"
)


def main():
    if not PDF_PATH.is_file():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    reader = PdfReader(PDF_PATH)

    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()

        pages.append({
            "page_number": page_number,
            "text": text,
        })

        if not text:
            print(f"WARNING: Page {page_number} has no extracted text.")

    if not any(page["text"] for page in pages):
        raise ValueError("No readable text was extracted from the PDF.")

    document = {
        "id": "syllabus_csci526_20263_friday",
        "title": "CSCI 526 — Fall 2026 — Friday Syllabus",
        "source_type": "syllabus",
        "course_code": "CSCI 526",
        "term_code": "20263",
        "section_label": "Friday",
        "source_file": PDF_PATH.name,
        "url": None,
        "file_hash": hashlib.sha256(
            PDF_PATH.read_bytes()
        ).hexdigest(),
        "page_count": len(pages),
        "pages": pages,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Read {len(pages)} pages.")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()