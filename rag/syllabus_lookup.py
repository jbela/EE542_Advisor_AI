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