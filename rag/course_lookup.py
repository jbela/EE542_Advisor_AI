import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COURSES_DIR = ROOT / "data" / "courses"

COURSE_PATTERN = re.compile(
    r"\b([A-Z]{2,5})[\s-]*(\d{3}[A-Z]?)\b",
    re.IGNORECASE
)


def extract_course_codes(question):
    """Identify course codes mentioned in a question."""

    matches = COURSE_PATTERN.findall(question)

    return list(dict.fromkeys(
        f"{prefix.upper()} {number.upper()}"
        for prefix, number in matches
    ))


def lookup_course(course_code, term_code):
    """Retrieve a course directly from stored USC data."""

    path = COURSES_DIR / f"ee_{term_code}.json"

    if not path.exists():
        return None

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    for course in data["courses"]:
        if course.get("course_code", "").upper() == course_code.upper():
            return {
                **course,
                "term_code": str(term_code),
                "source_url": (
                    f"https://classes.usc.edu/term/{term_code}/"
                    f"course/{course_code.replace(' ', '')}"
                ),
                "collected_at": data.get("collected_at")
            }

    return None


if __name__ == "__main__":
    question = input("Ask a course question: ")

    codes = extract_course_codes(question)

    if not codes:
        print("No explicit course code found.")

    for code in codes:
        course = lookup_course(code, "20271")

        if course:
            print(f"\nCourse: {course['course_code']}")
            print(f"Title: {course['title']}")
            print(
                "Prerequisites:",
                course.get("prerequisites_display")
            )
            print("Source:", course["source_url"])
        else:
            print(f"No stored record found for {code}.")
