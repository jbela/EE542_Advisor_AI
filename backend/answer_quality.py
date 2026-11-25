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


CITATION_GROUP = re.compile(r"\[(\s*\d+\s*(?:(?:[-–,]|and)\s*\d+\s*)+)\]")
MAX_RANGE = 10


def normalize_citation_groups(answer):
    """Rewrite [1-3], [1, 2] and [1 and 2] as separate [n] citations.

    Small models often group citations; without this the validator treats a
    correctly sourced answer as uncited and triggers a slow retry. Each number
    is still checked individually afterward. Ranges that are reversed or too
    wide are left unchanged (and so stay invalid).
    """
    def expand(match):
        numbers = []
        for part in re.split(r"\s*(?:,|and)\s*", match.group(1).strip()):
            bounds = [int(x) for x in re.split(r"\s*[-–]\s*", part)]
            if len(bounds) == 1:
                numbers.append(bounds[0])
            elif len(bounds) == 2 and bounds[0] <= bounds[1] and bounds[1] - bounds[0] < MAX_RANGE:
                numbers.extend(range(bounds[0], bounds[1] + 1))
            else:
                return match.group()
        return "".join(f"[{n}]" for n in dict.fromkeys(numbers))

    return CITATION_GROUP.sub(expand, answer)


def is_citable(doc):
    """A source is citable if a student can trace it: a public URL, or an
    imported syllabus identified by document and page number."""
    if doc.get("url"):
        return True
    return (
        doc.get("source_type") == "syllabus"
        and bool(doc.get("document_id"))
        and doc.get("page_number") is not None
    )


def check_citations(answer, docs):
    """Remove invalid numeric citations; this does NOT verify claim support."""
    valid = {i for i, doc in enumerate(docs, 1) if is_citable(doc)}
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
    cite = f" [{i}]" if doc.get("url") else ""
    prep = doc.get("recommended_preparation")
    if prep and rule in (None, []):
        statement += f" The listing gives recommended preparation (not a formal prerequisite): {str(prep).rstrip('.')}."
    if doc.get("historical"):
        statement += (f" {code} is not listed in the collected {format_term(doc.get('requested_term'))} "
                      "records, so this is historical information; current prerequisites and "
                      "future availability are not confirmed.")
    statement += cite
    from backend.course_schedule import prerequisite_change
    change = prerequisite_change(code, doc.get("term_code"))
    if change:
        statement += f"\n\n{change}{cite}"
    return statement


def requires_source_citations(question, docs):
    """Only answers grounded in retrieved public facts require citations."""
    if not docs:
        return False
    methods = {d.get("retrieval_method") for d in docs}
    return bool(methods & {"hybrid", "semantic_bge"})


def citation_coverage(answer, docs, required=False):
    """Check citation presence/validity, not whether claims are entailed."""
    cited = {int(x) for x in CITATION.findall(answer)}
    valid = {i for i, doc in enumerate(docs, 1) if is_citable(doc)}
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

def cite_exact_course_listings(answer, docs):
    """Add citations to course-title list items matching retrieved records."""
    if not any(d.get("retrieval_method") == "semantic_bge" for d in docs):
        return answer

    def norm(value):
        return re.sub(r"[^a-z0-9]", "", str(value).lower())

    lines = []

    for line in answer.splitlines():
        match = re.match(
            r"^\s*(?:[-*]\s+|\d+[.)]\s+)([A-Z]{2,5}\s*-?\s*\d{3}[A-Z]?)\s*(.*)$",
            line,
            re.I,
        )

        if not match or CITATION.search(line):
            lines.append(line)
            continue

        code = norm(match.group(1))
        title_text = norm(match.group(2))
        candidates = []

        for i, doc in enumerate(docs, 1):
            if norm(doc.get("course_code") or "") != code:
                continue

            if not doc.get("url"):
                continue

            title = str(doc.get("title") or "")

            title = re.sub(
                r"^\s*[A-Z]{2,5}\s*-?\s*\d{3}[A-Z]?\s*[-:–—]?\s*",
                "",
                title,
                flags=re.I,
            )

            if norm(title) and title_text.endswith(norm(title)):
                candidates.append(i)

        if len(candidates) == 1:
            line = f"{line.rstrip()} [{candidates[0]}]"

        lines.append(line)

    return "\n".join(lines)