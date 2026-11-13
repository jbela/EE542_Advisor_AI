"""Import a locally supplied syllabus with explicit course metadata."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--course", required=True)
    parser.add_argument("--term", required=True)
    parser.add_argument("--section", default="Unspecified")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    match = re.fullmatch(
        r"\s*([A-Za-z]{2,5})[\s-]*(\d{3}[A-Za-z]?)\s*",
        args.course,
    )
    if not match:
        parser.error('--course must be a course code such as "EE 542".')
    course_code = f"{match[1].upper()} {match[2].upper()}"

    if not re.fullmatch(r"20\d{2}[123]", args.term):
        parser.error("--term must be a semester code such as 20263.")

    section_label = args.section.strip()
    section_id = re.sub(r"[^a-z0-9]+", "_", section_label.lower()).strip("_")
    if not section_id:
        parser.error("--section must contain letters or numbers.")

    pdf_path = args.pdf.expanduser()
    if not pdf_path.is_absolute():
        pdf_path = ROOT / pdf_path
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        parser.error(f"PDF not found or not a PDF file: {pdf_path}")

    course_id = course_code.replace(" ", "").lower()
    document_key = f"{course_id}_{args.term}_{section_id}"
    output_path = (
        ROOT / "data" / "processed" / "syllabi" / f"{document_key}.json"
    )
    if output_path.exists() and not args.overwrite:
        parser.error(
            f"Output already exists: {output_path}. "
            "Use --overwrite only to intentionally replace this document."
        )

    reader = PdfReader(pdf_path)
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append({"page_number": page_number, "text": text})
        if not text:
            print(f"WARNING: Page {page_number} has no extracted text.")

    if not any(page["text"] for page in pages):
        raise ValueError("No readable text was extracted from the PDF.")

    semester = {"1": "Spring", "2": "Summer", "3": "Fall"}[args.term[-1]]
    document = {
        "id": f"syllabus_{document_key}",
        "title": (
            f"{course_code} — {semester} {args.term[:4]} — "
            f"{section_label} Syllabus"
        ),
        "source_type": "syllabus",
        "course_code": course_code,
        "term_code": args.term,
        "section_label": section_label,
        "source_file": pdf_path.name,
        "url": None,
        "file_hash": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "page_count": len(pages),
        "pages": pages,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open(
        "w" if args.overwrite else "x", encoding="utf-8"
    ) as output:
        json.dump(document, output, ensure_ascii=False, indent=2)

    print(f"Course: {course_code}; term: {args.term}; section: {section_label}")
    print(f"Read {len(pages)} pages.")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()