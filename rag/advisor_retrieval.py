import re

from rag.course_lookup import (
    extract_course_codes,
    lookup_course
)


# Questions that explicitly request information about a course.
EXACT_LOOKUP_PATTERN = re.compile(
    r"\b(prerequisites?|corequisites?|units?|"
    r"requirements?|restrictions?|"
    r"who teaches|course description)\b",
    re.IGNORECASE
)


def choose_retrieval_method(question):
    """Choose exact lookup or hybrid search."""

    codes = extract_course_codes(question)

    if codes and EXACT_LOOKUP_PATTERN.search(question):
        return "exact"

    return "hybrid"


def retrieve_for_advisor(
    question,
    term_code="20271",
    top_k=5
):
    """Retrieve evidence for an academic advising question."""

    method = choose_retrieval_method(question)

    if method == "exact":
        codes = extract_course_codes(question)

        results = []

        for code in codes:
            course = lookup_course(code, term_code)

            if course:
                results.append({
                    "retrieval_method": "exact",
                    "course_code": course["course_code"],
                    "title": course["title"],
                    "term_code": course["term_code"],
                    "description": course.get("description"),
                    "prerequisites": course.get(
                        "prerequisites_display"
                    ),
                    "corequisites": course.get(
                        "corequisites_display"
                    ),
                    "units": course.get("units"),
                    "source_url": course["source_url"]
                })

        return results

    # Import lazily to avoid loading the embedding model
    # when exact lookup is sufficient.
    from rag.retrieve import retrieve

    results = retrieve(
        question,
        top_k=top_k,
        category="course",
        term_code=term_code
    )

    return [
        {
            "retrieval_method": "hybrid",
            **result
        }
        for result in results
    ]


if __name__ == "__main__":
    question = input("Ask a USC advising question: ")

    results = retrieve_for_advisor(question)

    for result in results:
        print("\n" + "=" * 50)
        print(result)
