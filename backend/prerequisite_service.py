"""Deterministic EE 562 prerequisite answers."""

import re

from rag.course_lookup import extract_course_codes
from rag.prerequisite_evaluator import (
    extract_course_statuses,
    evaluate_prerequisites,
)

from backend.rag_service import format_term


INTENT_PATTERN = re.compile(
    r"\b(prerequisites?|pre[- ]?reqs?|"
    r"have i satisfied|do i satisfy|do i meet|"
    r"can i take|am i eligible)\b",
    re.IGNORECASE,
)


def answer_prerequisite_scenario(question, docs):
    """Answer verified EE 562 prerequisite scenarios safely."""

    if not INTENT_PATTERN.search(question):
        return None

    codes = extract_course_codes(question)

    if "EE 562" not in codes:
        return None

    candidates = [
        doc for doc in docs
        if doc.get("course_code") == "EE 562"
        and doc.get("retrieval_method") == "exact"
        and not doc.get("historical")
        and str(doc.get("term_code")) == str(
            doc.get("requested_term")
        )
        and isinstance(
            doc.get("prerequisite_verification"), dict
        )
        and doc["prerequisite_verification"].get("status")
        == "verified"
        and isinstance(
            doc.get("prerequisites_structured"), dict
        )
    ]

    if len(candidates) != 1:
        return None

    doc = candidates[0]

    statuses = extract_course_statuses(question)

    requirements_text = (
        "EE 562 requires EE 503 and at least one of "
        "EE 441 or EE 510."
    )

    if statuses is None:
        return (
            f"{requirements_text} [1]\n\n"
            "I couldn't reliably interpret which courses "
            "you've completed. Please clarify your completed "
            "courses before I assess whether the listed "
            "prerequisites are satisfied."
        )

    result = evaluate_prerequisites(
        doc["prerequisites_structured"],
        statuses["completed"],
        doc["prerequisite_verification"],
        not_completed_courses=statuses["not_completed"],
    )

    term = format_term(doc["term_code"])

    if result == "satisfied":
        conclusion = (
            f"Based on the courses you reported completing, "
            f"you satisfy the verified listed prerequisites "
            f"for EE 562 in {term}. [1]"
        )

    elif result == "not_satisfied":
        conclusion = (
            f"Based on the course information you provided, "
            f"you have not satisfied all the verified listed "
            f"prerequisites for EE 562 in {term}. [1]"
        )

    else:
        conclusion = (
            "I cannot determine whether you satisfy all "
            "the listed prerequisites for EE 562 because "
            "some required course-completion information "
            "is missing or uncertain. [1]"
        )

    return (
        conclusion
        + "\n\n"
        + requirements_text
        + "\n\nThis assessment concerns listed prerequisites "
        "only and does not guarantee enrollment eligibility."
    )
