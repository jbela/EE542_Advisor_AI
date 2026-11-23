from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / ".secrets"
CREDENTIALS_FILE = SECRETS / "gmail_credentials.json"
TOKEN_FILE = SECRETS / "gmail_token.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
EXPECTED_ACCOUNT = "usctrojanguide@gmail.com"


def main():
    if not CREDENTIALS_FILE.is_file():
        raise FileNotFoundError(
            f"Credentials file not found: {CREDENTIALS_FILE}"
        )

    credentials = None

    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            str(TOKEN_FILE), SCOPES
        )

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            credentials = flow.run_local_server(
                port=0,
                login_hint=EXPECTED_ACCOUNT,
                prompt="select_account",
                timeout_seconds=300,
            )

    service = build("gmail", "v1", credentials=credentials)

    profile = service.users().getProfile(userId="me").execute()
    account = profile["emailAddress"]

    if account.lower() != EXPECTED_ACCOUNT:
        raise RuntimeError(
            f"Wrong account: {account}. "
            f"Please use {EXPECTED_ACCOUNT}."
        )

    TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Connected: {account}")

    result = service.users().messages().list(
        userId="me",
        q='in:inbox subject:"AdvisorAI Update"',
        maxResults=5,
    ).execute()

    messages = result.get("messages", [])

    if not messages:
        print("Connection OK. No test emails found yet.")
        return

    for item in messages:
        message = service.users().messages().get(
            userId="me",
            id=item["id"],
            format="metadata",
            metadataHeaders=["Subject"],
        ).execute()

        headers = message.get("payload", {}).get("headers", [])
        subject = next(
            (
                h["value"]
                for h in headers
                if h["name"].lower() == "subject"
            ),
            "(No subject)",
        )
        print(f"Test email: {subject}")


if __name__ == "__main__":
    main()