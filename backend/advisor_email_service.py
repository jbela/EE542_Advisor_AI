"""Prepare applicable advisor emails as answer evidence."""

import re

from rag.advisor_updates import get_eligible_updates


STOP_WORDS = set("""
the and for with from that this what when where which how
are was were will would could should can does did have has
not only demo students student ece usc spring summer fall
january february march april may june july august september
october november december
""".split())


def keywords(text):
    words = re.findall(r"[a-z]{3,}", text.lower())
    return set(words) - STOP_WORDS


def get_email_context(
    question,
    *,
    department,
    audience,
    term,
    on_date,
    include_demo=False,
):
    updates = get_eligible_updates(
        department=department,
        audience=audience,
        term=term,
        on_date=on_date,
        include_demo=include_demo,
    )

    query_words = keywords(question)
    ranked = []

    for update in updates:
        text_words = keywords(update["message"])
        score = len(query_words & text_words)

        if score >= 2:
            ranked.append((score, update))

    ranked.sort(
        key=lambda item: (
            -item[0],
            item[1]["update_id"],
            item[1]["gmail_message_id"],
        )
    )

    documents = []

    for _, update in ranked[:2]:
        prefix = "DEMO — " if update["is_demo"] else ""
        document_id = f"advisor_email_{update['gmail_message_id']}"
        notice_title = re.sub(
            r"^(?:(?:subject|fwd|fw|re)\s*:\s*"
            r"|\[advisorai update\]\s*)+",
            "",
            update["subject"],
            flags=re.IGNORECASE,
        ).strip()

        documents.append({
            "id": document_id,
            "document_id": document_id,
            "title": f"{prefix}{update['subject']}",
            "text": (
                f"Source type: advisor email.\n"
                f"Demo notice: {update['is_demo']}.\n"
                f"Department: {update['department']}.\n"
                f"Audience: {update['audience']}.\n"
                f"Semester: {update['term']}.\n"
                f"Applicable period: {update['effective_from']} "
                f"through {update['effective_until']} inclusive.\n"
                f"Question context date: {on_date}.\n"
                f"Email sent: {update['email_date']}.\n\n"
                f"{update['message']}"
            ),
            "url": update.get("source_url"),
            "category": "graduate",
            "retrieval_method": "advisor_email",
            "source_type": "advisor_email",
            "sender": update["sender"],
            "email_date": update["email_date"],
            "effective_from": update["effective_from"],
            "effective_until": update["effective_until"],
            "is_demo": update["is_demo"],
            "notice_title": notice_title or "Advising update",
            "notice_text": update["message"],
            "department": update["department"],
            "audience": update["audience"],
        })

    return documents

def get_demo_advising_response(
    question,
    *,
    term_code="20271",
    department=None,
    audience=None,
    on_date=None,
):
    """Return a scoped demo answer, or None for other question intents.

    A matched request with no applicable evidence returns (answer, None),
    so the API can decline without citing unrelated retrieved passages.
    """
    from datetime import datetime

    # Narrow advising-hours intent, without affecting normal RAG.
    match = re.fullmatch(
        r"(?:what (?:are|were|will be) (?:the )?)?"
        r"(?:(?P<department>ece|cs) )?advising (?:walk-in )?hours"
        r"(?: on (?P<day>[a-z]+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2}))?"
        r"(?: in spring 2027)?\s*\??",
        question.strip(),
        re.IGNORECASE,
    )

    if not match:
        return None

    # The explicit question takes precedence over sidebar defaults.
    target_department = (
        match.group("department") or department or "ECE"
    ).strip().upper()
    date_text = match.group("day")
    target_date = on_date

    if date_text:
        target_date = None

        for fmt in (
            "%B %d %Y",
            "%b %d %Y",
            "%Y-%m-%d",
        ):
            try:
                target_date = datetime.strptime(
                    date_text.replace(",", ""), fmt
                ).date()
                break
            except ValueError:
                continue

    if not target_date:
        return (
            "Please provide a valid calendar date so I can check "
            f"{target_department} advising hours.",
            None,
        )

    date_label = (
        f"{target_date:%B} {target_date.day}, {target_date.year}"
    )
    unavailable = (
        f"I couldn't verify {target_department} advising hours for "
        f"{date_label} from the available sources. Please contact "
        f"{target_department} advising to confirm.",
        None,
    )

    # Only the scoped ECE notice is available in this presentation PoC.
    # Missing/inapplicable evidence must not fall through to unrelated RAG
    # passages or manufacture a claim that advising is closed.
    if (
        term_code != "20271"
        or target_department != "ECE"
        or (audience and audience.casefold() != "continuing ms students")
    ):
        return unavailable

    docs = get_email_context(
        question,
        department="ECE",
        audience="Continuing MS students",
        term="Spring 2027",
        on_date=target_date.isoformat(),
        include_demo=True,
    )

    docs = [doc for doc in docs if doc.get("is_demo") is True]

    if len(docs) != 1:
        return unavailable

    doc = docs[0]

    # Render the approved notice directly instead of asking the
    # LLM to paraphrase and potentially introduce errors.
    notice = " ".join(doc["notice_text"].split())

    notice = re.sub(
        r"^DEMO ONLY\.\s*",
        "",
        notice,
        flags=re.IGNORECASE,
    )

    notice = re.sub(
        r"^This notice replaces [^.]+\.\s*",
        "",
        notice,
        flags=re.IGNORECASE,
    )

    if not notice:
        return unavailable

    answer = (
        f"{notice} [1]\n\n"
        "*Demo only — fictional advising notice.*"
    )

    return answer, doc