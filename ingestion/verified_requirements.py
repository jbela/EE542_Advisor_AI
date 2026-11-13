"""Load semester-specific verified course requirements."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIED_DIR = ROOT / "data" / "verified_requirements"


def load_verified_requirements(term_code):
    path = VERIFIED_DIR / f"ee_{term_code}.json"

    if not path.is_file():
        return {}

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if str(data.get("term_code")) != str(term_code):
        raise ValueError(
            "Verified requirements term mismatch"
        )

    return data.get("courses", {})


def apply_verified_requirements(course, term_code):
    verified = load_verified_requirements(term_code)

    course_code = course.get("course_code")

    if course_code not in verified:
        return course

    override = verified[course_code]

    result = dict(course)

    result["prerequisites_display"] = override[
        "prerequisites_display"
    ]

    result["prerequisite_verification"] = {
        "status": override["verification_status"],
        "source": override["verification_source"],
        "source_url": override["source_url"],
        "source_text": override.get("source_text")
    }

    return result
