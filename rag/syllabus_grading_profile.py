"""Load source-validated grading profiles for any imported syllabus."""

import json
import re

from rag.syllabus_grading import SYLLABI_DIR, GRADING_DIR
from ingestion.review_syllabus_facts import (
    validate_candidate,
    validate_policy_candidate,
)


def get_verified_grading_profile(course_code, term_code):
    documents = []

    for path in SYLLABI_DIR.glob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))

        if (
            document.get("course_code") == course_code
            and str(document.get("term_code")) == str(term_code)
        ):
            documents.append(document)

    if len(documents) != 1:
        return None

    document = documents[0]
    document_id = document.get("id", "")

    if not re.fullmatch(r"[A-Za-z0-9_-]+", document_id):
        return None

    reviewed_path = GRADING_DIR / f"{document_id}.json"

    if not reviewed_path.is_file():
        return None

    reviewed = json.loads(
        reviewed_path.read_text(encoding="utf-8")
    )

    if (
        reviewed.get("document_id") != document_id
        or reviewed.get("source_file_hash") != document.get("file_hash")
        or not document.get("file_hash")
    ):
        return None

    items = reviewed.get("items", [])
    policies = reviewed.get("policies", [])

    if not isinstance(items, list) or not isinstance(policies, list):
        return None

    verified_items = []

    for item in items:
        if not isinstance(item, dict):
            return None

        if item.get("verified") is not True:
            return None

        candidate = {
            **item,
            "type": "assessment_weight",
        }

        if not validate_candidate(candidate, document):
            return None

        verified_items.append({
            "name": item["name"],
            "weight_percent": item["weight_percent"],
            "page_number": item["page_number"],
            "source_quote": item["source_quote"],
        })

    verified_policies = []

    for policy in policies:
        if not isinstance(policy, dict):
            return None

        if policy.get("verified") is not True:
            return None

        if not validate_policy_candidate(policy, document):
            return None

        verified_policies.append({
            "type": policy["type"],
            "page_number": policy["page_number"],
            "source_quote": policy["source_quote"],
        })

    if not verified_items and not verified_policies:
        return None

    return {
        "document_id": document_id,
        "course_code": course_code,
        "term_code": str(term_code),
        "title": document["title"],
        "instructor": document.get("instructor"),
        "section_label": document.get("section_label"),
        "source_file": document.get("source_file"),
        "url": document.get("url"),
        "items": verified_items,
        "policies": verified_policies,
    }
