"""Review extracted syllabus grading candidates before publication."""

import argparse
import json
import os
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYLLABI_DIR = ROOT / "data" / "processed" / "syllabi"
CANDIDATES_DIR = ROOT / "data" / "processed" / "syllabi_candidates"
REVIEWED_DIR = ROOT / "data" / "syllabus_poc" / "reviewed_grading"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(value):
    return " ".join(str(value).split())


def validate_candidate(candidate, document):
    if candidate.get("type") != "assessment_weight":
        return False

    name = candidate.get("name")
    source_label = candidate.get("source_label", name)
    weight = candidate.get("weight_percent")
    page_number = candidate.get("page_number")
    quote = candidate.get("source_quote")

    if (
        not isinstance(name, str) or not name.strip()
        or not isinstance(source_label, str) or not source_label.strip()
        or type(weight) is not int or not 0 <= weight <= 100
        or type(page_number) is not int or page_number < 1
        or not isinstance(quote, str) or not quote.strip()
    ):
        return False

    page = next(
        (
            p for p in document.get("pages", [])
            if p.get("page_number") == page_number
        ),
        None,
    )

    if page is None:
        return False

    clean_quote = normalize_text(quote)
    clean_page = normalize_text(page.get("text", ""))

    if clean_quote not in clean_page:
        return False

    label_pattern = r"\s+".join(
        re.escape(part) for part in source_label.split()
    )

    association = (
        rf"(?<![\w.]){weight}\s*%\s*{label_pattern}(?!\w)"
        rf"|(?<!\w){label_pattern}\s*:\s*{weight}\s*%(?!\w)"
        rf"|(?<!\w){label_pattern}\s+{weight}(?![\d.%])"
    )

    return bool(
        re.search(association, clean_quote, re.IGNORECASE)
    )


POLICY_TYPES = {
    "late_penalty",
    "grade_dispute",
    "threshold_adjustment",
    "participation_adjustment",
}


def validate_policy_candidate(candidate, document):
    if candidate.get("type") not in POLICY_TYPES:
        return False

    page_number = candidate.get("page_number")
    quote = candidate.get("source_quote")

    if (
        type(page_number) is not int
        or page_number < 1
        or not isinstance(quote, str)
        or not quote.strip()
    ):
        return False

    page = next(
        (
            p for p in document.get("pages", [])
            if p.get("page_number") == page_number
        ),
        None,
    )

    if page is None:
        return False

    clean_quote = normalize_text(quote)
    clean_page = normalize_text(page.get("text", ""))

    if clean_quote not in clean_page:
        return False

    return True


def fact_identity(item):
    label = item.get("source_label") or item.get("name", "")

    return (
        normalize_text(label).lower(),
        item.get("page_number"),
    )


def policy_identity(policy):
    return (
        policy.get("type"),
        policy.get("page_number"),
        normalize_text(
            policy.get("source_quote", "")
        ).lower(),
    )


def save_reviewed_atomic(output_path, reviewed):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps(
        reviewed,
        indent=2,
        ensure_ascii=False,
    )

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=".review_",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)

        os.replace(temporary_path, output_path)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def review_policy_candidates(candidates, document):
    approved = []

    for index, policy in enumerate(candidates, start=1):
        print("\n" + "-" * 60)
        print(f"Policy candidate {index}")
        print("Course:", document["course_code"])
        print("Semester:", document["term_code"])
        print("Type:", policy.get("type"))
        print("Page:", policy.get("page_number"))
        print("Source:", policy.get("source_quote"))

        if not validate_policy_candidate(policy, document):
            print("INVALID: Policy source validation failed.")
            continue

        decision = input(
            "Approve [a], reject [r], skip [s], cancel [q]: "
        ).strip().lower()

        if decision == "q":
            return None

        if decision != "a":
            continue

        approved.append({
            "type": policy["type"],
            "page_number": policy["page_number"],
            "source_quote": policy["source_quote"],
            "verified": True,
        })

    return approved



def review_document(document_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", document_id):
        raise ValueError("Invalid document ID.")

    candidate_path = CANDIDATES_DIR / f"{document_id}.json"
    document_path = (
        SYLLABI_DIR
        / f"{document_id.removeprefix('syllabus_')}.json"
    )
    output_path = REVIEWED_DIR / f"{document_id}.json"

    if not candidate_path.is_file():
        raise FileNotFoundError(candidate_path)

    if not document_path.is_file():
        raise FileNotFoundError(document_path)

    candidates = load_json(candidate_path)
    document = load_json(document_path)

    if (
        candidates.get("document_id") != document.get("id")
        or candidates.get("source_file_hash") != document.get("file_hash")
        or not document.get("file_hash")
    ):
        raise ValueError(
            "Candidate data does not match the source document."
        )

    existing_items = []
    existing_policies = []

    if output_path.exists():
        existing = load_json(output_path)

        if (
            existing.get("document_id") != document["id"]
            or existing.get("source_file_hash") != document["file_hash"]
        ):
            raise ValueError(
                "Existing reviewed facts do not match the syllabus."
            )

        existing_items = existing.get("items", [])
        existing_policies = existing.get("policies", [])

        if (
            not isinstance(existing_items, list)
            or not isinstance(existing_policies, list)
        ):
            raise ValueError("Invalid existing reviewed data.")

        for item in existing_items:
            if (
                not isinstance(item, dict)
                or item.get("verified") is not True
                or not validate_candidate(
                    {**item, "type": "assessment_weight"},
                    document,
                )
            ):
                raise ValueError(
                    "Existing grading fact failed validation."
                )

        for policy in existing_policies:
            if (
                not isinstance(policy, dict)
                or policy.get("verified") is not True
                or not validate_policy_candidate(policy, document)
            ):
                raise ValueError(
                    "Existing policy failed validation."
                )

    approved_items = []

    for index, item in enumerate(candidates.get("items", []), start=1):
        print("\n" + "-" * 60)
        print(f"Candidate {index}")
        print("Course:", document["course_code"])
        print("Semester:", document["term_code"])
        print("Assessment:", item.get("name"))
        print("Weight:", item.get("weight_percent"))
        print("Page:", item.get("page_number"))
        print("Source:", item.get("source_quote"))

        if not validate_candidate(item, document):
            print("INVALID: Source validation failed.")
            continue

        decision = input(
            "Approve [a], reject [r], skip [s], cancel [q]: "
        ).strip().lower()

        if decision == "q":
            print("\nReview cancelled. No changes saved.")
            return

        if decision != "a":
            continue

        name = input(
            f"Canonical name [{item['name']}]: "
        ).strip() or item["name"]

        aliases_text = input(
            "Aliases (comma-separated, optional): "
        ).strip()

        aliases = [
            alias.strip()
            for alias in aliases_text.split(",")
            if alias.strip()
        ]

        approved_items.append({
            "name": name,
            "source_label": item.get(
                "source_label",
                item["name"],
            ),
            "aliases": aliases,
            "weight_percent": item["weight_percent"],
            "page_number": item["page_number"],
            "source_quote": item["source_quote"],
            "verified": True,
        })

    approved_policies = review_policy_candidates(
        candidates.get("policies", []),
        document,
    )

    if approved_policies is None:
        print("\nReview cancelled. No changes saved.")
        return

    merged_items = list(existing_items)
    merged_policies = list(existing_policies)

    item_keys = {}

    for item in existing_items:
        key = fact_identity(item)

        if key in item_keys:
            raise ValueError("Duplicate existing grading fact.")

        item_keys[key] = item

    policy_keys = set()

    for policy in existing_policies:
        key = policy_identity(policy)

        if key in policy_keys:
            raise ValueError("Duplicate existing policy.")

        policy_keys.add(key)

    item_additions = 0
    policy_additions = 0

    for item in approved_items:
        key = fact_identity(item)

        if key in item_keys:
            old = item_keys[key]

            if old.get("weight_percent") != item["weight_percent"]:
                raise ValueError(
                    f"Conflicting weight for {item['name']}."
                )

            print(f"Already reviewed: {item['name']}")
            continue

        merged_items.append(item)
        item_keys[key] = item
        item_additions += 1

    for policy in approved_policies:
        key = policy_identity(policy)

        if key in policy_keys:
            print(f"Already reviewed policy: {policy['type']}")
            continue

        merged_policies.append(policy)
        policy_keys.add(key)
        policy_additions += 1

    if item_additions == 0 and policy_additions == 0:
        print("\nNo new facts to save.")
        return

    reviewed = {
        "document_id": document["id"],
        "source_file_hash": document["file_hash"],
        "items": merged_items,
        "policies": merged_policies,
    }

    REVIEWED_DIR.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        backup = output_path.with_suffix(".json.bak")

        if backup.exists():
            raise FileExistsError(
                f"Backup already exists: {backup}"
            )

        backup.write_bytes(output_path.read_bytes())

    save_reviewed_atomic(output_path, reviewed)

    print(
        f"\nSaved {item_additions} grading facts "
        f"and {policy_additions} policies."
    )
    print(
        f"Total: {len(merged_items)} grading facts, "
        f"{len(merged_policies)} policies."
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--document-id",
        required=True,
    )

    args = parser.parse_args()

    review_document(args.document_id)


if __name__ == "__main__":
    main()
