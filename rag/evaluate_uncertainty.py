"""Evaluate uncertainty handling on the six benchmark questions."""

import json
from pathlib import Path

from rag.advisor_retrieval import retrieve_for_advisor
from rag.evidence_sufficiency import classify_evidence

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_FILE = ROOT / "tests" / "retrieval_questions_v2.json"

EXPECTED = {
    "Q35": "no_enrollment_guarantee",
    "Q36": "advisor_verification_required",
    "Q37": "future_availability_unconfirmed",
    "Q38": "course_not_found",
    "Q39": "advisor_verification_required",
    "Q40": "student_context_required",
}


def check_evidence(qid, results):
    if qid == "Q35":
        return any(
            r.get("course_code") == "EE 597"
            for r in results
        )

    if qid == "Q36":
        return all(
            r.get("category") != "course"
            for r in results
        )

    if qid == "Q37":
        return any(
            r.get("availability_status") == "term_not_collected"
            and str(r.get("term_code")) == "20273"
            for r in results
        )

    if qid == "Q38":
        return not results

    if qid == "Q39":
        return all(
            r.get("category") != "course"
            for r in results
        )

    if qid == "Q40":
        return True

    return False


def main():
    questions = json.loads(
        QUESTIONS_FILE.read_text(encoding="utf-8")
    )

    selected = [
        q for q in questions
        if q["category"] == "uncertainty"
    ]

    passed = 0

    print("=" * 65)
    print("USC ADVISOR AI - UNCERTAINTY EVALUATION")
    print("=" * 65)

    for q in selected:
        results = retrieve_for_advisor(
            q["question"],
            term_code=q.get("term_code", "20271"),
            top_k=5
        )

        classification = classify_evidence(
            q["question"],
            results
        )

        correct_status = (
            classification["decision_status"]
            == EXPECTED[q["id"]]
        )

        correct_evidence = check_evidence(
            q["id"],
            results
        )

        success = (
            correct_status
            and correct_evidence
            and classification["evidence_sufficient"] is False
        )

        passed += int(success)

        print(
            f"{q['id']}: "
            f"{'PASS' if success else 'FAIL'} "
            f"status={classification['decision_status']} "
            f"evidence_check={correct_evidence}"
        )

    print("\n" + "=" * 65)
    print(f"Questions evaluated: {len(selected)}")
    print(f"Passed: {passed}/{len(selected)}")
    print(f"Accuracy: {passed / len(selected):.3f}")
    print("=" * 65)


if __name__ == "__main__":
    main()