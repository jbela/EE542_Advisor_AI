import unittest
from unittest.mock import patch

from rag.advisor_retrieval import retrieve_for_advisor


class TestSyllabusComparison(unittest.TestCase):

    def test_comparison_uses_both_syllabi(self):
        def fake_find_term(course, requested_term=None, max_term=None):
            return "20263"

        def fake_retrieve(question, **kwargs):
            course = kwargs["course_codes"][0]
            return [{
                "source_type": "syllabus",
                "course_code": course,
                "term_code": "20263",
                "syllabus_section": "Grading",
                "text": f"{course} grading policy",
                "score": 0.03,
            }]

        with (
            patch(
                "rag.advisor_retrieval.find_syllabus_term",
                side_effect=fake_find_term,
            ),
            patch(
                "rag.retrieve.retrieve",
                side_effect=fake_retrieve,
            ),
        ):
            results = retrieve_for_advisor(
                "Compare the grading policies of EE 510 and EE 542 "
                "in Fall 2026.",
                term_code="20263",
            )

        self.assertEqual(
            {doc["course_code"] for doc in results},
            {"EE 510", "EE 542"},
        )

        self.assertTrue(
            all(doc["source_type"] == "syllabus" for doc in results)
        )

    def test_catalog_comparison_remains_unchanged(self):
        results = retrieve_for_advisor(
            "Compare EE 510 and EE 542 course descriptions.",
            term_code="20263",
        )

        self.assertTrue(results)
        self.assertTrue(
            all(
                doc["retrieval_method"] == "comparison"
                for doc in results
            )
        )


if __name__ == "__main__":
    unittest.main()
