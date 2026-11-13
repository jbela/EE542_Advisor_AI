import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_FILE = ROOT / "tests" / "retrieval_questions_v2.json"
COURSES_DIR = ROOT / "data" / "courses"
INDEX_DIR = ROOT / "indexes"

questions = json.loads(
    QUESTIONS_FILE.read_text(encoding="utf-8")
)

manifest = json.loads(
    (INDEX_DIR / "current.json").read_text(encoding="utf-8")
)

version_dir = INDEX_DIR / "versions" / manifest["version"]

documents = json.loads(
    (version_dir / "chunks.json").read_text(encoding="utf-8")
)

course_data = {}

for path in COURSES_DIR.glob("ee_*.json"):
    data = json.loads(path.read_text(encoding="utf-8"))
    course_data[str(data["term_code"])] = {
        c["course_code"] for c in data["courses"]
    }

document_ids = {
    d.get("document_id") for d in documents
}

print("=" * 60)
print("USC ADVISOR AI - BENCHMARK VALIDATION")
print("=" * 60)

print(f"\nTotal questions: {len(questions)}")
print("Categories:", dict(Counter(q["category"] for q in questions)))

warnings = 0

for q in questions:
    qid = q["id"]
    category = q["category"]
    term = str(q.get("term_code", ""))

    if category in ("course_discovery", "prerequisites"):
        if term not in course_data:
            print(f"{qid}: WARNING - term {term} not collected")
            warnings += 1
            continue

        for code in q.get("expected_courses", []):
            if code not in course_data[term]:
                print(
                    f"{qid}: WARNING - {code} not found "
                    f"in term {term}"
                )
                warnings += 1

    elif category == "historical":
        if term and term not in course_data:
            print(
                f"{qid}: INFO - historical term {term} "
                "not collected"
            )
            continue

        source_term = str(q.get("expected_source_term", ""))

        if source_term and source_term not in course_data:
            print(
                f"{qid}: WARNING - expected source term "
                f"{source_term} not collected"
            )
            warnings += 1

    elif category == "policy":
        for doc_id in q.get("expected_document_ids", []):
            if doc_id not in document_ids:
                print(
                    f"{qid}: WARNING - document "
                    f"{doc_id} not indexed"
                )
                warnings += 1

print("\n" + "=" * 60)
print(f"Validation warnings: {warnings}")
print("=" * 60)
