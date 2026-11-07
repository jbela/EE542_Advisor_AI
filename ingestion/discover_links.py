
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[1]

SOURCES = ROOT / "ingestion" / "sources.json"

KEYWORDS = [
    "degree",
    "requirement",
    "curriculum",
    "course",
    "syllabus",
    "prerequisite",
    "registration",
    "enrollment",
    "academic",
    "international",
    "status"
]

USER_AGENT = "USCAdvisorAI-StudentResearch/0.1"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def allowed(url):
    parsed = urlparse(url)
    robots_url = (
        f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    )

    response = session.get(robots_url, timeout=20)
    response.raise_for_status()

    parser = RobotFileParser()
    parser.parse(response.text.splitlines())

    return parser.can_fetch(USER_AGENT, url)


def discover(url):
    if not allowed(url):
        print(f"Skipping disallowed source: {url}")
        return []

    response = session.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    links = []

    for anchor in soup.find_all("a", href=True):
        href = urljoin(url, anchor["href"])
        parsed = urlparse(href)

        if parsed.scheme not in ("http", "https"):
            continue

        if not (
            parsed.hostname == "usc.edu"
            or parsed.hostname.endswith(".usc.edu")
        ):
            continue

        label = anchor.get_text(" ", strip=True)

        searchable = (label + " " + parsed.path).lower()

        if any(word in searchable for word in KEYWORDS):
            links.append({
                "label": label,
                "url": href
            })

    return links


def main():
    sources = json.loads(
        SOURCES.read_text(encoding="utf-8")
    )

    all_links = []

    for source in sources:
        print(f"Checking links: {source['title']}")

        try:
            results = discover(source["url"])

            for result in results:
                result["discovered_from"] = source["id"]

            all_links.extend(results)

        except Exception as error:
            print(f"Error: {error}")

    # Remove duplicates
    unique = {
        item["url"]: item
        for item in all_links
    }

    output = ROOT / "data" / "processed" / "discovered_links.json"

    output.write_text(
        json.dumps(list(unique.values()), indent=2),
        encoding="utf-8"
    )

    print(f"\nDiscovered {len(unique)} candidate links.")
    print(f"Saved to: {output}")


if __name__ == "__main__":
    main()
