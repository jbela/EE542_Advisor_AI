"""Evaluate factual prerequisite retrieval against benchmark labels."""

import json
import re
from pathlib import Path

from rag.advisor_retrieval import retrieve_for_advisor

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_FILE = ROOT / "tests" / "retrieval_questions_v2.json"

EXPECTED = {
    "Q09": {
        "course": "EE 597",
        "term": "20271",
        "prerequisites": ("AND", {"EE 450", "EE 503"}),
    },
    "Q10": {
        "course": "EE 597",
        "term": "20271",
        "prerequisites": ("AND", {"EE 450", "EE 503"}),
    },
    "Q11": {
        "course": "EE 542",
        "term": "20263",
        "prerequisites": ("SINGLE", {"EE 450"}),
    },
    "Q12": {
        "course": "EE 542",
        "term": "20263",
        "preparation_codes": {"EE 457"},
        "preparation_terms": {"c++"},
    },
    "Q13": {
        "course": "EE 535",
        "term": "20271",
        "corequisites": ("SINGLE", {"EE 503"}),
    },
    "Q14": {
        "course": "EE 557",
        "term": "20271",
        "prerequisites": ("SINGLE", {"EE 457"}),
    },
    "Q15": {
        "course": "EE 597",
        "term": "20271",
        "prerequisites": ("AND", {"EE 450", "EE 503"}),
    },
    "Q16": {
        "course": "EE 542",
        "term": "20263",
        "prerequisites": ("SINGLE", {"EE 450"}),
        "preparation_codes": {"EE 457"},
        "preparation_terms": {"c++"},
    },
     "Q41": {
        "course": "EE 562",
        "term": "20271",
        "prerequisites": ("AND", {"EE 503", "EE 441", "EE 510"}),
    },
    "Q42": {
        "course": "EE 562",
        "term": "20271",
        "prerequisites": ("AND", {"EE 503", "EE 441", "EE 510"}),
    },
    "Q43": {
        "course": "EE 562",
        "term": "20271",
        "prerequisites": ("AND", {"EE 503", "EE 441", "EE 510"}),
    },
    "Q44": {
        "course": "EE 562",
        "term": "20271",
        "prerequisites": ("AND", {"EE 503", "EE 441", "EE 510"}),
    },
}


def requirement_codes(value):
    """Extract course codes from a structured requirement."""

    if not isinstance(value, dict):
        return set()

    codes = set(value.get("courses") or [])

    for group in value.get("groups") or []:
        codes.update(requirement_codes(group))

    return codes


def check_requirement(value, expected):
    operator, codes = expected

    return (
        isinstance(value, dict)
        and value.get("operator") == operator
        and requirement_codes(value) == codes
    )


def check_preparation(text, codes, terms):
    if not isinstance(text, str):
        return False

    normalized = text.lower()

    found_codes = {
        f"{prefix.upper()} {number.upper()}"
        for prefix, number in re.findall(
            r"\b([A-Z]{2,5})[\s-]*(\d{3}[A-Z]?)\b",
            text,
            re.IGNORECASE,
        )
    }

    return (
        found_codes == codes
        and all(term in normalized for term in terms)
    )

def check_ee562_structure(value):
    if not isinstance(value, dict):
        return False

    if value.get("operator") != "AND":
        return False

    groups = value.get("groups")

    if not isinstance(groups, list) or len(groups) != 2:
        return False

    mandatory, alternative = groups

    return (
        mandatory.get("operator") == "SINGLE"
        and mandatory.get("courses") == ["EE 503"]
        and alternative.get("operator") == "OR"
        and set(alternative.get("courses", []))
        == {"EE 441", "EE 510"}
        and alternative.get("required_courses") == 1
    )

def evaluate_question(question, results):
    expected = EXPECTED[question["id"]]
    primary = results[0] if results else {}

    checks = {
        "target": primary.get("course_code") == expected["course"],
        "term": str(primary.get("term_code")) == expected["term"],
        "route": primary.get("retrieval_method") == "exact",
    }

    if "prerequisites" in expected:
        checks["prerequisites"] = check_requirement(
            primary.get("prerequisites"),
            expected["prerequisites"],
        )

    if "corequisites" in expected:
        checks["corequisites"] = check_requirement(
            primary.get("corequisites"),
            expected["corequisites"],
        )

    if "preparation_codes" in expected:
        checks["preparation"] = check_preparation(
            primary.get("recommended_preparation"),
            expected["preparation_codes"],
            expected["preparation_terms"],
        )

        # Recommended preparation must not be treated as mandatory.
        prereq_codes = requirement_codes(
            primary.get("prerequisites")
        )
        checks["preparation_separate"] = not bool(
            prereq_codes & expected["preparation_codes"]
        )

    if question["id"] in {"Q41", "Q42", "Q43", "Q44"}:
        checks["nested_structure"] = check_ee562_structure(
            primary.get("prerequisites")
        )

    return checks


def main():
    questions = json.loads(
        QUESTIONS_FILE.read_text(encoding="utf-8")
    )

    selected = [
        q for q in questions
        if q["category"] == "prerequisites"
    ]

    passed = 0

    print("=" * 65)
    print("USC ADVISOR AI - FACTUAL PREREQUISITE EVALUATION")
    print("=" * 65)

    for q in selected:
        results = retrieve_for_advisor(
            q["question"],
            term_code=q.get("term_code", "20271"),
            top_k=5,
        )

        checks = evaluate_question(q, results)
        success = all(checks.values())
        passed += int(success)

        failures = [
            name for name, ok in checks.items()
            if not ok
        ]

        print(
            f"{q['id']}: {'PASS' if success else 'FAIL'} "
            f"checks={checks}"
        )

        if failures:
            print(f"  Failed checks: {failures}")

    print("\n" + "=" * 65)
    print(f"Questions evaluated: {len(selected)}")
    print(f"Passed: {passed}/{len(selected)}")
    print(f"Accuracy: {passed / len(selected):.3f}")
    print("=" * 65)


if __name__ == "__main__":
    main()
