"""Normalize Teammate 1's retrieval results for FastAPI and Ollama."""
import json
import re

from rag.course_lookup import extract_course_codes

TERM_CODE = "20271"  # Change to the semester covered by the collected data.
MAX_CHARS = 1800

# These words signal structured course facts, handled by exact lookup.
EXACT_WORDS = re.compile(
    r"\b(prerequisites?|corequisites?|units?|restrictions?|who teaches|course description)\b",
    re.IGNORECASE,
)


def normalize(doc, method):
    """Convert exact-course and hybrid-search results to one common schema."""
    if method == "exact":
        parts = [
            f"Course: {doc.get('course_code', '')}",
            f"Title: {doc.get('title', '')}",
            f"Term: {doc.get('term_code', '')}",
        ]
        for key in ("description", "prerequisites", "corequisites", "units"):
            value = doc.get(key)
            if value is not None and value != "":
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                parts.append(f"{key.capitalize()}: {value}")
        text = "\n".join(parts)
        return {
            "id": f"{doc.get('term_code', '')}_{doc.get('course_code', '')}",
            "title": doc.get("title", "Course record"),
            "text": text[:MAX_CHARS],
            "url": doc.get("source_url"),
            "category": "course",
            "term_code": doc.get("term_code"),
            "retrieval_method": "exact",
        }

    return {
        "id": doc.get("chunk_id") or doc.get("document_id"),
        "title": doc.get("title", "USC source"),
        "text": str(doc.get("text", ""))[:MAX_CHARS],
        "url": doc.get("url"),
        "category": doc.get("category"),
        "term_code": doc.get("term_code"),
        "retrieval_method": "hybrid",
    }


def get_context(question, term_code=TERM_CODE, top_k=5):
    """Retrieve evidence. Import vector search only when it is needed."""
    codes = extract_course_codes(question)
    if codes and EXACT_WORDS.search(question):
        from rag.course_lookup import lookup_course

        matches = [lookup_course(code, term_code) for code in codes]
        # Do not substitute semantically similar courses for an exact course code.
        return [normalize(course, "exact") for course in matches if course][:top_k]

    from rag.retrieve import retrieve

    # A specific course code or a course-discovery question is course-focused.
    # Otherwise search every category, including policy and shared pages.
    course_words = re.search(
        r"\b(courses?|classes|syllab(?:us|i)|topics?|curriculum)\b",
        question,
        re.IGNORECASE,
    )
    category = "course" if codes or course_words else None
    results = retrieve(question, top_k=top_k, category=category, term_code=term_code)
    return [normalize(doc, "hybrid") for doc in results if doc.get("text")]
