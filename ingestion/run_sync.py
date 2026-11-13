"""Automated USC academic data synchronization."""

from pathlib import Path

from filelock import FileLock, Timeout

from ingestion.discover_terms import main as discover_terms
from ingestion.sync_courses import main as sync_courses
from ingestion.collect import main as sync_policies
from rag.sync_index import sync_index

ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = ROOT / "data" / ".academic_sync.lock"


def main():
    print("=" * 50)
    print("USC ADVISOR AI - AUTOMATED DATA SYNC")
    print("=" * 50)

    print("\nSTEP 1: Discovering semesters...")
    discover_terms()

    print("\nSTEP 2: Synchronizing EE courses...")
    course_result = sync_courses()

    print("\nSTEP 3: Synchronizing USC policies...")
    policy_result = sync_policies()

    failed_terms = course_result["failed_terms"]
    failed_sources = policy_result["failed_sources"]

    if failed_terms or failed_sources:
        raise RuntimeError(
            "Synchronization incomplete. "
            f"Failed semesters: {failed_terms}; "
            f"Failed policy sources: {failed_sources}"
        )

    print("\nSTEP 4: Synchronizing RAG index...")
    index_result = sync_index()

    print("\nSynchronization finished successfully.")

    return {
        "course_result": course_result,
        "policy_result": policy_result,
        "index_result": index_result
    }


if __name__ == "__main__":
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    lock = FileLock(str(LOCK_FILE), timeout=0)

    try:
        with lock:
            main()

    except Timeout:
        print(
            "Another academic synchronization is already running. "
            "Skipping this execution."
        )
        raise SystemExit(1)
