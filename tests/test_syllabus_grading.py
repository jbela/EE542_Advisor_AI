"""Source-bound grading answers; fixtures contain no real syllabus text."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from backend import main
from rag import advisor_retrieval as router
from rag import syllabus_grading as grading
from rag import syllabus_lookup


class GradingFixture:
    def setUp(self):
        super().setUp()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.docs = root / "syllabi"
        self.facts = root / "facts"
        self.docs.mkdir()
        self.facts.mkdir()
        self.doc = {
            "id": "example_20263",
            "title": "Example Course - Fall 2026",
            "course_code": "ZZ 123",
            "term_code": "20263",
            "section_label": "Friday",
            "file_hash": "example-hash",
            "source_file": "example.pdf",
            "url": None,
            "pages": [{"page_number": 2, "text": "Grading: 37% Final Project. 15% Attendance."}],
        }
        self.reviewed = {
            "document_id": "example_20263",
            "source_file_hash": "example-hash",
            "items": [{
                "name": "Final Project",
                "aliases": ["Capstone"],
                "weight_percent": 37,
                "page_number": 2,
                "source_quote": "37% Final Project",
                "verified": True,
            }],
        }
        self.save()
        for target, name, value in (
            (grading, "SYLLABI_DIR", self.docs),
            (grading, "GRADING_DIR", self.facts),
            (syllabus_lookup, "SYLLABI_DIR", self.docs),
        ):
            guard = patch.object(target, name, value)
            guard.start()
            self.addCleanup(guard.stop)

    def save(self):
        (self.docs / "example.json").write_text(json.dumps(self.doc), encoding="utf-8")
        (self.facts / "example_20263.json").write_text(json.dumps(self.reviewed), encoding="utf-8")

    def lookup(self, question="What percentage is the final project worth in ZZ 123?"):
        return grading.lookup_grading_fact(question, "ZZ 123", "20263")


class TestGradingLookup(GradingFixture, unittest.TestCase):
    def test_value_and_page_come_from_data(self):
        result = self.lookup()
        self.assertEqual(result["grading_fact"]["weight_percent"], 37)
        self.assertEqual(result["page_number"], 2)
        self.assertEqual(result["text"], "37% Final Project")

    def test_alias(self):
        self.assertIsNotNone(self.lookup("How much is the Capstone worth in ZZ 123?"))

    def test_wrong_assessment_percentage_is_rejected(self):
        self.reviewed["items"][0]["weight_percent"] = 15
        self.reviewed["items"][0]["source_quote"] = self.doc["pages"][0]["text"]
        self.save()
        self.assertIsNone(self.lookup())

    def test_stale_source_hash_is_rejected(self):
        self.reviewed["source_file_hash"] = "old-source"
        self.save()
        self.assertIsNone(self.lookup())

    def test_missing_quote_is_rejected(self):
        self.reviewed["items"][0]["source_quote"] = "37% Final Project is guaranteed"
        self.save()
        self.assertIsNone(self.lookup())

    def test_wrong_page_is_rejected(self):
        self.reviewed["items"][0]["page_number"] = 1
        self.save()
        self.assertIsNone(self.lookup())

    def test_unreviewed_item_is_rejected(self):
        self.reviewed["items"][0]["verified"] = False
        self.save()
        self.assertIsNone(self.lookup())

    def test_course_and_term_must_match(self):
        self.assertIsNone(grading.lookup_grading_fact("Final project worth?", "EE 542", "20263"))
        self.assertIsNone(grading.lookup_grading_fact("Final project worth?", "ZZ 123", "20271"))

    def test_non_weight_question_is_not_handled(self):
        self.assertIsNone(self.lookup("When is the final project due in ZZ 123?"))

    def test_unknown_assessment_is_not_handled(self):
        self.assertIsNone(self.lookup("What is the attendance worth in ZZ 123?"))

    def test_ambiguous_assessment_is_not_selected(self):
        self.reviewed["items"].append(dict(self.reviewed["items"][0]))
        self.save()
        self.assertIsNone(self.lookup())

    def test_multiple_sections_are_not_silently_selected(self):
        other = dict(self.doc, id="example_other", section_label="Monday")
        (self.docs / "other.json").write_text(json.dumps(other), encoding="utf-8")
        self.assertIsNone(self.lookup())

    def test_table_row_name_before_number(self):
        self.doc["pages"][0]["text"] = "Team Gold Version (Final) 37 Week 15"
        self.reviewed["items"][0].update(
            name="Gold Version (Final)", aliases=["Gold Version"],
            source_quote="Gold Version (Final) 37 Week 15",
        )
        self.save()
        self.assertIsNotNone(self.lookup("How much is the Gold Version worth in ZZ 123?"))

    def test_router_does_not_load_vector_search(self):
        fake = ModuleType("rag.retrieve")
        fake.retrieve = Mock(side_effect=AssertionError("Vector search should not run"))
        with patch.dict(sys.modules, {"rag.retrieve": fake}):
            result = router.retrieve_for_advisor("What percentage is the final project worth in ZZ 123?")
        fake.retrieve.assert_not_called()
        self.assertEqual(result[0]["grading_fact"]["weight_percent"], 37)

    def test_missing_explicit_term_has_no_answer(self):
        result = router.retrieve_for_advisor(
            "What percentage is the final project worth in ZZ 123 in Spring 2027?"
        )
        self.assertEqual(result, [])


class TestGradingAPI(GradingFixture, unittest.IsolatedAsyncioTestCase):
    async def test_answer_and_source_stay_together_without_llm(self):
        with patch.object(main.httpx, "AsyncClient") as client:
            result = await main.ask(main.Question(
                question="What percentage is the final project worth in ZZ 123?"
            ))
        client.assert_not_called()
        self.assertIn("37%", result["answer"])
        self.assertIn("Fall 2026", result["answer"])
        self.assertIn("[1]", result["answer"])
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["page_number"], 2)
        self.assertEqual(result["sources"][0]["course_code"], "ZZ 123")
        self.assertEqual(result["status"], "review_required")

    async def test_missing_explicit_term_skips_llm(self):
        with patch.object(main.httpx, "AsyncClient") as client:
            result = await main.ask(main.Question(
                question="What percentage is the final project worth in ZZ 123 in Spring 2027?"
            ))
        client.assert_not_called()
        self.assertEqual(result["sources"], [])
        self.assertNotIn("37%", result["answer"])


if __name__ == "__main__":
    unittest.main()
