"""Exact semester-specific USC course lookups and historical fallback."""

import json
import re
from pathlib import Path

from ingestion.verified_requirements import apply_verified_requirements


ROOT = Path(__file__).resolve().parents[1]
COURSES_DIR = ROOT / "data" / "courses"

COURSE_PATTERN = re.compile(
    r"\b([A-Z]{2,5})[\s-]*(\d{3}[A-Z]?)\b",
    re.IGNORECASE
)


def extract_course_codes(question):
    """Identify and normalize course codes in a question."""

    matches = COURSE_PATTERN.findall(question)

    return list(
        dict.fromkeys(
            f"{prefix.upper()} {number.upper()}"
            for prefix, number in matches
        )
    )


def _load_course(course_code, term_code, path):
    """
    Load a course from a specific semester.

    Apply semester-specific verified requirements
    without modifying the original USC dataset.
    """

    if not path.is_file():
        return None

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    for course in data.get("courses", []):
        if (
            course.get("course_code", "").upper()
            != course_code.upper()
        ):
            continue

        record = {
            **course,
            "term_code": str(term_code),
            "source_url": (
                f"https://classes.usc.edu/term/{term_code}/"
                f"course/{course_code.replace(' ', '')}"
            ),
            "collected_at": data.get("collected_at")
        }

        return apply_verified_requirements(
            record,
            term_code
        )

    return None


def lookup_course(course_code, term_code):
    """Look up a course only in the requested semester."""

    term_code = str(term_code)

    path = COURSES_DIR / f"ee_{term_code}.json"

    return _load_course(
        course_code,
        term_code,
        path
    )


def lookup_course_history(course_code, requested_term):
    """
    Find the latest collected earlier offering.

    Never use a future semester as historical evidence.
    """

    requested_term = str(requested_term)

    requested_path = (
        COURSES_DIR / f"ee_{requested_term}.json"
    )

    requested_term_checked = requested_path.is_file()

    files = sorted(
        COURSES_DIR.glob("ee_*.json"),
        reverse=True
    )

    for path in files:
        match = re.fullmatch(
            r"ee_(\d+)\.json",
            path.name
        )

        if not match:
            continue

        term_code = match.group(1)

        if int(term_code) >= int(requested_term):
            continue

        record = _load_course(
            course_code,
            term_code,
            path
        )

        if record is not None:
            record["requested_term_checked"] = (
                requested_term_checked
            )

            return record

    return None


def find_course_offerings(course_code, max_term=None):
    """
    Return all collected offerings of a course.

    Results are ordered from newest to oldest.
    Optionally exclude semesters after max_term.
    """

    offerings = []

    for path in COURSES_DIR.glob("ee_*.json"):
        match = re.fullmatch(
            r"ee_(\d+)\.json",
            path.name
        )

        if not match:
            continue

        term_code = match.group(1)

        if (
            max_term is not None
            and int(term_code) > int(max_term)
        ):
            continue

        record = _load_course(
            course_code,
            term_code,
            path
        )

        if record is not None:
            offerings.append(record)

    offerings.sort(
        key=lambda item: int(item["term_code"]),
        reverse=True
    )

    return offerings


def get_term_collection_status(term_code):
    """Check whether a semester's EE data exists locally."""

    term_code = str(term_code)

    path = COURSES_DIR / f"ee_{term_code}.json"

    if not path.is_file():
        return {
            "term_code": term_code,
            "status": "term_not_collected",
            "course_count": None
        }

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    return {
        "term_code": term_code,
        "status": "collected",
        "course_count": len(
            data.get("courses", [])
        )
    }


if __name__ == "__main__":
    question = input("Ask a course question: ")

    codes = extract_course_codes(question)

    if not codes:
        print("No course code found in the question.")

    for code in codes:
        course = lookup_course(code, "20271")

        if course is None:
            course = lookup_course_history(
                code,
                "20271"
            )

        if course is None:
            print(
                f"No stored record found for {code}."
            )
            continue

        print("\n" + "=" * 50)
        print(f"Course: {course.get('course_code')}")
        print(f"Title: {course.get('title')}")
        print(f"Source semester: {course.get('term_code')}")
        print(
            f"Prerequisites: "
            f"{course.get('prerequisites_display')}"
        )
        print(
            f"Verification: "
            f"{course.get('prerequisite_verification')}"
        )
        print(f"Source: {course.get('source_url')}")
