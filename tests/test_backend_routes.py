"""Regression tests for new unified-router evidence types (no Ollama needed)."""
import unittest
from unittest.mock import patch

from backend.rag_service import format_requirement, get_context, normalize


class TestBackendRoutes(unittest.TestCase):
    def check(self, raw, question="Example question"):
        with patch("backend.rag_service.retrieve_for_advisor", return_value=raw):
            return get_context(question)

    def test_not_listed_is_not_discarded(self):
        result = self.check([{
            "retrieval_method": "availability", "course_code": "EE 542",
            "term_code": "20271", "requested_term_checked": True,
            "availability_status": "not_listed", "source_url": "https://example.edu",
        }])
        self.assertEqual(len(result), 1)
        self.assertIn("not listed", result[0]["text"])
        self.assertEqual(result[0]["retrieval_method"], "availability")

    def test_uncollected_term_does_not_claim_absence(self):
        result = self.check([{
            "retrieval_method": "availability", "course_code": "EE 542",
            "term_code": "20271", "availability_status": "term_not_collected",
        }])
        self.assertEqual(len(result), 1)
        self.assertIn("have not been collected", result[0]["text"])
        self.assertIsNone(result[0]["url"])

    def test_history_keeps_source_term(self):
        result = self.check([{
            "retrieval_method": "history", "course_code": "EE 542",
            "title": "Internet and Cloud Computing", "term_code": "20263",
            "requested_term": "20271", "historical": True,
            "requested_term_checked": True, "prerequisites": {"courses": ["EE 450"]},
            "available_terms": ["20263", "20253"],
        }])
        self.assertEqual(result[0]["term_code"], "20263")
        self.assertIn("Fall 2026", result[0]["text"])
        self.assertIn("Fall 2025", result[0]["text"])
        self.assertEqual(result[0]["retrieval_method"], "history")

    def test_comparison_terms_required(self):
        result = self.check([{
            "retrieval_method": "comparison", "course_code": "EE 450",
            "comparison_status": "terms_required",
            "message": "Please specify two semesters to compare.",
        }])
        self.assertEqual(len(result), 1)
        self.assertIn("two semesters", result[0]["text"])

    def test_comparison_two_terms(self):
        result = self.check([{
            "retrieval_method": "comparison", "course_code": "EE 450",
            "title": "Networking", "term_code": term, "requested_term": term,
            "prerequisites": [],
        } for term in ("20262", "20263")])
        self.assertEqual(len(result), 2)
        self.assertIn("Summer 2026", result[0]["text"])
        self.assertIn("Fall 2026", result[1]["text"])

    def test_catalog_truncated_honestly(self):
        result = self.check([{
            "retrieval_method": "historical_catalog", "term_code": "20253",
            "status": "collected", "course_count": 20,
            "courses": [{"course_code": f"EE {400+i}", "title": "Example"} for i in range(20)],
        }])
        self.assertIn("first 15", result[0]["text"])
        self.assertNotIn("EE 419", result[0]["text"])

    def test_uncollected_catalog(self):
        result = self.check([{
            "retrieval_method": "historical_catalog", "term_code": "20253",
            "status": "term_not_collected", "course_count": None,
        }])
        self.assertIn("have not been collected", result[0]["text"])
        self.assertIsNone(result[0]["url"])

    def test_verified_and_and_provenance(self):
        evidence = normalize({
            "retrieval_method": "exact", "course_code": "EE 597",
            "term_code": "20271", "prerequisites": {
                "operator": "AND", "courses": ["EE 450", "EE 503"]
            },
            "source_url": "https://example.edu/course",
            "prerequisite_verification": {
                "status": "verified", "source": "official_course_listing",
                "source_url": "https://example.edu/prerequisites",
                "source_text": "EE 450 and EE 503",
            },
        })
        self.assertIn("EE 450 AND EE 503", evidence["text"])
        self.assertIn("Prerequisite verification status: verified", evidence["text"])
        self.assertEqual(evidence["url"], "https://example.edu/prerequisites")
        self.assertEqual(evidence["prerequisite_verification"]["status"], "verified")

    def test_unverified_logic_not_flattened(self):
        self.assertIn("UNVERIFIED", format_requirement({
            "operator": "UNVERIFIED", "courses": ["EE 450", "EE 503"]
        }))

    def test_unknown_route_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, "Unsupported retrieval method"):
            self.check([{"retrieval_method": "new_method", "text": "info"}])


if __name__ == "__main__":
    unittest.main()
