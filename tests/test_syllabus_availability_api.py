import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


class TestSyllabusAvailabilityAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_missing_fall_2025(self):
        self.check_missing("20253", "Fall 2025")

    def test_missing_spring_2027(self):
        self.check_missing("20271", "Spring 2027")

    def check_missing(self, term, semester):
        docs = [{
            "id": "syllabus_missing_EE510_" + term,
            "title": "EE 510 syllabus unavailable",
            "text": f"No imported syllabus for EE 510 in {semester}.",
            "url": None,
            "course_code": "EE 510",
            "source_type": "syllabus",
            "term_code": term,
            "requested_term": term,
            "retrieval_method": "syllabus_unavailable",
            "available_terms": ["20263"],
            "historical": False,
        }]

        with (
            patch("backend.main.get_context", return_value=docs),
            patch("backend.main.httpx.AsyncClient") as mock_llm,
        ):
            response = self.client.post(
                "/ask",
                json={
                    "question": f"What is the grading policy for EE 510 in {semester}?",
                    "term_code": term,
                },
            )

        self.assertEqual(response.status_code, 200)

        result = response.json()

        self.assertIn(semester, result["answer"])
        self.assertIn("don't have an imported", result["answer"])
        self.assertIn("Fall 2026", result["answer"])
        self.assertEqual(result["sources"], [])

        mock_llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
