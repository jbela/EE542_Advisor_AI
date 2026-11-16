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
            "Is EE 542 offered in Spring 2027?": "availability",
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
        self.assertIn("Source semester: Fall 2026", result[0]["text"])
        self.assertIn("Historical requirements may have changed", result[0]["text"])
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

    def test_sufficient_prerequisite_question_uses_exact_lookup(self):
        from rag.advisor_retrieval import (
            choose_retrieval_method,
            prioritize_course_codes,
        )

        question = "Is EE 503 alone sufficient for EE 562?"

        self.assertEqual(
            choose_retrieval_method(question),
            "exact"
        )

        self.assertEqual(
            prioritize_course_codes(question)[0],
            "EE 562"
        )

    def test_complete_catalog_questions(self):
        from rag.advisor_retrieval import (
            choose_retrieval_method,
            retrieve_for_advisor,
        )

        questions = [
            "Show me all EE courses offered in Spring 2027.",
            "List every electrical engineering course in Spring 2027.",
            "What EE courses are available in Spring 2027?",
            "How many EE courses are offered in Spring 2027?",
        ]

        for question in questions:
            with self.subTest(question=question):
                self.assertEqual(
                    choose_retrieval_method(question),
                    "historical_catalog"
                )

                results = retrieve_for_advisor(
                    question,
                    term_code="20271"
                )

                self.assertEqual(
                    results[0]["retrieval_method"],
                    "historical_catalog"
                )

                self.assertEqual(
                    results[0]["course_count"],
                    len(results[0]["courses"])
                )

    def test_course_discovery_excludes_policy_documents(self):
        from rag.advisor_retrieval import retrieve_for_advisor

        question = (
            "Which classes teach deploying applications "
            "on remote servers?"
        )

        results = retrieve_for_advisor(
            question,
            term_code="20271",
            top_k=5
        )

        self.assertTrue(results)

        for result in results:
            self.assertEqual(
                result.get("category"),
                "course"
            )


    def test_course_discovery_uses_bge(self):
        from rag.advisor_retrieval import retrieve_for_advisor

        fake_results = [{
            "course_code": "EE 250",
            "title": "EE 250 - Distributed Systems",
            "term_code": "20271",
            "category": "course",
            "url": "https://classes.usc.edu/term/20271/course/EE250",
            "retrieval_method": "semantic_bge",
        }]

        with patch(
            "rag.discovery_retrieve.retrieve_discovery",
            return_value=fake_results,
        ) as mock_discovery:

            results = retrieve_for_advisor(
                "Which courses teach distributed systems?",
                term_code="20271",
                top_k=5,
            )

        mock_discovery.assert_called_once_with(
            "Which courses teach distributed systems?",
            term_code="20271",
            top_k=5,
        )

        self.assertEqual(
            results[0]["retrieval_method"],
            "semantic_bge",
        )

        self.assertEqual(
            results[0]["course_code"],
            "EE 250",
        )

        self.assertEqual(
            results[0]["source_url"],
            fake_results[0]["url"],
        )


    def test_natural_language_course_discovery_routing(self):
        from rag.advisor_retrieval import choose_retrieval_method

        questions = [
            "Which class teaches deploying software on cloud platforms?",
            "Where can I learn about random processes and Markov chains?",
            "Which courses teach distributed systems?",
            "Which classes cover wireless communications?",
        ]

        for question in questions:
            with self.subTest(question=question):
                self.assertEqual(
                    choose_retrieval_method(question),
                    "course"
                )

    def test_policy_and_exact_routing_preserved(self):
        from rag.advisor_retrieval import choose_retrieval_method

        cases = {
            "What are the prerequisites for EE 597?": "exact",
            "Can I substitute EE 450 with another course?": "policy",
            "What are USC's reduced course load rules?": "policy",
            "Was EE 562 offered in Fall 2025?": "availability",
            "Show all EE courses offered in Spring 2027.": "historical_catalog",
        }

        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertEqual(
                    choose_retrieval_method(question),
                    expected
                )

if __name__ == "__main__":
    unittest.main()
