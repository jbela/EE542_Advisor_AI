"""Read reviewed grading facts and validate them against the source document.

Only named assessment-weight questions are supported. Facts are local data,
not course-specific answers embedded in Python. Source changes invalidate facts.
"""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYLLABI_DIR = ROOT / "data" / "processed" / "syllabi"
GRADING_DIR = ROOT / "data" / "processed" / "syllabi_grading"
WEIGHT_QUESTION = re.compile(
    r"\b(percent(?:age)?|weight(?:ing)?|worth|how much)\b|%",
    re.IGNORECASE,
)


def _phrase(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def lookup_grading_fact(question, course_code, term_code):
    """Return one source-checked grading item, or None when not established."""
    if not WEIGHT_QUESTION.search(question):
        return None

    documents = []
    for path in SYLLABI_DIR.glob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if (
            doc.get("course_code") == course_code
            and str(doc.get("term_code")) == str(term_code)
        ):
            documents.append(doc)

    # Do not silently select a section when more than one syllabus is present.
    if len(documents) != 1:
        return None
    doc = documents[0]
    document_id = doc.get("id", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", document_id):
        return None
    fact_path = GRADING_DIR / f"{document_id}.json"
    if not fact_path.is_file():
        return None
    reviewed = json.loads(fact_path.read_text(encoding="utf-8"))
    if (
        reviewed.get("document_id") != document_id
        or reviewed.get("source_file_hash") != doc.get("file_hash")
        or not doc.get("file_hash")
    ):
        return None

    question_words = f" {_phrase(question)} "
    matches = []
    for index, item in enumerate(reviewed.get("items", [])):
        if item.get("verified") is not True:
            continue
        name = item.get("name")
        weight = item.get("weight_percent")
        page_number = item.get("page_number")
        quote = item.get("source_quote")
        if (
            not isinstance(name, str) or not name.strip()
            or type(weight) is not int or not 0 <= weight <= 100
            or type(page_number) is not int or page_number < 1
            or not isinstance(quote, str) or not quote.strip()
        ):
            continue
        aliases = [name] + [
            a for a in item.get("aliases", []) if isinstance(a, str)
        ]
        if not any(
            _phrase(a) and f" {_phrase(a)} " in question_words for a in aliases
        ):
            continue
        page = next(
            (p for p in doc.get("pages", [])
             if p.get("page_number") == page_number),
            None,
        )
        if page is None:
            continue
        clean_quote = " ".join(quote.split())
        if clean_quote not in " ".join(page.get("text", "").split()):
            continue
        # Require the assessment and its weight to be adjacent in the quote.
        # This rejects using the attendance percentage for a final project.
        item_name = r"\s+".join(re.escape(part) for part in name.split())
        association = (
            rf"(?<![\w.]){weight}\s*%\s*{item_name}(?!\w)"
            rf"|(?<!\w){item_name}\s+{weight}(?![\d.%])"
        )
        if not re.search(association, clean_quote, re.IGNORECASE):
            continue
        matches.append({
            "chunk_id": f"{document_id}_grading_{index}",
            "document_id": document_id,
            "title": doc["title"],
            "text": clean_quote,
            "url": doc.get("url"),
            "category": "course",
            "source_type": "syllabus",
            "course_code": course_code,
            "term_code": str(term_code),
            "section_label": doc.get("section_label"),
            "source_file": doc.get("source_file"),
            "page_number": page_number,
            "grading_fact": {
                "name": name.strip(),
                "weight_percent": weight,
                "verified": True,
            },
        })

    return matches[0] if len(matches) == 1 else None
