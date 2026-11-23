"""Import approved proof-of-concept syllabi and synchronize RAG."""

import json
from pathlib import Path

from ingestion.import_syllabus import main as import_syllabus
from rag.sync_index import sync_index


ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "data" / "syllabus_poc" / "pdfs"
PROCESSED_DIR = ROOT / "data" / "processed" / "syllabi"

SYLLABI = [
    {
        "filename": "EE510_20263.pdf",
        "course": "EE 510",
        "term": "20263",
        "section": "Unspecified",
        "instructor": "Michael J. Neely",
    },
    {
        "filename": "EE542_20263.pdf",
        "course": "EE 542",
        "term": "20263",
        "section": "Unspecified",
        "instructor": "Young Cho",
    },
]


def main():
    print("=" * 60)
    print("USC ADVISOR AI - SYLLABUS POC IMPORT")
    print("=" * 60)

    for syllabus in SYLLABI:
        pdf_path = PDF_DIR / syllabus["filename"]

        if not pdf_path.is_file():
            raise FileNotFoundError(
                f"Missing syllabus PDF: {pdf_path}"
            )

        course_id = syllabus["course"].replace(" ", "").lower()

        output_path = (
            PROCESSED_DIR
            / (
                f"{course_id}_{syllabus['term']}"
                "_unspecified.json"
            )
        )

        if output_path.exists():
            existing = json.loads(
                output_path.read_text(encoding="utf-8")
            )

            if (
                existing.get("course_code") == syllabus["course"]
                and existing.get("term_code") == syllabus["term"]
                and existing.get("instructor") == syllabus["instructor"]
                and existing.get("source_file") == syllabus["filename"]
            ):
                import hashlib

                current_hash = hashlib.sha256(
                    pdf_path.read_bytes()
                ).hexdigest()

                if existing.get("file_hash") == current_hash:
                    print(
                        f"Already imported: {syllabus['course']} "
                        f"({syllabus['term']})"
                    )
                    continue

        print(
            f"Importing {syllabus['course']} "
            f"({syllabus['term']})..."
        )

        import_syllabus([
            "--pdf", str(pdf_path),
            "--course", syllabus["course"],
            "--term", syllabus["term"],
            "--section", syllabus["section"],
            "--instructor", syllabus["instructor"],
            "--overwrite",
        ])

    print("\nSynchronizing RAG index...")
    result = sync_index()

    print("\nSynchronization result:")
    print(result)

    return result


if __name__ == "__main__":
    main()
