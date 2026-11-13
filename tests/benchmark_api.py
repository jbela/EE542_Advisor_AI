"""Simple Week 2 end-to-end response and latency recorder.

Run from project root after starting FastAPI and Ollama:
    python tests/benchmark_api.py
"""
import csv
import time
from pathlib import Path

import requests

URL = "http://127.0.0.1:8000/ask"
QUESTIONS = [
    ("EE542", "What are the prerequisites for EE 542?", "20271"),
    ("EE450", "What are the prerequisites for EE 450?", "20271"),
    ("ML", "Which EE courses teach machine learning?", "20271"),
    ("DClearance", "What is USC's D-Clearance policy?", "20271"),
    ("Availability", "Is EE 542 listed in Spring 2027?", "20271"),
    ("History", "When was EE 542 last offered?", "20271"),
    ("EE597", "Do I need both EE 450 and EE 503 for EE 597?", "20271"),
    ("Catalog", "What courses were offered in Fall 2025?", "20253"),
]


def main():
    results = []
    for name, question, term in QUESTIONS:
        start = time.perf_counter()
        row = {"test": name, "question": question, "term_code": term}
        try:
            response = requests.post(
                URL, json={"question": question, "term_code": term}, timeout=240
            )
            row["http_status"] = response.status_code
            response.raise_for_status()
            data = response.json()
            row["status"] = data.get("status", "")
            row["source_count"] = len(data.get("sources", []))
            row["sources"] = "; ".join(str(s.get("url") or "") for s in data.get("sources", []))
            row["answer"] = data.get("answer", "")
        except (requests.RequestException, ValueError) as exc:
            row.update(http_status="error", status="error", source_count=0,
                       sources="", answer=str(exc))
        row["seconds"] = round(time.perf_counter() - start, 2)
        results.append(row)
        print(f"{name}: {row['seconds']}s, status={row['http_status']}")

    output = Path("week2_results.csv")
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f"Saved to {output.resolve()}")


if __name__ == "__main__":
    main()
