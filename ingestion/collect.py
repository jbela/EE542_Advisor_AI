import time
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[1]

SOURCES_FILE = ROOT / "ingestion" / "sources.json"
RAW_DIR = ROOT / "data" / "raw"
VERSIONS_DIR = ROOT / "data" / "versions"

RAW_DIR.mkdir(parents=True, exist_ok=True)
VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "USCAdvisorAI-StudentResearch/0.1"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def check_robots(url):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    response = session.get(robots_url, timeout=20)
    response.raise_for_status()

    robots = RobotFileParser()
    robots.parse(response.text.splitlines())

    allowed = robots.can_fetch(USER_AGENT, url)

    if not allowed:
        print(f"Robots.txt disallows: {url}")

    return allowed


def extract_text(url):
    if not check_robots(url):
        raise PermissionError(
            f"Automated access not allowed: {url}"
        )

    response = session.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for element in soup.select(
        "script, style, nav, footer, header"
    ):
        element.decompose()

    main = soup.find("main") or soup.body

    if main is None:
        raise ValueError("No readable page content found")

    text = main.get_text(separator=" ", strip=True)
    text = " ".join(text.split())

    if len(text) < 100:
        raise ValueError("Extracted content is too short")

    return text


def collect_source(source):
    print(f"\nChecking: {source['title']}")

    text = extract_text(source["url"])

    content_hash = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    output_file = RAW_DIR / f"{source['id']}.json"

    old_data = None

    if output_file.exists():
        old_data = json.loads(
            output_file.read_text(encoding="utf-8")
        )

    if old_data and old_data["content_hash"] == content_hash:
        print("No changes detected.")
        return False

    if old_data:
        timestamp = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d_%H%M%S")

        backup_file = VERSIONS_DIR / (
            f"{source['id']}_{timestamp}.json"
        )

        backup_file.write_text(
            json.dumps(old_data, indent=2),
            encoding="utf-8"
        )

        print("Changes detected. Old version backed up.")

    document = {
        "id": source["id"],
        "title": source["title"],
        "url": source["url"],
        "category": source["category"],
        "retrieved_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "published_date": None,
        "effective_date": None,
        "content_hash": content_hash,
        "text": text
    }

    output_file.write_text(
        json.dumps(document, indent=2),
        encoding="utf-8"
    )

    print(f"Saved: {output_file.name}")
    return True



def main():
    sources = json.loads(
        SOURCES_FILE.read_text(encoding="utf-8")
    )

    changed_sources = []
    failed_sources = []

    for source in sources:
        if not source.get("enabled", True):
            continue

        try:
            changed = collect_source(source)

            if changed:
                changed_sources.append(source["id"])

        except Exception as error:
            print(f"Error collecting {source['id']}: {error}")
            failed_sources.append(source["id"])

    print("\nPolicy collection summary:")
    print(f"Changed sources: {len(changed_sources)}")
    print(f"Failed sources: {len(failed_sources)}")

    return {
        "academic_updates": bool(changed_sources),
        "changed_sources": changed_sources,
        "failed_sources": failed_sources
    }


if __name__ == "__main__":
    main()

