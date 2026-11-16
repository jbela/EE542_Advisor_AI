"""Compare embedding models and course text representations."""

import json
import math
import time
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from ingestion.verified_requirements import apply_verified_requirements


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

    dataset = json.loads(
        COURSES_FILE.read_text(encoding="utf-8")
    )

    term_code = str(dataset["term_code"])

    courses = [
        apply_verified_requirements(course, term_code)
        for course in dataset["courses"]
    ]

    return questions, courses, term_code


def build_full_text(course, term_code):
    parts = [
        f"Course: {course.get('course_code')}",
        f"Title: {course.get('title')}",
        f"Term: {term_code}"
    ]

    if course.get("description"):
        parts.append(
            f"Description: {course['description']}"
        )

    if course.get("units"):
        parts.append(
            f"Units: {course['units']}"
        )

    if course.get("prerequisites_display"):
        parts.append(
            "Prerequisite information: "
            + json.dumps(
                course["prerequisites_display"],
                ensure_ascii=False
            )
        )

    if course.get("corequisites_display"):
        parts.append(
            "Corequisite information: "
            + json.dumps(
                course["corequisites_display"],
                ensure_ascii=False
            )
        )

    if course.get("recommended_preparation"):
        parts.append(
            "Recommended preparation: "
            + str(course["recommended_preparation"])
        )

    if course.get("restrictions"):
        parts.append(
            "Restrictions: "
            + json.dumps(
                course["restrictions"],
                ensure_ascii=False
            )
        )

    return "\n".join(parts)


def build_clean_text(course):
    parts = [
        f"Course: {course.get('course_code')}",
        f"Title: {course.get('title')}",
        f"Description: {course.get('description') or ''}"
    ]

    if course.get("recommended_preparation"):
        parts.append(
            "Recommended preparation: "
            + str(course["recommended_preparation"])
        )

    return "\n".join(parts)


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

    ideal = min(len(expected), TOP_K)

    idcg = sum(
        1 / math.log2(rank + 1)
        for rank in range(1, ideal + 1)
    )

    ndcg = dcg / idcg if idcg else 0.0

    return {
        "hit_at_5": hit,
        "mrr_at_5": mrr,
        "precision_at_5": precision,
        "ndcg_at_5": ndcg
    }


def main():
    questions, courses, term_code = load_data()

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    codes = [c["course_code"] for c in courses]

    formats = {
        "full": [
            build_full_text(c, term_code)
            for c in courses
        ],
        "clean": [
            build_clean_text(c)
            for c in courses
        ]
    }

    output = {}

    print("=" * 70)
    print("USC ADVISOR AI - COURSE TEXT FORMAT EXPERIMENT")
    print("=" * 70)

    print("Courses:", len(courses))
    print("Questions:", len(questions))

    for model_label, model_name in MODELS.items():
        print("\nLoading:", model_label)

        model = SentenceTransformer(model_name)

        query_vectors = model.encode(
            [q["question"] for q in questions],
            normalize_embeddings=True,
            convert_to_numpy=True,
            batch_size=32
        ).astype(np.float32)

        for format_name, texts in formats.items():
            label = f"{model_label}_{format_name}"

            print("\n" + "=" * 70)
            print("CONFIGURATION:", label)
            print("=" * 70)

            start = time.perf_counter()

            embeddings = model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                batch_size=32,
                show_progress_bar=True
            ).astype(np.float32)

            index = faiss.IndexFlatIP(
                embeddings.shape[1]
            )

            index.add(embeddings)

            build_seconds = time.perf_counter() - start

            _, indices = index.search(
                query_vectors,
                TOP_K
            )

            totals = {
                "hit_at_5": 0.0,
                "mrr_at_5": 0.0,
                "precision_at_5": 0.0,
                "ndcg_at_5": 0.0
            }

            details = []

            for q, row in zip(questions, indices):
                retrieved = [
                    codes[int(i)]
                    for i in row
                    if i >= 0
                ]

                metrics = evaluate(
                    retrieved,
                    q["expected_courses"]
                )

                for key in totals:
                    totals[key] += metrics[key]

                details.append({
                    "id": q["id"],
                    "question": q["question"],
                    "expected": q["expected_courses"],
                    "retrieved": retrieved,
                    **metrics
                })

                print(
                    f"{q['id']}: "
                    f"Top5={retrieved} "
                    f"MRR={metrics['mrr_at_5']:.3f}"
                )

            n = len(questions)

            summary = {
                key: value / n
                for key, value in totals.items()
            }

            summary["build_seconds"] = build_seconds

            output[label] = {
                "model": model_name,
                "text_format": format_name,
                "summary": summary,
                "details": details
            }

            print("\nSUMMARY:", summary)

    path = REPORTS_DIR / "text_format_comparison.json"

    path.write_text(
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
            f"nDCG@5={s['ndcg_at_5']:.3f}"
        )

    print("\nSaved:", path)


if __name__ == "__main__":
    main()
