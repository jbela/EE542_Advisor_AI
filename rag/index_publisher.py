import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import faiss


def publish_index(index, documents, model_name, index_dir, knowledge_fingerprint=None):
    """Validate and atomically publish a new FAISS index."""

    index_dir = Path(index_dir)
    versions_dir = index_dir / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)

    version_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        + "_"
        + uuid.uuid4().hex[:8]
    )

    version_dir = versions_dir / version_id
    version_dir.mkdir()

    index_path = version_dir / "faiss.index"
    chunks_path = version_dir / "chunks.json"

    # Write both files before publishing.
    faiss.write_index(index, str(index_path))

    chunks_path.write_text(
        json.dumps(documents, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Verify the saved files.
    verified_index = faiss.read_index(str(index_path))

    verified_documents = json.loads(
        chunks_path.read_text(encoding="utf-8")
    )

    if verified_index.ntotal != len(verified_documents):
        raise RuntimeError("Index and metadata counts differ")

    if verified_index.d != index.d:
        raise RuntimeError("Embedding dimensions differ")

    manifest = {
        "version": version_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chunk_count": len(verified_documents),
        "embedding_model": model_name,
        "knowledge_fingerprint": knowledge_fingerprint
    }

    temporary_manifest = index_dir / f".current_{version_id}.tmp"
    current_file = index_dir / "current.json"

    temporary_manifest.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8"
    )

    # Switch active version only after successful validation.
    os.replace(temporary_manifest, current_file)

    return manifest
