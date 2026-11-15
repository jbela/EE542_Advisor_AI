"""Evaluate USC academic policy retrieval at document level."""

import json
from pathlib import Path
from urllib.parse import urlparse

from rag.advisor_retrieval import retrieve_for_advisor

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_FILE = ROOT / "tests" / "retrieval_questions_v2.json"


def unique_documents(results):
    """Keep the highest-ranked chunk from each document."""

    seen = set()
    unique = []

    for result in results:
        document_id = result.get("document_id")

        if not document_id or document_id in seen:
            continue

        seen.add(document_id)
        unique.append(result)

    return unique


def evaluate_policy(question, results):
    expected = set(question["expected_document_ids"])
    unique = unique_documents(results)

    first_rank = None

    for rank, result in enumerate(unique[:5], start=1):
        if result["document_id"] in expected:
            first_rank = rank
            break

    valid_urls = all(
        urlparse(r.get("url") or r.get("source_url") or "").scheme
        in ("http", "https")
        and bool(
            urlparse(
                r.get("url") or r.get("source_url") or ""
            ).netloc
        )
        for r in unique[:5]
    )

    return {
        "hit_at_5": int(first_rank is not None),
        "reciprocal_rank": (
            1 / first_rank if first_rank else 0
        ),
        "top_1": int(first_rank == 1),
        "unique_documents": len(unique),
        "valid_urls": valid_urls,
        "first_relevant_rank": first_rank,
        "document_ids": [
            r["document_id"] for r in unique[:5]
        ],
    }


def main():
    questions = json.loads(
        QUESTIONS_FILE.read_text(encoding="utf-8")
    )

    selected = [
        q for q in questions
        if q["category"] == "policy"
    ]

    total_hit = 0
    total_rr = 0
    total_top1 = 0

    print("=" * 65)
    print("USC ADVISOR AI - POLICY RETRIEVAL EVALUATION")
    print("=" * 65)

    for q in selected:
        results = retrieve_for_advisor(
            q["question"],
            term_code=q.get("term_code", "20271"),
            top_k=20,
        )

        metrics = evaluate_policy(q, results)

        total_hit += metrics["hit_at_5"]
        total_rr += metrics["reciprocal_rank"]
        total_top1 += metrics["top_1"]

        print(
            f"{q['id']}: "
            f"Hit@5={metrics['hit_at_5']} "
            f"RR={metrics['reciprocal_rank']:.3f} "
            f"Top1={metrics['top_1']} "
            f"Unique={metrics['unique_documents']} "
            f"URLsValid={metrics['valid_urls']}"
        )

        print(
            "  Documents:",
            metrics["document_ids"]
        )

    n = len(selected)

    print("\n" + "=" * 65)
    print(f"Questions evaluated: {n}")
    print(f"Document Hit@5: {total_hit / n:.3f}")
    print(f"Document MRR@5: {total_rr / n:.3f}")
    print(f"Document Top-1 Accuracy: {total_top1 / n:.3f}")
    print("=" * 65)


if __name__ == "__main__":
    main()
