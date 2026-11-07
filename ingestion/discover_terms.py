import json
import requests
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data" / "processed"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TERMS_FILE = DATA_DIR / "terms.json"

TERMS_API = "https://classes.usc.edu/api/Terms/All"


def fetch_terms():
    """Retrieve semester information from USC."""

    response = requests.get(
        TERMS_API,
        headers={
            "User-Agent": "USCAdvisorAI-StudentResearch/0.1",
            "Accept": "application/json"
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError("Unexpected USC API response format")

    return data


def normalize_terms(data):
    """Convert USC term records into our format."""

    terms = []

    for item in data:
        term = item.get("term") or {}

        code = term.get("value")
        year = term.get("year")
        season = item.get("seasonName") or term.get("season")

        if not code or not year or not season:
            continue

        terms.append({
            "term_code": str(code),
            "name": f"{season} {year}",
            "year": year,
            "season": season,
            "status": item.get("status"),
            "date_active": item.get("dateActive"),
            "date_modified": item.get("dateModified"),
            "source_url": (
                f"https://classes.usc.edu/term/{code}/"
                "catalogue/school/ENGV/program/EE"
            )
        })

    return sorted(
        terms,
        key=lambda x: int(x["term_code"]),
        reverse=True
    )


def main():
    print("Fetching USC academic semesters...")

    raw_terms = fetch_terms()
    terms = normalize_terms(raw_terms)

    if not terms:
        raise ValueError("No valid academic terms returned")

    old_codes = set()

    if TERMS_FILE.exists():
        previous = json.loads(
            TERMS_FILE.read_text(encoding="utf-8")
        )

        old_codes = {
            t["term_code"]
            for t in previous.get("terms", [])
        }

    new_terms = [
        t for t in terms
        if t["term_code"] not in old_codes
    ]

    output = {
        "source": TERMS_API,
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "terms": terms
    }

    TERMS_FILE.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8"
    )

    print(f"\nTotal semesters found: {len(terms)}")
    print(f"New semesters detected: {len(new_terms)}")

    print("\nMost recent semesters:")

    for term in terms[:10]:
        print(
            f"{term['name']} "
            f"({term['term_code']}) "
            f"- {term['status']}"
        )

    if new_terms:
        print("\nNew semesters:")
        for term in new_terms:
            print(f"  + {term['name']}")


if __name__ == "__main__":
    main()
