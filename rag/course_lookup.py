"""Exact semester-specific course lookups and conservative historical fallback."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COURSES_DIR = ROOT / "data" / "courses"

COURSE_PATTERN = re.compile(r"\b([A-Z]{2,5})[\s-]*(\d{3}[A-Z]?)\b", re.IGNORECASE)


def extract_course_codes(question):
    """Identify and normalize course codes in the question."""
    matches = COURSE_PATTERN.findall(question)
    return list(dict.fromkeys(f"{prefix.upper()} {number.upper()}" for prefix, number in matches))


def _load_course(course_code, term_code, path):
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    for course in data.get("courses", []):
        if course.get("course_code", "").upper() == course_code.upper():
            return {
                **course,
                "term_code": str(term_code),
                # Point to the course page associated with the actual source term.
                "source_url": f"https://classes.usc.edu/term/{term_code}/course/{course_code.replace(' ', '')}",
                "collected_at": data.get("collected_at"),
            }
    return None


def lookup_course(course_code, term_code):
    """Look up a course only in the requested term, preserving existing behavior."""
    term_code = str(term_code)
    return _load_course(course_code, term_code, COURSES_DIR / f"ee_{term_code}.json")


def lookup_course_history(course_code, requested_term):
    """Return the latest stored OTHER term's record, if available.

    Never infer that a class is fall-only or will be offered again. If the
    requested term's dataset is missing, make that limitation explicit.
    """
    requested_term = str(requested_term)
    # Collected course snapshots use a term code in the filename.
    files = sorted(COURSES_DIR.glob("ee_*.json"), reverse=True)
    requested_term_checked = (COURSES_DIR / f"ee_{requested_term}.json").is_file()
    for path in files:
        match = re.fullmatch(r"ee_(\d+)\.json", path.name)
        if not match or match.group(1) >= requested_term:
            continue
        term = match.group(1)
        record = _load_course(course_code, term, path)
        if record is not None:
            record["requested_term_checked"] = requested_term_checked
            return record
    return None


if __name__ == "__main__":
    question = input("Ask a course question: ")
    for code in extract_course_codes(question):
        course = lookup_course(code, "20271")
        print(course or f"No stored record found for {code} in 20271.")
