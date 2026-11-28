"""Fixed-rule answers for high-stakes policy questions.

These answers quote the collected USC pages verbatim instead of asking the
LLM to paraphrase immigration rules. Each required sentence is located in the
current copy of the source page; if any is missing (the page changed or was
not collected), the function returns None and the normal pipeline answers.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

INTERNATIONAL = re.compile(
    r"\b(?:f-?1|j-?1|visa|international students?|ois|sevis|immigration|"
    r"(?:student|visa|immigration) status)\b", re.I)
FINAL_TERM = re.compile(
    r"\b(?:final|last|graduating)\s+(?:semester|term)\b", re.I)
REDUCED_LOAD = re.compile(
    r"\b(?:only|just|fewer|less|part[- ]time|reduced|below full[- ]time|"
    r"not full[- ]time|full[- ]time|course load|units?|"
    r"(?:\d|one|two|three)\s+(?:classes|courses|class|course))\b", re.I)


def is_final_semester_load_question(question):
    return bool(INTERNATIONAL.search(question)
                and FINAL_TERM.search(question)
                and REDUCED_LOAD.search(question))


def _load(source_id):
    path = RAW_DIR / f"{source_id}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    text = re.sub(r"\s+", " ", data.get("text") or "")
    text = text.replace(" .", ".").replace("’", "'")
    return {**data, "text": text}


def _sentence(text, pattern):
    """Return the sentence matching pattern, verbatim, or None.

    A pattern starting with '^' marks where the quote begins, which drops
    page headings that run into the sentence without punctuation.
    """
    anchored = pattern.startswith("^")
    regex = re.compile(pattern[1:] if anchored else pattern, re.I)
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        match = regex.search(sentence)
        if match:
            return (sentence[match.start():] if anchored else sentence).strip()
    return None


def _source(doc):
    return {
        "id": doc["id"],
        "title": doc["title"],
        "url": doc["url"],
        "category": doc.get("category"),
        "retrieval_method": "policy_rule",
        "text": doc["text"],
    }


def final_semester_answer(question):
    """Answer the F-1/J-1 final-semester reduced-load question from OIS text.

    Returns {"answer", "sources"} or None when the question doesn't match or
    the required source sentences can't all be found.
    """
    if not is_final_semester_load_question(question):
        return None
    rcl = _load("ois_reduced_course_load")
    if rcl is None:
        return None

    required = {
        "exemption": r"^Students in their final semester are not required to be enrolled full time",
        "remaining": r"^Students must be enrolled in all remaining degree requirements",
        "sevis": r"SEVIS Final Semester Check through Trojan International",
        "in_person": r"^If only one course is needed to complete the degree",
    }
    quotes = {key: _sentence(rcl["text"], pattern) for key, pattern in required.items()}
    if any(value is None for value in quotes.values()):
        return None
    out_of_status = _sentence(
        rcl["text"],
        r"^Students who drop below full-time enrollment without prior authorization")

    sources = [_source(rcl)]
    minimum = tuition = None
    registration = _load("usc_registration")
    if registration is not None:
        minimum = _sentence(registration["text"],
                            r"International students must register in a minimum of")
        tuition = _sentence(registration["text"],
                            r"^All enrollment, tuition and fee information is available")
        if minimum or tuition:
            sources.append(_source(registration))

    reg_cite = f"[{len(sources)}]"
    lines = [
        "**Short answer:** Yes, an F-1 or J-1 student can take fewer than a "
        "full course load in their final semester, but only if they don't "
        "need a full load to finish the degree, and they must file a SEVIS "
        "Final Semester Check with USC's Office of International Services "
        "(OIS). [1]",
        "",
        "**What OIS says:**",
        f"- “{quotes['exemption']}” [1]",
        f"- “{quotes['remaining']}” [1]",
        f"- “{quotes['sevis']}” [1]",
        f"- “{quotes['in_person']}” [1]",
    ]
    if out_of_status:
        lines.append(f"- “{out_of_status}” [1]")
    if minimum:
        lines += ["", "**For comparison, the normal minimum load:**",
                  f"- “{minimum}” {reg_cite}"]
    lines += ["", "**Tuition:** The collected USC sources don't say how tuition "
              "changes when you take fewer units."]
    if tuition:
        lines[-1] += f" “{tuition}” {reg_cite}"
    lines += [
        "",
        "**Next steps:** Confirm with your academic advisor that these classes "
        "are all you have left for your degree, then submit the SEVIS Final "
        "Semester Check in Trojan International by the end of the second week "
        "of classes. Only OIS can confirm your immigration status.",
    ]
    return {"answer": "\n".join(lines), "sources": sources}
