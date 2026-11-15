"""Batch collection of archived USC EE course catalogs."""

import argparse
import json
import sys
import time

from datetime import datetime
from pathlib import Path

from filelock import FileLock, Timeout

from ingestion.backfill_courses import (
    backfill_term,
    load_known_terms,
    LOCK_FILE,
    COURSES_DIR,
)
from rag.sync_index import sync_index


def select_archived_terms(known_terms, years=5):
    """Select archived semesters in a rolling calendar-year window."""

    current_year = datetime.now().year
    earliest_year = current_year - years

    selected = []

    for code, term in known_terms.items():
        try:
            year = int(term["year"])
        except (ValueError, TypeError, KeyError):
            continue

        if not (earliest_year <= year <= current_year):
            continue

        if str(term.get("status", "")).lower() != "archived":
            continue

        selected.append(term)

    return sorted(
        selected,
        key=lambda term: int(term["term_code"])
    )


def backfill_history(years=5, delay=10, max_terms=None, dry_run=False):
    """Collect missing archived terms and update FAISS once."""

    known_terms = load_known_terms()
    selected = select_archived_terms(known_terms, years)

    missing = [
        term for term in selected
        if not (
            COURSES_DIR / f"ee_{term['term_code']}.json"
        ).is_file()
    ]

    if max_terms is not None:
        missing = missing[:max_terms]

    print("=" * 65)
    print("USC ADVISOR AI - HISTORICAL COURSE BACKFILL")
    print("=" * 65)

    print(f"Historical window: {years} years")
    print(f"Archived semesters identified: {len(selected)}")
    print(f"Missing semesters to collect: {len(missing)}")

    for term in missing:
        print(f"  {term['name']} ({term['term_code']})")

    if dry_run:
        print("\nDry run complete. No data downloaded.")
        return {
            "status": "dry_run",
            "missing_terms": [
                t["term_code"] for t in missing
            ],
        }

    results = []
    failures = []

    for index, term in enumerate(missing):
        code = term["term_code"]

        print(
            f"\n[{index + 1}/{len(missing)}] "
            f"Collecting {term['name']} ({code})..."
        )

        try:
            result = backfill_term(code)
            results.append(result)

        except Exception as error:
            print(f"ERROR: {error}")
            failures.append({
                "term_code": code,
                "error": str(error),
            })

        if index < len(missing) - 1:
            time.sleep(delay)

    index_result = None

    if results or not failures:
        print("\nSynchronizing collected academic data...")
        index_result = sync_index()

    if failures:
        print(
            "\nWARNING: Some semesters failed. "
            "Successfully collected semesters were retained. "
            "Historical coverage remains incomplete."
        )

    summary = {
        "status": (
            "complete" if not failures else "partial_failure"
        ),
        "selected_terms": len(selected),
        "attempted_terms": len(missing),
        "collected_terms": len(results),
        "failed_terms": failures,
        "index": index_result,
    }

    print("\n" + "=" * 65)
    print("BACKFILL SUMMARY")
    print("=" * 65)
    print(json.dumps(summary, indent=2))

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Collect archived USC EE semesters."
    )

    parser.add_argument(
        "--years",
        type=int,
        default=5
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=10
    )

    parser.add_argument(
        "--max-terms",
        type=int,
        default=None
    )

    parser.add_argument(
        "--dry-run",
        action="store_true"
    )

    args = parser.parse_args()

    if args.years < 1 or args.years > 10:
        parser.error("--years must be between 1 and 10")

    if args.delay < 0:
        parser.error("--delay cannot be negative")

    if args.max_terms is not None and args.max_terms < 1:
        parser.error("--max-terms must be positive")

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        with FileLock(str(LOCK_FILE), timeout=0):
            result = backfill_history(
                years=args.years,
                delay=args.delay,
                max_terms=args.max_terms,
                dry_run=args.dry_run,
            )

        if result["status"] == "partial_failure":
            raise SystemExit(1)

    except Timeout:
        print(
            "Another academic synchronization is running.",
            file=sys.stderr
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
