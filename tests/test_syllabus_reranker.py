import unittest

from rag.syllabus_reranker import rerank_syllabus


class TestSyllabusReranker(unittest.TestCase):

    def make_doc(self, section, text, score=0.03):
        return {
            "source_type": "syllabus",
            "course_code": "EE 542",
            "term_code": "20263",
            "instructor": "Young Cho",
            "syllabus_section": section,
            "text": text,
            "score": score,
        }

    def test_final_project_grading_ranks_first(self):
        docs = [
            self.make_doc(
                "Final Project",
                "The final project includes a report and presentation.",
                0.04,
            ),
            self.make_doc(
                "Grading",
                "Grading: 15% attendance, 25% labs, 50% Final Project",
                0.02,
            ),
        ]

        results = rerank_syllabus(
            "How much is the EE 542 final project worth?",
            docs,
        )

        self.assertEqual(
            results[0]["syllabus_section"],
            "Grading",
        )

    def test_textbook_evidence_ranks_first(self):
        docs = [
            self.make_doc(
                "General",
                "Students will complete a final project.",
                0.04,
            ),
            self.make_doc(
                "Course Description",
                "Required Textbook: None",
                0.02,
            ),
        ]

        results = rerank_syllabus(
            "Does EE 542 have a required textbook?",
            docs,
        )

        self.assertIn(
            "Required Textbook: None",
            results[0]["text"],
        )

    def test_metadata_preserved(self):
        docs = [
            self.make_doc(
                "Preparation for Classes",
                "Python is recommended.",
            ),
        ]

        results = rerank_syllabus(
            "Do I need Python for EE 542?",
            docs,
        )

        self.assertEqual(
            results[0]["course_code"],
            "EE 542",
        )
        self.assertEqual(
            results[0]["term_code"],
            "20263",
        )
        self.assertEqual(
            results[0]["instructor"],
            "Young Cho",
        )

    def test_top_k_limit(self):
        docs = [
            self.make_doc("General", f"Document {i}")
            for i in range(10)
        ]

        results = rerank_syllabus(
            "Tell me about EE 542",
            docs,
            top_k=3,
        )

        self.assertEqual(len(results), 3)

    def test_non_syllabus_evidence_not_modified(self):
        doc = {
            "source_type": "catalog",
            "course_code": "EE 542",
            "text": "Course catalog description",
            "score": 0.03,
        }

        results = rerank_syllabus(
            "Tell me about EE 542",
            [doc],
        )

        self.assertEqual(
            results[0]["text"],
            doc["text"],
        )
        self.assertEqual(
            results[0]["score"],
            doc["score"],
        )


if __name__ == "__main__":
    unittest.main()
