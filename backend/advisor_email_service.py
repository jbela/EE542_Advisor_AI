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