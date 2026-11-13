"""Synchronize the published FAISS index with stored academic data."""

import json
import subprocess
import sys
from pathlib import Path

from rag.knowledge_fingerprint import calculate_fingerprint

ROOT = Path(__file__).resolve().parents[1]
CURRENT_FILE = ROOT / "indexes" / "current.json"


def sync_index():
    latest_fingerprint = calculate_fingerprint()
    active_fingerprint = None

    if CURRENT_FILE.is_file():
        try:
            manifest = json.loads(
                CURRENT_FILE.read_text(encoding="utf-8")
            )
            active_fingerprint = manifest.get("knowledge_fingerprint")
        except (OSError, ValueError, TypeError):
            print("WARNING: Active index manifest could not be read.")

    if active_fingerprint == latest_fingerprint:
        print("Knowledge unchanged. Skipping RAG rebuild.")
        return {
            "rebuilt": False,
            "knowledge_fingerprint": latest_fingerprint
        }

    print("Knowledge changed. Rebuilding RAG index...")

    subprocess.run(
        [sys.executable, "-m", "rag.build_index"],
        check=True,
        cwd=ROOT
    )

    published = json.loads(
        CURRENT_FILE.read_text(encoding="utf-8")
    )

    if published.get("knowledge_fingerprint") != latest_fingerprint:
        raise RuntimeError(
            "Published index fingerprint does not match source data."
        )

    print("RAG index updated successfully.")

    return {
        "rebuilt": True,
        "version": published["version"],
        "knowledge_fingerprint": latest_fingerprint
    }
