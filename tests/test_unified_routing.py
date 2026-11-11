"""Focused tests for one canonical routing decision and backend normalization.

Run with: python -m unittest tests/test_unified_routing.py -v
No real USC data, FAISS, or Ollama is required.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag import advisor_retrieval as router
from rag import course_lookup
from backend.rag_service import get_context


class TestUnifiedRouting(unittest.TestCase):
    def test_question_types(self):
        cases = {
            "What are the prerequisites for EE 542?": "exact",
            "What are the requirements for EE 542?": "exact",
            "Is EE 542 offered in Spring 2027?": "exact",
            "Which courses cover machine learning?": "course",
            "What does EE 542 cover in detail?": "course",
            "How does USC D-Clearance work?": "policy",
            "Can international students take a reduced course load?": "policy",
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertEqual(router.choose_retrieval_method(question), expected)

    def test_backend_uses_router_not_duplicate_routing(self):
        raw = [{"retrieval_method": "exact", "course_code": "EE 542",
                "title": "Test course", "term_code": "20263",
                "requested_term": "20271", "historical": True,
                "requested_term_checked": True,
                "prerequisites": {"operator": "UNVERIFIED", "groups": []},
                "source_url": "https://example.edu/ee542"}]
        with patch("backend.rag_service.retrieve_for_advisor", return_value=raw) as search:
            result = get_context("prerequisites for EE 542", "20271")
        search.assert_called_once_with("prerequisites for EE 542", term_code="20271", top_k=5)
        self.assertEqual(result[0]["term_code"], "20263")
        self.assertTrue(result[0]["historical"])
        self.assertIn("UNVERIFIED", result[0]["text"])
        self.assertIn("historical term 20263", result[0]["text"])
        self.assertNotIn('"source_url":', result[0]["text"])

    def test_policy_search_does_not_substitute_course(self):
        import sys
        from types import ModuleType
        fake = ModuleType("rag.retrieve")
        fake.retrieve = lambda *a, **kw: [
            {"category": "international", "text": "OIS policy text", "title": "OIS", "url": "u"}
        ] if kw.get("exclude_category") == "course" else []
        with patch.dict(sys.modules, {"rag.retrieve": fake}):
            result = router.retrieve_for_advisor("Can international students take a reduced course load?")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["category"], "international")

    def test_exact_does_not_import_vector_model(self):
        record = {"course_code": "EE 542", "title": "Demo", "term_code": "20271",
                  "prerequisites_display": {"operator": "SINGLE", "courses": ["EE 450"]},
                  "source_url": "https://example.edu"}
        with patch.object(router, "lookup_course", return_value=record), \
             patch.object(router, "lookup_course_history") as history:
            results = router.retrieve_for_advisor("Prerequisites for EE 542?", "20271")
        self.assertEqual(results[0]["prerequisites"], record["prerequisites_display"])
        history.assert_not_called()

    def test_historical_fallback_and_checked_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for term, code in [("20263", "EE 542"), ("20261", "EE 542"), ("20271", "EE 450")]:
                path = folder / f"ee_{term}.json"
                path.write_text(json.dumps({"courses": [
                    {"course_code": code, "title": "Intro", "prerequisites_display": []}
                ]}))
            with patch.object(course_lookup, "COURSES_DIR", folder):
                record = course_lookup.lookup_course_history("EE 542", "20271")
                self.assertEqual(record["term_code"], "20263")
                self.assertTrue(record["requested_term_checked"])
                self.assertIsNone(course_lookup.lookup_course("EE 542", "20271"))
                (folder / "ee_20271.json").unlink()
                record = course_lookup.lookup_course_history("EE 542", "20271")
                self.assertFalse(record["requested_term_checked"])

    def test_history_never_uses_future_term(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "ee_20281.json").write_text(json.dumps({"courses": [
                {"course_code": "EE 542", "title": "Future"}]}))
            with patch.object(course_lookup, "COURSES_DIR", folder):
                self.assertIsNone(course_lookup.lookup_course_history("EE 542", "20271"))


if __name__ == "__main__":
    unittest.main()
