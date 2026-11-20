"""Week 3 backend checks, no real USC data, Ollama, GPU, or FAISS needed."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.answer_quality import answer_exact_prerequisites, check_citations
from backend.student_question import (
    completion_statuses, is_personal_prerequisite, target_course
)
from backend.prerequisite_service import format_rule


RULE_597 = {"operator": "AND", "courses": ["EE 450", "EE 503"]}
RULE_562 = {"operator": "AND", "groups": [
    {"operator": "SINGLE", "courses": ["EE 503"]},
    {"operator": "OR", "courses": ["EE 441", "EE 510"], "required_courses": 1},
]}


def course(code, rule, term="20271", historical=False, verified=True):
    return {
        "id": term + "_" + code,
        "title": code + " - Course",
        "text": "Course: " + code + "\nPrerequisites: " + str(rule),
        "url": "https://classes.usc.edu/term/" + term + "/course/" + code.replace(" ", ""),
        "category": "course", "course_code": code,
        "term_code": term, "requested_term": "20271",
        "historical": historical, "retrieval_method": "exact",
        "prerequisites_structured": rule,
        "prerequisite_verification": {"status": "verified" if verified else "unverified"},
    }


class TestStudentQuestion(unittest.TestCase):
    def test_supported_phrasings(self):
        questions = [
            ("I passed EE 450 and EE 503. Am I eligible for EE 597?", "satisfied"),
            ("I took EE 450 and EE 503. Can I take EE 597?", "satisfied"),
            ("I've finished EE 450 and EE 503. Do I meet the requirements for EE 597?", "satisfied"),
            ("I completed EE 450 and EE 503, can I take EE 597?", "satisfied"),
            ("If I've completed EE 450 and EE 503, have I satisfied the prerequisites for EE 597?", "satisfied"),
            ("I passed EE 450. Can I take EE 597?", "unknown"),
            ("I only completed EE 450. Can I take EE 597?", "unknown"),
            ("I have already completed EE 450 and EE 503. Can I enroll in EE 597?", "satisfied"),
            ("I took EE 450 but not EE 503. Can I take EE 597?", "not_satisfied"),
            ("I haven't taken EE 503, but I completed EE 450. Can I take EE 597?", "not_satisfied"),
            ("If I've completed EE 503 and EE 510, have I satisfied EE 562 prerequisites?", "satisfied"),
            ("If I've completed EE 503, have I satisfied EE 562 prerequisites?", "unknown"),
            ("If I've completed EE 503 but not EE 441 or EE 510, have I satisfied EE 562 prerequisites?", "not_satisfied"),
        ]
        from backend.prerequisite_service import assess_prerequisite_scenario
        for question, expected in questions:
            with self.subTest(question=question):
                docs = [course("EE 597", RULE_597)] if "EE 597" in question else [course("EE 562", RULE_562)]
                result = assess_prerequisite_scenario(question, docs)
                self.assertIsNotNone(result)
                self.assertEqual(result["decision_status"], expected)

    def test_reject_ambiguous_completion(self):
        questions = [
            "f I've completed EE 503 but not EE 441 or EE 510, have I satisfied EE 562 prerequisites?",
            "I plan to take EE 450. Can I take EE 597?",
            "I might have passed EE 450. Can I take EE 597?",
            "I passed EE 450 and I haven't taken EE 450. Can I take EE 597?",
            "Did I pass EE 450? Can I take EE 597?",
        ]
        for question in questions:
            with self.subTest(question=question):
                self.assertIsNone(completion_statuses(question))

    def test_course_target_and_information_intent(self):
        self.assertEqual(target_course("I passed EE 450 and EE 503, can I take EE 597?"), "EE 597")
        self.assertFalse(is_personal_prerequisite("What are the prerequisites for EE 597?"))
        self.assertFalse(is_personal_prerequisite("I have a question about prerequisites for EE 597"))
        self.assertIsNone(target_course("I passed EE 450 and EE 503; do I qualify?"))

    def test_nested_rule_is_readable(self):
        self.assertEqual(format_rule(RULE_562), "EE 503 and one of (EE 441 or EE 510)")


class TestDirectAnswers(unittest.TestCase):
    def test_unknown_is_not_none_required(self):
        doc = course("EE 450", None)
        answer = answer_exact_prerequisites("Does EE 450 have prerequisites?", [doc])
        self.assertIn("does not specify", answer)
        self.assertIn("does not establish that none", answer)

    def test_historical_has_warning(self):
        doc = course("EE 542", {"courses": ["EE 450"]}, term="20263", historical=True)
        answer = answer_exact_prerequisites("What are the prerequisites for EE 542?", [doc])
        self.assertIn("EE 450", answer)
        self.assertIn("historical", answer.lower())
        self.assertIn("Fall 2026", answer)

    def test_verified_rule_is_not_model_guessed(self):
        doc = course("EE 597", RULE_597)
        answer = answer_exact_prerequisites("What are the prereqs for EE 597?", [doc])
        self.assertIn("EE 450 and EE 503", answer)
        variant = answer_exact_prerequisites("Do I need both EE 450 and EE 503 for EE 597?", [doc])
        self.assertIn("EE 450 and EE 503", variant)

    def test_invalid_numeric_citation(self):
        docs = [course("EE 597", RULE_597), {"url": None}]
        answer, invalid = check_citations("First claim [1]. Second [2] and [9].", docs)
        self.assertIn("[1]", answer)
        self.assertNotIn("[2]", answer)
        self.assertNotIn("[9]", answer)
        self.assertEqual(invalid, [2, 9])


class TestAPIIntegration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def ask(self, question, docs):
        with patch("backend.main.get_context", return_value=docs) as retrieve, \
             patch("backend.main.httpx.AsyncClient") as model:
            response = self.client.post("/ask", json={"question": question})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json(), retrieve, model

    def test_informal_question_canonicalizes_retrieval(self):
        q = "I passed EE 450 and EE 503. Am I eligible for EE 597?"
        response, retrieval, model = self.ask(q, [course("EE 597", RULE_597)])
        self.assertEqual(response["decision_status"], "satisfied")
        self.assertEqual(retrieval.call_args.args[0], "What are the prerequisites for EE 597?")
        model.assert_not_called()

    def test_ee562_and_missing_info(self):
        q = "I passed EE 503. Can I take EE 562?"
        response, _, model = self.ask(q, [course("EE 562", RULE_562)])
        self.assertEqual(response["decision_status"], "unknown")
        model.assert_not_called()

    def test_verified_rule_is_required(self):
        q = "I passed EE 450 and EE 503. Can I take EE 597?"
        response, _, model = self.ask(q, [course("EE 597", RULE_597, verified=False)])
        self.assertEqual(response["decision_status"], "unknown")
        model.assert_not_called()

    def test_historical_only_unknown(self):
        q = "I passed EE 450 and EE 503. Can I take EE 597?"
        response, _, model = self.ask(q, [course("EE 597", RULE_597, term="20263", historical=True)])
        self.assertEqual(response["decision_status"], "unknown")
        model.assert_not_called()

    def test_guarantee_is_escalated(self):
        response, _, model = self.ask("Can you guarantee I can enroll in EE 562?", [course("EE 562", RULE_562)])
        self.assertEqual(response["decision_status"], "no_enrollment_guarantee")
        model.assert_not_called()

    def test_waiver_is_escalated(self):
        response, _, model = self.ask("Can I waive EE 503 as a prerequisite?", [course("EE 597", RULE_597)])
        self.assertEqual(response["decision_status"], "advisor_verification_required")
        model.assert_not_called()

    def test_missing_personal_context(self):
        response, _, model = self.ask("Which courses should I take next semester?", [])
        self.assertEqual(response["decision_status"], "student_context_required")
        model.assert_not_called()

    def test_missing_catalog_has_no_fabricated_citation(self):
        docs = [{"id": "catalog_20253", "title": "Fall 2025 EE catalog", "url": None,
                 "category": "course", "retrieval_method": "historical_catalog",
                 "catalog_status": "term_not_collected", "text": "EE course records have not been collected."}]
        response, _, model = self.ask("What EE courses were offered in Fall 2025?", docs)
        self.assertEqual(response["sources"], [])
        self.assertNotIn("[1]", response["answer"])
        model.assert_not_called()

    def test_syllabus_grading_handler_retained(self):
        doc = {"id": "syllabus", "title": "EE 562 syllabus", "url": "https://example.edu/syllabus",
               "category": "syllabus", "retrieval_method": "hybrid",
               "source_type": "syllabus", "course_code": "EE 562", "term_code": "20271",
               "grading_fact": {"verified": True, "name": "Final Project", "weight_percent": 20},
               "text": "Final Project 20%"}
        response, _, model = self.ask("How much is the final project worth in EE 562?", [doc])
        self.assertIn("20%", response["answer"])
        model.assert_not_called()


    def test_llm_citation_validation_and_quality_prompt(self):
        class FakeResponse:
            def raise_for_status(self):
                pass
            def json(self):
                return {"message": {"content": "EE courses cover networks [1]. Another unsupported claim [9]."}}

        class FakeClient:
            request = None
            def __init__(self, *args, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def post(self, url, json):
                FakeClient.request = json
                return FakeResponse()

        docs = [{"id": "policy1", "title": "USC policy", "text": "Network policy excerpt",
                 "url": "https://example.edu/policy", "category": "policy", "retrieval_method": "hybrid"}]
        with patch("backend.main.get_context", return_value=docs), \
             patch("backend.main.httpx.AsyncClient", FakeClient):
            result = self.client.post("/ask", json={"question": "What is USC's network policy?"})
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["invalid_citations"], [9])
        self.assertNotIn("[9]", data["answer"])
        self.assertIn("[1]", data["answer"])
        self.assertIn("Network policy excerpt", FakeClient.request["messages"][1]["content"])
        self.assertIn("clear student-friendly language", FakeClient.request["messages"][0]["content"])

    def test_registered_availability_is_preserved_in_adapter(self):
        from backend.rag_service import get_context
        record = {"retrieval_method": "availability", "course_code": "EE 542",
                  "title": "Internet and Cloud Computing", "term_code": "20271",
                  "requested_term": "20271", "availability_status": "listed",
                  "requested_term_checked": True, "source_url": "https://example.edu/course"}
        with patch("backend.rag_service.retrieve_for_advisor", return_value=[record]):
            docs = get_context("Is EE 542 offered in Spring 2027?")
        self.assertEqual(docs[0]["availability_status"], "listed")


if __name__ == "__main__":
    unittest.main()
