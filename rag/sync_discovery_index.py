"""Synchronize the BGE discovery index with collected course data."""

import json
import subprocess
import sys
from pathlib import Path

from rag.build_discovery_index import (
    INDEX_DIR,
    MODEL_NAME,
    calculate_discovery_fingerprint,
)


ROOT = Path(__file__).resolve().parents[1]
CURRENT_FILE = INDEX_DIR / "current.json"


def sync_discovery_index():
    latest_fingerprint = calculate_discovery_fingerprint()
    active_fingerprint = None
    active_model = None
    active_version = None

    if CURRENT_FILE.is_file():
        try:
            manifest = json.loads(
                CURRENT_FILE.read_text(encoding="utf-8")
            )
            active_fingerprint = manifest.get(
                "knowledge_fingerprint"
            )
            active_model = manifest.get("embedding_model")
            active_version = manifest.get("version")
        except (OSError, ValueError, TypeError):
            print("WARNING: Discovery index manifest could not be read.")

    if (
        active_fingerprint == latest_fingerprint
        and active_model == MODEL_NAME
        and active_version
        and (INDEX_DIR / "versions" / active_version / "faiss.index").is_file()
        and (INDEX_DIR / "versions" / active_version / "chunks.json").is_file()
    ):
        print("Discovery knowledge unchanged. Skipping BGE rebuild.")
        return {
            "rebuilt": False,
            "version": active_version,
            "knowledge_fingerprint": latest_fingerprint
        }

    print("Discovery knowledge changed. Rebuilding BGE index...")

    subprocess.run(
        [sys.executable, "-m", "rag.build_discovery_index"],
        check=True,
        cwd=ROOT
    )

    published = json.loads(
        CURRENT_FILE.read_text(encoding="utf-8")
    )

    if (
        published.get("knowledge_fingerprint")
        != latest_fingerprint
    ):
        raise RuntimeError(
            "Published discovery index fingerprint does not match source data."
        )

    if published.get("embedding_model") != MODEL_NAME:
        raise RuntimeError(
            "Published discovery index uses an unexpected embedding model."
        )

    print("BGE discovery index updated successfully.")

    return {
        "rebuilt": True,
        "version": published["version"],
        "knowledge_fingerprint": latest_fingerprint
    }


if __name__ == "__main__":
    print(sync_discovery_index())
