# USC Advisor AI

Final Project for EE 542 — Fall 2026
Professor Young Cho
University of Southern California

## Project Overview

USC Advisor AI is an AI-powered academic advising assistant designed to help students explore Electrical Engineering courses, understand prerequisites, review historical course offerings, and find relevant USC academic policies.

The application combines structured USC academic data with retrieval-augmented generation (RAG) and a locally hosted large language model.

### Features

- **Semantic course discovery:** Find relevant EE courses using natural-language questions about topics, skills, and technologies.
- **Course information:** Retrieve course descriptions, prerequisites, and recommended preparation.
- **Historical course catalogs:** Explore collected EE course listings across multiple semesters.
- **Prerequisite verification:** Preserve structured prerequisite relationships, including AND/OR requirements.
- **Academic policy retrieval:** Answer questions using collected USC policy documents.
- **Syllabus retrieval:** Retrieve information from imported course syllabi used for proof-of-concept testing.
- **Source citations:** Link course recommendations to official USC course listings.
- **Automated synchronization:** Detect academic data changes and rebuild affected retrieval indexes.

## System Architecture

The application uses:

| Component | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | FastAPI |
| Local LLM | Ollama with Qwen 2.5 3B |
| Semantic course retrieval | BAAI/bge-base-en-v1.5 |
| General RAG retrieval | MiniLM, FAISS, BM25 |
| Vector search | FAISS |
| Data ingestion | Python, Requests, BeautifulSoup |
| Academic data | USC course catalogs and policy sources |

The retrieval system uses two separate indexes.

**General RAG index:** Uses MiniLM and BM25 for policy and document retrieval.

**Course discovery index:** Uses BGE embeddings to identify relevant courses from natural-language descriptions of academic interests.

Exact course lookups and verified prerequisite relationships use structured course records rather than relying exclusively on semantic similarity.

## Local Setup

The application can run locally without an AWS GPU. Performance depends on the available CPU, memory, and GPU hardware.

### 1. Clone the repository

```powershell
git clone https://github.com/jbela/EE542_Advisor_AI.git
cd EE542_Advisor_AI
```

### 2. Install Python dependencies

```powershell
py -m pip install -r requirements.txt
```

### 3. Install Ollama

Download Ollama from:

https://ollama.com/download/windows

After installation, download the local language model:

```powershell
ollama pull qwen2.5:3b
```

Verify that Ollama is available:

```powershell
ollama list
```

Ensure the Ollama server is running before starting the backend.

### 4. Collect academic data

The repository excludes generated academic data and FAISS indexes. These must be created locally.

Run the automated academic synchronization:

```powershell
py -m ingestion.run_sync
```

This process discovers semesters, collects active EE course records and USC policies, and builds the general RAG and BGE discovery indexes.

The first execution may take several minutes because embedding models must be downloaded and indexes generated.

### 5. Collect historical course records

To collect missing archived semesters within the configured five-year window:

```powershell
py -m ingestion.backfill_history --years 5
```

Historical backfill synchronizes both retrieval indexes after collecting academic data.

A dry run is also available:

```powershell
py -m ingestion.backfill_history --years 5 --dry-run
```

Academic collection requires access to the USC data sources. Failed requests are reported, and historical coverage may be incomplete if sources are unavailable.

### 6. Start the backend

In a PowerShell terminal:

```powershell
py -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend runs at:

http://127.0.0.1:8000

### 7. Start the frontend

In another PowerShell terminal:

```powershell
py -m streamlit run frontend/app.py
```

Open:

http://localhost:8501

Keep Ollama, FastAPI, and Streamlit running while using the application.

## Updating Academic Data

Run:

```powershell
py -m ingestion.run_sync
```

The synchronization workflow checks academic data and rebuilds indexes when changes are detected.

The BGE discovery index can also be synchronized independently:

```powershell
py -m rag.sync_discovery_index
```

The general RAG index can be synchronized with:

```powershell
py -m rag.sync_index
```

## Testing

Run all automated unit tests:

```powershell
py -m unittest discover -s tests -v
```

Run prerequisite evaluation:

```powershell
py -m rag.evaluate_prerequisites
```

Run semantic course retrieval evaluation:

```powershell
py -m rag.evaluate_semantic_courses
```

Additional evaluation scripts compare embedding models and course-text formatting strategies.

## Retrieval Evaluation

Development and holdout experiments compare MiniLM and BGE embeddings for semantic course discovery.

The experiments evaluate:

- Hit@5
- Mean Reciprocal Rank at 5 (MRR@5)
- Precision@5
- Normalized Discounted Cumulative Gain at 5 (nDCG@5)

The selected BGE discovery approach improves semantic matching for questions that do not explicitly mention course titles.

Evaluation results are stored in the `reports/` directory.

## Limitations

- Course availability and enrollment eligibility must be verified against current official USC records.
- Historical course listings do not guarantee future offerings.
- Prerequisite information may require additional verification.
- The syllabus retrieval component currently uses a limited proof-of-concept dataset.
- AI-generated advising responses may require review by an official academic advisor.
- Academic data collection depends on the availability of USC source systems.

## Disclaimer

USC Advisor AI is an academic project and is not an official USC advising service. Students should verify important academic decisions with USC's official course catalog and academic advisors.
