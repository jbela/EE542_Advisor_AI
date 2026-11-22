"""Tests for deterministic syllabus grading comparisons."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


class TestSyllabusGradingComparisonAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_verified_comparison_skips_llm(self):
        with patch(
            "backend.main.compare_grading_profiles"
        ) as comparison:
            comparison.return_value = {
                "answer": (
                    "EE 510: Homework 20%. "
                    "EE 542: Final Project 50%."
                ),
                "sources": [
                    {
                        "course_code": "EE 510",
                        "source_type": "syllabus",
                    },
                    {
                        "course_code": "EE 542",
                        "source_type": "syllabus",
                    },
                ],
                "status": "review_required",
            }

            with patch(
                "backend.main.get_context",
                side_effect=AssertionError(
                    "RAG should not run for verified comparisons."
                ),
            ):
                response = self.client.post(
                    "/ask",
                    json={
                        "question": (
                            "Compare the grading policies of "
                            "EE 510 and EE 542 in Fall 2026."
                        ),
                        "term_code": "20263",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Homework 20%", response.json()["answer"])
        self.assertEqual(len(response.json()["sources"]), 2)
        comparison.assert_called_once_with(
            ["EE 510", "EE 542"],
            "20263",
        )

    def test_general_course_comparison_not_intercepted(self):
        with patch(
            "backend.main.compare_grading_profiles"
        ) as comparison:
            with patch(
                "backend.main.get_context",
                return_value=[],
            ):
                response = self.client.post(
                    "/ask",
                    json={
                        "question": (
                            "Compare the course descriptions of "
                            "EE 510 and EE 542 in Fall 2026."
                        ),
                        "term_code": "20263",
                    },
                )

        self.assertEqual(response.status_code, 200)
        comparison.assert_not_called()

    def test_missing_verified_profile_returns_uncertainty(self):
        with patch(
            "backend.main.compare_grading_profiles",
            return_value=None,
        ):
            with patch(
                "backend.main.get_context",
                side_effect=AssertionError(
                    "Unverified comparison must not use RAG."
                ),
            ):
                response = self.client.post(
                    "/ask",
                    json={
                        "question": (
                            "Compare the grading policies of "
                            "EE 510 and EE 999 in Fall 2026."
                        ),
                        "term_code": "20263",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "could not verify complete grading profiles",
            response.json()["answer"],
        )
        self.assertEqual(response.json()["sources"], [])
        self.assertEqual(
            response.json()["status"],
            "review_required",
        )


if __name__ == "__main__":
    unittest.main()
