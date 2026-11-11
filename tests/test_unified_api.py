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


if __name__ == "__main__":
    unittest.main()
