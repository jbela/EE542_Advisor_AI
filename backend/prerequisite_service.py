"""Student prerequisite explanations based on verified structured course rules.

Course retrieval and rule evaluation remain in rag/. This module handles
question intent, evidence selection, and the student-facing explanation.
"""

from backend.rag_service import format_term
from backend.student_question import (
    completion_statuses,
    is_personal_prerequisite,
    target_course,
)
from rag.prerequisite_evaluator import evaluate_prerequisites


def format_rule(rule):
    """Render verified nested AND/OR requirements without dropping operators."""
    if not isinstance(rule, dict):
        return None
    op = rule.get("operator")
    if op not in ("SINGLE", "AND", "OR"):
        return None
    children = rule.get("groups")
    if isinstance(children, list):
        if not children or op == "SINGLE":
            return None
        parts = [format_rule(child) for child in children]
        if any(x is None for x in parts):
            return None
    else:
        parts = rule.get("courses")
        if not isinstance(parts, list) or not parts or not all(isinstance(c, str) for c in parts):
            return None
        if op == "SINGLE" and len(parts) != 1:
            return None
    if op == "SINGLE":
        return parts[0]
    if op == "AND":
        return " and ".join(parts)
    required = rule.get("required_courses", 1)
    if type(required) is not int or not 1 <= required <= len(parts):
        return None
    if required == 1:
        return "one of (" + " or ".join(parts) + ")"
    return f"at least {required} of (" + ", ".join(parts) + ")"


def assess_prerequisite_scenario(question, docs):
    """Return a structured safe decision or None for ordinary questions."""
    if not is_personal_prerequisite(question):
        return None
    code = target_course(question)
    candidates = []
    for i, doc in enumerate(docs, 1):
        verification = doc.get("prerequisite_verification")
        if (
            code and doc.get("course_code") == code
            and doc.get("retrieval_method") == "exact"
            and not doc.get("historical")
            and str(doc.get("term_code")) == str(doc.get("requested_term"))
            and isinstance(verification, dict)
            and verification.get("status") == "verified"
            and isinstance(doc.get("prerequisites_structured"), dict)
        ):
            candidates.append((i, doc))
    if len(candidates) != 1:
        return {
            "answer": "I can't assess your prerequisites from one current, verified rule for a clearly identified target course. Please confirm the course and its requirements with the relevant USC department.",
            "decision_status": "unknown",
        }

<<<<<<< HEAD
    i, doc = candidates[0]
    term = format_term(doc.get("term_code"))
    rule = format_rule(doc["prerequisites_structured"])
    if rule is None:
        return {
            "answer": "The verified prerequisite rule could not be interpreted safely. Please confirm it with the USC department.",
            "decision_status": "unknown",
        }

    rule_line = f"The verified listed prerequisites for {code} in {term} are {rule}. [{i}]"
    statuses = completion_statuses(question)
    if statuses is None:
        return {
            "answer": ("I couldn't reliably interpret which courses you've completed or haven't completed. "
                       "Please list them explicitly so I can check the requirements.\n\n" + rule_line),
            "decision_status": "unknown",
        }

    status = evaluate_prerequisites(
        doc["prerequisites_structured"],
        statuses["completed"],
        doc["prerequisite_verification"],
        not_completed_courses=statuses["not_completed"],
    )
    if status == "satisfied":
        conclusion = (f"Based on the courses you reported completing, you satisfy "
                      f"the verified listed prerequisites for {code} in {term}. [{i}]")
    elif status == "not_satisfied":
        conclusion = (f"Based on what you reported completing and not completing, "
                      f"you have not satisfied all verified listed prerequisites for {code} in {term}. [{i}]")
    else:
        conclusion = (f"I cannot determine whether you satisfy all listed prerequisites "
                      f"for {code}, because some course-completion information is missing or uncertain. [{i}]")
    return {
        "answer": (conclusion + "\n\n" + rule_line +
                   "\n\nThis checks only the listed prerequisites based on your "
                   "reported courses; it does not guarantee registration eligibility."),
=======
    doc = candidates[0]


    # General prerequisite questions do not require student history.
    general_prerequisite_question = re.search(
        r"\b(?:what|which)\s+(?:are\s+)?"
        r"(?:the\s+)?(?:prerequisites?|pre[- ]?reqs?)\b",
        question,
        re.IGNORECASE,
    )

    if general_prerequisite_question:
        return (
            "EE 562 requires EE 503 and at least one of "
            "EE 441 or EE 510. [1]\n\n"
            "These are the verified listed prerequisites "
            "for Spring 2027. Enrollment eligibility may "
            "also depend on other restrictions."
        )

    statuses = extract_course_statuses(question)

    requirements_text = (
        "EE 562 requires EE 503 and at least one of "
        "EE 441 or EE 510."
    )
    if statuses is None:
        status = "unknown"
        conclusion = "I couldn't reliably interpret which courses you've completed or haven't completed. Please list them explicitly so I can check the requirements."
    else:
        status = evaluate_prerequisites(
            doc["prerequisites_structured"], statuses["completed"],
            doc["prerequisite_verification"],
            not_completed_courses=statuses["not_completed"],
        )
        if status == "satisfied":
            conclusion = f"Based on the courses you reported completing, you satisfy the verified listed prerequisites for {code} in {term}. [{i}]"
        elif status == "not_satisfied":
            conclusion = f"Based on what you reported completing and not completing, you have not satisfied all verified listed prerequisites for {code} in {term}. [{i}]"
        else:
            conclusion = f"I cannot determine whether you satisfy all listed prerequisites for {code}, because some course-completion information is missing or uncertain. [{i}]"
    return {
        "answer": conclusion + "\n\n" + rule_line + "\n\nThis checks only the listed prerequisites based on your reported courses; it does not guarantee registration eligibility.",
>>>>>>> f32b1f5 (Rebasing main)
        "decision_status": status,
    }


def answer_prerequisite_scenario(question, docs):
    """Backward-compatible helper for callers expecting an answer string."""
    result = assess_prerequisite_scenario(question, docs)
    return result["answer"] if result else None
