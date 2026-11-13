import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw"
COURSES_DIR = ROOT / "data" / "courses"
VERIFIED_DIR = ROOT / "data" / "verified_requirements"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Increase this when changing chunking or indexed text formatting.
INDEX_SCHEMA_VERSION = "1"


def hash_json(value):
    serialized = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def calculate_fingerprint(
    raw_dir=None,
    courses_dir=None
):
    """Fingerprint the academic inputs used by the RAG index."""

    raw_dir = Path(raw_dir) if raw_dir is not None else RAW_DIR
    courses_dir = (
        Path(courses_dir)
        if courses_dir is not None
        else COURSES_DIR
    )

    sources = []

    for path in sorted(raw_dir.glob("*.json")):
        data = json.loads(
            path.read_text(encoding="utf-8")
        )

        sources.append({
            "type": "policy",
            "file": path.name,
            "id": data["id"],
            "content_hash": hash_json(data["text"])
        })

    for path in sorted(courses_dir.glob("ee_*.json")):
        data = json.loads(
            path.read_text(encoding="utf-8")
        )

        # Recompute to avoid trusting a stale stored hash.
        from ingestion.collect_courses import (
            calculate_academic_hash
        )

        sources.append({
            "type": "course",
            "file": path.name,
            "term_code": str(data["term_code"]),
            "academic_hash": calculate_academic_hash(
                data["courses"]
            )
        })

    for path in sorted(VERIFIED_DIR.glob("*.json")):
        data = json.loads(
            path.read_text(encoding="utf-8")
        )

        sources.append({
            "type": "verified_requirements",
            "file": path.name,
            "content_hash": hash_json(data)
        })

    if not sources:
        raise ValueError(
            "Cannot fingerprint an empty knowledge base."
        )

    return hash_json({
        "model": MODEL_NAME,
        "schema_version": INDEX_SCHEMA_VERSION,
        "sources": sources
    })


if __name__ == "__main__":
    print("Knowledge fingerprint:")
    print(calculate_fingerprint())
