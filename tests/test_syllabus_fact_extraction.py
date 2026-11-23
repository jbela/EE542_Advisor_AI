import unittest

from ingestion.extract_syllabus_facts import extract_weight_candidates


class TestSyllabusFactExtraction(unittest.TestCase):

    def test_name_before_percentage(self):
        text = "Homework: 20%, Midterm: 40%, Final: 40%"
        results = extract_weight_candidates(text, 1)

        weights = {
            item["name"]: item["weight_percent"]
            for item in results
        }

        self.assertEqual(
            weights,
            {"Homework": 20, "Midterm": 40, "Final": 40},
        )

    def test_percentage_before_name(self):
        text = (
            "Grading\n"
            "15% Attendance, class participation, and Quizzes\n"
            "25% Laboratory assignments\n"
            "50% Final Project"
        )

        results = extract_weight_candidates(text, 2)

        self.assertEqual(len(results), 3)
        self.assertEqual(
            {item["weight_percent"] for item in results},
            {15, 25, 50},
        )

    def test_reject_grade_threshold_sentence(self):
        text = (
            "Suppose the threshold for A is 86% "
            "and a student earns 85.6%."
        )

        results = extract_weight_candidates(text, 1)

        self.assertEqual(results, [])

    def test_candidates_are_not_verified(self):
        results = extract_weight_candidates(
            "Homework: 20%",
            1,
        )

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["verified"])

    def test_invalid_percentage(self):
        results = extract_weight_candidates(
            "Homework: 150%",
            1,
        )

        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
