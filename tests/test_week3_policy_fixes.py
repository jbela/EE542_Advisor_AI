"""Regression tests for Week 3 quality changes; no model/index required."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.answer_quality import citation_coverage, course_citation_issues
from rag.advisor_retrieval import choose_retrieval_method, retrieve_for_advisor


class TestPolicyRouting(unittest.TestCase):
    def test_policy_examples(self):
        questions = [
            "How do I request D-Clearance for EE 597?",
            "What is USC's D-Clearance policy?",
            "Can an international student request a reduced course load?",
            "Where can I request disability accommodations at USC?",
            "Who handles international student enrollment policy?",
        ]
        for question in questions:
            with self.subTest(question=question):
                self.assertEqual(choose_retrieval_method(question), "policy")

    def test_course_prerequisites_stay_exact(self):
        self.assertEqual(choose_retrieval_method("What are the prerequisites for EE 597?"), "exact")
        self.assertEqual(choose_retrieval_method("Is EE 542 offered in Spring 2027?"), "availability")

    def test_named_course_policy_uses_hybrid(self):
        import sys
        from types import ModuleType
        module = ModuleType("rag.retrieve")
        hits = []
        def mock_retrieve(*args, **kwargs):
            hits.append(kwargs)
            return [{"title": "USC policy", "text": "Policy source", "url": "https://example.edu/policy"}]
        module.retrieve = mock_retrieve
        with patch.dict(sys.modules, {"rag.retrieve": module}):
            results = retrieve_for_advisor("How do I get D-Clearance for EE 597?")
        self.assertEqual(results[0]["retrieval_method"], "hybrid")
        self.assertEqual(hits[0]["exclude_category"], "course")


class TestDiscoveryEnrichment(unittest.TestCase):
    def test_structured_catalog_from_exact_term(self):
        import sys
        from types import ModuleType
        module = ModuleType("rag.discovery_retrieve")
        module.retrieve_discovery = lambda *args, **kwargs: [
            {"course_code": "EE 550", "term_code": "20271", "title": "AI Applications",
             "category": "course", "text": "Topics: machine learning", "url": "https://example.edu/ee550"}
        ]
        with patch.dict(sys.modules, {"rag.discovery_retrieve": module}), \
             patch("rag.advisor_retrieval.lookup_course", return_value={
                 "course_code": "EE 550", "title": "AI Applications", "term_code": "20271",
                 "prerequisites_display": ["EE 450"], "source_url": "https://example.edu/ee550"
             }):
            result = retrieve_for_advisor("Which courses cover machine learning?")
        self.assertEqual(result[0]["catalog_record"]["prerequisites"], ["EE 450"])
        self.assertEqual(result[0]["retrieval_method"], "semantic_bge")

    def test_no_catalog_does_not_invent(self):
        import sys
        from types import ModuleType
        module = ModuleType("rag.discovery_retrieve")
        module.retrieve_discovery = lambda *args, **kwargs: [
            {"course_code": "EE 550", "term_code": "20271", "title": "AI Applications",
             "category": "course", "text": "machine learning", "url": "https://example.edu/ee550"}
        ]
        with patch.dict(sys.modules, {"rag.discovery_retrieve": module}), \
             patch("rag.advisor_retrieval.lookup_course", return_value=None):
            result = retrieve_for_advisor("Which classes teach machine learning?")
        self.assertNotIn("catalog_record", result[0])


class TestEvidenceChecks(unittest.TestCase):
    def test_missing_citation_is_flagged(self):
        docs = [{"url": "https://example.edu"}]
        self.assertTrue(citation_coverage("A policy claim.", docs, required=True)["missing_citations"])
        self.assertFalse(citation_coverage("A policy claim [1].", docs, required=True)["missing_citations"])

    def test_recommendation_citation_checked_per_course(self):
        docs = [
            {"retrieval_method": "semantic_bge", "course_code": "EE 460", "url": "https://example.edu/460"},
            {"retrieval_method": "semantic_bge", "course_code": "EE 559", "url": "https://example.edu/559"},
        ]
        good = "- EE 460: Intro to learning [1]\n- EE 559: Advanced learning [2]"
        bad = "- EE 460: Intro to learning [1]\n- EE 559: Advanced learning [1]"
        self.assertEqual(course_citation_issues(good, docs), [])
        self.assertEqual(len(course_citation_issues(bad, docs)), 1)

    def test_history_uses_latest_collected_term(self):
        docs = [
            {"id": "old", "title": "History", "text": "Fall 2022 listing", "url": "https://example.edu/1",
             "category": "course", "retrieval_method": "history", "course_code": "EE 542", "term_code": "20223"},
            {"id": "new", "title": "History", "text": "Fall 2026 listing", "url": "https://example.edu/2",
             "category": "course", "retrieval_method": "history", "course_code": "EE 542", "term_code": "20263"},
        ]
        with patch("backend.main.get_context", return_value=docs), \
             patch("backend.main.httpx.AsyncClient") as llm:
            result = TestClient(app).post("/ask", json={"question": "When was EE 542 last offered?"})
        self.assertEqual(result.status_code, 200)
        self.assertIn("Fall 2026", result.json()["answer"])
        llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
