"""Section schedules, offering gaps, prerequisite changes, and routing.

Run: python -m unittest tests.test_course_schedule -v
"""
import unittest
from unittest.mock import patch

from backend import course_schedule
from backend.course_schedule import (
    offering_context, prerequisite_change, schedule_answer, section_lines,
)
from backend.student_question import completion_statuses, target_course
from rag.advisor_retrieval import choose_retrieval_method

SECTIONS = [
    {"section_id": "30991", "type": "Lecture",
     "instructors": [{"firstName": "Urbashi", "lastName": "Mitra"}],
     "schedule": [{"days": ["Mon", "Wed"], "startTime": "10:00", "endTime": "11:50"}],
     "registered_seats": 4, "total_seats": 25, "d_clearance": False},
    {"section_id": "30992", "type": "Discussion", "instructors": [],
     "schedule": [{"days": ["Fri"], "startTime": "13:00", "endTime": "13:50"}],
     "registered_seats": 4, "total_seats": 25, "d_clearance": True},
]


def exact_doc(**overrides):
    doc = {"retrieval_method": "exact", "course_code": "EE 562", "term_code": "20271",
           "requested_term": "20271", "historical": False, "sections": SECTIONS,
           "collected_at": "2026-11-23T08:05:00+00:00",
           "url": "https://classes.usc.edu/term/20271/course/EE562"}
    doc.update(overrides)
    return doc


def raw(*groups):
    return [{"requiredCourses": 1, "courseOptions": [{"courseSpace": c} for c in g]}
            for g in groups]


class Sections(unittest.TestCase):
    def test_section_lines_format_times_people_seats(self):
        lines = section_lines(SECTIONS)
        self.assertEqual(lines[0], "- **Lecture 30991** · Mon/Wed 10:00 am–11:50 am · "
                                   "Urbashi Mitra · 4 of 25 seats registered")
        self.assertIn("1:00 pm–1:50 pm", lines[1])
        self.assertIn("requires D-Clearance", lines[1])

    @patch.object(course_schedule, "offering_context", return_value=None)
    def test_schedule_answer_cites_and_dates_snapshot(self, _):
        answer = schedule_answer("When does EE 562 meet?", [exact_doc()], target="EE 562")
        self.assertIn("**EE 562 in Spring 2027** has 1 lecture section: [1]", answer)
        self.assertIn("as of Nov 23, 2026", answer)

    def test_historical_record_does_not_claim_sections(self):
        doc = exact_doc(term_code="20263", historical=True)
        answer = schedule_answer("Who teaches EE 562?", [doc], target="EE 562")
        self.assertIn("not listed in the collected Spring 2027", answer)
        self.assertNotIn("Mitra", answer)

    def test_non_schedule_question_returns_none(self):
        self.assertIsNone(schedule_answer("What are the prerequisites for EE 562?", [exact_doc()]))


class OfferingHistory(unittest.TestCase):
    TERMS = ["20243", "20251", "20253", "20261", "20263", "20271"]

    def offerings(self, terms, prereqs=None):
        prereqs = prereqs or {}
        return [{"term_code": t, "prerequisites": prereqs.get(t),
                 "prerequisites_display": None, "recommended_preparation": None}
                for t in sorted(terms, reverse=True)]

    def test_gap_of_three_semesters_is_reported(self):
        with patch.object(course_schedule, "_main_terms_collected", return_value=self.TERMS), \
             patch.object(course_schedule, "find_course_offerings",
                          return_value=self.offerings(["20251", "20271"])):
            text = offering_context("EE 562", "20271")
        self.assertEqual(text, "Before Spring 2027, the most recent collected listing of EE 562 "
                               "was Spring 2025; it was not listed in Fall 2025, Spring 2026, "
                               "or Fall 2026.")

    def test_regular_offering_has_no_gap_note(self):
        with patch.object(course_schedule, "_main_terms_collected", return_value=self.TERMS), \
             patch.object(course_schedule, "find_course_offerings",
                          return_value=self.offerings(["20261", "20263", "20271"])):
            self.assertIsNone(offering_context("EE 503", "20271"))

    def test_prerequisite_removal_is_explained(self):
        old = raw(["EE 510"])
        rows = self.offerings(["20243", "20253", "20263"], {"20243": old, "20253": old})
        for row in rows[1:]:
            row["prerequisites_display"] = {"operator": "SINGLE", "courses": ["EE 510"]}
        rows[0]["recommended_preparation"] = "EE 503 and EE 510"
        with patch.object(course_schedule, "find_course_offerings", return_value=rows):
            text = prerequisite_change("EE 588", "20263")
        self.assertEqual(text, "This changed recently: collected listings from Fall 2024 through "
                               "Fall 2025 listed EE 510 as a prerequisite; the Fall 2026 listing "
                               "lists no prerequisites and gives recommended preparation: "
                               "EE 503 and EE 510.")

    def test_same_raw_rule_with_different_display_is_not_a_change(self):
        rule = raw(["EE 503"], ["EE 441", "EE 510"])
        rows = self.offerings(["20251", "20271"], {"20251": rule, "20271": rule})
        rows[0]["prerequisites_display"] = {"operator": "AND", "groups": []}  # verified override
        with patch.object(course_schedule, "find_course_offerings", return_value=rows):
            self.assertIsNone(prerequisite_change("EE 562", "20271"))


class HeadlineAndFormat(unittest.TestCase):
    def test_headline_answers_both_halves(self):
        self.assertEqual(course_schedule.headline("satisfied", exact_doc()),
                         "**Yes.** You meet the listed prerequisites, and EE 562 meets "
                         "Mon/Wed 10:00 am–11:50 am with Urbashi Mitra in Spring 2027 (one section).")
        self.assertTrue(course_schedule.headline("not_satisfied", exact_doc()).startswith("**Not yet.**"))
        self.assertTrue(course_schedule.headline("unknown", exact_doc()).startswith("**I can't confirm"))

    def test_dropped_discussions_are_reported(self):
        previous = {"term_code": "20251", "sections": [
            {"type": "Lecture"}, {"type": "Discussion"}, {"type": "Lecture"}, {"type": "Discussion"}]}
        current = [{"type": "Lecture"}]
        with patch.object(course_schedule, "find_course_offerings",
                          return_value=[{"term_code": "20271", "sections": current}, previous]):
            text = course_schedule.format_change("EE 562", "20271", current)
        self.assertEqual(text, "The section format changed: the Spring 2025 listing had 4 sections "
                               "(Discussion, Lecture); the Spring 2027 listing has 1 section (Lecture).")

    def test_same_format_is_not_reported(self):
        same = [{"type": "Lecture"}]
        with patch.object(course_schedule, "find_course_offerings",
                          return_value=[{"term_code": "20271", "sections": same},
                                        {"term_code": "20263", "sections": same}]):
            self.assertIsNone(course_schedule.format_change("EE 503", "20271", same))


class QuestionParsing(unittest.TestCase):
    def test_context_sentence_before_completion_claim(self):
        statuses = completion_statuses(
            "I'm an EE master's student. I've completed EE 503 and EE 441. "
            "Can I take EE 562 in Spring 2027, and when does it meet?")
        self.assertEqual(statuses, {"completed": {"EE 503", "EE 441"}, "not_completed": set()})

    def test_context_sentence_naming_courses_is_still_rejected(self):
        self.assertIsNone(completion_statuses(
            "EE 441 was hard. I've completed EE 503. Can I take EE 562?"))

    def test_before_taking_targets_the_later_course(self):
        self.assertEqual(target_course("Do I need EE 510 before taking EE 588?"), "EE 588")

    def test_schedule_questions_route_to_exact_records(self):
        for q in ("When does EE 562 meet in Spring 2027?", "Who teaches EE 503?",
                  "How many seats are left in EE 503?"):
            self.assertEqual(choose_retrieval_method(q), "exact", q)
        self.assertEqual(choose_retrieval_method("Is EE 562 offered in Fall 2026?"), "availability")


if __name__ == "__main__":
    unittest.main()
