"""Evaluate semantic course discovery using weighted RRF."""

import json
import math
from pathlib import Path

import numpy as np

from rag import retrieve as rag


ROOT = Path(__file__).resolve().parents[1]

QUESTIONS_FILE = (
    ROOT / "tests" / "semantic_course_questions.json"
)

REPORTS_DIR = ROOT / "reports"

WEIGHTS = [0.0, 0.50, 0.75, 0.85, 1.0]
TOP_K = 5
RRF_K = 60


def load_questions():
    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        return json.load(f)


def is_valid_course(index, term_code):
    doc = rag.documents[int(index)]

    return (
        doc.get("category") == "course"
        and str(doc.get("term_code")) == str(term_code)
        and bool(doc.get("course_code"))
    )


def rank_courses(question, term_code, weight):
    vector = rag.model.encode(
        [question],
        normalize_embeddings=True,
        convert_to_numpy=True
    ).astype(np.float32)

    _, faiss_indices = rag.index.search(
        vector,
        len(rag.documents)
    )

    bm25_scores = rag.bm25.get_scores(
        rag.tokenize(question)
    )

    bm25_indices = np.argsort(
        bm25_scores,
        kind="stable"
    )[::-1]

    scores = {}

    for rank, idx in enumerate(faiss_indices[0], 1):
        idx = int(idx)

        if idx < 0:
            continue

        scores[idx] = scores.get(idx, 0) + (
            weight / (RRF_K + rank)
        )

    for rank, idx in enumerate(bm25_indices, 1):
        idx = int(idx)

        scores[idx] = scores.get(idx, 0) + (
            (1 - weight) / (RRF_K + rank)
        )

    ranked = sorted(
        scores,
        key=lambda idx: scores[idx],
        reverse=True
    )

    results = []
    seen = set()

    for idx in ranked:
        if not is_valid_course(idx, term_code):
            continue

        code = rag.documents[idx]["course_code"]

        if code in seen:
            continue

        seen.add(code)
        results.append(code)

        if len(results) >= TOP_K:
            break

    return results


def evaluate_ranking(results, expected):
    expected = set(expected)

    relevant_ranks = [
        rank
        for rank, code in enumerate(results, 1)
        if code in expected
    ]

    hit = int(bool(relevant_ranks))

    mrr = (
        1 / relevant_ranks[0]
        if relevant_ranks else 0.0
    )

    precision = (
        len(relevant_ranks) / TOP_K
    )

    dcg = sum(
        1 / math.log2(rank + 1)
        for rank in relevant_ranks
    )

    ideal_count = min(len(expected), TOP_K)

    idcg = sum(
        1 / math.log2(rank + 1)
        for rank in range(1, ideal_count + 1)
    )

    ndcg = dcg / idcg if idcg else 0.0

    return {
        "hit_at_5": hit,
        "mrr_at_5": mrr,
        "precision_at_5": precision,
        "ndcg_at_5": ndcg
    }


def main():
    questions = load_questions()

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print("=" * 70)
    print("USC ADVISOR AI - SEMANTIC COURSE EVALUATION")
    print("=" * 70)

    print("Questions:", len(questions))
    print("Index version:", rag.version_id)

    summary = []
    details = []

    # Cache rankings so embeddings and BM25 are computed
    # once per question rather than once per weight.
    for weight in WEIGHTS:
        totals = {
            "hit_at_5": 0.0,
            "mrr_at_5": 0.0,
            "precision_at_5": 0.0,
            "ndcg_at_5": 0.0
        }

        print("\n" + "-" * 70)
        print(f"FAISS weight: {weight:.2f}")
        print("-" * 70)

        for q in questions:
            results = rank_courses(
                q["question"],
                q["term_code"],
                weight
            )

            metrics = evaluate_ranking(
                results,
                q["expected_courses"]
            )

            for key in totals:
                totals[key] += metrics[key]

            details.append({
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "weight": weight,
                "expected_courses": q["expected_courses"],
                "retrieved_courses": results,
                **metrics
            })

            print(
                f"{q['id']}: "
                f"Top5={results} "
                f"MRR={metrics['mrr_at_5']:.3f}"
            )

        n = len(questions)

        averages = {
            key: value / n
            for key, value in totals.items()
        }

        summary.append({
            "faiss_weight": weight,
            "bm25_weight": 1 - weight,
            **averages
        })

        print(
            f"\nHit@5={averages['hit_at_5']:.3f} "
            f"MRR@5={averages['mrr_at_5']:.3f} "
            f"Precision@5={averages['precision_at_5']:.3f} "
            f"nDCG@5={averages['ndcg_at_5']:.3f}"
        )

    output = {
        "index_version": rag.version_id,
        "question_count": len(questions),
        "summary": summary,
        "details": details
    }

    output_path = (
        REPORTS_DIR / "semantic_course_evaluation.json"
    )

    output_path.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8"
    )

    print("\n" + "=" * 70)
    print("FINAL COMPARISON")
    print("=" * 70)

    for row in summary:
        print(
            f"FAISS={row['faiss_weight']:.2f} "
            f"BM25={row['bm25_weight']:.2f} "
            f"Hit@5={row['hit_at_5']:.3f} "
            f"MRR@5={row['mrr_at_5']:.3f} "
            f"P@5={row['precision_at_5']:.3f} "
            f"nDCG@5={row['ndcg_at_5']:.3f}"
        )

    print("\nResults saved to:", output_path)


if __name__ == "__main__":
    main()
