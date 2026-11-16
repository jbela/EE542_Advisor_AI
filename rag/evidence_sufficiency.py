"""Conservative evidence-sufficiency checks for academic advising."""

import re


def classify_evidence(question, results):
    """
    Classify whether retrieved evidence supports an advising decision.

    This does not grant approvals or determine student eligibility.
    """

    q = question.lower()
    results = results or []

    if re.search(
        r"\b(guaranteed|guarantee)\b",
        q
    ):
        return {
            "decision_status": "no_enrollment_guarantee",
            "evidence_sufficient": False,
            "reason": (
                "Course prerequisites do not establish "
                "guaranteed enrollment."
            )
        }

    if re.search(
        r"\b(substitute|substitution|transfer credit|"
        r"equivalency|waive|waiver)\b",
        q
    ):
        return {
            "decision_status": "advisor_verification_required",
            "evidence_sufficient": False,
            "reason": (
                "A substitution or waiver decision requires "
                "verification by an authorized USC office."
            )
        }

    if re.search(
        r"\b(which|what)\s+courses?\s+should\s+i\s+take\b",
        q
    ):
        return {
            "decision_status": "student_context_required",
            "evidence_sufficient": False,
            "missing_information": [
                "degree_program",
                "completed_courses",
                "academic_interests",
                "intended_semester"
            ]
        }

    if re.search(
        r"\b(will|definitely|guaranteed)\b.*"
        r"\b(offered|available|listed)\b",
        q
    ):
        if not any(
            r.get("availability_status") == "listed"
            and r.get("requested_term_checked") is True
            for r in results
        ):
            return {
                "decision_status": "future_availability_unconfirmed",
                "evidence_sufficient": False,
                "reason": (
                    "No collected official listing confirms "
                    "availability for the requested semester."
                )
            }

    if not results:
        return {
            "decision_status": "course_not_found",
            "evidence_sufficient": False,
            "reason": "No matching verified course evidence was retrieved."
        }

    return {
        "decision_status": "evidence_available",
        "evidence_sufficient": True
    }
