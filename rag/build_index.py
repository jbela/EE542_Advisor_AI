
import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from rag.index_publisher import publish_index
from rag.knowledge_fingerprint import calculate_fingerprint
from ingestion.verified_requirements import apply_verified_requirements

# --------------------------------------------------
# Project configuration
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw"
SYLLABI_DIR = ROOT / "data" / "processed" / "syllabi"
COURSES_DIR = ROOT / "data" / "courses"
INDEX_DIR = ROOT / "indexes"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

INDEX_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Text chunking
# --------------------------------------------------

def chunk_text(text, chunk_size=180, overlap=30):
    """Split academic documents into overlapping chunks."""

    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Invalid chunk size or overlap")

    words = text.split()
    chunks = []

    step = chunk_size - overlap

    for start in range(0, len(words), step):
        chunk = " ".join(
            words[start:start + chunk_size]
        )

        if chunk.strip():
            chunks.append(chunk)

    return chunks


def chunk_syllabus_text(text, chunk_size=180, overlap=30):
    """Split syllabus text at verified heading boundaries."""

    import re

    headings = [
        "Course Description",
        "Recommended Courses",
        "Required Textbook",
        "Other Requirements",
        "Grading Policies",
        "Grading",
        "Preparation for Classes",
        "Statement on Academic Integrity",
        "Lecture Contents",
        "Reading Assignments",
        "Laboratory Assignments",
        "Final Project",
        "Project Demonstrations",
        "Project Report",
        "Class Participation",
        "Special dates/times",
        "Course Topics",
    ]

    heading_pattern = re.compile(
        r"^("
        + "|".join(
            re.escape(h)
            for h in sorted(headings, key=len, reverse=True)
        )
        + r")\s*:?\s*$",
        re.IGNORECASE,
    )

    lines = text.splitlines()

    sections = []
    current_heading = "General"
    current_lines = []

    def save_section():
        if current_lines:
            section_text = "\n".join(current_lines).strip()

            if section_text:
                sections.append(
                    (current_heading, section_text)
                )

    for line in lines:
        stripped = line.strip()
        match = heading_pattern.fullmatch(stripped)

        if match:
            save_section()
            current_heading = match.group(1)
            current_lines = [stripped]
        else:
            current_lines.append(line)

    save_section()

    results = []

    for section_name, section_text in sections:
        for chunk in chunk_text(
            section_text,
            chunk_size=chunk_size,
            overlap=overlap,
        ):
            results.append({
                "section": section_name,
                "text": chunk,
            })

    return results

# --------------------------------------------------
# Process USC academic and policy documents
# --------------------------------------------------

def load_policy_documents():
    """Load previously collected USC academic documents."""

    documents = []

    for file in sorted(RAW_DIR.glob("*.json")):
        data = json.loads(
            file.read_text(encoding="utf-8")
        )

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

        print(
            f"{data['title']}: {len(chunks)} chunks"
        )

    return documents


# --------------------------------------------------
# Process structured USC EE courses
# --------------------------------------------------

def load_course_documents():
    """Convert semester-specific EE courses into searchable text."""

    documents = []

    for file in sorted(COURSES_DIR.glob("ee_*.json")):
        dataset = json.loads(
            file.read_text(encoding="utf-8")
        )

        term_code = str(dataset["term_code"])
        source_url = dataset["source_url"]

        count = 0

        for course in dataset["courses"]:
            course = apply_verified_requirements(
                course,
                term_code
            )
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

            # Readable prerequisite information
            prerequisites = course.get(
                "prerequisites_display"
            )

            if prerequisites:
                parts.append(
                    "Prerequisite information: "
                    + json.dumps(
                        prerequisites,
                        ensure_ascii=False
                    )
                )

            # Readable corequisite information
            corequisites = course.get(
                "corequisites_display"
            )

            if corequisites:
                parts.append(
                    "Corequisite information: "
                    + json.dumps(
                        corequisites,
                        ensure_ascii=False
                    )
                )

            if course.get("recommended_preparation"):
                parts.append(
                    "Recommended preparation: "
                    + str(
                        course["recommended_preparation"]
                    )
                )

            if course.get("restrictions"):
                parts.append(
                    "Restrictions: "
                    + json.dumps(
                        course["restrictions"],
                        ensure_ascii=False
                    )
                )

            text = "\n".join(parts)

            course_id = course.get("course_id")

            if course_id is None:
                raise ValueError(
                    f"Missing course ID for {course_code}"
                )

            document_id = (
                f"course_{term_code}_{course_id}"
            )

            documents.append({
                "chunk_id": document_id,
                "document_id": document_id,
                "text": text,
                "title": f"{course_code} - {title}",
                "url": source_url,
                "category": "course",
                "term_code": term_code,
                "course_code": course_code,
                "retrieved_at": dataset.get(
                    "collected_at"
                )
            })

            count += 1

        print(
            f"Added {count} EE courses from term {term_code}"
        )

    return documents

def load_syllabus_documents():
    """Turn imported syllabi into page-aware searchable chunks."""
    documents = []

    for file in sorted(SYLLABI_DIR.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))

        for page in data["pages"]:
            page_number = page["page_number"]
            text = page["text"].strip()

            if not text:
                continue

            for i, item in enumerate(chunk_syllabus_text(text)):
                section_name = item["section"]
                chunk = item["text"]
                documents.append({
                    "chunk_id": (
                        f"{data['id']}_p{page_number}_{i}"
                    ),
                    "document_id": data["id"],
                    "title": data["title"],
                    "text": (
                        f"Course: {data['course_code']}\n"
                        f"Source term: {data['term_code']}\n"
                        f"Class section: {data['section_label']}\n"
                        f"Syllabus topic: {section_name}\n"
                        f"Source: Syllabus, page {page_number}\n\n"
                        f"{chunk}"
                    ),
                    "syllabus_section": section_name,
                    "url": data.get("url"),
                    "category": "course",
                    "source_type": "syllabus",
                    "course_code": data["course_code"],
                    "term_code": data["term_code"],
                    "section_label": data["section_label"],
                    "instructor": data.get("instructor"),
                    "source_file": data["source_file"],
                    "page_number": page_number,
                })

        print(
            f"{data['title']}: "
            f"{len(data['pages'])} pages processed"
        )

    return documents

# --------------------------------------------------
# Build and publish FAISS index
# --------------------------------------------------

def main():
    # Record the academic data state before indexing.
    starting_fingerprint = calculate_fingerprint()

    print("Loading USC academic documents...")

    policy_documents = load_policy_documents()
    course_documents = load_course_documents()
    syllabus_documents = load_syllabus_documents()

    documents = policy_documents + course_documents + syllabus_documents

    if not documents:
        raise ValueError(
            "No academic documents found to index."
        )

    chunk_ids = [doc["chunk_id"] for doc in documents]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError(
            "Duplicate chunk IDs detected."
        )

    print(
        f"\nTotal searchable chunks: {len(documents)}"
    )

    print("\nLoading embedding model...")

    model = SentenceTransformer(MODEL_NAME)

    print("\nGenerating embeddings...")

    embeddings = model.encode(
        [doc["text"] for doc in documents],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    embeddings = np.asarray(
        embeddings,
        dtype=np.float32
    )

    if embeddings.ndim != 2:
        raise ValueError(
            "Embedding output must be a 2D matrix."
        )

    if embeddings.shape[0] != len(documents):
        raise ValueError(
            "Embedding count does not match document count."
        )

    if not np.isfinite(embeddings).all():
        raise ValueError(
            "Embeddings contain invalid numeric values."
        )

    print("\nBuilding FAISS index...")

    index = faiss.IndexFlatIP(
        embeddings.shape[1]
    )

    index.add(embeddings)

    if index.ntotal != len(documents):
        raise RuntimeError(
            "FAISS vector count does not match documents."
        )

    # Publish exactly once using the separate publisher.
    # The publisher writes and validates a complete version
    # before atomically updating indexes/current.json.

    # Confirm academic source data did not change during indexing.
    ending_fingerprint = calculate_fingerprint()

    if starting_fingerprint != ending_fingerprint:
        raise RuntimeError(
            "Academic source data changed during indexing. "
            "The new index will not be published. "
            "Retry after synchronization finishes."
        )

    manifest = publish_index(
        index=index,
        documents=documents,
        model_name=MODEL_NAME,
        index_dir=INDEX_DIR,
        knowledge_fingerprint=starting_fingerprint
    )

    print("\n" + "=" * 50)
    print("USC ADVISOR AI - INDEX BUILD COMPLETE")
    print("=" * 50)

    print(
        f"Policy chunks: {len(policy_documents)}"
    )

    print(
        f"Course records: {len(course_documents)}"
    )

    print(
        f"Total indexed chunks: {manifest['chunk_count']}"
    )

    print(
        f"Published index version: {manifest['version']}"
    )


if __name__ == "__main__":
    main()
