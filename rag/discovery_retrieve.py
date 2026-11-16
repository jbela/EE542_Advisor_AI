"""Semantic EE course discovery using the separate BGE index."""

import json
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from rag.build_discovery_index import (
    MODEL_NAME,
    INDEX_DIR,
    calculate_discovery_fingerprint,
)


@lru_cache(maxsize=1)
def load_model():
    """Load BGE only when discovery retrieval is requested."""
    return SentenceTransformer(MODEL_NAME)


@lru_cache(maxsize=2)
def load_index(version):
    """Load a published discovery index and its metadata."""

    version_dir = INDEX_DIR / "versions" / version

    index = faiss.read_index(
        str(version_dir / "faiss.index")
    )

    documents = json.loads(
        (version_dir / "chunks.json").read_text(
            encoding="utf-8"
        )
    )

    if index.ntotal != len(documents):
        raise RuntimeError(
            "Discovery index and metadata counts differ."
        )

    if index.d != 768:
        raise RuntimeError(
            "Unexpected BGE embedding dimensions."
        )

    return index, documents


def load_manifest():
    """Read the active discovery index manifest."""

    path = INDEX_DIR / "current.json"

    if not path.is_file():
        raise FileNotFoundError(
            "Discovery index missing. Run "
            "'py -m rag.build_discovery_index' first."
        )

    manifest = json.loads(
        path.read_text(encoding="utf-8")
    )

    version = manifest.get("version")

    if (
        not isinstance(version, str)
        or not version
        or "/" in version
        or "\\" in version
        or version in (".", "..")
    ):
        raise ValueError(
            "Invalid discovery index version."
        )

    if manifest.get("embedding_model") != MODEL_NAME:
        raise RuntimeError(
            "Discovery embedding model mismatch."
        )

    return manifest


def retrieve_discovery(
    question,
    term_code=None,
    top_k=5,
):
    """Retrieve semantically relevant catalog courses."""

    if top_k <= 0:
        return []

    manifest = load_manifest()

    latest_fingerprint = calculate_discovery_fingerprint()

    if (
        manifest.get("knowledge_fingerprint")
        != latest_fingerprint
    ):
        raise RuntimeError(
            "Discovery index is stale. "
            "Rebuild it before retrieving courses."
        )

    index, documents = load_index(
        manifest["version"]
    )

    model = load_model()

    query_vector = model.encode(
        [question],
        normalize_embeddings=True,
        convert_to_numpy=True
    ).astype(np.float32)

    _, indices = index.search(
        query_vector,
        index.ntotal
    )

    results = []
    seen = set()

    for idx in indices[0]:
        idx = int(idx)

        if idx < 0:
            continue

        document = documents[idx]

        if document.get("category") != "course":
            continue

        if term_code is not None:
            if str(document.get("term_code")) != str(term_code):
                continue

        key = (
            document.get("course_code"),
            document.get("term_code")
        )

        if key in seen:
            continue

        seen.add(key)

        results.append({
            **document,
            "retrieval_method": "semantic_bge",
        })

        if len(results) >= top_k:
            break

    return results


if __name__ == "__main__":
    question = input(
        "Ask a semantic course discovery question: "
    )

    results = retrieve_discovery(
        question,
        term_code="20271",
        top_k=5
    )

    for rank, result in enumerate(results, 1):
        print(
            f"{rank}. "
            f"{result['course_code']} | "
            f"{result['title']}"
        )
