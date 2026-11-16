"""Conservative evaluation of verified course prerequisites."""

import re


def normalize_course_code(code):
    if not isinstance(code, str):
        return None

    match = re.fullmatch(
        r"\s*([A-Za-z]{2,5})\s*[- ]?\s*(\d{3}[A-Za-z]?)\s*",
        code,
    )

    if not match:
        return None

    return f"{match.group(1).upper()} {match.group(2).upper()}"



def evaluate_group(group, completed, not_completed=None):
    """Evaluate prerequisites using three-valued logic."""

    if not_completed is None:
        not_completed = set()

    if not isinstance(group, dict):
        return "unknown"

    operator = group.get("operator")

    if operator == "UNVERIFIED":
        return "unknown"

    children = group.get("groups")

    if operator in ("AND", "OR") and isinstance(children, list):
        if not children:
            return "unknown"

        outcomes = [
            evaluate_group(child, completed, not_completed)
            for child in children
        ]

        if operator == "AND":
            if "not_satisfied" in outcomes:
                return "not_satisfied"
            if all(x == "satisfied" for x in outcomes):
                return "satisfied"
            return "unknown"

        required = group.get("required_courses", 1)

        if (
            type(required) is not int
            or not 1 <= required <= len(outcomes)
        ):
            return "unknown"

        satisfied = outcomes.count("satisfied")
        possible = satisfied + outcomes.count("unknown")

        if satisfied >= required:
            return "satisfied"
        if possible < required:
            return "not_satisfied"
        return "unknown"

    courses = group.get("courses")

    if not isinstance(courses, list) or not courses:
        return "unknown"

    normalized = [
        normalize_course_code(code)
        for code in courses
    ]

    if any(code is None for code in normalized):
        return "unknown"

    if len(set(normalized)) != len(normalized):
        return "unknown"

    outcomes = []

    for code in normalized:
        if code in completed:
            outcomes.append("satisfied")
        elif code in not_completed:
            outcomes.append("not_satisfied")
        else:
            outcomes.append("unknown")

    if operator == "SINGLE":
        if len(outcomes) != 1:
            return "unknown"
        return outcomes[0]

    if operator == "AND":
        if "not_satisfied" in outcomes:
            return "not_satisfied"
        if all(x == "satisfied" for x in outcomes):
            return "satisfied"
        return "unknown"

    if operator == "OR":
        required = group.get("required_courses", 1)

        if (
            type(required) is not int
            or not 1 <= required <= len(outcomes)
        ):
            return "unknown"

        satisfied = outcomes.count("satisfied")
        possible = satisfied + outcomes.count("unknown")

        if satisfied >= required:
            return "satisfied"
        if possible < required:
            return "not_satisfied"
        return "unknown"

    return "unknown"


def evaluate_prerequisites(
    prerequisites,
    completed_courses,
    verification=None,
    not_completed_courses=None,
):
    """Evaluate verified prerequisites without assuming missing facts."""

    if not isinstance(verification, dict):
        return "unknown"

    if verification.get("status") != "verified":
        return "unknown"

    if not isinstance(completed_courses, (set, list, tuple)):
        return "unknown"

    if not_completed_courses is None:
        not_completed_courses = set()

    if not isinstance(not_completed_courses, (set, list, tuple)):
        return "unknown"

    completed = {
        normalize_course_code(code)
        for code in completed_courses
    }

    incomplete = {
        normalize_course_code(code)
        for code in not_completed_courses
    }

    if None in completed or None in incomplete:
        return "unknown"

    if completed & incomplete:
        return "unknown"

    return evaluate_group(prerequisites, completed, incomplete)

def extract_course_statuses(question):
    """Extract course completion from narrowly supported statements.

    Returns None for unsupported or ambiguous wording.
    Never treats an unmentioned course as incomplete.
    """

    if not isinstance(question, str):
        return None

    text = question.upper().replace("’", "'")

    code_pattern = r"[A-Z]{2,5}\s*[- ]?\s*\d{3}[A-Z]?"

    # Accept only an explicit first-person completion statement.
    start = re.search(
    r"\b(?:IF\s+)?I(?:'VE| HAVE)?\s+COMPLETED\s+",
    text,
    )

    if not start:
        return None

    # Reject questions such as "Have I completed EE 503?"
    # and unsupported wording before the completion statement.
    prefix = text[:start.start()].strip()

    if prefix:
        return None

    
    statement = text[start.end():]

    # Stop before a follow-up question about the scenario.
    statement = re.split(
        r",?\s+(?:HAVE I SATISFIED|DO I SATISFY|"
        r"CAN I TAKE|AM I ELIGIBLE|DO I MEET)\b",
        statement,
        maxsplit=1,
    )[0]

    # Stop at a sentence or question boundary.
    statement = re.split(
        r"[?.!]",
        statement,
        maxsplit=1,
    )[0]

    statement = statement.strip().rstrip(",")


    # Separate explicitly incomplete courses.
    negative = re.search(
        r"\bBUT\s+(?:NOT|I\s+HAVEN'T\s+COMPLETED|"
        r"I\s+HAVE\s+NOT\s+COMPLETED)\b",
        statement,
    )

    if negative:
        positive_text = statement[:negative.start()]
        negative_text = statement[negative.end():]
    else:
        positive_text = statement
        negative_text = ""

    # Reject unsupported negation or additional completion clauses.
    if re.search(
        r"\b(?:NOT|HAVEN'T|DIDN'T|WITHOUT|EXCEPT)\b",
        positive_text,
    ):
        return None

    # Only allow course codes, commas, AND/OR, and whitespace.
    def parse_codes(value):
        codes = re.findall(code_pattern, value)

        if not codes:
            return set() if not value.strip() else None

        remainder = re.sub(code_pattern, " ", value)
        remainder = re.sub(r"\b(?:AND|OR)\b", " ", remainder)
        remainder = re.sub(r"[,\s]", "", remainder)

        if remainder:
            return None

        return {
            normalize_course_code(code)
            for code in codes
        }

    completed = parse_codes(positive_text)
    incomplete = parse_codes(negative_text)

    if completed is None or incomplete is None:
        return None

    if not completed or None in completed or None in incomplete:
        return None

    if completed & incomplete:
        return None

    return {
        "completed": completed,
        "not_completed": incomplete,
    }


