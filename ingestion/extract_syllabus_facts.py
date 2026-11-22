"""Extract unverified grading candidates from imported syllabi."""

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYLLABI_DIR = ROOT / "data" / "processed" / "syllabi"
CANDIDATES_DIR = ROOT / "data" / "processed" / "syllabi_candidates"


WEIGHT_PATTERNS = [
    re.compile(
        r"(?<![\w.])(?P<weight>\d{1,3})\s*%\s+"
        r"(?P<name>[A-Za-z][A-Za-z ,/&()+-]{1,80}?)"
        r"(?=\s*[•\n]|\s+\d{1,3}\s*%|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<name>[A-Za-z][A-Za-z /&()+-]{1,60}?)"
        r"\s*:\s*(?P<weight>\d{1,3})\s*%",
        re.IGNORECASE,
    ),
]


def normalize_assessment_name(name):
    """Remove explanatory parentheticals without changing source evidence."""
    name = " ".join(str(name).split()).strip(" ,:")

    if re.search(r"\([^()]*\)\s*$", name):
        name = re.sub(r"\s*\([^()]*\)\s*$", "", name)

    return name.strip(" ,:")

def extract_weight_candidates(text, page_number):
    candidates = []
    seen = set()

    assessment_start = re.compile(
        r"^(?:homework|assignments?|labs?|laboratory|"
        r"reading|attendance|participation|quizzes?|"
        r"midterms?|finals?|projects?|exams?|"
        r"presentations?|reports?|problem sets?|"
        r"tests?|exercises?|discussions?|"
        r"practicals?|portfolios?|capstones?)\b",
        re.IGNORECASE,
    )

    sentence_start = re.compile(
        r"^(?:and|or|but|if|when|while|because|"
        r"that|which|who|where|a student|"
        r"the student|students?)\b",
        re.IGNORECASE,
    )

    for pattern in WEIGHT_PATTERNS:
        for match in pattern.finditer(text):
            source_label = " ".join(
                match.group("name").split()
            ).strip(" ,:")

            name = normalize_assessment_name(source_label)

            weight = int(match.group("weight"))

            if not name or weight > 100:
                continue

            if sentence_start.search(name):
                continue

            if not assessment_start.search(name):
                continue

            key = (name.lower(), weight, page_number)

            if key in seen:
                continue

            seen.add(key)

            candidates.append({
                "type": "assessment_weight",
                "name": name,
                "source_label": source_label,
                "weight_percent": weight,
                "page_number": page_number,
                "source_quote": match.group(0).strip(),
                "verified": False,
            })

    return candidates


POLICY_PATTERNS = {
    "late_penalty": re.compile(
        r"\b(?:late policy|late assignments?|turned in late)"
        r".{0,180}?(?:deduct(?:ed|ion)?|penalt(?:y|ies)|"
        r"reduc(?:ed|tion))"
        r".{0,100}",
        re.IGNORECASE | re.DOTALL,
    ),
    "grade_dispute": re.compile(
        r"\b(?:grade adjustment|disput(?:e|ing)|"
        r"request a change in (?:the )?grade)"
        r".{0,300}",
        re.IGNORECASE | re.DOTALL,
    ),
    "threshold_adjustment": re.compile(
        r"\b(?:thresholds?|grade cutoffs?)"
        r".{0,160}?"
        r"(?:adjusted|lowered|raised|discretion)"
        r".{0,160}",
        re.IGNORECASE | re.DOTALL,
    ),
    "participation_adjustment": re.compile(
        r"\bclass participation"
        r".{0,160}?"
        r"(?:bump|threshold|grade)"
        r".{0,120}",
        re.IGNORECASE | re.DOTALL,
    ),
}


def extract_policy_candidates(text, page_number):
    candidates = []
    seen = set()

    normalized = " ".join(text.split())

    boundaries = re.split(
        r"(?<=[.!?])\s+(?=[A-Z])|(?=•\s*[A-Z])",
        normalized,
    )

    for segment in boundaries:
        segment = segment.strip(" •")

        if not segment:
            continue

        for policy_type, pattern in POLICY_PATTERNS.items():
            if not pattern.search(segment):
                continue

            quote = segment.strip()

            key = (policy_type, quote.lower())

            if key in seen:
                continue

            seen.add(key)

            candidates.append({
                "type": policy_type,
                "page_number": page_number,
                "source_quote": quote,
                "verified": False,
            })

    return candidates


def extract_candidates(document):
    items = []
    policies = []

    for page in document.get("pages", []):
        page_number = page["page_number"]
        text = page.get("text", "")

        items.extend(
            extract_weight_candidates(
                text,
                page_number,
            )
        )

        policies.extend(
            extract_policy_candidates(
                text,
                page_number,
            )
        )

    return {
        "document_id": document["id"],
        "course_code": document["course_code"],
        "term_code": document["term_code"],
        "section_label": document.get("section_label"),
        "source_file_hash": document["file_hash"],
        "items": items,
        "policies": policies,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--course")
    args = parser.parse_args()

    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

    count = 0

    for path in sorted(SYLLABI_DIR.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))

        if args.course and document.get("course_code") != args.course:
            continue

        candidates = extract_candidates(document)

        output = CANDIDATES_DIR / f"{document['id']}.json"

        output.write_text(
            json.dumps(candidates, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(
            f"{document['course_code']} "
            f"({document['term_code']}): "
            f"{len(candidates['items'])} candidates"
        )

        count += 1

    print(f"\nProcessed {count} syllabi.")


if __name__ == "__main__":
    main()
