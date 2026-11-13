import csv
import json
from collections import Counter
from pathlib import Path

from rag.advisor_retrieval import retrieve_for_advisor

ROOT = Path(__file__).resolve().parents[1]

QUESTIONS_FILE = ROOT / "tests" / "retrieval_questions_v2.json"
OUTPUT_FILE = ROOT / "reports" / "retrieval_v2_results.csv"

TOP_K = 5


def evaluate(question, results):
    expected_courses = set(question.get("expected_courses", []))
    expected_docs = set(question.get("expected_document_ids", []))

    retrieved_courses = [
        r.get("course_code") for r in results[:TOP_K]
    ]

    retrieved_docs = [
        r.get("document_id") for r in results[:TOP_K]
    ]

    if expected_courses:
        ranks = [
            i + 1
            for i, code in enumerate(retrieved_courses)
            if code in expected_courses
        ]
    elif expected_docs:
        ranks = [
            i + 1
            for i, doc_id in enumerate(retrieved_docs)
            if doc_id in expected_docs
        ]
    else:
        ranks = []

    # Questions without relevance labels are not scored as misses.
    scorable = bool(expected_courses or expected_docs)

    hit = int(bool(ranks)) if scorable else None
    rr = (1 / ranks[0] if ranks else 0.0) if scorable else None

    expected_term = question.get("expected_source_term")

    source_term_correct = None
    if expected_term:
        source_term_correct = any(
            str(r.get("term_code")) == str(expected_term)
            for r in results
        )

    return {
        "hit_at_5": hit,
        "rr_at_5": rr,
        "source_term_correct": source_term_correct
    }


def main():
    questions = json.loads(
        QUESTIONS_FILE.read_text(encoding="utf-8")
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    rows = []

    print("=" * 70)
    print("USC ADVISOR AI - RETRIEVAL EVALUATION V2")
    print("=" * 70)

    for q in questions:
        try:
            results = retrieve_for_advisor(
                question=q["question"],
                term_code=q.get("term_code", "20271"),
                top_k=TOP_K
            )

            metrics = evaluate(q, results)

            method = (
                results[0].get("retrieval_method", "none")
                if results else "none"
            )

            top_course = (
                results[0].get("course_code", "")
                if results else ""
            )

            row = {
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "method": method,
                "top_course": top_course,
                "results_count": len(results),
                **metrics,
                "error": ""
            }

        except Exception as error:
            row = {
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "method": "error",
                "top_course": "",
                "results_count": 0,
                "hit_at_5": None,
                "rr_at_5": None,
                "source_term_correct": None,
                "error": str(error)
            }

        rows.append(row)

        print(
            f"{row['id']}: "
            f"{row['category']:<18} "
            f"method={row['method']:<7} "
            f"hit={row['hit_at_5']} "
            f"source_term={row['source_term_correct']}"
        )

    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    scored = [
        r for r in rows
        if r["hit_at_5"] is not None
    ]

    if scored:
        hit_rate = sum(r["hit_at_5"] for r in scored) / len(scored)
        mrr = sum(r["rr_at_5"] for r in scored) / len(scored)

        print(f"Scored questions: {len(scored)}")
        print(f"Hit Rate@5: {hit_rate:.3f}")
        print(f"MRR@5: {mrr:.3f}")

    print("Methods:", dict(Counter(r["method"] for r in rows)))
    print("Errors:", sum(bool(r["error"]) for r in rows))
    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
