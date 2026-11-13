"""Convert unified RAG results into clear, source-aware LLM evidence.

All retrieval decisions remain in rag.advisor_retrieval.
"""
import json

from rag.advisor_retrieval import DEFAULT_TERM, retrieve_for_advisor

MAX_CHARS = 1800


def _value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def format_requirement(value):
    """Keep complex prerequisite logic intact; clarify simple relationships."""
    if isinstance(value, dict):
        courses = value.get("courses")
        operator = value.get("operator")
        if isinstance(courses, list) and courses and all(isinstance(c, str) for c in courses):
            if len(courses) == 1 and operator in (None, "SINGLE", "AND", "OR"):
                return courses[0]
            if operator == "AND":
                return " AND ".join(courses) + " (all listed courses required)"
            if operator == "OR":
                return " OR ".join(courses) + " (one of the listed courses required)"
        return _value(value)

    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
        return value[0]
    return _value(value)


def format_term(code):
    code = str(code or "")
    if len(code) == 5 and code.isdigit():
        season = {"1": "Spring", "2": "Summer", "3": "Fall"}.get(code[-1])
        if season:
            return f"{season} {code[:4]}"
    return code or "unspecified semester"


def _course_record(doc, method="exact"):
    term = str(doc.get("term_code") or "")
    requested = str(doc.get("requested_term") or term)
    historical = bool(doc.get("historical", term != requested))
    checked = bool(doc.get("requested_term_checked", True))
    code = doc.get("course_code") or ""
    title = doc.get("title") or "Course record"

    parts = [f"Course: {code}", f"Title: {title}",
             f"Source semester: {format_term(term)}"]
    if historical:
        if checked:
            parts.append(
                f"NOTICE: This course was not found in the collected "
                f"{format_term(requested)} records. The information below "
                f"comes from {format_term(term)}. Historical requirements may "
                "have changed; future availability is not confirmed."
            )
        else:
            parts.append(
                f"NOTICE: No course dataset was collected for {format_term(requested)}. "
                f"The information below comes from {format_term(term)}; "
                "current requirements and availability are unverified."
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
        elif value not in (None, "", []):
            parts.append(f"{label}: {_value(value)}")

    verification = doc.get("prerequisite_verification")
    if isinstance(verification, dict):
        parts.append("Prerequisite verification status: " + str(verification.get("status", "unknown")))
        if verification.get("source"):
            parts.append("Prerequisite verification method: " + str(verification["source"]))
        if verification.get("source_text"):
            parts.append("Verified source excerpt: " + str(verification["source_text"]))
        if verification.get("source_url"):
            parts.append("Prerequisite verification URL: " + str(verification["source_url"]))

    return {
        "id": f"{term}_{code}",
        "title": f"{code} - {title}",
        "text": "\n".join(parts)[:MAX_CHARS],
        "url": (verification or {}).get("source_url") if isinstance(verification, dict) and verification.get("status") == "verified" else doc.get("source_url"),
        "category": "course",
        "course_code": code,
        "term_code": term,
        "requested_term": requested,
        "historical": historical,
        "requested_term_checked": checked,
        "retrieval_method": method,
        "prerequisite_verification": verification,
    }


def normalize(doc):
    """Normalize exact and hybrid retrieval results."""
    method = doc.get("retrieval_method", "hybrid")
    if method == "exact":
        return _course_record(doc, "exact")

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


def normalize_special(doc):
    """Present non-text retrieval outcomes without inventing course facts."""
    method = doc.get("retrieval_method")
    term = str(doc.get("term_code") or "")
    requested = str(doc.get("requested_term") or term)
    code = doc.get("course_code") or ""
    checked = bool(doc.get("requested_term_checked", False))
    source = doc.get("source_url")

    if method in ("availability", "history", "comparison"):
        status = doc.get("availability_status")
        comparison_status = doc.get("comparison_status")

        if status == "listed":
            result = _course_record(doc, method)
            result["text"] += (
                f"\nAvailability: Listed in collected {format_term(term)} EE records. "
                "Listing does not confirm open seats, registration clearance, or future offerings."
            )
            return result

        if method == "history":
            result = _course_record(doc, method)
            terms = doc.get("available_terms") or []
            if terms:
                result["text"] += "\nCollected offering semesters: " + ", ".join(format_term(t) for t in terms)
            result["text"] += "\nThese are collected historical listings, not proof of a future offering."
            return result

        if method == "comparison" and comparison_status is None and term:
            result = _course_record(doc, method)
            result["text"] += "\nComparison evidence: This is one semester's record. Compare it with the other retrieved term before drawing conclusions."
            return result

        if status == "not_listed":
            text = f"{code} is not listed in the collected {format_term(term)} EE course records. This does not prove it will never be offered."
        elif status == "term_not_collected":
            text = f"EE course records for {format_term(term)} have not been collected. Course availability cannot be verified."
            source = None
        elif comparison_status == "terms_required":
            text = doc.get("message") or "Please specify two semesters to compare."
            source = None
        elif comparison_status == "missing":
            if checked:
                text = f"{code} was not found in the collected {format_term(term)} EE records."
            else:
                text = f"No EE dataset is available for {format_term(term)}; comparison is unavailable."
                source = None
        else:
            raise ValueError(f"Unexpected {method} result: {doc}")

        return {
            "id": f"{method}_{term}_{code}",
            "title": f"{code} - {format_term(term)}" if code else "Academic information",
            "text": text[:MAX_CHARS],
            "url": source,
            "category": "course",
            "course_code": code or None,
            "term_code": term,
            "requested_term": requested,
            "historical": bool(doc.get("historical", False)),
            "requested_term_checked": checked,
            "retrieval_method": method,
        }

    if method == "historical_catalog":
        status = doc.get("status")
        if status == "term_not_collected":
            text = f"EE course records for {format_term(term)} have not been collected. No course list can be verified."
            source = None
        elif status == "collected":
            courses = doc.get("courses") or []
            count = doc.get("course_count", len(courses))
            lines = [f"{c.get('course_code')}: {c.get('title')}" for c in courses[:15]]
            text = f"Collected EE course catalog for {format_term(term)}: {count} records.\n" + "\n".join(lines)
            if len(courses) > 15:
                text += "\nOnly the first 15 are shown; this is not the complete list."
        else:
            raise ValueError(f"Unexpected historical catalog status: {status}")
        return {
            "id": f"catalog_{term}",
            "title": f"EE course catalog - {format_term(term)}",
            "text": text[:MAX_CHARS],
            "url": source,
            "category": "course",
            "course_code": None,
            "term_code": term,
            "requested_term": term,
            "historical": True,
            "retrieval_method": method,
        }

    raise ValueError(f"Unsupported special retrieval method: {method}")


def get_context(question, term_code=DEFAULT_TERM, top_k=5):
    """Use the one canonical router, then translate each supported result."""
    results = retrieve_for_advisor(question, term_code=term_code, top_k=top_k)
    evidence = []
    for doc in results:
        method = doc.get("retrieval_method", "hybrid")
        if method in ("exact", "hybrid"):
            item = normalize(doc)
            if method == "hybrid":
                item["requested_term"] = str(term_code or DEFAULT_TERM)
        elif method in ("availability", "history", "comparison", "historical_catalog"):
            item = normalize_special(doc)
        else:
            raise ValueError(f"Unsupported retrieval method: {method}")
        if item and item.get("text"):
            evidence.append(item)
    return evidence
