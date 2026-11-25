"""Fixed-rule policy answers, citation normalization, and prompt composition.

Run: python -m unittest tests.test_policy_answers -v
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import policy_answers
from backend.answer_quality import normalize_citation_groups
from backend.prompts import CORE, DISCOVERY, POLICY, SYLLABUS, system_prompt

RCL_TEXT = (
    "Category 2: Medical Reasons Students who drop below full-time enrollment "
    "without prior authorization may be considered out of status. Category 3: "
    "Final Semester Exemption Students in their final semester are not required "
    "to be enrolled full time if they do not need a full course load to complete "
    "their degree requirements. Students must be enrolled in all remaining degree "
    "requirements needed to complete their program during the semester. To confirm "
    "their final semester status, students must submit the appropriate SEVIS Final "
    "Semester Check through Trojan International by the end of the second week of "
    "classes . If only one course is needed to complete the degree during the final "
    "semester, that course must be taken in person."
)
REG_TEXT = (
    "International students must register in a minimum of 12 units as "
    "undergraduates, 8 units as master's degree students and 6 units as doctoral "
    "students. Registration Confirmation Copies All enrollment, tuition and fee "
    "information is available on the Registration & Fee Summary."
)


class FinalSemesterAnswer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raw = Path(self.tmp.name)
        for source_id, text, url in (
            ("ois_reduced_course_load", RCL_TEXT, "https://ois.usc.edu/rcl/"),
            ("usc_registration", REG_TEXT, "https://arr.usc.edu/registration-services/"),
        ):
            (raw / f"{source_id}.json").write_text(json.dumps({
                "id": source_id, "title": source_id, "url": url,
                "category": "international", "text": text}), encoding="utf-8")
        self.patch = patch.object(policy_answers, "RAW_DIR", raw)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_mom_question_quotes_ois_verbatim(self):
        result = policy_answers.final_semester_answer(
            "I'm an international student in my final semester. If I only take "
            "2 classes, will my F-1 visa or tuition be affected?")
        answer = result["answer"]
        self.assertIn("“Students in their final semester are not required", answer)
        self.assertNotIn("Final Semester Exemption Students", answer)  # heading dropped
        self.assertIn("SEVIS Final Semester Check through Trojan International", answer)
        self.assertIn("8 units as master's degree students", answer)
        self.assertIn("don't say how tuition changes", answer)
        self.assertIn("“All enrollment, tuition", answer)
        self.assertNotIn("Registration Confirmation Copies", answer)
        self.assertEqual([s["url"] for s in result["sources"]],
                         ["https://ois.usc.edu/rcl/", "https://arr.usc.edu/registration-services/"])

    def test_third_person_parent_phrasing_matches(self):
        self.assertIsNotNone(policy_answers.final_semester_answer(
            "My daughter is on an F-1 visa in her last semester. Can she take just two courses?"))

    def test_unrelated_questions_do_not_match(self):
        for question in ("What should I do after graduation as an F-1 student?",
                         "How many units is EE 562 in my final semester?",
                         "What are the prerequisites for EE 562?"):
            self.assertIsNone(policy_answers.final_semester_answer(question), question)

    def test_changed_source_falls_back(self):
        path = Path(self.tmp.name) / "ois_reduced_course_load.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["text"] = data["text"].replace("Students in their final semester", "Final-term students")
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIsNone(policy_answers.final_semester_answer(
            "As an F-1 student in my final semester, can I take only two classes?"))

    def test_missing_registration_page_still_answers(self):
        (Path(self.tmp.name) / "usc_registration.json").unlink()
        result = policy_answers.final_semester_answer(
            "As an F-1 student in my final semester, can I take only two classes?")
        self.assertEqual(len(result["sources"]), 1)
        self.assertNotIn("[2]", result["answer"])


class CitationGroups(unittest.TestCase):
    def test_expands_ranges_and_lists(self):
        self.assertEqual(normalize_citation_groups("a [1-3]."), "a [1][2][3].")
        self.assertEqual(normalize_citation_groups("b [1, 3]"), "b [1][3]")
        self.assertEqual(normalize_citation_groups("c [2 and 4]"), "c [2][4]")
        self.assertEqual(normalize_citation_groups("d [1–2, 4]"), "d [1][2][4]")

    def test_leaves_invalid_groups_unchanged(self):
        self.assertEqual(normalize_citation_groups("[5-1]"), "[5-1]")
        self.assertEqual(normalize_citation_groups("[1-40]"), "[1-40]")
        self.assertEqual(normalize_citation_groups("[2]"), "[2]")


class PromptComposition(unittest.TestCase):
    def test_rules_follow_evidence_type(self):
        policy = system_prompt([{"retrieval_method": "hybrid"}])
        syllabus = system_prompt([{"retrieval_method": "hybrid", "source_type": "syllabus"}])
        discovery = system_prompt([{"retrieval_method": "semantic_bge"}])
        self.assertTrue(all(p.startswith(CORE) for p in (policy, syllabus, discovery)))
        self.assertIn(POLICY, policy)
        self.assertNotIn(SYLLABUS, policy)
        self.assertIn(SYLLABUS, syllabus)
        self.assertNotIn(POLICY, syllabus)
        self.assertIn(DISCOVERY, discovery)


if __name__ == "__main__":
    unittest.main()
