"""Student question API backed by USC retrieval and local Ollama inference."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import re
from datetime import date
from backend.advisor_email_service import get_demo_advising_response

from backend.rag_service import get_context, format_term
from backend.prerequisite_service import assess_prerequisite_scenario
from backend.student_question import is_personal_prerequisite, target_course
from backend.answer_quality import (
    answer_exact_prerequisites, check_citations, requires_source_citations,
    citation_coverage, course_citation_issues, cite_exact_course_listings,
    normalize_citation_groups,
)
from backend.prompts import RETRY as RETRY_PROMPT, system_prompt
from backend.policy_answers import final_semester_answer
from backend.course_schedule import headline, schedule_answer
from backend.quality_improvements import (
    course_discovery_answer, catalog_availability_answer,
    clearance_evidence_answer, cite_safe_policy_excerpts, citation_problems,
)
from rag.evidence_sufficiency import classify_evidence
from rag.advisor_retrieval import choose_retrieval_method, extract_semester
from rag.course_lookup import extract_course_codes
from rag.syllabus_grading_comparison import compare_grading_profiles

MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
# Keep the model in memory between questions; a cold load costs 10-25 s on CPU.
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
# Deterministic decoding so repeated runs (e.g. the recorded showdown) match.
TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0"))
NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "320"))
RETRY_NUM_PREDICT = int(os.getenv("OLLAMA_RETRY_NUM_PREDICT", "280"))
LLM_TIMEOUT = httpx.Timeout(float(os.getenv("OLLAMA_TIMEOUT", "180")), connect=10.0)

log = logging.getLogger("trojan_guide")


async def _ollama_chat(messages, num_predict):
    """One non-streaming Ollama chat call with the shared speed settings."""
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        response = await client.post(
            URL,
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False,
                "keep_alive": KEEP_ALIVE,
                "options": {"num_predict": num_predict, "temperature": TEMPERATURE},
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


def _warm_retrieval():
    """Load embedding models and indexes so the first question isn't slow."""
    import rag.retrieve  # noqa: F401  (loads MiniLM + the FAISS/BM25 index)
    from rag.discovery_retrieve import load_model
    load_model()


async def _warm_llm():
    """Load the model into memory; an empty chat only loads it."""
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        response = await client.post(
            URL, json={"model": MODEL, "messages": [], "keep_alive": KEEP_ALIVE},
        )
        response.raise_for_status()


async def warm_up():
    """Best-effort warm-up; failures are logged and never block startup."""
    for name, step in (("retrieval", asyncio.to_thread(_warm_retrieval)),
                       ("llm", _warm_llm())):
        try:
            await step
            log.warning("Warm-up complete: %s", name)
        except Exception as exc:  # noqa: BLE001 - warm-up must not crash the API
            log.warning("Warm-up skipped for %s: %s", name, exc)


@asynccontextmanager
async def lifespan(_app):
    task = None
    if os.getenv("TG_WARMUP", "1") != "0":
        task = asyncio.create_task(warm_up())
    yield
    if task is not None and not task.done():
        task.cancel()


app = FastAPI(title="USC Advisor AI Backend", lifespan=lifespan)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    term_code: str = "20271"

    department: str | None = None
    audience: str | None = None
    on_date: date | None = None
    include_demo_updates: bool = False


@app.get("/health")
def health():
    return {"status": "ok"}


def _response_sources(docs):
    return [
        {
            "id": doc["id"],
            "title": doc["title"],
            "url": doc["url"],
            "category": doc["category"],
            "retrieval_method": doc["retrieval_method"],
            "term_code": doc.get("term_code"),
            "historical": doc.get("historical", False),
            "requested_term": doc.get("requested_term"),
            "prerequisite_verification": doc.get("prerequisite_verification"),
            "document_id": doc.get("document_id"),
            "course_code": doc.get("course_code"),
            "source_type": doc.get("source_type"),
            "instructor": doc.get("instructor"),
            "section_label": doc.get("section_label"),
            "source_file": doc.get("source_file"),
            "page_number": doc.get("page_number"),
            "sender": doc.get("sender"),
            "email_date": doc.get("email_date"),
            "effective_from": doc.get("effective_from"),
            "effective_until": doc.get("effective_until"),
            "is_demo": doc.get("is_demo", False),
            "notice_title": doc.get("notice_title"),
            "notice_text": doc.get("notice_text"),
            "department": doc.get("department"),
            "audience": doc.get("audience"),
        }
        for doc in docs
    ]


@app.post("/ask")
async def ask(data: Question):
    question = data.question
    course_codes = extract_course_codes(question)
    requested_term = extract_semester(question)
    if data.include_demo_updates:
        if os.getenv("ALLOW_ADVISOR_EMAIL_DEMO") != "1":
            raise HTTPException(
                status_code=403,
                detail="Advisor email demo mode is disabled.",
            )

        if not course_codes:
            result = get_demo_advising_response(
                question,
                term_code=requested_term or data.term_code,
                department=data.department,
                audience=data.audience,
                on_date=data.on_date,
            )

            if result is not None:
                answer, doc = result
                has_evidence = doc is not None

                return {
                    "answer": answer,
                    "sources": _response_sources([doc]) if has_evidence else [],
                    "status": "demo" if has_evidence else "review_required",
                    "decision_status": (
                        "evidence_available" if has_evidence
                        else "evidence_unavailable"
                    ),
                    "invalid_citations": [],
                    "citations_required": has_evidence,
                    "missing_citations": False,
                    "cited_source_count": int(has_evidence),
                }
    comparison_requested = bool(re.search(
        r"\b(compare|comparison|differences?|versus|vs\.?)\b",
        question, re.IGNORECASE,
    ))
    grading_requested = bool(re.search(
        r"\b(grading|grades?|grade adjustments?|grading policies|grading weights?)\b",
        question, re.IGNORECASE,
    ))
    if comparison_requested and grading_requested and len(course_codes) >= 2 and requested_term is not None:
        comparison = compare_grading_profiles(course_codes, requested_term)
        if comparison is not None:
            return comparison
        return {
            "answer": (
                "I could not verify complete grading profiles for all requested "
                "courses in this semester. I cannot provide a reliable grading "
                "comparison from the available reviewed records. Please consult "
                "the relevant course syllabi or instructors for confirmation."
            ),
            "sources": [],
            "status": "review_required",
        }

    retrieval_question = question
    if is_personal_prerequisite(question):
        code = target_course(question)
        if code:
            retrieval_question = f"What are the prerequisites for {code}?"

    try:
        # A semester named in the question ("in Fall 2026") overrides the
        # default term; otherwise answers would silently use Spring 2027.
        docs = get_context(retrieval_question, term_code=requested_term or data.term_code, top_k=5)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Academic retrieval is unavailable: {exc}",
        ) from exc

    decision = classify_evidence(data.question, docs)
    decision_status = decision["decision_status"]

    # Advising approvals and guarantees are not LLM decisions.
    responses = {
        "no_enrollment_guarantee": (
            "Meeting listed prerequisites does not guarantee enrollment. "
            "Registration may also depend on clearance, restrictions, and open seats; "
            "confirm with the responsible USC office."
        ),
        "advisor_verification_required": (
            "I can't approve a waiver, substitution, or transfer equivalency. "
            "Please ask the authorized USC department or advisor to verify the decision."
        ),
        "student_context_required": (
            "To suggest a personalized course plan, please share your degree program, "
            "courses already completed, academic interests, and intended semester. "
            "An advisor should confirm final degree requirements."
        ),
        "future_availability_unconfirmed": (
            "The available sources do not confirm that this course will be offered "
            "in the requested future semester. Historical listings cannot guarantee future availability."
        ),
    }
    if decision_status in responses:
        return {
            "answer": responses[decision_status],
            "sources": _response_sources(docs),
            "status": "review_required",
            "decision_status": decision_status,
            "invalid_citations": [],
        }

    # Immigration rules are quoted from OIS, not paraphrased by the LLM.
    policy_rule = final_semester_answer(question)
    if policy_rule is not None:
        return {
            "answer": policy_rule["answer"],
            "sources": _response_sources(policy_rule["sources"]),
            "status": "review_required",
            "decision_status": "evidence_available",
            "invalid_citations": [],
            "citations_required": False,
            "missing_citations": False,
        }

    if not docs:
        return {
            "answer": "I could not find verified USC evidence for this question. Please check with an academic advisor or the relevant USC office.",
            "sources": [],
            "status": "review_required",
            "decision_status": "course_not_found",
            "invalid_citations": [],
        }

    # QUALITY_UPDATE_V1: availability derives from checked records only.
    availability_answer = catalog_availability_answer(docs)
    if availability_answer is not None:
        return {
            "answer": availability_answer,
            "sources": _response_sources(docs),
            "status": "review_required",
            "decision_status": "evidence_available" if docs[0].get("availability_status") == "listed" else "evidence_unavailable",
            "invalid_citations": [],
            "citations_required": False,
            "missing_citations": False,
        }

    if (
        len(docs) == 1
        and docs[0].get("retrieval_method") == "syllabus_unavailable"
    ):
        doc = docs[0]

        course = doc["course_code"]
        requested = format_term(doc["requested_term"])
        available = doc.get("available_terms", [])

        answer = (
            f"I don't have an imported {course} syllabus "
            f"for {requested}, so I cannot verify its "
            "course-specific policies or requirements."
        )

        if available:
            semesters = ", ".join(
                format_term(term) for term in available
            )

            answer += (
                f"\n\nImported syllabi are available for: "
                f"{semesters}. Their policies may differ "
                "from the requested semester."
            )

        return {
            "answer": answer,
            "sources": [],
            "status": "review_required",
        }

    prerequisite = assess_prerequisite_scenario(data.question, docs)
    if prerequisite is not None:
        answer = prerequisite["answer"]
        # "Can I take X, and when does it meet?" gets both parts answered.
        target = target_course(question)
        schedule = schedule_answer(question, docs, target=target)
        if schedule:
            record = next((d for d in docs if d.get("retrieval_method") == "exact"
                           and d.get("course_code") == target and not d.get("historical")), None)
            top = headline(prerequisite["decision_status"], record) if record else None
            answer = (top + "\n\n" if top else "") + answer + "\n\n" + schedule
        return {
            "answer": answer,
            "sources": _response_sources(docs),
            "status": "review_required",
            "decision_status": prerequisite["decision_status"],
            "invalid_citations": [],
        }

    schedule = schedule_answer(question, docs, target=target_course(question))
    if schedule is not None:
        return {
            "answer": schedule,
            "sources": _response_sources(docs),
            "status": "review_required",
            "decision_status": "evidence_available",
            "invalid_citations": [],
        }

    direct = answer_exact_prerequisites(data.question, docs)
    if direct is not None:
        return {
            "answer": direct,
            "sources": _response_sources(docs),
            "status": "review_required",
            "decision_status": "evidence_available",
            "invalid_citations": [],
        }

    # History is a collected structured fact. Do not let the LLM choose
    # an arbitrary semester when multiple history records are retrieved.
    if docs and all(d.get("retrieval_method") == "history" for d in docs) and \
            "last offered" in data.question.lower():
        latest = max(docs, key=lambda d: str(d.get("term_code") or ""))
        code = latest.get("course_code") or "The course"
        term = format_term(latest.get("term_code"))
        citation_index = docs.index(latest) + 1
        cite = f" [{citation_index}]" if latest.get("url") else ""
        answer = (f"The latest collected listing for {code} is {term}.{cite} "
                  "This only reflects collected course records and does not establish future availability.")
        return {
            "answer": answer,
            "sources": _response_sources(docs),
            "status": "review_required",
            "decision_status": "evidence_available",
            "invalid_citations": [],
        }

    # Complete catalogs are structured facts, not LLM-generated answers.
    if (
        len(docs) == 1
        and docs[0].get("retrieval_method") == "historical_catalog"
        and docs[0].get("catalog_status") == "collected"
    ):
        doc = docs[0]
        courses = doc.get("courses") or []

        lines = [
            f"- {course.get('course_code')}: {course.get('title')}"
            for course in courses
        ]

        answer = (
            f"The collected USC Electrical Engineering catalog "
            f"for {format_term(doc['term_code'])} contains "
            f"{len(courses)} courses:\n\n"
            + "\n".join(lines)
        )

        return {
            "answer": answer,
            "sources": _response_sources(docs),
            "status": "review_required",
            "decision_status": "evidence_available",
            "invalid_citations": [],
        }


    if len(docs) == 1:
        doc = docs[0]

        if (
            doc.get("retrieval_method") == "historical_catalog"
            and not doc.get("url")
            and "have not been collected" in doc.get("text", "")
        ):
            return {
                "answer": doc["text"],
                "sources": [],
                "status": "review_required",
                "decision_status": "evidence_unavailable",
                "invalid_citations": [],
            }

    # Reviewed grading facts are rendered directly, not reinterpreted by an LLM.
    if len(docs) == 1:
        doc = docs[0]
        fact = doc.get("grading_fact")
        if (
            doc.get("source_type") == "syllabus"
            and isinstance(fact, dict)
            and fact.get("verified") is True
        ):
            answer = (
                f"In {format_term(doc['term_code'])}, "
                f"{fact['name']} is worth {fact['weight_percent']}% "
                f"of the final grade in {doc['course_code']}. [1]"
            )
            return {
                "answer": answer,
                "sources": _response_sources(docs),
                "status": "review_required",
                "decision_status": "evidence_available",
                "invalid_citations": [],
            }

    if len(docs) == 1 and not docs[0].get("url") and docs[0].get("retrieval_method") in (
        "historical_catalog", "availability", "comparison", "history"
    ):
        return {
            "answer": docs[0]["text"],
            "sources": [],
            "status": "review_required",
            "decision_status": "evidence_unavailable",
            "invalid_citations": [],
        }

    # QUALITY_UPDATE_V1: deterministic answers where evidence is structured.
    structured = clearance_evidence_answer(question, docs)
    if structured is None:
        structured = course_discovery_answer(question, docs)
    if structured is not None:
        return {
            "answer": structured,
            "sources": _response_sources(docs),
            "status": "review_required",
            "decision_status": "evidence_available",
            "invalid_citations": [],
            "citations_required": False,
            "missing_citations": False,
        }

    context = "\n\n".join(
        f"[{i}] {doc['title']}\n{doc['text']}"
        for i, doc in enumerate(docs, start=1)
    )
    messages = [
        {"role": "system", "content": system_prompt(docs)},
        {
            "role": "user",
            "content": f"Sources:\n{context}\n\nQuestion: {data.question}",
        },
    ]
    try:
        answer = await _ollama_chat(messages, NUM_PREDICT)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="LLM request timed out") from exc
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="LLM service failed") from exc

    answer = cite_exact_course_listings(normalize_citation_groups(answer), docs)
    # QUALITY_UPDATE_V1: validate, retry once, and validate again.
    required = requires_source_citations(data.question, docs)
    answer, invalid, coverage, course_issues = citation_problems(
        answer, docs, required, check_citations, citation_coverage, course_citation_issues
    )
    if coverage["missing_citations"] or course_issues:
        # Preserve supplied evidence and ask the model to fix only verifiable
        # citation format. The same validation rules still apply on retry.
        retry_messages = messages + [
            {"role": "assistant", "content": answer},
            {"role": "user", "content": RETRY_PROMPT},
        ]
        try:
            retry_answer = await _ollama_chat(retry_messages, RETRY_NUM_PREDICT)
            # Exact-title repair is safe to apply again; it will not invent
            # citations for arbitrary policy or course claims.
            retry_answer = cite_exact_course_listings(
                normalize_citation_groups(retry_answer), docs
            )
            retry_clean, retry_invalid, retry_coverage, retry_course_issues = citation_problems(
                retry_answer, docs, required, check_citations,
                citation_coverage, course_citation_issues
            )
            if not (retry_coverage["missing_citations"] or retry_course_issues or retry_invalid):
                answer = retry_clean
                invalid = []
                coverage = retry_coverage
                course_issues = []
            else:
                answer = None
                invalid = retry_invalid
                coverage = retry_coverage
                course_issues = retry_course_issues
        except (httpx.HTTPError, KeyError, ValueError):
            answer = None
    if answer is None or coverage["missing_citations"] or course_issues:
        # Grounded excerpts are more useful than a fabricated policy answer.
        answer = cite_safe_policy_excerpts(docs) or (
            "I found related USC sources, but couldn't produce an answer "
            "with a verifiable source reference. Please review the sources "
            "below or ask the appropriate USC office."
        )
        # The status reflects a fallback; don't report the rejected model's
        # citation check as success.
        coverage = citation_coverage(answer, docs, required=required)
    if course_issues:
        coverage["course_citation_issues"] = course_issues
    sources = _response_sources(docs)
    return {
        "answer": answer,
        "sources": sources,
        # Citation presence alone is not proof that the answer is supported.
        "status": "review_required",
        "decision_status": "evidence_available",
        "invalid_citations": invalid,
        **coverage,
    }