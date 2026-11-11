"""Translate the unified RAG router's records into LLM-ready source passages.

Routing belongs exclusively to rag.advisor_retrieval.  Do not duplicate
question classification or direct lookup in this module.
"""
import json

from rag.advisor_retrieval import DEFAULT_TERM, retrieve_for_advisor

MAX_CHARS = 1800


def _value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def format_requirement(value):
    if isinstance(value, dict):
        courses = value.get("courses")

        if isinstance(courses, list) and len(courses) == 1:
            if isinstance(courses[0], str):
                return courses[0]

        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], str):
            return value[0]

        return json.dumps(value, ensure_ascii=False)

    return str(value)


def format_term(code):
    code = str(code)

    if len(code) != 5 or not code.isdigit():
        return code

    year = code[:4]
    semester = {
        "1": "Spring",
        "2": "Summer",
        "3": "Fall"
    }.get(code[-1])

    if semester:
        return f"{semester} {year}"

    return code

def normalize(doc):
    """Normalize exact-course and hybrid results to a common evidence schema."""
    method = doc.get("retrieval_method", "hybrid")
    if method == "exact":
        term = str(doc.get("term_code") or "")
        requested = str(doc.get("requested_term") or term)
        historical = bool(doc.get("historical", term != requested))
        checked = bool(doc.get("requested_term_checked", True))
        parts = [
            f"Course: {doc.get('course_code', '')}",
            f"Title: {doc.get('title') or ''}",
            f"Source semester: {format_term(term)}"
        ]

        if historical:
            if checked:
                parts.append(
                    f"NOTICE: This course was not found in the collected "
                    f"{format_term(requested)} records. "
                    f"The information below comes from {format_term(term)}. "
                    "Historical requirements may have changed, and future "
                    "course availability is not confirmed."
                )
            else:
                parts.append(
                    f"NOTICE: No course dataset is available for "
                    f"{format_term(requested)}. "
                    f"The information below comes from {format_term(term)}. "
                    "Current requirements and availability are not verified."
                )

        for label, key in [
            ("Description", "description"),
            ("Prerequisites", "prerequisites"),
            ("Corequisites", "corequisites"),
            ("Units", "units"),
            ("Restrictions", "restrictions"),
            ("Recommended preparation", "recommended_preparation"),
        ]:
            value = doc.get(key)

            if key in ("prerequisites", "corequisites"):
                if value == []:
                    parts.append(f"{label}: None listed in source record")
                elif value is None:
                    parts.append(f"{label}: Not specified in source record")
                else:
                    parts.append(f"{label}: {format_requirement(value)}")
            elif value is not None and value != "" and value != []:
                parts.append(f"{label}: {_value(value)}")

        result = {
            "id": f"{term}_{doc.get('course_code', '')}",
            "title": f"{doc.get('course_code', '')} - {doc.get('title') or 'Course record'}",
            "text": "\n".join(parts)[:MAX_CHARS],
            "url": doc.get("source_url"),
            "category": "course", "course_code": doc.get("course_code"),
            "term_code": term, "requested_term": requested,
            "historical": historical, "requested_term_checked": checked,
            "retrieval_method": "exact",
        }
        return result

    return {
        "id": doc.get("chunk_id") or doc.get("document_id"),
        "title": doc.get("title", "USC source"),
        "text": str(doc.get("text", ""))[:MAX_CHARS],
        "url": doc.get("url"),
        "category": doc.get("category"),
        "course_code": doc.get("course_code"),
        "term_code": doc.get("term_code"),
        "requested_term": doc.get("term_code"),
        "historical": False,
        "retrieval_method": "hybrid",
    }


def get_context(question, term_code=DEFAULT_TERM, top_k=5):
    """Call the one canonical router and normalize its evidence."""
    results = retrieve_for_advisor(question, term_code=term_code, top_k=top_k)
    evidence = [normalize(result) for result in results
                if result.get("retrieval_method") == "exact" or result.get("text")]
    for item in evidence:
        if item["retrieval_method"] == "hybrid":
            item["requested_term"] = str(term_code or DEFAULT_TERM)
    return evidence
