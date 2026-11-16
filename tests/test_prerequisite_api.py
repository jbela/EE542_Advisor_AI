import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app

class TestPrerequisiteAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

        self.requirements = {
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

        self.docs = [{
            "id": "20271_EE 562",
            "title": "EE 562 - Random Processes in Engineering",
            "text": "Verified prerequisite information",
            "url": "https://classes.usc.edu/term/20271/course/EE562",
            "category": "course",
            "course_code": "EE 562",
            "term_code": "20271",
            "requested_term": "20271",
            "historical": False,
            "retrieval_method": "exact",
            "prerequisites_structured": self.requirements,
            "prerequisite_verification": {
                "status": "verified",
                "source_url": "https://classes.usc.edu/term/20271/course/EE562",
            },
        }]

    def ask(self, question):
        with (
            patch(
                "backend.main.get_context",
                return_value=self.docs,
            ),
            patch(
                "backend.main.httpx.AsyncClient",
            ) as mock_llm,
        ):
            response = self.client.post(
                "/ask",
                json={
                    "question": question,
                    "term_code": "20271",
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_llm.assert_not_called()

        return response.json()

    def test_not_satisfied(self):
        result = self.ask(
            "If I've completed EE 503 but not EE 441 or EE 510, "
            "have I satisfied the prerequisites for EE 562 "
            "in Spring 2027?"
        )

        self.assertIn(
            "not satisfied",
            result["answer"].lower(),
        )

    def test_satisfied(self):
        result = self.ask(
            "If I've completed EE 503 and EE 510, "
            "have I satisfied the prerequisites for EE 562?"
        )

        self.assertIn(
            "you satisfy",
            result["answer"].lower(),
        )

    def test_unknown(self):
        result = self.ask(
            "If I've completed EE 503, "
            "have I satisfied the prerequisites for EE 562?"
        )

        self.assertIn(
            "cannot determine",
            result["answer"].lower(),
        )

    def test_malformed_question(self):
        result = self.ask(
            "f I've completed EE 503 but not EE 441 or EE 510, "
            "have I satisfied the prerequisites for EE 562?"
        )

        self.assertIn(
            "couldn't reliably interpret",
            result["answer"].lower(),
        )

if __name__ == "__main__":
    unittest.main()