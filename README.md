
# USC Advisor AI

Final Project for EE 542 — Fall 2026  
Professor Young Cho  
University of Southern California

## Project Overview

USC Advisor AI is an AI-powered academic advising assistant designed to help students explore Electrical Engineering courses, understand prerequisites, review historical course offerings, access course syllabi, and find relevant USC academic policies.

The application combines structured USC academic data with retrieval-augmented generation (RAG), semantic search, verified academic information, and a locally hosted large language model.

The goal is to develop a digital academic advising assistant that provides accurate, source-grounded answers to common student questions while reducing reliance on manual information searches.

## Features

- **Semantic course discovery:** Find relevant EE courses using natural-language questions about topics, skills, and technologies.
- **Course information:** Retrieve course descriptions, prerequisites, and recommended preparation.
- **Historical course catalogs:** Explore collected EE course listings across multiple semesters.
- **Prerequisite verification:** Preserve structured prerequisite relationships, including AND/OR requirements.
- **Academic policy retrieval:** Answer questions using collected USC policy documents.
- **Syllabus retrieval:** Retrieve course-specific information from imported syllabi.
- **Hybrid syllabus search:** Combine semantic similarity, keyword matching, and section-aware reranking.
- **Verified grading information:** Extract and review assessment weights and grading policies using source validation.
- **Deterministic grading comparisons:** Compare verified grading policies across courses without relying on LLM-generated interpretations.
- **Source citations:** Attribute answers to the relevant USC course records, policy documents, or syllabus pages.
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
| Academic data | USC course catalogs, syllabi, and policy sources |

### Retrieval Architecture

The retrieval system uses two separate indexes.

**General RAG index:** Uses MiniLM embeddings and BM25 keyword matching for academic policy, course, and syllabus document retrieval.

**Course discovery index:** Uses BGE embeddings to identify relevant courses from natural-language descriptions of academic interests.

Exact course lookups and verified prerequisite relationships use structured course records rather than relying exclusively on semantic similarity.

### Syllabus Retrieval

Imported syllabi are processed into page-aware, section-aware searchable chunks.

The syllabus retrieval pipeline includes:

1. PDF text extraction.
2. Course, semester, section, and instructor metadata.
3. Section-aware document chunking.
4. Semantic retrieval using MiniLM.
5. BM25 keyword retrieval.
6. Reciprocal Rank Fusion (RRF).
7. Syllabus-specific reranking.
8. Source-grounded answer generation.

This approach allows the assistant to retrieve relevant information even when a student's question does not use the exact wording found in the syllabus.

### Verified Grading Information

For grading-related questions, the system also supports structured, reviewed information.

The workflow includes:

1. Automatic extraction of grading-weight candidates.
2. Automatic extraction of grading-policy candidates.
3. Source quotation and page validation.
4. Human review and approval.
5. Storage of verified grading records.
6. Validation against the original syllabus before retrieval.

Verified records are associated with their original document identifiers and source hashes.

If the source document changes, previously reviewed records must be revalidated.

### Deterministic Grading Comparisons

When complete verified grading profiles are available for the requested courses and semester, the backend generates grading comparisons directly from structured records.

This reduces the risk of mixing grading policies between different courses.

If a required verified grading profile is unavailable, the system reports that a reliable comparison cannot be established from the reviewed records.

General course comparisons and other academic questions continue through the existing retrieval pipeline.

## Local Setup

The application can run locally without an AWS GPU. Performance depends on the available CPU, memory, and GPU hardware.

### 1. Clone the repository

```powershell
git clone https://github.com/jbela/EE542_Advisor_AI.git
cd EE542_Advisor_AI
```

To use the syllabus development branch before it is merged into `main`:

```powershell
git switch feature/syllabus-policy-rag
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

This process discovers semesters, collects EE course records and USC policies, and builds the general RAG and BGE discovery indexes.

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

Academic collection requires access to USC data sources. Failed requests are reported, and historical coverage may be incomplete if sources are unavailable.

### 6. Initialize syllabus data

The repository includes two proof-of-concept syllabi:

- EE 510 — Linear Algebra, Fall 2026
- EE 542 — Internet and Cloud Computing, Fall 2026

The original PDFs are stored in:

```text
data/syllabus_poc/pdfs/
```

To import both syllabi and synchronize the general RAG index:

```powershell
py -m ingestion.import_poc_syllabi
```

This command generates local syllabus records and makes the documents searchable.

The repository also includes reviewed grading records in:

```text
data/syllabus_poc/reviewed_grading/
```

These records contain approved grading weights and policy statements that are validated against their original syllabus documents.

The initial reviewed data includes:

**EE 510**
- Homework: 20%
- Midterm: 40%
- Final: 40%
- Grade-threshold adjustment policy
- Participation-based grade adjustment policy

**EE 542**
- Attendance, participation, and quizzes: 15%
- Reading assignments: 10%
- Laboratory assignments: 25%
- Final project: 50%
- Late-submission penalty
- Grade-dispute procedure

The grading-profile system is designed to work with additional imported syllabi without requiring course-specific Python logic.

### 7. Start the backend

In a PowerShell terminal:

```powershell
py -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend runs at:

http://127.0.0.1:8000

On startup the backend loads the retrieval models and the LLM in the
background so the first question is not slow. LLM settings can be changed
with environment variables (defaults shown):

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5:3b` | Model used for generated answers |
| `OLLAMA_URL` | `http://127.0.0.1:11434/api/chat` | Ollama chat endpoint |
| `OLLAMA_KEEP_ALIVE` | `30m` | How long the model stays loaded between questions |
| `OLLAMA_TEMPERATURE` | `0` | Deterministic answers for repeatable runs |
| `OLLAMA_NUM_PREDICT` | `320` | Maximum answer length in tokens |
| `OLLAMA_RETRY_NUM_PREDICT` | `280` | Maximum length of the citation-repair retry |
| `OLLAMA_TIMEOUT` | `180` | LLM request timeout in seconds |
| `TG_WARMUP` | `1` | Set to `0` to skip the startup warm-up |

To measure LLM latency on a machine (for example a GPU instance):

```powershell
py tests/benchmark_llm_latency.py qwen2.5:3b qwen2.5:7b --runs 3
```

Results are written to `reports/llm_latency.csv`.

### 8. Start the frontend

In another PowerShell terminal:

```powershell
py -m streamlit run frontend/app.py
```

Open:

http://localhost:8501

Keep Ollama, FastAPI, and Streamlit running while using the application.

## Adding New Syllabi

The syllabus ingestion and grading-review workflow is designed to support additional courses and semesters.

### 1. Import a syllabus

Place the PDF in an appropriate local directory.

Example:

```powershell
py -m ingestion.import_syllabus --pdf "path/to/syllabus.pdf" --course "EE 500" --term 20263 --section "Unspecified" --instructor "Instructor Name"
```

Replace the example course information with the actual syllabus metadata.

The importer generates a structured JSON document containing extracted pages and course metadata.

Use `--overwrite` only when intentionally replacing an existing imported document.

### 2. Extract grading candidates

Run:

```powershell
py -m ingestion.extract_syllabus_facts
```

To extract candidates for one course:

```powershell
py -m ingestion.extract_syllabus_facts --course "EE 500"
```

The extractor identifies potential grading weights and policy statements.

Candidates are stored in:

```text
data/processed/syllabi_candidates/
```

Extracted candidates are not automatically considered verified.

### 3. Review grading information

Run the review workflow using the imported syllabus document ID:

```powershell
py -m ingestion.review_syllabus_facts --document-id syllabus_ee500_20263_unspecified
```

The reviewer can approve, reject, skip, or cancel each candidate.

Approved records are saved to:

```text
data/syllabus_poc/reviewed_grading/
```

The review process validates source quotations and page references, preserves existing approved records, and prevents duplicate entries.

### 4. Synchronize the RAG index

After importing a new syllabus:

```powershell
py -m rag.sync_index
```

The new syllabus can then be retrieved through the general RAG system.

Verified grading information becomes available when a valid reviewed grading profile exists for the corresponding course and semester.

## Example Questions

USC Advisor AI supports questions such as:

**Course discovery**

- Which EE courses cover machine learning?
- What courses should I consider if I am interested in cloud computing?
- Which courses teach computer networking?

**Prerequisites**

- What are the prerequisites for EE 562?
- Can I take a course if I have completed certain prerequisites?
- What preparation is recommended before taking a course?

**Historical course information**

- Was EE 510 offered in Fall 2025?
- Which EE courses were listed in Spring 2026?
- How have course offerings changed across semesters?

**Syllabus information**

- What is the grading policy for EE 510 in Fall 2026?
- How much is the final project worth in EE 542?
- Does EE 542 require Python programming?
- What textbook does EE 510 use?
- What happens if I submit an EE 542 assignment late?

**Grading comparisons**

- Compare the grading policies of EE 510 and EE 542 in Fall 2026, including grade adjustments.

**Academic policies**

- What are USC's registration requirements?
- Where can international students find information about maintaining status?
- What should a student do when an academic policy requires an exception or approval?

Answers depend on the academic documents and verified records available in the local knowledge base.

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

Run syllabus grading tests:

```powershell
py -m unittest discover -s tests -p "test_syllabus_grading.py" -v
```

Run syllabus extraction tests:

```powershell
py -m unittest discover -s tests -p "test_syllabus_fact_extraction.py" -v
```

Run syllabus review tests:

```powershell
py -m unittest discover -s tests -p "test_syllabus_fact_review.py" -v
```

Run deterministic grading-comparison API tests:

```powershell
py -m unittest discover -s tests -p "test_syllabus_grading_comparison_api.py" -v
```

Run syllabus reranking tests:

```powershell
py -m unittest discover -s tests -p "test_syllabus_reranker.py" -v
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
- Syllabus coverage is currently limited to the imported proof-of-concept documents.
- Verified grading comparisons require reviewed grading profiles for every requested course and semester.
- Unavailable or unverified grading information is not treated as an established course policy.
- Reviewed grading profiles may not contain every policy described in the original syllabus.
- Some PDF text extraction artifacts may affect the formatting of retrieved quotations.
- AI-generated advising responses may require review by an official academic advisor.
- Academic data collection depends on the availability of USC source systems.
- The system does not replace official academic advising or authorized university decisions.

## Disclaimer

USC Advisor AI is an academic project developed for EE 542 at the University of Southern California.

It is not an official USC advising service.

Students should verify important academic decisions, including course requirements, registration eligibility, degree progress, and academic policies, with USC's official course catalog and authorized academic advisors.
