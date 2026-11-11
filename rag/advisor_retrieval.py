"""Single routing entry point for USC advising retrieval.

Retrieval algorithms live in course_lookup.py and retrieve.py.  The backend
should use retrieve_for_advisor() instead of deciding routes independently.
"""
import re

from rag.course_lookup import extract_course_codes, lookup_course, lookup_course_history

DEFAULT_TERM = "20271"

EXACT_LOOKUP_PATTERN = re.compile(
    r"\b(prerequisites?|pre[- ]?reqs?|corequisites?|co[- ]?reqs?|units?|"
    r"requirements?|restrictions?|who teaches|instructors?|course description|"
    r"offered|offering|available|availability|schedule|sections?)\b",
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


def choose_retrieval_method(question):
    """Return 'exact', 'policy', or 'course' for a student question.

    A course code only selects exact lookup for a structured-fact question.
    Other code-containing questions remain course discovery queries.
    """
    codes = extract_course_codes(question)
    if codes and EXACT_LOOKUP_PATTERN.search(question):
        return "exact"
    if codes:
        return "course"
    if POLICY_PATTERN.search(question):
        return "policy"
    if COURSE_PATTERN.search(question):
        return "course"
    return "general"


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

    if method == "exact":
        results = []
        for code in extract_course_codes(question):
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
