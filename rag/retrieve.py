
import json
import re
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "indexes"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

print("Loading retrieval models...")

model = SentenceTransformer(MODEL_NAME)


CURRENT_FILE = INDEX_DIR / "current.json"

manifest = json.loads(
    CURRENT_FILE.read_text(encoding="utf-8")
)

version_id = manifest["version"]

# Reject unexpected paths in the manifest
if (
    not isinstance(version_id, str)
    or not version_id
    or "/" in version_id
    or "\\" in version_id
    or version_id in (".", "..")
):
    raise ValueError("Invalid index version identifier")

version_dir = INDEX_DIR / "versions" / version_id

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
        "Active FAISS index does not match its metadata"
    )

if manifest.get("embedding_model") != MODEL_NAME:
    raise RuntimeError(
        "Embedding model does not match active index"
    )

print(f"Loaded index version: {version_id}")



def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


tokenized_corpus = [
    tokenize(doc["text"])
    for doc in documents
]

bm25 = BM25Okapi(tokenized_corpus)


def retrieve(question, top_k=5, category=None, term_code=None):
    query_vector = model.encode(
        [question],
        normalize_embeddings=True,
        convert_to_numpy=True
    ).astype(np.float32)

    # FAISS semantic ranking
    _, faiss_indices = index.search(
        query_vector,
        len(documents)
    )

    # BM25 keyword ranking
    bm25_scores = bm25.get_scores(
        tokenize(question)
    )

    bm25_indices = np.argsort(
        bm25_scores
    )[::-1]

    # Reciprocal Rank Fusion
    rrf_scores = {}

    for rank, idx in enumerate(faiss_indices[0]):
        idx = int(idx)

        if idx < 0:
            continue

        rrf_scores[idx] = (
            rrf_scores.get(idx, 0)
            + 1 / (60 + rank + 1)
        )

    for rank, idx in enumerate(bm25_indices):
        idx = int(idx)

        rrf_scores[idx] = (
            rrf_scores.get(idx, 0)
            + 1 / (60 + rank + 1)
        )

    ranked = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    results = []

    for idx, score in ranked:
        doc = documents[idx]

        # Filter by category
        if category and doc["category"] not in (
            category, "shared"
        ):
            continue

        # Filter courses by semester
        if term_code is not None:
            if doc.get("category") == "course":
                if str(doc.get("term_code")) != str(term_code):
                    continue

        results.append({
            **doc,
            "score": float(score)
        })

        if len(results) >= top_k:
            break

    return results


if __name__ == "__main__":
    question = input(
        "Ask a USC academic question: "
    )

    results = retrieve(
        question,
        top_k=5,
        category="course",
        term_code="20271"
    )

    for i, result in enumerate(results, start=1):
        print(f"\n{'=' * 50}")
        print(f"RESULT {i}")
        print(f"Title: {result['title']}")
        print(f"Category: {result['category']}")
        print(f"RRF Score: {result['score']:.4f}")
        print(f"Source: {result['url']}")
        print(f"\nText:\n{result['text'][:700]}")
