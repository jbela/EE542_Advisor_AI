import os
import uuid
from datetime import datetime, timezone
import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from rag.index_publisher import publish_index

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw"
INDEX_DIR = ROOT / "indexes"
VERSIONS_DIR = INDEX_DIR / "versions"
CURRENT_FILE = INDEX_DIR / "current.json"

VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
COURSES_DIR = ROOT / "data" / "courses"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

INDEX_DIR.mkdir(parents=True, exist_ok=True)


def chunk_text(text, chunk_size=180, overlap=30):
    words = text.split()
    chunks = []

    step = chunk_size - overlap

    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + chunk_size])

        if chunk.strip():
            chunks.append(chunk)

    return chunks


def main():
    print("Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    documents = []

    for file in sorted(RAW_DIR.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))

        chunks = chunk_text(data["text"])

        for i, chunk in enumerate(chunks):
            documents.append({
                "chunk_id": f"{data['id']}_{i}",
                "document_id": data["id"],
                "text": chunk,
                "title": data["title"],
                "url": data["url"],
                "category": data["category"],
                "retrieved_at": data.get("retrieved_at")
            })

        print(f"{data['title']}: {len(chunks)} chunks")

    
    # Add structured EE courses to the RAG index
    for file in sorted(COURSES_DIR.glob("ee_*.json")):
        dataset = json.loads(
            file.read_text(encoding="utf-8")
        )

        term_code = str(dataset["term_code"])
        source_url = dataset["source_url"]

        for course in dataset["courses"]:
            course_code = course.get("course_code")
            title = course.get("title")
            description = course.get("description")

            if not course_code or not title:
                continue

            parts = [
                f"Course: {course_code}",
                f"Title: {title}",
                f"Term: {term_code}"
            ]

            if description:
                parts.append(
                    f"Description: {description}"
                )

            if course.get("units"):
                parts.append(
                    f"Units: {course['units']}"
                )

            # Prerequisites
            prerequisites = course.get("prerequisites_display")

            if prerequisites:
                parts.append(
                    "Prerequisite information: "
                    + json.dumps(prerequisites, ensure_ascii=False)
                )

            # Corequisites
            corequisites = course.get("corequisites_display")

            if corequisites:
                parts.append(
                    "Corequisite information: "
                    + json.dumps(corequisites, ensure_ascii=False)
                )

            if course.get("recommended_preparation"):
                parts.append(
                    f"Recommended preparation: "
                    f"{course['recommended_preparation']}"
                )

            if course.get("restrictions"):
                parts.append(
                    f"Restrictions: {course['restrictions']}"
                )

            text = "\n".join(parts)

            documents.append({
                "chunk_id": (
                    f"course_{term_code}_"
                    f"{course['course_id']}"
                ),
                "document_id": (
                    f"course_{term_code}_"
                    f"{course['course_id']}"
                ),
                "text": text,
                "title": f"{course_code} - {title}",
                "url": source_url,
                "category": "course",
                "term_code": term_code,
                "course_code": course_code,
                "retrieved_at": dataset.get("collected_at")
            })

        print(
            f"Added EE courses from term {term_code}"
        )

    if not documents:
        raise ValueError("No documents found.")

    print("\nGenerating embeddings...")

    embeddings = model.encode(
        [doc["text"] for doc in documents],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    embeddings = np.asarray(embeddings, dtype=np.float32)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    # Create a unique version for this index
    version_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        + "_"
        + uuid.uuid4().hex[:8]
    )

    version_dir = VERSIONS_DIR / version_id
    version_dir.mkdir(parents=True, exist_ok=False)

    # Write the new index and its matching metadata
    index_path = version_dir / "faiss.index"
    chunks_path = version_dir / "chunks.json"

    faiss.write_index(index, str(index_path))

    chunks_path.write_text(
        json.dumps(documents, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Validate the saved index before publishing
    verified_index = faiss.read_index(str(index_path))

    verified_chunks = json.loads(
        chunks_path.read_text(encoding="utf-8")
    )

    if verified_index.ntotal != len(verified_chunks):
        raise RuntimeError(
            "Index validation failed: "
            "vector count does not match chunk count"
        )

    if verified_index.d != embeddings.shape[1]:
        raise RuntimeError(
            "Index validation failed: "
            "embedding dimensions do not match"
        )

    manifest = publish_index(
        index=index,
        documents=documents,
        model_name=MODEL_NAME,
        index_dir=INDEX_DIR
    )

    print(f"Published version: {manifest['version']}")
    print(f"Validated {manifest['chunk_count']} chunks.")

    temporary_manifest = INDEX_DIR / (
        f".current_{version_id}.tmp"
    )

    temporary_manifest.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8"
    )

    os.replace(temporary_manifest, CURRENT_FILE)

    print(f"Published index version: {version_id}")
    print(f"Validated {len(verified_chunks)} chunks.")


    print(f"\nSuccessfully indexed {len(documents)} chunks.")


if __name__ == "__main__":
    main()
