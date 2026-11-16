"""Test response provenance and LLM prompts without a real Ollama server."""
import unittest
from unittest.mock import patch

from backend import main


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": "According to the older record [1], the listed prerequisite is EE 450. Confirm current requirements."}}


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.payload = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json):
        FakeClient.last_request = json
        return FakeResponse()


class TestUnifiedAPI(unittest.IsolatedAsyncioTestCase):
    async def test_historical_source_reaches_llm_and_response(self):
        evidence = [{
            "id": "20263_EE 542", "title": "EE 542 - Example",
            "text": "NOTICE: Historical term 20263. Prerequisites: EE 450",
            "url": "https://example.edu", "category": "course",
            "retrieval_method": "exact", "term_code": "20263",
            "requested_term": "20271", "historical": True,
        }]
        with patch.object(main, "get_context", return_value=evidence), \
             patch.object(main.httpx, "AsyncClient", FakeClient):
            answer = await main.ask(main.Question(question="Prerequisites for EE 542?"))
        self.assertEqual(answer["sources"][0]["term_code"], "20263")
        self.assertTrue(answer["sources"][0]["historical"])
        self.assertEqual(answer["sources"][0]["requested_term"], "20271")
        self.assertEqual(answer["status"], "review_required")
        self.assertIn("Historical term", FakeClient.last_request["messages"][1]["content"])
        self.assertIn("Historical course records", FakeClient.last_request["messages"][0]["content"])

    async def test_no_evidence_skips_llm(self):
        with patch.object(main, "get_context", return_value=[]), \
             patch.object(main.httpx, "AsyncClient") as client:
            answer = await main.ask(main.Question(question="A question without evidence"))
        client.assert_not_called()
        self.assertEqual(answer["sources"], [])
        self.assertEqual(answer["status"], "review_required")


    def test_bge_evidence_reaches_backend(self):
        from unittest.mock import patch
        from backend.rag_service import get_context

        fake_results = [{
            "retrieval_method": "semantic_bge",
            "course_code": "EE 547",
            "title": "EE 547 - Applied and Cloud Computing",
            "term_code": "20271",
            "requested_term": "20271",
            "historical": False,
            "requested_term_checked": True,
            "category": "course",
            "source_type": "catalog",
            "document_id": "course_20271_123",
            "chunk_id": "course_20271_123",
            "url": "https://classes.usc.edu/term/20271/course/EE547",
            "text": (
                "Course: EE 547\n"
                "Description: Cloud applications, APIs, "
                "databases and software deployment."
            ),
        }]

        with patch(
            "backend.rag_service.retrieve_for_advisor",
            return_value=fake_results,
        ):
            docs = get_context(
                "Which class teaches cloud computing?",
                term_code="20271",
                top_k=5,
            )

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["course_code"], "EE 547")
        self.assertEqual(docs[0]["retrieval_method"], "semantic_bge")
        self.assertEqual(docs[0]["term_code"], "20271")
        self.assertIn("software deployment", docs[0]["text"])
        self.assertTrue(docs[0]["url"])


    def test_complete_catalog_skips_llm(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from backend.main import app

        courses = [
            {
                "course_code": f"EE {100+i}",
                "title": f"Example Course {i}"
            }
            for i in range(82)
        ]

        fake_context = [{
            "id": "catalog_20271",
            "title": "EE course catalog - Spring 2027",
            "text": "Collected EE course catalog for Spring 2027: 82 courses.",
            "url": "https://classes.usc.edu/term/20271/catalogue/school/ENGV/program/EE",
            "category": "course",
            "course_code": None,
            "term_code": "20271",
            "requested_term": "20271",
            "historical": True,
            "retrieval_method": "historical_catalog",
            "catalog_status": "collected",
            "course_count": 82,
            "courses": courses,
        }]

        with patch(
            "backend.main.get_context",
            return_value=fake_context,
        ), patch(
            "backend.main.httpx.AsyncClient"
        ) as mock_llm:

            client = TestClient(app)

            response = client.post(
                "/ask",
                json={
                    "question": "What courses are offered in Spring 2027?",
                    "term_code": "20271",
                },
            )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        answer = data["answer"]

        self.assertIn("82 courses", answer)
        self.assertIn("EE 100", answer)
        self.assertIn("EE 181", answer)

        self.assertEqual(
            len(data["sources"]),
            1
        )

        self.assertEqual(
            data["sources"][0]["retrieval_method"],
            "historical_catalog"
        )

        mock_llm.assert_not_called()




if __name__ == "__main__":
    unittest.main()
