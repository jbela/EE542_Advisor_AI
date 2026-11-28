"""Twenty question end-to-end API benchmark; no synthetic accuracy claims.

Run with FastAPI and Ollama running. The CSV includes manual-review columns
because HTTP 200 and citation validity do not establish factual correctness.
"""

import csv
import time
from pathlib import Path

import requests

URL = "http://127.0.0.1:8000/ask"
TERM = "20271"
QUESTIONS = [
    ("prereq_ee597_both", "I passed EE 450 and EE 503. Am I eligible for EE 597?", "satisfied"),
    ("prereq_ee597_took", "I took EE 450 but not EE 503. Can I take EE 597?", "not_satisfied"),
    ("prereq_ee597_unknown", "I passed EE 450. Can I take EE 597?", "unknown"),
    ("prereq_ee597_finished", "I've finished EE 450 and EE 503. Do I meet the requirements for EE 597?", "satisfied"),
    ("prereq_ee562_or", "If I've completed EE 503 and EE 510, have I satisfied EE 562 prerequisites?", "satisfied"),
    ("prereq_ee562_incomplete", "If I've completed EE 503 but not EE 441 or EE 510, have I satisfied EE 562 prerequisites?", "not_satisfied"),
    ("prereq_ee562_unknown", "If I've completed EE 503, have I satisfied EE 562 prerequisites?", "unknown"),
    ("prereq_ee597_plain", "What are the prerequisites for EE 597?", "evidence_available"),
    ("prereq_ee450_missing", "Does EE 450 have prerequisites?", "evidence_available"),
    ("historical_ee542", "What are the prerequisites for EE 542?", "evidence_available"),
    ("history", "When was EE 542 last offered?", "evidence_available"),
    ("availability", "Is EE 542 offered in Spring 2027?", "evidence_available"),
    ("course_discovery", "Which EE courses cover machine learning?", "evidence_available"),
    ("course_discovery_natural", "I'm interested in cloud computing. Which classes explore it?", "evidence_available"),
    ("policy", "What is USC's D-Clearance policy?", "evidence_available"),
    ("guarantee", "Can you guarantee that I can enroll in EE 562?", "no_enrollment_guarantee"),
    ("waiver", "Can USC waive a prerequisite for me?", "advisor_verification_required"),
    ("transfer", "Will EE 450 count as transfer credit?", "advisor_verification_required"),
    ("personal_planning", "Which courses should I take next semester?", "student_context_required"),
    ("missing_catalog", "What EE courses were offered in Fall 2025?", "depends_on_collected_data"),
]


def run():
    output = Path("reports/week3_api_results.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, question, expected in QUESTIONS:
        started = time.perf_counter()
        row = {
            "test": name, "question": question, "expected_decision": expected,
            "actual_decision": "", "decision_match": "", "seconds": "",
            "http_status": "", "source_count": "", "invalid_citations": "",
            "answer": "", "manual_correctness": "", "manual_source_support": "",
            "manual_unsupported_claims": "", "manual_notes": "",
        }
        try:
            response = requests.post(URL, json={"question": question, "term_code": TERM}, timeout=240)
            row["seconds"] = round(time.perf_counter() - started, 2)
            row["http_status"] = response.status_code
            response.raise_for_status()
            data = response.json()
            row["actual_decision"] = data.get("decision_status", "")
            row["decision_match"] = (row["actual_decision"] == expected) if expected != "depends_on_collected_data" else ""
            row["source_count"] = len(data.get("sources", []))
            row["invalid_citations"] = data.get("invalid_citations", [])
            row["answer"] = data.get("answer", "")
        except (requests.RequestException, ValueError) as exc:
            row["seconds"] = round(time.perf_counter() - started, 2)
            row["answer"] = "REQUEST FAILED: " + str(exc)
        rows.append(row)
        print(f"{name}: HTTP={row['http_status']} decision={row['actual_decision']} expected={expected} {row['seconds']} s")
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print("Results saved:", output)
    print("Fill in manual_correctness and manual_source_support after reviewing evidence.")


if __name__ == "__main__":
    run()
