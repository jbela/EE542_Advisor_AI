import json
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "indexes"
QUESTIONS_FILE = ROOT / "tests" / "retrieval_questions.json"

TOP_K = 5
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_index():
    manifest = json.loads(
        (INDEX_DIR / "current.json").read_text(encoding="utf-8")
    )

    version = manifest["version"]
    version_dir = INDEX_DIR / "versions" / version

    index = faiss.read_index(str(version_dir / "faiss.index"))

    documents = json.loads(
        (version_dir / "chunks.json").read_text(encoding="utf-8")
    )

    if index.ntotal != len(documents):
        raise ValueError("FAISS index and document count mismatch")

    if manifest.get("embedding_model") != MODEL_NAME:
        raise ValueError("Embedding model mismatch")

    return index, documents, version


def tokenize(text):
    return text.lower().split()


def rank_results(question, method, index, documents, model, bm25):
    # Filter BEFORE ranking, so top-k results come from the
    # requested semester and category.
    eligible = [
        i for i, doc in enumerate(documents)
        if doc.get("category") == question["category"]
        and (
            not question.get("term_code")
            or str(doc.get("term_code")) == str(question["term_code"])
        )
    ]

    if not eligible:
        return []

    query = question["question"]
    candidate_count = len(eligible)

    # FAISS search over the full index, retrieving every vector
    # so filtering cannot discard all relevant candidates.
    vector = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True
    )
    vector = np.asarray(vector, dtype=np.float32)

    _, ids = index.search(vector, index.ntotal)

    eligible_set = set(eligible)

    faiss_rank = [
        int(i) for i in ids[0]
        if int(i) in eligible_set
    ]

    # BM25 ranking restricted to eligible documents.
    bm25_scores = bm25.get_scores(tokenize(query))

    bm25_rank = sorted(
        eligible,
        key=lambda i: (-bm25_scores[i], i)
    )

    if method == "faiss":
        ranked = faiss_rank

    elif method == "bm25":
        ranked = bm25_rank

    elif method == "hybrid":
        rrf_scores = {}

        for ranking in (faiss_rank, bm25_rank):
            for rank, idx in enumerate(ranking, start=1):
                rrf_scores[idx] = rrf_scores.get(idx, 0) + (
                    1 / (60 + rank)
                )

        ranked = sorted(
            eligible,
            key=lambda i: (-rrf_scores.get(i, 0), i)
        )

    else:
        raise ValueError(f"Unknown method: {method}")

    return [documents[i] for i in ranked[:TOP_K]]


def evaluate_question(question, results):
    expected = set(question["relevant_course_codes"])

    hits = [
        i + 1
        for i, doc in enumerate(results)
        if doc.get("course_code") in expected
    ]

    hit_rate = 1.0 if hits else 0.0
    reciprocal_rank = 1 / hits[0] if hits else 0.0

    return hit_rate, reciprocal_rank


def main():
    questions = json.loads(
        QUESTIONS_FILE.read_text(encoding="utf-8")
    )

    index, documents, version = load_index()

    print(f"Loaded index version: {version}")
    print(f"Indexed documents: {len(documents)}")
    print(f"Evaluation questions: {len(questions)}")

    print("\nLoading retrieval models...")
    model = SentenceTransformer(MODEL_NAME)

    bm25 = BM25Okapi([
        tokenize(doc["text"]) for doc in documents
    ])

    print("\n" + "=" * 60)
    print("USC ADVISOR AI - RETRIEVAL EVALUATION")
    print("=" * 60)

    for method in ("faiss", "bm25", "hybrid"):
        total_hits = 0
        total_rr = 0

        print(f"\nMETHOD: {method.upper()}")

        for question in questions:
            results = rank_results(
                question, method, index, documents, model, bm25
            )

            hit, rr = evaluate_question(question, results)

            total_hits += hit
            total_rr += rr

            top_result = (
                results[0].get("course_code", "N/A")
                if results else "None"
            )

            print(
                f"{question['id']}: "
                f"Hit@5={int(hit)} "
                f"RR={rr:.3f} "
                f"Top={top_result}"
            )

        n = len(questions)

        print(f"\nHit Rate@5: {total_hits / n:.3f}")
        print(f"MRR@5:      {total_rr / n:.3f}")


if __name__ == "__main__":
    main()
