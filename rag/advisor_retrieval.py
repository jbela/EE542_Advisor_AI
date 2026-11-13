"""Single routing entry point for USC advising retrieval.

Retrieval algorithms live in course_lookup.py and retrieve.py.  The backend
should use retrieve_for_advisor() instead of deciding routes independently.
"""
import re
from rag.course_lookup import get_term_collection_status
from rag.syllabus_lookup import find_syllabus_term

from rag.course_lookup import (
    extract_course_codes,
    find_course_offerings,
    lookup_course,
    lookup_course_history,
    COURSES_DIR,
)

DEFAULT_TERM = "20271"


HISTORICAL_CATALOG_PATTERN = re.compile(
    r"\b(what|which|list|show|find)\b.*"
    r"\b(courses?|classes)\b.*"
    r"\b(offered|available|listed|scheduled)\b",
    re.IGNORECASE,
)

SEMESTER_PATTERN = re.compile(
    r"\b(Spring|Summer|Fall)\s+(20\d{2})\b",
    re.IGNORECASE,
)


def extract_semester(question):
    matches = SEMESTER_PATTERN.findall(question)

    if len(matches) != 1:
        return None

    season, year = matches[0]

    season_codes = {
        "spring": "1",
        "summer": "2",
        "fall": "3",
    }

    return year + season_codes[season.lower()]


EXACT_LOOKUP_PATTERN = re.compile(
    r"\b(prerequisites?|pre[- ]?reqs?|corequisites?|co[- ]?reqs?|"
    r"units?|requirements?|restrictions?|who teaches|instructors?|"
    r"course description|offered|offering|available|availability|"
    r"schedule|sections?|recommended preparation|"
    r"preparation|prepare|before taking|need to take|"
    r"need to complete|completed|enroll|enrollment|"
    r"eligible|eligibility|need both|need either|"
    r"last offered|most recent listing)\b",
    re.IGNORECASE,
)

# Prefer policies for university-wide questions that are not about a named course.
POLICY_PATTERN = re.compile(
    r"\b(policy|policies|visa|immigration|ois|international student|"
    r"registration|register|d[- ]?clearance|waiver|exception|"
    r"degree requirements?|graduation requirements?|academic standing|"
    r"leave of absence|reduced course load|deadline|tuition|"
    r"academic calendar|student services)\b",
    re.IGNORECASE,
)

COURSE_PATTERN = re.compile(
    r"\b(courses?|classes|syllab(?:us|i)|topics?|curriculum|"
    r"instructors?|prerequisites?|corequisites?|electives?)\b",
    re.IGNORECASE,
)


COMPARISON_PATTERN = re.compile(
    r"\b(compare|comparison|difference|different|"
    r"changed|change between|versus|vs\.?)\b",
    re.IGNORECASE,
)

AVAILABILITY_PATTERN = re.compile(
    r"\b(offered|offering|available|availability|"
    r"scheduled|listed|sections?)\b",
    re.IGNORECASE,
)

HISTORY_PATTERN = re.compile(
    r"\b(last offered|most recent listing|"
    r"previously offered|course history)\b",
    re.IGNORECASE,
)

ENROLLMENT_PATTERN = re.compile(
    r"\b(can i enroll|can i take|am i eligible|"
    r"do i need|have i completed|"
    r"need both|need either)\b",
    re.IGNORECASE,
)


def choose_retrieval_method(question):
    """
    Route academic advising questions by intent.

    Returns:
        exact: specific course facts
        availability: course offering questions
        history: previous course offerings
        comparison: compare course records
        policy: university policy questions
        course: course discovery
        general: general academic questions
    """

    codes = extract_course_codes(question)

    if (
        not codes
        and HISTORICAL_CATALOG_PATTERN.search(question)
        and extract_semester(question)
    ):
        return "historical_catalog"

    if codes:
        q = question.lower()

        if (
            ("last known" in q or "last available" in q)
            and (
                "requirements" in q
                or "prerequisites" in q
                or "show" in q
            )
        ):
            return "history"

        if re.search(
            r"\b(can i take|can i enroll|is .* offered|"
            r"is .* listed|is .* available)\b",
            q
        ) and not re.search(
            r"\b(if i completed|if i have completed|"
            r"without|prerequisites?)\b",
            q
        ):
            return "availability"

        if (
            "difference between" in q
            and "prerequisite" in q
            and "recommended preparation" in q
        ):
            return "exact"

    if codes:
        if COMPARISON_PATTERN.search(question):
            return "comparison"

        if HISTORY_PATTERN.search(question):
            return "history"

        if AVAILABILITY_PATTERN.search(question):
            return "availability"

        if ENROLLMENT_PATTERN.search(question):
            return "exact"

        if EXACT_LOOKUP_PATTERN.search(question):
            return "exact"

        return "course"

    if POLICY_PATTERN.search(question):
        return "policy"

    if COURSE_PATTERN.search(question):
        return "course"

    return "general"


def _course_evidence(course, requested_term, method="exact"):
    return {
        "retrieval_method": method,
        "course_code": course.get("course_code"),
        "title": course.get("title"),
        "term_code": str(course.get("term_code")),
        "requested_term": str(requested_term),
        "historical": str(course.get("term_code")) != str(requested_term),
        "requested_term_checked": (
            COURSES_DIR / f"ee_{requested_term}.json"
        ).is_file(),
        "description": course.get("description"),
        "prerequisites": course.get("prerequisites_display"),
        "corequisites": course.get("corequisites_display"),
        "units": course.get("units"),
        "restrictions": course.get("restrictions"),
        "recommended_preparation": course.get("recommended_preparation"),
        "source_url": course.get("source_url"),
        "prerequisite_verification": course.get("prerequisite_verification"),
    }

def _availability_evidence(code, term_code):
    checked = (COURSES_DIR / f"ee_{term_code}.json").is_file()
    course = lookup_course(code, term_code) if checked else None

    if course:
        result = _course_evidence(course, term_code, "availability")
        result["availability_status"] = "listed"
        return result

    return {
        "retrieval_method": "availability",
        "course_code": code,
        "term_code": str(term_code),
        "requested_term": str(term_code),
        "requested_term_checked": checked,
        "historical": False,
        "availability_status": (
            "not_listed" if checked else "term_not_collected"
        ),
        "source_url": (
            f"https://classes.usc.edu/term/{term_code}/"
            "catalogue/school/ENGV/program/EE"
        ),
    }

def _history_evidence(code, term_code):
    offerings = find_course_offerings(code, max_term=term_code)

    if not offerings:
        return []

    return [
        {
            **_course_evidence(course, term_code, "history"),
            "available_terms": [
                item["term_code"] for item in offerings
            ],
        }
        for course in offerings
    ]

def _comparison_evidence(code, term_code, question):
    term_names = {
        "Spring": "1",
        "Summer": "2",
        "Fall": "3",
    }

    matches = re.findall(
        r"\b(Spring|Summer|Fall)\s+(20\d{2})\b",
        question,
        re.IGNORECASE,
    )

    terms = []

    for season, year in matches:
        season_digit = term_names[season.capitalize()]
        code_term = f"{year}{season_digit}"

        if code_term not in terms:
            terms.append(code_term)

    if len(terms) != 2:
        return [{
            "retrieval_method": "comparison",
            "course_code": code,
            "comparison_status": "terms_required",
            "message": "Please specify two semesters to compare.",
        }]

    results = []

    for selected_term in terms:
        course = lookup_course(code, selected_term)

        if course:
            results.append(
                _course_evidence(
                    course,
                    selected_term,
                    "comparison"
                )
            )
        else:
            results.append({
                "retrieval_method": "comparison",
                "course_code": code,
                "term_code": selected_term,
                "requested_term": selected_term,
                "comparison_status": "missing",
                "requested_term_checked": (
                    COURSES_DIR / f"ee_{selected_term}.json"
                ).is_file(),
            })

    return results


def prioritize_course_codes(question):
    """Order mentioned courses by likely question target."""

    codes = extract_course_codes(question)

    if len(codes) <= 1:
        return codes

    patterns = [
        r"\b(?:for|of|about)\s+([A-Z]{2,5})[\s-]*(\d{3}[A-Z]?)\b",
        r"\b(?:take|enroll in|taking)\s+([A-Z]{2,5})[\s-]*(\d{3}[A-Z]?)\b",
    ]

    for pattern in patterns:
        matches = re.findall(
            pattern,
            question,
            re.IGNORECASE
        )

        if matches:
            prefix, number = matches[-1]
            target = f"{prefix.upper()} {number.upper()}"

            if target in codes:
                return [target] + [
                    code for code in codes
                    if code != target
                ]

    return codes


def retrieve_for_advisor(question, term_code=DEFAULT_TERM, top_k=5):
    """Return raw retrieved evidence with route and term provenance.

    Historical fallback is only used when exact current-term lookup fails.
    It never treats a historical listing as confirmation of current offering.
    Missing current-term datasets are explicitly marked as not checked.
    """
    if top_k < 1:
        return []
    term_code = str(term_code or DEFAULT_TERM)
    method = choose_retrieval_method(question)

    if method == "historical_catalog":
        requested = extract_semester(question)

        status = get_term_collection_status(requested)

        if status["status"] == "term_not_collected":
            return [{
                "retrieval_method": "historical_catalog",
                "term_code": requested,
                "status": "term_not_collected",
                "course_count": None,
                "message": (
                    f"Course records for term {requested} "
                    "have not been collected. "
                    "This does not establish which courses "
                    "USC offered that semester."
                )
            }]

        import json

        path = COURSES_DIR / f"ee_{requested}.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        return [{
            "retrieval_method": "historical_catalog",
            "term_code": requested,
            "status": "collected",
            "course_count": len(data.get("courses", [])),
            "courses": [
                {
                    "course_code": c.get("course_code"),
                    "title": c.get("title")
                }
                for c in data.get("courses", [])
            ],
            "source_url": (
                f"https://classes.usc.edu/term/{requested}/"
                "catalogue/school/ENGV/program/EE"
            )
        }]


    codes = extract_course_codes(question)

    # Explicit syllabus questions use imported course documents.
    if (
        len(codes) == 1
        and re.search(r"\bsyllab(?:us|i)\b", question, re.IGNORECASE)
        and method not in (
            "availability",
            "history",
            "comparison",
        )
    ):
        explicit_term = extract_semester(question)

        selected_term = find_syllabus_term(
            codes[0],
            requested_term=explicit_term,
            max_term=term_code,
        )

        if selected_term is None:
            return []

        from rag.retrieve import retrieve

        results = retrieve(
            question,
            top_k=top_k,
            category="course",
            term_code=selected_term,
            source_type="syllabus",
            course_codes=codes,
        )

        return [
            {
                **result,
                "retrieval_method": "hybrid",
                "requested_term": explicit_term or term_code,
                "historical": (
                    selected_term != (explicit_term or term_code)
                ),
            }
            for result in results
        ]

    if method == "availability":
        return [
            _availability_evidence(code, term_code)
            for code in codes[:top_k]
        ]

    if method == "history":
        results = []

        for code in codes:
            results.extend(
                _history_evidence(code, term_code)
            )

        return results[:top_k]

    if method == "comparison":
        results = []

        for code in codes:
            results.extend(
                _comparison_evidence(code, term_code, question)
            )

        return results[:top_k]

    if method == "exact":
        results = []
        for code in prioritize_course_codes(question):
            course = lookup_course(code, term_code)
            if course is None:
                course = lookup_course_history(code, term_code)
            if course is None:
                continue
            results.append({
                "retrieval_method": "exact",
                "course_code": course.get("course_code", code),
                "title": course.get("title"),
                "term_code": course.get("term_code"),
                "requested_term": term_code,
                "historical": course.get("term_code") != term_code,
                "requested_term_checked": course.get("requested_term_checked", True),
                "description": course.get("description"),
                "prerequisites": course.get("prerequisites_display"),
                "corequisites": course.get("corequisites_display"),
                "units": course.get("units"),
                "restrictions": course.get("restrictions"),
                "recommended_preparation": course.get("recommended_preparation"),
                "source_url": course.get("source_url"),
                "prerequisite_verification": course.get("prerequisite_verification"),
            })
            if len(results) >= top_k:
                break
        return results

    # Lazy import: exact lookups work without loading FAISS or embeddings.
    from rag.retrieve import retrieve

    category = "course" if method == "course" else None
    # Policy sources have several categories (graduate, international, shared),
    # so exclude courses rather than requiring one specific policy category.
    results = retrieve(question, top_k=top_k, category=category,
                       term_code=term_code,
                       exclude_category="course" if method == "policy" else None)
    return [{"retrieval_method": "hybrid", **r} for r in results]


if __name__ == "__main__":
    question = input("Ask a USC advising question: ")
    for result in retrieve_for_advisor(question):
        print("\n" + "=" * 50)
        print(result)
