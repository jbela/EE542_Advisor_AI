"""Import formatted advisor emails as local PoC drafts."""

import argparse
import base64
import hashlib
import json
import re
from datetime import date, datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


ROOT = Path(__file__).resolve().parents[1]
TOKEN_FILE = ROOT / ".secrets" / "gmail_token.json"
OUTPUT_DIR = ROOT / "data" / "processed" / "advisor_updates"

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
EXPECTED_ACCOUNT = "usctrojanguide@gmail.com"

FIELDS = {
    "Update-ID": "update_id",
    "Department": "department",
    "Audience": "audience",
    "Term": "term",
    "Effective-From": "effective_from",
    "Effective-Until": "effective_until",
    "Source-URL": "source_url",
}


def get_service():
    if not TOKEN_FILE.is_file():
        raise RuntimeError("Run python -m ingestion.gmail_check first.")

    credentials = Credentials.from_authorized_user_file(
        str(TOKEN_FILE), SCOPES
    )

    if not credentials.valid:
        if not credentials.refresh_token:
            raise RuntimeError("Run ingestion.gmail_check to sign in again.")
        credentials.refresh(Request())
        TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")

    service = build("gmail", "v1", credentials=credentials)
    profile = service.users().getProfile(userId="me").execute()

    if profile["emailAddress"].lower() != EXPECTED_ACCOUNT:
        raise RuntimeError("Wrong Gmail account. Check gmail_check first.")

    return service


def parse_update(body):
    body = body.replace("\r\n", "\n").replace("\r", "\n")

    parts = re.split(
        r"^Message:[ \t]*$",
        body,
        maxsplit=1,
        flags=re.MULTILINE,
    )
    if len(parts) != 2 or not parts[1].strip():
        raise ValueError("Missing Message: line or message text.")

    values = {}

    for line in parts[0].splitlines():
        if not line.strip():
            continue

        label, separator, value = line.partition(":")
        label = label.strip()

        if not separator or label not in FIELDS:
            raise ValueError(f"Unknown format field: {label}")

        key = FIELDS[label]
        if key in values:
            raise ValueError(f"Duplicate field: {label}")

        values[key] = value.strip()

    for label, key in FIELDS.items():
        if label != "Source-URL" and not values.get(key):
            raise ValueError(f"Missing field: {label}")

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", values["update_id"]):
        raise ValueError("Update-ID must use letters, numbers, - or _.")

    if not re.fullmatch(r"(Spring|Summer|Fall) \d{4}", values["term"]):
        raise ValueError("Term must look like Spring 2027.")

    start = date.fromisoformat(values["effective_from"])
    end = date.fromisoformat(values["effective_until"])

    if end < start:
        raise ValueError("Effective-Until is earlier than Effective-From.")

    source_url = values.get("source_url", "")
    if source_url:
        parsed = urlparse(source_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Source-URL must be an HTTP/HTTPS URL.")

    values["source_url"] = source_url or None
    values["message"] = parts[1].strip()
    return values


def import_message(service, message_id, allowed_sender):
    # Use the Gmail message ID for duplicate detection.
    file_key = hashlib.sha256(message_id.encode("utf-8")).hexdigest()
    output_file = OUTPUT_DIR / f"{file_key}.json"

    if output_file.exists():
        return "duplicate"

    result = service.users().messages().get(
        userId="me",
        id=message_id,
        format="raw",
    ).execute()

    encoded = result["raw"]
    raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    mail = BytesParser(policy=policy.default).parsebytes(raw)

    sender = parseaddr(str(mail.get("From", "")))[1].lower()
    if sender != allowed_sender:
        return "other_sender"

    subject = str(mail.get("Subject", ""))
    if "[advisorai update]" not in subject.lower():
        return "other_subject"

    body_part = mail.get_body(preferencelist=("plain",))
    if body_part is None:
        raise ValueError("No plain-text body. Send a text-format email.")

    update = parse_update(body_part.get_content())

    record = {
        "schema_version": 1,
        "status": "draft",
        "is_demo": True,
        "source_type": "advisor_email",
        "mailbox": EXPECTED_ACCOUNT,
        "gmail_message_id": message_id,
        "sender": sender,
        "subject": subject,
        "email_date": str(mail.get("Date", "")),
        "received_at": datetime.fromtimestamp(
            int(result["internalDate"]) / 1000,
            tz=timezone.utc,
        ).isoformat(),
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "raw_body": body_part.get_content(),
        **update,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with output_file.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)

    print(f"Saved draft: {update['update_id']}")
    return "saved"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sender",
        required=True,
        help="Exact email address used to send the test update.",
    )
    args = parser.parse_args()
    allowed_sender = args.sender.strip().lower()

    service = get_service()

    # First PoC: inspect up to 20 matching inbox messages.
    result = service.users().messages().list(
        userId="me",
        q='in:inbox subject:"AdvisorAI Update"',
        maxResults=20,
    ).execute()

    counts = {}

    for item in result.get("messages", []):
        try:
            outcome = import_message(
                service, item["id"], allowed_sender
            )
        except ValueError as error:
            print(f"Invalid format ({item['id']}): {error}")
            outcome = "invalid"

        counts[outcome] = counts.get(outcome, 0) + 1

    print("Import summary:", counts)
    print("Drafts only. Chatbot knowledge has not been updated.")


if __name__ == "__main__":
    main()