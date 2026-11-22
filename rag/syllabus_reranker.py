"""Lightweight evidence-aware reranking for syllabus passages."""

import re


def detect_intent(question):
    q = question.lower()

    if re.search(
        r"\b(textbooks?|books?|reading materials?)\b", q
    ):
        return "textbook"

    if re.search(
        r"\b(python|c\+\+|c programming|programming experience)\b", q
    ):
        return "preparation"

    if re.search(
        r"\b(late|deadline|extension|penalty)\b", q
    ):
        return "late_policy"

    if re.search(
        r"\b(attendance|participation|quizzes?)\b", q
    ):
        return "participation"

    if re.search(
        r"\b(grade|grading|score|percent|percentage|worth|"
        r"weight|final exam|final project)\b", q
    ):
        return "grading"

    if re.search(
        r"\b(labs?|laborator(?:y|ies))\b", q
    ):
        return "laboratory"

    if re.search(
        r"\b(instructor|professor|who teaches)\b", q
    ):
        return "instructor"

    return "general"


SECTION_PREFERENCES = {
    "textbook": {
        "required textbook": 0.025,
        "course description": 0.005,
    },
    "preparation": {
        "preparation for classes": 0.025,
        "other requirements": 0.020,
        "course description": 0.005,
    },
    "late_policy": {
        "grading policies": 0.025,
    },
    "participation": {
        "class participation": 0.025,
        "grading": 0.010,
    },
    "grading": {
        "grading": 0.025,
        "grading policies": 0.005,
    },
    "laboratory": {
        "laboratory assignments": 0.025,
    },
    "instructor": {
        "general": 0.015,
    },
}


def evidence_bonus(question, text, intent):
    q = question.lower()
    t = text.lower()

    bonus = 0.0

    if intent == "grading":
        if re.search(r"\b\d+(?:\.\d+)?\s*%", t):
            bonus += 0.012

        if "final project" in q:
            if re.search(
                r"\b\d+(?:\.\d+)?\s*%\s+final project\b",
                t,
            ):
                bonus += 0.030

        if re.search(r"\b(?:an?\s+)?a(?:\s+grade)?\b", q):
            if re.search(r"\b86\s*[-–]\s*100\s+A\b", text):
                bonus += 0.030

    elif intent == "textbook":
        if re.search(r"required textbook\s*:\s*none", t):
            bonus += 0.030

    elif intent == "preparation":
        if "python" in q and "python" in t:
            bonus += 0.020

        if "c programming" in q and "c programming" in t:
            bonus += 0.020

    elif intent == "late_policy":
        if "late policy" in t:
            bonus += 0.020

    return bonus


def rerank_syllabus(question, results, top_k=5):
    """Rerank existing syllabus evidence without changing metadata."""

    if top_k <= 0:
        return []

    intent = detect_intent(question)
    preferences = SECTION_PREFERENCES.get(intent, {})

    ranked = []

    for position, doc in enumerate(results):
        if doc.get("source_type") != "syllabus":
            ranked.append((float(doc.get("score", 0)), position, doc))
            continue

        section = str(
            doc.get("syllabus_section") or "general"
        ).lower()

        text = str(doc.get("text") or "")
        original_score = float(doc.get("score") or 0)

        section_bonus = preferences.get(section, 0.0)

        content_bonus = evidence_bonus(
            question,
            text,
            intent,
        )

        adjusted_score = (
            original_score
            + section_bonus
            + content_bonus
        )

        ranked.append(
            (adjusted_score, position, doc)
        )

    ranked.sort(key=lambda item: (-item[0], item[1]))

    return [
        {
            **doc,
            "rerank_score": score,
            "rerank_intent": intent,
        }
        for score, _, doc in ranked[:top_k]
    ]
