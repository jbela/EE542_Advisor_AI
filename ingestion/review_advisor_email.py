"""Review a locally imported advisor email."""

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ingestion.import_advisor_emails import OUTPUT_DIR, parse_update


def load_record(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_atomic(path, record):
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary_path, path)

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--message-id")
    parser.add_argument("--reviewer")
    args = parser.parse_args()

    # Without a message ID, list available drafts.
    if not args.message_id:
        paths = sorted(OUTPUT_DIR.glob("*.json"))

        if not paths:
            print("No imported emails found.")
            return

        for path in paths:
            record = load_record(path)
            print(
                f"\nMessage ID: {record['gmail_message_id']}\n"
                f"Update ID: {record['update_id']}\n"
                f"Status: {record['status']}\n"
                f"Subject: {record['subject']}"
            )
        return

    if not args.reviewer or not args.reviewer.strip():
        parser.error("--reviewer is required when reviewing a message.")

    file_key = hashlib.sha256(
        args.message_id.encode("utf-8")
    ).hexdigest()
    path = OUTPUT_DIR / f"{file_key}.json"

    if not path.is_file():
        raise FileNotFoundError("Imported message not found.")

    original = path.read_text(encoding="utf-8")
    record = json.loads(original)

    if record.get("gmail_message_id") != args.message_id:
        raise ValueError("Message ID mismatch.")

    if record.get("status") != "draft":
        print(f"No change. Current status: {record.get('status')}")
        return

    # Revalidate the stored fields against the imported email body.
    parsed = parse_update(record["raw_body"])
    for key, value in parsed.items():
        if record.get(key) != value:
            raise ValueError(
                f"Stored field differs from the email body: {key}"
            )

    print("\n--- EMAIL REVIEW ---")
    for key in (
        "sender",
        "subject",
        "email_date",
        "update_id",
        "department",
        "audience",
        "term",
        "effective_from",
        "effective_until",
        "source_url",
        "is_demo",
    ):
        print(f"{key}: {record.get(key)}")

    print("\nMessage:\n")
    print(record["message"])

    decision = input("\nApprove this draft? Type yes: ").strip().lower()
    if decision != "yes":
        print("Not approved. Draft unchanged.")
        return

    if path.read_text(encoding="utf-8") != original:
        raise RuntimeError("Record changed during review. Please review again.")

    record["status"] = "approved"
    record["reviewed_by"] = args.reviewer.strip()
    record["approved_at"] = datetime.now(timezone.utc).isoformat()

    save_atomic(path, record)
    print(f"Approved: {record['update_id']}")
    print("Demo flag preserved. Chatbot index has not been changed.")


if __name__ == "__main__":
    main()