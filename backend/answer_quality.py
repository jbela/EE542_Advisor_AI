"""Small, measurable safeguards for student-facing academic answers."""

import re

from backend.rag_service import format_requirement, format_term
from backend.student_question import is_personal_prerequisite, target_course
from backend.prerequisite_service import format_rule

CITATION = re.compile(r"\[(\d+)\]")
FACT_QUESTION = re.compile(
    r"\b(?:prerequisites?|pre[- ]?reqs?|what do i need (?:to take|before)|"
    r"what(?:'s| is| are) required before|do i need)\b", re.I,
)


def check_citations(answer, docs):
    """Remove invalid numeric citations; this does NOT verify claim support."""
    valid = {i for i, doc in enumerate(docs, 1) if doc.get("url")}
    invalid = set()

    def replace(match):
        i = int(match.group(1))
        if i in valid:
            return match.group()
        invalid.add(i)
        return ""

    cleaned = CITATION.sub(replace, answer)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned, sorted(invalid)


def answer_exact_prerequisites(question, docs):
    """Answer direct prerequisite field questions without an LLM guessing."""
    if is_personal_prerequisite(question) or not FACT_QUESTION.search(question):
        return None
    code = target_course(question)
    if not code:
        return None
    matches = [(i, doc) for i, doc in enumerate(docs, 1)
               if doc.get("retrieval_method") == "exact" and doc.get("course_code") == code]
    if len(matches) != 1:
        return None
    i, doc = matches[0]
    # An exact record's field is structured independently of any model output.
    rule = doc.get("prerequisites_structured")
    verification = doc.get("prerequisite_verification")
    term = format_term(doc.get("term_code"))
    if rule is None:
        statement = f"The available {term} course record does not specify prerequisites for {code}. This does not establish that none are required."
    elif rule == []:
        statement = f"No prerequisites are listed in the collected {term} record for {code}; other enrollment conditions may still apply."
    elif isinstance(verification, dict) and verification.get("status") == "verified":
        formatted = format_rule(rule) or format_requirement(rule)
        statement = f"The verified listed prerequisites for {code} in {term} are {formatted}."
    elif isinstance(rule, dict) and rule.get("operator") == "UNVERIFIED":
        statement = f"The collected {term} record for {code} contains prerequisite data, but the logical relationship has not been verified. Please check the official listing or the department."
    else:
        statement = f"The {term} record for {code} lists prerequisites: {format_rule(rule) or format_requirement(rule)}."
    if doc.get("historical"):
        statement += " This is historical information; current prerequisites and future availability are not confirmed."
    if doc.get("url"):
        statement += f" [{i}]"
    return statement
<<<<<<< HEAD


def requires_source_citations(question, docs):
    """Only answers grounded in retrieved public facts require citations."""
    if not docs:
        return False
    methods = {d.get("retrieval_method") for d in docs}
    return bool(methods & {"hybrid", "semantic_bge"})


def citation_coverage(answer, docs, required=False):
    """Check citation presence/validity, not whether claims are entailed."""
    cited = {int(x) for x in CITATION.findall(answer)}
    valid = {i for i, doc in enumerate(docs, 1) if doc.get("url")}
    return {
        "citations_required": bool(required),
        "missing_citations": bool(required and not (cited & valid)),
        "cited_source_count": len(cited & valid),
    }


def course_citation_issues(answer, docs):
    """Spot obvious uncited/miscited course lines in BGE recommendation answers.

    This is a conservative structural check, not semantic fact verification.
    It only checks lines that visibly name a retrieved course code.
    """
    if not any(d.get("retrieval_method") == "semantic_bge" for d in docs):
        return []
    issues = []
    for line in answer.splitlines():
        codes = set(re.findall(r"\b[A-Z]{2,5}\s*[- ]?\s*\d{3}[A-Z]?\b", line, re.I))
        if not codes:
            continue
        normalized = {re.sub(r"[^A-Z0-9]", "", c.upper()) for c in codes}
        cited = {int(i) for i in CITATION.findall(line)}
        supported = {
            re.sub(r"[^A-Z0-9]", "", str(d.get("course_code") or "").upper())
            for index, d in enumerate(docs, 1) if index in cited
        }
        if not normalized.issubset(supported):
            issues.append(line.strip()[:150])
    return issues
=======
>>>>>>> f32b1f5 (Rebasing main)
