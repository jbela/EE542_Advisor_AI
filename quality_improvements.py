"""Evidence-first response helpers; no LLM-generated source claims."""
import re

from backend.rag_service import format_term

_STOP = set('which what where when how can do does is are the a an i me my we to for of in on with about and or class classes course courses ee usc interested interest learn study cover covers explore explores teach teaches related recommend recommendations some available best should take'.split())
_CODE = re.compile(r'\b[A-Z]{2,5}\s*-?\s*\d{3}[A-Z]?\b', re.I)
_CITE = re.compile(r'\[(\d+)\]')


def course_terms(question):
    return {w for w in re.findall(r'[a-z]{3,}', question.lower()) if w not in _STOP}


def _description(text):
    """Use only the description, not metadata/prerequisite fields."""
    match = re.search(r'(?im)^\s*description\s*:\s*(.+)', text or '')
    if match:
        return match.group(1).strip()
    # For indexed prose chunks, avoid manufacturing a course description.
    return ''


def course_discovery_answer(question, docs, limit=5):
    """Render only catalog-supported course candidates with topical evidence.

    Return None for non-discovery paths or insufficient description evidence.
    """
    if not docs or not all(d.get('retrieval_method') == 'semantic_bge' for d in docs):
        return None
    terms = course_terms(question)
    if not terms:
        return None
    options = []
    seen = set()
    for i, doc in enumerate(docs, 1):
        code = (doc.get('course_code') or '').strip()
        url = doc.get('url')
        desc = _description(doc.get('text') or '')
        if not code or not url or not desc or code in seen:
            continue
        # An available, topic-relevant description is required. Never infer
        # relevance from BGE rank or course title alone.
        title = doc.get('title') or code
        content = f'{title} {desc}'.lower()
        matched = {t for t in terms if re.search(r'\b' + re.escape(t) + r'\b', content)}
        if not matched:
            continue
        seen.add(code)
        # Keep input retrieval order for equal coverage; reward broader match.
        options.append((len(matched), i, code, title, desc, doc))
    options.sort(key=lambda x: (-x[0], x[1]))
    if not options:
        return None
    lines = ['These collected USC course descriptions are relevant to your interests:']
    for _, i, code, title, desc, doc in options[:limit]:
        name = re.sub(r'^\s*' + re.escape(code) + r'\s*[-:–—]?\s*', '', title, flags=re.I).strip()
        # Cite the exact description excerpt instead of generating a new claim.
        excerpt = re.split(r'(?<=[.!?])\s+', desc)[0].strip()
        if len(excerpt) > 210:
            excerpt = excerpt[:207].rsplit(' ', 1)[0] + '...'
        lines.append(f'- **{code} — {name}** [${i}]: {excerpt}'.replace(f'[${i}]', f'[{i}]'))
    lines.append('These are exploratory matches, not a verified degree plan or an enrollment guarantee.')
    return '\n'.join(lines)


def catalog_availability_answer(docs):
    """Structured status, not model speculation. Only single-course queries."""
    if len(docs) != 1 or docs[0].get('retrieval_method') != 'availability':
        return None
    d = docs[0]
    status = d.get('availability_status')
    term = format_term(d.get('requested_term') or d.get('term_code'))
    code = d.get('course_code') or 'This course'
    cite = ' [1]' if d.get('url') else ''
    if status == 'listed' and d.get('requested_term_checked', False):
        return (f'{code} appears in the collected USC course listings for {term}.{cite} '
                'A listing does not confirm open seats or eligibility to register.')
    if status == 'not_listed' and d.get('requested_term_checked', False):
        return (f'{code} was not found in the collected USC course listings for {term}.{cite} '
                'This does not independently establish whether the official schedule will change.')
    if status == 'term_not_collected':
        return (f'USC course records for {term} have not been collected in this system, '
                f'so I cannot verify whether {code} is listed. Check the official USC Schedule of Classes.')
    return None


def clearance_evidence_answer(question, docs):
    """Use verbatim, relevant evidence for D-Clearance; never infer a policy.

    Does not assert that USC-wide prerequisites, exam rules or eligibility exist.
    """
    if not re.search(r'\b(?:d[- ]?clearance|departmental clearance)\b', question, re.I):
        return None
    evidence = []
    seen = set()
    for i, d in enumerate(docs, 1):
        if not d.get('url'):
            continue
        raw = d.get('text') or ''
        # Prefer compact source sentences/lines mentioning D-Clearance.
        passages = re.split(r'(?<=[.!?])\s+|\n+', raw)
        for phrase in passages:
            phrase = re.sub(r'\s+', ' ', phrase).strip()
            if not re.search(r'\b(?:d[- ]?clearance|departmental clearance)\b', phrase, re.I):
                continue
            if not 20 <= len(phrase) <= 350 or phrase.lower() in seen:
                continue
            seen.add(phrase.lower())
            evidence.append((i, d, phrase))
            break
        if len(evidence) == 3:
            break
    if not evidence:
        return ('I could not verify a D-Clearance procedure from the retrieved USC passages. '
                'Please consult the department offering the course or USC Registration Services.')
    lines = ['The retrieved USC sources state:']
    for i, d, phrase in evidence:
        title = d.get('title') or 'USC source'
        lines.append(f'- **{title}**: “{phrase}” [{i}]')
    lines.append('Procedures may be department-specific. For your particular course, confirm the process with the offering department; a source excerpt does not establish approval.')
    return '\n'.join(lines)


def cite_safe_policy_excerpts(docs, limit=2):
    """Conservative fallback if generation cannot pass citation validation."""
    lines = []
    seen = set()
    for i, d in enumerate(docs, 1):
        if not d.get('url'):
            continue
        raw = re.sub(r'\s+', ' ', (d.get('text') or '')).strip()
        if len(raw) < 25:
            continue
        excerpt = raw[:260].rsplit(' ', 1)[0]
        if excerpt.lower() in seen:
            continue
        seen.add(excerpt.lower())
        lines.append(f'- “{excerpt}…” [{i}]')
        if len(lines) == limit:
            break
    if not lines:
        return None
    return ('I could not verify a complete answer. Here are excerpts from the retrieved USC sources; '
            'please consult the linked source or responsible office before making an academic decision:\n' + '\n'.join(lines))


def citation_problems(answer, docs, required, check_citations, citation_coverage, course_citation_issues):
    """Never accept a response because invalid citation numbers were stripped."""
    clean, invalid = check_citations(answer, docs)
    coverage = citation_coverage(clean, docs, required=required)
    course_issues = course_citation_issues(clean, docs)
    return clean, invalid, coverage, course_issues
