import json
from pathlib import Path

from rag.advisor_retrieval import retrieve_for_advisor

ROOT = Path(__file__).resolve().parents[1]

QUESTIONS_FILE = ROOT / "tests" / "retrieval_questions.json"

TOP_K = 5


def evaluate_question(question, results):
    expected = set(question["relevant_course_codes"])

    retrieved = [
        result.get("course_code")
        for result in results[:TOP_K]
    ]

    ranks = [
        i + 1
        for i, code in enumerate(retrieved)
        if code in expected
    ]

    hit = 1.0 if ranks else 0.0
    rr = 1.0 / ranks[0] if ranks else 0.0

    return hit, rr


def main():
    questions = json.loads(
        QUESTIONS_FILE.read_text(encoding="utf-8")
    )

    total_hits = 0.0
    total_rr = 0.0
    exact_count = 0
    hybrid_count = 0

    print("=" * 60)
    print("USC ADVISOR AI - ROUTED RETRIEVAL EVALUATION")
    print("=" * 60)

    for question in questions:
        results = retrieve_for_advisor(
            question=question["question"],
            term_code=question.get("term_code"),
            top_k=TOP_K
        )

        hit, rr = evaluate_question(question, results)

        total_hits += hit
        total_rr += rr

        method = (
            results[0].get("retrieval_method", "none")
            if results else "none"
        )

        if method == "exact":
            exact_count += 1
        elif method == "hybrid":
            hybrid_count += 1

        top_result = (
            results[0].get("course_code", "N/A")
            if results else "None"
        )

        print(
            f"{question['id']}: "
            f"Method={method:<7} "
            f"Hit@5={int(hit)} "
            f"RR={rr:.3f} "
            f"Top={top_result}"
        )

    n = len(questions)

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)

    print(f"Questions evaluated: {n}")
    print(f"Exact lookups: {exact_count}")
    print(f"Hybrid searches: {hybrid_count}")
    print(f"Hit Rate@5: {total_hits / n:.3f}")
    print(f"MRR@5:      {total_rr / n:.3f}")


if __name__ == "__main__":
    main()
