"""Run against a live FastAPI server, then manually assess source support.

Example: python tests/benchmark_week3_policies.py
"""
import csv
import json
from pathlib import Path
import time
import requests

QUESTIONS = json.loads((Path(__file__).parent / "week3_policy_questions.json").read_text())
URL = "http://127.0.0.1:8000/ask"


def main():
    out = Path("reports/week3_policy_results.csv")
    out.parent.mkdir(exist_ok=True, parents=True)
    rows = []
    for entry in QUESTIONS:
        start = time.perf_counter()
        row = {"id": entry["id"], "question": entry["question"],
               "http_status": "", "latency_s": "", "answer": "", "source_count": "",
               "citations_missing": "", "decision_status": "", "correct": "",
               "source_supported": "", "scope_correct": "", "unsupported_claims": "", "notes": ""}
        try:
            response = requests.post(URL, json={"question": entry["question"],
                                                "term_code": "20271"}, timeout=240)
            row["http_status"] = response.status_code
            response.raise_for_status()
            result = response.json()
            row["answer"] = result.get("answer", "")
            row["source_count"] = len(result.get("sources", []))
            row["citations_missing"] = result.get("missing_citations", "")
            row["decision_status"] = result.get("decision_status", "")
        except (requests.RequestException, ValueError) as exc:
            row["notes"] = str(exc)
        row["latency_s"] = round(time.perf_counter() - start, 2)
        rows.append(row)
        print(entry["id"], row["http_status"], row["latency_s"])
    with out.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("Review accuracy, citations and claims manually:", out)


if __name__ == "__main__":
    main()
