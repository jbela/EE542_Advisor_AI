"""Find available syllabus semesters from imported documents."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYLLABI_DIR = ROOT / "data" / "processed" / "syllabi"


def find_syllabus_term(
    course_code,
    requested_term=None,
    max_term=None,
):
    terms = set()

    for path in sorted(SYLLABI_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))

        if data.get("course_code") != course_code:
            continue

        term = str(data["term_code"])

        if requested_term is not None:
            if term != str(requested_term):
                continue
        elif max_term is not None:
            if int(term) > int(max_term):
                continue

        terms.add(term)

    return max(terms, key=int) if terms else None


def syllabus_availability(course_code, requested_term):
    """Return whether a specific syllabus has been imported."""

    if not isinstance(requested_term, str):
        requested_term = str(requested_term)

    matching = []

    for path in sorted(SYLLABI_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))

        if data.get("course_code") != course_code:
            continue

        matching.append({
            "term_code": str(data["term_code"]),
            "section": data.get("section_label", "Unspecified"),
        })

    available_terms = sorted({
        item["term_code"] for item in matching
    })

    exact_matches = [
        item for item in matching
        if item["term_code"] == requested_term
    ]

    return {
        "course_code": course_code,
        "requested_term": requested_term,
        "available": bool(exact_matches),
        "available_terms": available_terms,
        "sections": [
            item["section"] for item in exact_matches
        ],
    }
