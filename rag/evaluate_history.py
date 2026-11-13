import json
from pathlib import Path

from rag.advisor_retrieval import retrieve_for_advisor

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_FILE = ROOT / "tests" / "retrieval_questions_v2.json"


def check_history(question, results):
    qid = question["id"]

    if qid == "Q17":
        return (
            len(results) > 0
            and results[0].get("course_code") == "EE 542"
            and str(results[0].get("term_code")) == "20263"
            and results[0].get("historical") is True
            and results[0].get("requested_term_checked") is True
        )

    if qid == "Q18":
        return (
            len(results) > 0
            and results[0].get("availability_status") == "listed"
            and str(results[0].get("term_code")) == "20263"
        )

    if qid in ("Q19", "Q23"):
        return (
            len(results) > 0
            and results[0].get("availability_status") == "not_listed"
            and results[0].get("requested_term_checked") is True
            and str(results[0].get("term_code")) == "20271"
        )

    if qid == "Q20":
        return (
            len(results) > 0
            and results[0].get("course_code") == "EE 542"
            and str(results[0].get("term_code")) == "20263"
        )

    if qid == "Q21":
        return (
            len(results) > 0
            and results[0].get("course_code") == "EE 450"
            and str(results[0].get("term_code")) == "20262"
        )

    if qid in ("Q22", "Q25"):
        return (
            len(results) > 0
            and results[0].get("course_code") == "EE 542"
            and str(results[0].get("term_code")) == "20263"
            and results[0].get("historical") is True
        )

    if qid == "Q24":
        terms = {
            str(r.get("term_code"))
            for r in results
            if r.get("course_code") == "EE 450"
        }
        return {"20262", "20263"}.issubset(terms)

    if qid == "Q26":
        return (
            len(results) == 1
            and results[0].get("retrieval_method") == "historical_catalog"
            and results[0].get("status") == "collected"
            and str(results[0].get("term_code")) == "20253"
            and results[0].get("course_count") == 71
            and len(results[0].get("courses", [])) == 71
        )

    return False


def main():
    questions = json.loads(
        QUESTIONS_FILE.read_text(encoding="utf-8")
    )

    historical = [
        q for q in questions
        if q["category"] == "historical"
    ]

    passed = 0

    print("=" * 60)
    print("USC ADVISOR AI - HISTORICAL RETRIEVAL EVALUATION")
    print("=" * 60)

    for question in historical:
        try:
            results = retrieve_for_advisor(
                question=question["question"],
                term_code=question.get("term_code", "20271"),
                top_k=5
            )

            success = check_history(question, results)

        except Exception as error:
            success = False
            print(f"{question['id']}: ERROR - {error}")

        passed += int(success)

        print(
            f"{question['id']}: "
            f"{'PASS' if success else 'FAIL'}"
        )

    print("\n" + "=" * 60)
    print(f"Historical questions: {len(historical)}")
    print(f"Passed: {passed}")
    print(f"Accuracy: {passed / len(historical):.3f}")


if __name__ == "__main__":
    main()
