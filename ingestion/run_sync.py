import json
import subprocess
import sys
from pathlib import Path

from ingestion.discover_terms import main as discover_terms
from ingestion.sync_courses import main as sync_courses
from ingestion.collect import main as sync_policies
from rag.knowledge_fingerprint import calculate_fingerprint
from filelock import FileLock, Timeout

ROOT = Path(__file__).resolve().parents[1]

CURRENT_FILE = ROOT / "indexes" / "current.json"

LOCK_FILE = ROOT / "data" / ".academic_sync.lock"

def main():
    print("=" * 50)
    print("USC ADVISOR AI - AUTOMATED DATA SYNC")
    print("=" * 50)

    # Step 1: Discover academic semesters
    print("\nSTEP 1: Discovering semesters...")
    discover_terms()

    # Step 2: Synchronize EE courses
    print("\nSTEP 2: Synchronizing EE courses...")
    course_result = sync_courses()

    # Step 3: Synchronize USC academic policies
    print("\nSTEP 3: Synchronizing USC policies...")
    policy_result = sync_policies()

    # Stop if any source failed
    failed_terms = course_result["failed_terms"]
    failed_sources = policy_result["failed_sources"]

    if failed_terms or failed_sources:
        raise RuntimeError(
            "Synchronization incomplete. "
            f"Failed semesters: {failed_terms}; "
            f"Failed policy sources: {failed_sources}"
        )


    # Compare the latest academic data with the active index.
    latest_fingerprint = calculate_fingerprint()

    active_fingerprint = None

    if CURRENT_FILE.exists():
        try:
            manifest = json.loads(
                CURRENT_FILE.read_text(encoding="utf-8")
            )

            active_fingerprint = manifest.get(
                "knowledge_fingerprint"
            )

        except (OSError, ValueError, TypeError):
            print("WARNING: Could not read active index manifest.")


    # Compare saved academic information against the active index.
    latest_fingerprint = calculate_fingerprint()

    active_fingerprint = None

    if CURRENT_FILE.exists():
        try:
            manifest = json.loads(
                CURRENT_FILE.read_text(encoding="utf-8")
            )

            active_fingerprint = manifest.get(
                "knowledge_fingerprint"
            )

        except (OSError, ValueError, TypeError):
            print(
                "WARNING: Could not read the active index manifest."
            )

    needs_rebuild = (
        active_fingerprint != latest_fingerprint
    )

    if needs_rebuild:
        print("\nSTEP 4: Rebuilding RAG index...")

        subprocess.run(
            [sys.executable, "-m", "rag.build_index"],
            check=True,
            cwd=ROOT
        )

        print("RAG index updated successfully.")

    else:
        print(
            "\nSTEP 4: No academic changes. "
            "Skipping RAG rebuild."
        )

    print("\nSynchronization finished successfully.")


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
