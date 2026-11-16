"""Evaluate cross-encoder reranking on USC policy questions."""

import json
from pathlib import Path

from sentence_transformers import CrossEncoder

from rag.advisor_retrieval import retrieve_for_advisor
from rag.evaluate_policies import evaluate_policy

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_FILE = ROOT / "tests" / "retrieval_questions_v2.json"

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def rerank_with_cross_encoder(question, results, model):
    if not results:
        return []

    pairs = [
        (question, result.get("text", ""))
        for result in results
    ]

    scores = model.predict(pairs)

    reranked = []

    for rank, (result, score) in enumerate(
        zip(results, scores),
        start=1
    ):
        reranked.append({
            **result,
            "cross_encoder_score": float(score),
            "original_rank": rank
        })

    reranked.sort(
        key=lambda r: r["cross_encoder_score"],
        reverse=True
    )

    return reranked


def main():
    questions = json.loads(
        QUESTIONS_FILE.read_text(encoding="utf-8")
    )

    selected = [
        q for q in questions
        if q["category"] == "policy"
    ]

    print("Loading cross-encoder model...")
    model = CrossEncoder(MODEL_NAME)

    baseline_rr = 0
    reranked_rr = 0
    baseline_top1 = 0
    reranked_top1 = 0
    baseline_hits = 0
    reranked_hits = 0

    for q in selected:
        results = retrieve_for_advisor(
            q["question"],
            top_k=20
        )

        reranked = rerank_with_cross_encoder(
            q["question"],
            results,
            model
        )

        before = evaluate_policy(q, results)
        after = evaluate_policy(q, reranked)

        baseline_rr += before["reciprocal_rank"]
        reranked_rr += after["reciprocal_rank"]

        baseline_top1 += before["top_1"]
        reranked_top1 += after["top_1"]

        baseline_hits += before["hit_at_5"]
        reranked_hits += after["hit_at_5"]

        print(
            f"{q['id']}: "
            f"BeforeTop={results[0].get('document_id')} "
            f"AfterTop={reranked[0].get('document_id')} "
            f"BeforeRR={before['reciprocal_rank']:.3f} "
            f"AfterRR={after['reciprocal_rank']:.3f}"
        )

    n = len(selected)

    print("\n" + "=" * 65)
    print("USC POLICY CROSS-ENCODER EVALUATION")
    print("=" * 65)

    print(
        f"Baseline Hit@5: {baseline_hits/n:.3f}"
    )
    print(
        f"Reranked Hit@5: {reranked_hits/n:.3f}"
    )
    print(
        f"Baseline MRR@5: {baseline_rr/n:.3f}"
    )
    print(
        f"Reranked MRR@5: {reranked_rr/n:.3f}"
    )
    print(
        f"Baseline Top-1: {baseline_top1/n:.3f}"
    )
    print(
        f"Reranked Top-1: {reranked_top1/n:.3f}"
    )


if __name__ == "__main__":
    main()
