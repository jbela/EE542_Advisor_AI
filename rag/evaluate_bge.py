"""Compare BGE and MiniLM for semantic course retrieval."""

import json
import math
import time
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_FILE = ROOT / "tests" / "semantic_course_questions.json"
COURSES_FILE = ROOT / "data" / "courses" / "ee_20271.json"
REPORTS_DIR = ROOT / "reports"

MODELS = {
    "MiniLM": "sentence-transformers/all-MiniLM-L6-v2",
    "BGE": "BAAI/bge-base-en-v1.5"
}

TOP_K = 5


def load_data():
    questions = json.loads(
        QUESTIONS_FILE.read_text(encoding="utf-8")
    )

    data = json.loads(
        COURSES_FILE.read_text(encoding="utf-8")
    )

    courses = data["courses"]

    return questions, courses


def course_text(course):
    return (
        f"Course: {course.get('course_code', '')}\n"
        f"Title: {course.get('title', '')}\n"
        f"Description: {course.get('description', '') or ''}\n"
        f"Recommended preparation: "
        f"{course.get('recommended_preparation') or ''}"
    )


def evaluate(results, expected):
    expected = set(expected)

    relevant = [
        rank
        for rank, code in enumerate(results, 1)
        if code in expected
    ]

    hit = int(bool(relevant))
    mrr = 1 / relevant[0] if relevant else 0.0
    precision = len(relevant) / TOP_K

    dcg = sum(
        1 / math.log2(rank + 1)
        for rank in relevant
    )

    idcg = sum(
        1 / math.log2(rank + 1)
        for rank in range(
            1, min(len(expected), TOP_K) + 1
        )
    )

    ndcg = dcg / idcg if idcg else 0.0

    return {
        "hit_at_5": hit,
        "mrr_at_5": mrr,
        "precision_at_5": precision,
        "ndcg_at_5": ndcg
    }


def main():
    questions, courses = load_data()

    texts = [
        course_text(course)
        for course in courses
    ]

    codes = [
        course["course_code"]
        for course in courses
    ]

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output = {}

    print("=" * 70)
    print("USC ADVISOR AI - EMBEDDING MODEL COMPARISON")
    print("=" * 70)

    print("Courses:", len(courses))
    print("Questions:", len(questions))

    for label, model_name in MODELS.items():
        print("\n" + "=" * 70)
        print("MODEL:", label)
        print("=" * 70)

        model = SentenceTransformer(model_name)

        start = time.perf_counter()

        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            batch_size=32,
            show_progress_bar=True
        ).astype(np.float32)

        dimension = embeddings.shape[1]

        index = faiss.IndexFlatIP(dimension)
        index.add(embeddings)

        build_seconds = time.perf_counter() - start

        totals = {
            "hit_at_5": 0.0,
            "mrr_at_5": 0.0,
            "precision_at_5": 0.0,
            "ndcg_at_5": 0.0
        }

        details = []

        query_start = time.perf_counter()

        for q in questions:
            query_vector = model.encode(
                [q["question"]],
                normalize_embeddings=True,
                convert_to_numpy=True
            ).astype(np.float32)

            _, indices = index.search(
                query_vector,
                TOP_K
            )

            results = [
                codes[int(i)]
                for i in indices[0]
                if i >= 0
            ]

            metrics = evaluate(
                results,
                q["expected_courses"]
            )

            for key in totals:
                totals[key] += metrics[key]

            details.append({
                "id": q["id"],
                "question": q["question"],
                "expected": q["expected_courses"],
                "retrieved": results,
                **metrics
            })

            print(
                f"{q['id']}: "
                f"Top5={results} "
                f"MRR={metrics['mrr_at_5']:.3f}"
            )

        query_seconds = time.perf_counter() - query_start

        n = len(questions)

        summary = {
            key: value / n
            for key, value in totals.items()
        }

        summary["build_seconds"] = build_seconds
        summary["average_query_seconds"] = query_seconds / n

        output[label] = {
            "model_name": model_name,
            "embedding_dimension": dimension,
            "summary": summary,
            "details": details
        }

        print("\nMODEL SUMMARY")
        for key, value in summary.items():
            print(f"{key}: {value:.4f}")

    output_path = REPORTS_DIR / "embedding_comparison.json"

    output_path.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8"
    )

    print("\n" + "=" * 70)
    print("FINAL COMPARISON")
    print("=" * 70)

    for label, result in output.items():
        s = result["summary"]

        print(
            f"{label}: "
            f"Hit@5={s['hit_at_5']:.3f} "
            f"MRR@5={s['mrr_at_5']:.3f} "
            f"P@5={s['precision_at_5']:.3f} "
            f"nDCG@5={s['ndcg_at_5']:.3f} "
            f"AvgQuery={s['average_query_seconds']:.3f}s"
        )

    print("\nResults saved to:", output_path)


if __name__ == "__main__":
    main()
