import json
import time
from pathlib import Path

from ingestion.collect_courses import fetch_courses, save_course_data

ROOT = Path(__file__).resolve().parents[1]
TERMS_FILE = ROOT / "data" / "processed" / "terms.json"


def main():
    if not TERMS_FILE.exists():
        raise FileNotFoundError(
            "Run discover_terms.py first."
        )

    data = json.loads(
        TERMS_FILE.read_text(encoding="utf-8")
    )

    active_terms = [
        term for term in data["terms"]
        if str(term.get("status", "")).lower() == "active"
    ]

    print(f"Found {len(active_terms)} active semesters.")

    academic_updates = False
    failed_terms = []

    for term in active_terms:
        code = term["term_code"]
        name = term["name"]

        print(f"\nSynchronizing {name} ({code})...")

        try:
            course_data = fetch_courses(code)
            result = save_course_data(course_data)
            if result["academic_changed"]:
                academic_updates = True
        except Exception as error:
            print(f"ERROR synchronizing {name}: {error}")
            failed_terms.append(code)

        time.sleep(10)

    print("\nSynchronization complete.")

    return {
        "academic_updates": academic_updates,
        "failed_terms": failed_terms
    }

if __name__ == "__main__":
    main()
