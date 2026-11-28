"""Select approved advisor updates for an explicit student context."""

import argparse
import json
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATES_DIR = ROOT / "data" / "processed" / "advisor_updates"


def normalized(value):
    return " ".join(str(value).split()).casefold()


def get_eligible_updates(
    *,
    department,
    audience,
    term,
    on_date,
    include_demo=False,
    updates_dir=None,
):
    directory = Path(updates_dir) if updates_dir else UPDATES_DIR
    target_date = date.fromisoformat(on_date)

    latest = {}

    for path in sorted(directory.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))

        if record.get("status") != "approved":
            continue

        # Require an explicit demo flag and an approval record.
        if not isinstance(record.get("is_demo"), bool):
            continue
        if record["is_demo"] and not include_demo:
            continue
        if not record.get("reviewed_by") or not record.get("approved_at"):
            continue

        if normalized(record.get("department")) != normalized(department):
            continue
        if normalized(record.get("audience")) != normalized(audience):
            continue
        if normalized(record.get("term")) != normalized(term):
            continue

        # Same Update-ID means a complete replacement within this scope.
        # Different senders cannot replace each other's updates.
        key = (
            normalized(record["mailbox"]),
            normalized(record["sender"]),
            normalized(record["department"]),
            normalized(record["audience"]),
            normalized(record["term"]),
            record["update_id"],
        )

        received = datetime.fromisoformat(record["received_at"])
        if received.tzinfo is None:
            raise ValueError(f"Missing timezone in {path.name}")

        revision = (
            received,
            record["gmail_message_id"],
        )

        if key not in latest or revision > latest[key][0]:
            latest[key] = (revision, record)

    results = []

    # Choose the latest approved revision BEFORE checking its date range.
    # This prevents an old revision from resurfacing after a replacement.
    for _, record in latest.values():
        start = date.fromisoformat(record["effective_from"])
        end = date.fromisoformat(record["effective_until"])

        if end < start:
            raise ValueError("Invalid update date range.")

        if start <= target_date <= end:
            results.append(record)

    return sorted(
        results,
        key=lambda item: (item["update_id"], item["gmail_message_id"]),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--department", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--term", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--include-demo", action="store_true")
    args = parser.parse_args()

    updates = get_eligible_updates(
        department=args.department,
        audience=args.audience,
        term=args.term,
        on_date=args.date,
        include_demo=args.include_demo,
    )

    print(f"Eligible updates: {len(updates)}")
    for update in updates:
        print(f"\nUpdate: {update['update_id']}")
        print(f"Subject: {update['subject']}")
        print(f"Demo: {update['is_demo']}")
        print(update["message"])


if __name__ == "__main__":
    main()