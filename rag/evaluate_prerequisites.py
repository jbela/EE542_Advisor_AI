
"""Evaluate prerequisite evidence without guessing AND/OR relationships."""

import json
from pathlib import Path

from rag.advisor_retrieval import retrieve_for_advisor

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_FILE = ROOT / "tests" / "retrieval_questions_v2.json"

EXPECTED_TARGETS = {
    "Q09": "EE 597",
    "Q10": "EE 597",
    "Q11": "EE 542",
    "Q12": "EE 542",
    "Q13": "EE 535",
    "Q14": "EE 557",
    "Q15": "EE 597",
    "Q16": "EE 542",
}

EXPECTED_FIELDS = {
    "Q09": "prerequisites",
    "Q10": "prerequisites",
    "Q11": "prerequisites",
    "Q12": "recommended_preparation",
    "Q13": "corequisites",
    "Q14": "prerequisites",
    "Q15": "prerequisites",
    "Q16": "recommended_preparation",
}


def extract_courses(value):
    if not isinstance(value, dict):
        return set()

    courses = set(value.get("courses", []))

    for group in value.get("groups", []):
        courses.update(group.get("courses", []))

    return courses


def main():
    questions = json.loads(
        QUESTIONS_FILE.read_text(encoding="utf-8")
    )

    selected = [
        q for q in questions
        if q["category"] == "prerequisites"
    ]

    passed = 0
    unverified = 0

    print("=" * 65)
    print("USC ADVISOR AI - PREREQUISITE EVIDENCE EVALUATION")
    print("=" * 65)

    for q in selected:
        results = retrieve_for_advisor(
            q["question"],
            term_code=q.get("term_code", "20271"),
            top_k=5
        )

        target = EXPECTED_TARGETS[q["id"]]
        field = EXPECTED_FIELDS[q["id"]]

        primary = results[0] if results else {}

        target_correct = primary.get("course_code") == target
        value = primary.get(field)

        field_present = value is not None and value != ""

        operator = (
            value.get("operator")
            if isinstance(value, dict)
            else None
        )

        relationship_unverified = operator == "UNVERIFIED"

        success = target_correct and field_present

        passed += int(success)
        unverified += int(relationship_unverified)

        print(
            f"{q['id']}: "
            f"{'PASS' if success else 'FAIL'} "
            f"target={primary.get('course_code')} "
            f"field={field} "
            f"operator={operator}"
        )

    print("\n" + "=" * 65)
    print(f"Questions: {len(selected)}")
    print(f"Target + field checks passed: {passed}/{len(selected)}")
    print(f"Unverified relationships: {unverified}")
    print("=" * 65)


if __name__ == "__main__":
    main()
