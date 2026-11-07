import subprocess
import sys
from pathlib import Path

from ingestion.discover_terms import main as discover_terms
from ingestion.sync_courses import main as sync_courses

ROOT = Path(__file__).resolve().parents[1]
CURRENT_FILE = ROOT / "indexes" / "current.json"

def main():
    print("=" * 50)
    print("USC ADVISOR AI - AUTOMATED DATA SYNC")
    print("=" * 50)

    print("\nSTEP 1: Discovering semesters...")
    discover_terms()

    print("\nSTEP 2: Synchronizing EE courses...")
    result = sync_courses()

    if result["failed_terms"]:
        raise RuntimeError(
            "Synchronization failed for semesters: "
            + ", ".join(result["failed_terms"])
        )

    needs_rebuild = (
        result["academic_updates"]
        or not CURRENT_FILE.exists()
    )

    if needs_rebuild:
        print("\nSTEP 3: Rebuilding RAG index...")

        subprocess.run(
            [sys.executable, "-m", "rag.build_index"],
            check=True,
            cwd=ROOT
        )

        print("RAG index updated successfully.")

    else:
        print(
            "\nSTEP 3: No academic changes. "
            "Skipping RAG rebuild."
        )

    print("\nSynchronization finished.")


if __name__ == "__main__":
    main()
