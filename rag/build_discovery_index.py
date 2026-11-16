"""Build a separate BGE index for semantic EE course discovery."""

import hashlib
import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from rag.index_publisher import publish_index


ROOT = Path(__file__).resolve().parents[1]

COURSES_DIR = ROOT / "data" / "courses"
INDEX_DIR = ROOT / "indexes" / "discovery"

MODEL_NAME = "BAAI/bge-base-en-v1.5"
DISCOVERY_SCHEMA_VERSION = "2"


def build_course_text(course):
    """Create focused semantic-search text from official course data."""

    parts = [
        f"Course: {course.get('course_code', '')}",
        f"Title: {course.get('title', '')}",
        f"Description: {course.get('description') or ''}"
    ]

    preparation = course.get("recommended_preparation")

    if preparation:
        parts.append(
            f"Recommended preparation: {preparation}"
        )

    return "\n".join(parts)


def load_discovery_documents(courses_dir=None):
    """Load course records from all collected semesters."""

    courses_dir = (
        Path(courses_dir)
        if courses_dir is not None
        else COURSES_DIR
    )

    documents = []

    for path in sorted(courses_dir.glob("ee_*.json")):
        dataset = json.loads(
            path.read_text(encoding="utf-8")
        )

        term_code = str(dataset["term_code"])
        source_url = dataset.get("source_url")

        for course in dataset["courses"]:
            code = course.get("course_code")
            title = course.get("title")

            if not code or not title:
                continue

            course_id = course.get("course_id")

            if course_id is None:
                raise ValueError(
                    f"Missing course ID for {code} in {term_code}"
                )

            document_id = (
                f"course_{term_code}_{course_id}"
            )

            documents.append({
                "chunk_id": document_id,
                "document_id": document_id,
                "text": build_course_text(course),
                "title": f"{code} - {title}",
                "url": (
                    course.get("source_url")
                    or f"https://classes.usc.edu/term/{term_code}/course/"
                    f"{code.replace(' ', '')}"
                ),
                "category": "course",
                "source_type": "catalog",
                "course_code": code,
                "term_code": term_code,
                "retrieved_at": dataset.get("collected_at")
            })

    return documents


def calculate_discovery_fingerprint(courses_dir=None):
    """Fingerprint only inputs used in discovery embeddings."""

    documents = load_discovery_documents(courses_dir)

    if not documents:
        raise ValueError("No courses available for discovery indexing.")

    payload = [
        {
            "chunk_id": doc["chunk_id"],
            "text": doc["text"],
            "term_code": doc["term_code"],
            "title": doc["title"],
            "url": doc["url"]
        }
        for doc in documents
    ]

    serialized = json.dumps(
        {
            "model": MODEL_NAME,
            "schema_version": DISCOVERY_SCHEMA_VERSION,
            "documents": payload
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def main():
    print("=" * 65)
    print("USC ADVISOR AI - BGE DISCOVERY INDEX")
    print("=" * 65)

    starting_fingerprint = calculate_discovery_fingerprint()

    documents = load_discovery_documents()

    if not documents:
        raise ValueError("No course records found.")

    chunk_ids = [doc["chunk_id"] for doc in documents]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Duplicate discovery document IDs detected.")

    print("Course records:", len(documents))
    print("Embedding model:", MODEL_NAME)

    model = SentenceTransformer(MODEL_NAME)

    embeddings = model.encode(
        [doc["text"] for doc in documents],
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=32,
        show_progress_bar=True
    )

    embeddings = np.asarray(
        embeddings,
        dtype=np.float32
    )

    if embeddings.ndim != 2:
        raise ValueError("Invalid embedding shape.")

    if embeddings.shape[0] != len(documents):
        raise ValueError("Embedding count mismatch.")

    if not np.isfinite(embeddings).all():
        raise ValueError("Embeddings contain invalid values.")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    ending_fingerprint = calculate_discovery_fingerprint()

    if starting_fingerprint != ending_fingerprint:
        raise RuntimeError(
            "Course data changed during discovery indexing."
        )

    manifest = publish_index(
        index=index,
        documents=documents,
        model_name=MODEL_NAME,
        index_dir=INDEX_DIR,
        knowledge_fingerprint=starting_fingerprint
    )

    print("\nDISCOVERY INDEX BUILD COMPLETE")
    print("Course records:", len(documents))
    print("Embedding dimension:", embeddings.shape[1])
    print("Published version:", manifest["version"])

    return manifest


if __name__ == "__main__":
    main()
