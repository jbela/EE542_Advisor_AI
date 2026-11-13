"""Controlled collection of historical USC EE semesters."""

import argparse
import json
import sys
from pathlib import Path

from filelock import FileLock, Timeout
from rag.sync_index import sync_index

from ingestion.collect_courses import (
    fetch_courses,
    save_course_data,
)

ROOT = Path(__file__).resolve().parents[1]
TERMS_FILE = ROOT / "data" / "processed" / "terms.json"
COURSES_DIR = ROOT / "data" / "courses"
LOCK_FILE = ROOT / "data" / ".academic_sync.lock"


def load_known_terms():
    if not TERMS_FILE.is_file():
        raise FileNotFoundError(
            "Semester metadata missing. Run "
            "'py -m ingestion.discover_terms' first."
        )

    data = json.loads(
        TERMS_FILE.read_text(encoding="utf-8")
    )

    return {
        str(term["term_code"]): term
        for term in data["terms"]
    }


def backfill_term(term_code, refresh=False):
    """Collect one known semester using the existing collector."""

    term_code = str(term_code)
    known_terms = load_known_terms()

    if term_code not in known_terms:
        raise ValueError(
            f"Unknown semester {term_code}. "
            "Refresh semester discovery first."
        )

    target = COURSES_DIR / f"ee_{term_code}.json"

    if target.is_file() and not refresh:
        print(
            f"{known_terms[term_code]['name']} "
            "has already been collected."
        )
        return {
            "term_code": term_code,
            "status": "already_collected",
            "academic_changed": False,
        }

    print(
        f"Collecting {known_terms[term_code]['name']} "
        f"({term_code})..."
    )

    data = fetch_courses(term_code)
    result = save_course_data(data)

    return {
        "term_code": term_code,
        "status": "collected",
        **result,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill a historical USC EE semester."
    )

    parser.add_argument(
        "--term",
        required=True,
        help="USC semester code, e.g. 20253"
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh an already collected semester"
    )

    args = parser.parse_args()

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        with FileLock(str(LOCK_FILE), timeout=0):
            result = backfill_term(
                args.term,
                refresh=args.refresh,
            )

            index_result = sync_index()

            result["index"] = index_result

            print(
                json.dumps(result, indent=2)
            )

    except Timeout:
        print(
            "Another academic synchronization is running.",
            file=sys.stderr
        )
        raise SystemExit(1)

    except Exception as error:
        print(
            f"Historical collection failed: {error}",
            file=sys.stderr
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
