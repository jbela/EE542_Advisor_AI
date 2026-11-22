"""Build source-grounded grading comparisons without an LLM."""

from rag.syllabus_grading_profile import get_verified_grading_profile


POLICY_LABELS = {
    "threshold_adjustment": "Grade threshold adjustments",
    "participation_adjustment": "Participation adjustments",
    "late_penalty": "Late submission policy",
    "grade_dispute": "Grade dispute procedure",
}

def format_policy_text(text):
    """Normalize policy text for display without changing source evidence."""
    import re

    text = " ".join(str(text).split())

    text = re.sub(
        r"^(?:Late Policy|Grade Adjustment)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip()

def format_term(term_code):
    term = str(term_code)
    seasons = {"1": "Spring", "2": "Summer", "3": "Fall"}

    if len(term) != 5 or term[-1] not in seasons:
        return term

    return f"{seasons[term[-1]]} {term[:4]}"


def compare_grading_profiles(course_codes, term_code):
    if len(course_codes) < 2:
        return None

    profiles = []

    for course in dict.fromkeys(course_codes):
        profile = get_verified_grading_profile(
            course,
            term_code,
        )

        if profile is None:
            return None

        profiles.append(profile)

    if len(profiles) < 2:
        return None

    lines = [
        f"Grading policy comparison for {format_term(term_code)}:",
    ]

    sources = []

    for index, profile in enumerate(profiles, start=1):
        course = profile["course_code"]

        lines.append(f"\n### {course}")

        lines.append("\n**Grading weights**")

        for item in profile["items"]:
            lines.append(
                f"- {item['name']}: {item['weight_percent']}%"
            )

        lines.append("\n**Documented grading policies**")

        if profile["policies"]:
            for policy in profile["policies"]:
                label = POLICY_LABELS.get(
                    policy["type"],
                    policy["type"].replace("_", " ").title(),
                )

                policy_text = format_policy_text(
                    policy["source_quote"]
                )

                lines.append(
                    f"- {label}: {policy_text}"
                )
        else:
            lines.append(
                "- No additional grading policies have been "
                "verified in the reviewed records."
            )

        lines.append(f"\nSource: [{index}]")

        pages = [
            item["page_number"]
            for item in (
                profile["items"] + profile["policies"]
            )
        ]

        sources.append({
            "id": profile["document_id"],
            "document_id": profile["document_id"],
            "title": profile["title"],
            "url": profile.get("url"),
            "category": "course",
            "source_type": "syllabus",
            "course_code": course,
            "term_code": profile["term_code"],
            "instructor": profile.get("instructor"),
            "section_label": profile.get("section_label"),
            "source_file": profile.get("source_file"),
            "page_number": min(pages) if pages else None,
        })

    lines.append(
        "\n**Note:** This comparison includes reviewed grading "
        "information from the specified semester's syllabi. "
        "An unlisted policy does not necessarily mean "
        "that the policy does not exist."
    )

    return {
        "answer": "\n".join(lines),
        "sources": sources,
        "status": "review_required",
    }
