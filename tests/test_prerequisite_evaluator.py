import unittest

from rag.prerequisite_evaluator import (
    evaluate_prerequisites,
    extract_course_statuses,
)

REQUIREMENTS = {
    "operator": "AND",
    "groups": [
        {"operator": "SINGLE", "courses": ["EE 503"]},
        {
            "operator": "OR",
            "courses": ["EE 441", "EE 510"],
            "required_courses": 1,
        },
    ],
}

VERIFIED = {"status": "verified"}

class TestPrerequisiteEvaluator(unittest.TestCase):

    def test_not_satisfied(self):
        result = evaluate_prerequisites(
            REQUIREMENTS,
            {"EE 503"},
            VERIFIED,
            not_completed_courses={"EE 441", "EE 510"},
        )
        self.assertEqual(result, "not_satisfied")

    def test_satisfied(self):
        result = evaluate_prerequisites(
            REQUIREMENTS,
            {"EE 503", "EE 510"},
            VERIFIED,
        )
        self.assertEqual(result, "satisfied")

    def test_unknown(self):
        result = evaluate_prerequisites(
            REQUIREMENTS,
            {"EE 503"},
            VERIFIED,
        )
        self.assertEqual(result, "unknown")

    def test_unverified(self):
        result = evaluate_prerequisites(
            REQUIREMENTS,
            {"EE 503", "EE 510"},
            {"status": "unverified"},
        )
        self.assertEqual(result, "unknown")

    def test_conflicting_information(self):
        result = evaluate_prerequisites(
            REQUIREMENTS,
            {"EE 503"},
            VERIFIED,
            not_completed_courses={"EE 503"},
        )
        self.assertEqual(result, "unknown")

    def test_extract_negative_courses(self):
        result = extract_course_statuses(
            "If I've completed EE 503 but not EE 441 or EE 510, "
            "have I satisfied the prerequisites for EE 562?"
        )

        self.assertEqual(result["completed"], {"EE 503"})
        self.assertEqual(
            result["not_completed"],
            {"EE 441", "EE 510"},
        )

    def test_reject_question_as_completion(self):
        result = extract_course_statuses(
            "Have I completed EE 503?"
        )
        self.assertIsNone(result)

    def test_reject_future_plan(self):
        result = extract_course_statuses(
            "I plan to complete EE 503 and EE 510."
        )
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()