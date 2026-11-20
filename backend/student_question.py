"""Conservative interpretation of common student prerequisite questions.

This is not a general transcript parser. Only explicit first-person course
completion statements are accepted; omitted courses remain unknown.
"""

import re

from rag.course_lookup import extract_course_codes
from rag.prerequisite_evaluator import normalize_course_code, extract_course_statuses

CODE = r"[A-Z]{2,5}\s*[- ]?\s*\d{3}[A-Z]?"
CODE_RE = re.compile(r"\b" + CODE + r"\b", re.I)

PERSONAL = re.compile(
    r"\b(?:i['’]ve|i\s+(?:have\s+(?:completed|passed|finished|taken|not)|"
    r"had\s+(?:completed|passed|finished|taken)|haven['’]t|didn['’]t|did\s+not|"
    r"passed|took|finished|completed|only\s+(?:completed|passed|taken)|"
    r"already\s+(?:completed|passed|taken))|"
    r"have i (?:met|satisfied)|do i (?:meet|satisfy|qualify)|"
    r"am i (?:eligible|cleared|allowed)|can i (?:take|enroll|register)|"
    r"would i (?:qualify|be eligible)|my (?:completed|courses|prerequisites))",
    re.I,
)

ELIGIBILITY = re.compile(
    r"\b(?:prereq(?:uisites?)?|pre[- ]?reqs?|requirements?|eligible|eligibility|"
    r"satisf(?:y|ied)|meet|qualify|can i (?:take|enroll|register)|"
    r"would i (?:qualify|be eligible)|cleared for|allowed to register)\b",
    re.I,
)

TARGET_PATTERNS = [
    re.compile(r"\b(?:prerequisites?|pre[- ]?reqs?|requirements?|eligibility)\s+(?:for|of)\s+(" + CODE + r")\b", re.I),
    re.compile(r"\b(?:take|enroll\s+in|register\s+for|eligible\s+for|qualify\s+for|cleared\s+for|before|for)\s+(" + CODE + r")\b", re.I),
    re.compile(r"\b(" + CODE + r")\s+(?:prerequisites?|requirements?)\b", re.I),
]

POSITIVE = re.compile(r"\b(?:i\s+(?:(?:have\s+)?(?:already\s+|only\s+)?(?:completed|passed|finished|taken)|took)|i['’]ve\s+(?:(?:already|only)\s+)?(?:completed|passed|finished|taken))\s+", re.I)
NEGATIVE = re.compile(r"\b(?:i\s+(?:have\s+not|haven['’]t|did\s+not|didn['’]t)\s+(?:completed|passed|finished|taken|take)|"
                      r"i\s+(?:still\s+)?need\s+to\s+(?:take|complete)|"
                      r"but\s+not|except)\s+", re.I)
STOP = re.compile(r"\b(?:have i|do i|can i|am i|would i|will i|what are|which|does|did i)\b", re.I)
CONNECTORS = re.compile(r"\b(?:and|or|also|either|both)\b", re.I)


def is_personal_prerequisite(question):
    return bool(PERSONAL.search(question) and ELIGIBILITY.search(question))


def target_course(question):
    """Return an unambiguous requested course; never guess from a course list."""
    targets = set()
    for pattern in TARGET_PATTERNS:
        for match in pattern.finditer(question):
            code = normalize_course_code(match.group(1))
            if code:
                targets.add(code)
    if len(targets) == 1:
        return next(iter(targets))
    if len(targets) > 1:
        return None
    codes = extract_course_codes(question)
    return codes[0] if len(codes) == 1 else None


def _parse_codes(segment):
    """Strict course-code list, with no claims outside supported grammar."""
    codes = [normalize_course_code(m.group()) for m in CODE_RE.finditer(segment)]
    if not codes or None in codes:
        return None
    remainder = CODE_RE.sub(" ", segment)
    remainder = CONNECTORS.sub(" ", remainder)
    remainder = re.sub(r"[,;\s]", "", remainder)
    if remainder:
        return None
    return set(codes)


def completion_statuses(question):
    """Extract explicit positive and negative course claims or return None."""
    # Keep compatibility with already supported narrow phrasing.
    old = extract_course_statuses(question)
    if old is not None:
        return old

    text = question.replace("’", "'")
    # Refuse contradictions and unsupported claims rather than infer intent.
    markers = sorted(
        [(m.start(), m.end(), True) for m in POSITIVE.finditer(text)]
        + [(m.start(), m.end(), False) for m in NEGATIVE.finditer(text)]
    )
    if not markers:
        return None
    prefix = text[:markers[0][0]].strip()
    if prefix and not re.fullmatch(
        r"(?:if|so|for\s+" + CODE + r"[,:]?|regarding\s+" + CODE + r"[,:]?)",
        prefix, re.I,
    ):
        return None
    completed, incomplete = set(), set()
    for i, (_, end, positive) in enumerate(markers):
        next_start = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        clause = text[end:next_start]
        clause = re.split(r"[.!?]", clause, maxsplit=1)[0]
        clause = STOP.split(clause, maxsplit=1)[0]
        clause = re.split(r"\b(?:but|however|although|yet)\b", clause, maxsplit=1, flags=re.I)[0]
        codes = _parse_codes(clause.strip())
        if codes is None:
            return None
        if positive:
            completed.update(codes)
        else:
            incomplete.update(codes)
    if not completed and not incomplete:
        return None
    if completed & incomplete:
        return None
    return {"completed": completed, "not_completed": incomplete}
