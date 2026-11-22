import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ingestion import review_syllabus_facts as review


class TestSyllabusFactReview(unittest.TestCase):

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)

        root = Path(temp.name)
        self.docs = root / "syllabi"
        self.candidates = root / "candidates"
        self.reviewed = root / "reviewed"

        for directory in (
            self.docs,
            self.candidates,
            self.reviewed,
        ):
            directory.mkdir()

        self.document = {
            "id": "syllabus_zz123_20263_test",
            "course_code": "ZZ 123",
            "term_code": "20263",
            "file_hash": "test-hash",
            "pages": [{
                "page_number": 1,
                "text": "Grading: Homework: 20%, Final Project: 50%",
            }],
        }

        self.candidate = {
            "type": "assessment_weight",
            "name": "Homework",
            "source_label": "Homework",
            "weight_percent": 20,
            "page_number": 1,
            "source_quote": "Homework: 20%",
            "verified": False,
        }

        self.candidate_data = {
            "document_id": self.document["id"],
            "source_file_hash": "test-hash",
            "items": [self.candidate],
        }

        (self.docs / "zz123_20263_test.json").write_text(
            json.dumps(self.document),
            encoding="utf-8",
        )

        (self.candidates / "syllabus_zz123_20263_test.json").write_text(
            json.dumps(self.candidate_data),
            encoding="utf-8",
        )

        for name, directory in (
            ("SYLLABI_DIR", self.docs),
            ("CANDIDATES_DIR", self.candidates),
            ("REVIEWED_DIR", self.reviewed),
        ):
            guard = patch.object(review, name, directory)
            guard.start()
            self.addCleanup(guard.stop)

    def test_valid_candidate(self):
        self.assertTrue(
            review.validate_candidate(
                self.candidate,
                self.document,
            )
        )

    def test_wrong_percentage_rejected(self):
        item = dict(self.candidate, weight_percent=50)

        self.assertFalse(
            review.validate_candidate(item, self.document)
        )

    def test_wrong_quote_rejected(self):
        item = dict(
            self.candidate,
            source_quote="Homework: 25%",
        )

        self.assertFalse(
            review.validate_candidate(item, self.document)
        )

    def test_wrong_page_rejected(self):
        item = dict(self.candidate, page_number=2)

        self.assertFalse(
            review.validate_candidate(item, self.document)
        )

    def test_source_hash_mismatch_rejected(self):
        self.candidate_data["source_file_hash"] = "old-hash"

        path = (
            self.candidates
            / "syllabus_zz123_20263_test.json"
        )

        path.write_text(
            json.dumps(self.candidate_data),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            review.review_document(
                "syllabus_zz123_20263_test"
            )


    def test_existing_reviewed_file_preserved_on_cancel(self):
        output = (
            self.reviewed
            / "syllabus_zz123_20263_test.json"
        )

        existing = {
            "document_id": self.document["id"],
            "source_file_hash": self.document["file_hash"],
            "items": [{
                "name": "Final Project",
                "source_label": "Final Project",
                "weight_percent": 50,
                "page_number": 1,
                "source_quote": "Final Project: 50%",
                "verified": True,
            }],
        }

        output.write_text(
            json.dumps(existing),
            encoding="utf-8",
        )

        original = output.read_bytes()

        with patch("builtins.input", return_value="q"):
            review.review_document(
                "syllabus_zz123_20263_test"
            )

        self.assertEqual(output.read_bytes(), original)


    def test_approved_fact_written(self):
        with patch(
            "builtins.input",
            side_effect=["a", "", ""],
        ):
            review.review_document(
                "syllabus_zz123_20263_test"
            )

        output = (
            self.reviewed
            / "syllabus_zz123_20263_test.json"
        )

        data = json.loads(
            output.read_text(encoding="utf-8")
        )

        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(
            data["items"][0]["weight_percent"],
            20,
        )
        self.assertTrue(
            data["items"][0]["verified"]
        )

    def test_invalid_existing_reviewed_file_rejected(self):
        output = (
            self.reviewed
            / "syllabus_zz123_20263_test.json"
        )

        output.write_text(
            '{"existing": true}',
            encoding="utf-8",
        )

        original = output.read_bytes()

        with self.assertRaises(ValueError):
            review.review_document(
                "syllabus_zz123_20263_test"
            )

        self.assertEqual(output.read_bytes(), original)


    def test_merge_preserves_existing_facts(self):
        output = (
            self.reviewed
            / "syllabus_zz123_20263_test.json"
        )

        existing = {
            "document_id": self.document["id"],
            "source_file_hash": self.document["file_hash"],
            "items": [{
                "name": "Final Project",
                "source_label": "Final Project",
                "weight_percent": 50,
                "page_number": 1,
                "source_quote": "Final Project: 50%",
                "verified": True,
            }],
        }

        output.write_text(
            json.dumps(existing),
            encoding="utf-8",
        )

        with patch(
            "builtins.input",
            side_effect=["a", "", ""],
        ):
            review.review_document(
                "syllabus_zz123_20263_test"
            )

        result = json.loads(
            output.read_text(encoding="utf-8")
        )

        self.assertEqual(len(result["items"]), 2)

        weights = {
            item["name"]: item["weight_percent"]
            for item in result["items"]
        }

        self.assertEqual(weights["Final Project"], 50)
        self.assertEqual(weights["Homework"], 20)

        backup = output.with_suffix(".json.bak")
        self.assertTrue(backup.exists())

    def test_duplicate_fact_not_added(self):
        output = (
            self.reviewed
            / "syllabus_zz123_20263_test.json"
        )

        existing = {
            "document_id": self.document["id"],
            "source_file_hash": self.document["file_hash"],
            "items": [{
                "name": "Homework",
                "source_label": "Homework",
                "weight_percent": 20,
                "page_number": 1,
                "source_quote": "Homework: 20%",
                "verified": True,
            }],
        }

        output.write_text(
            json.dumps(existing),
            encoding="utf-8",
        )

        original = output.read_bytes()

        with patch(
            "builtins.input",
            side_effect=["a", "", ""],
        ):
            review.review_document(
                "syllabus_zz123_20263_test"
            )

        self.assertEqual(output.read_bytes(), original)

        backup = output.with_suffix(".json.bak")
        self.assertFalse(backup.exists())


    def test_invalid_existing_fact_rejected(self):
        output = (
            self.reviewed
            / "syllabus_zz123_20263_test.json"
        )

        existing = {
            "document_id": self.document["id"],
            "source_file_hash": self.document["file_hash"],
            "items": [{
                "name": "Homework",
                "source_label": "Homework",
                "weight_percent": 90,
                "page_number": 1,
                "source_quote": "Homework: 20%",
                "verified": True,
            }],
        }

        output.write_text(
            json.dumps(existing),
            encoding="utf-8",
        )

        original = output.read_bytes()

        with self.assertRaises(ValueError):
            review.review_document(
                "syllabus_zz123_20263_test"
            )

        self.assertEqual(
            output.read_bytes(),
            original,
        )

    def test_unverified_existing_fact_rejected(self):
        output = (
            self.reviewed
            / "syllabus_zz123_20263_test.json"
        )

        existing = {
            "document_id": self.document["id"],
            "source_file_hash": self.document["file_hash"],
            "items": [{
                "name": "Homework",
                "source_label": "Homework",
                "weight_percent": 20,
                "page_number": 1,
                "source_quote": "Homework: 20%",
                "verified": False,
            }],
        }

        output.write_text(
            json.dumps(existing),
            encoding="utf-8",
        )

        original = output.read_bytes()

        with self.assertRaises(ValueError):
            review.review_document(
                "syllabus_zz123_20263_test"
            )

        self.assertEqual(
            output.read_bytes(),
            original,
        )


    def test_valid_policy_candidate(self):
        self.document["pages"][0]["text"] += (
            " Late assignments receive a 50% deduction."
        )

        candidate = {
            "type": "late_penalty",
            "page_number": 1,
            "source_quote": (
                "Late assignments receive a 50% deduction."
            ),
            "verified": False,
        }

        self.assertTrue(
            review.validate_policy_candidate(
                candidate,
                self.document,
            )
        )

    def test_policy_wrong_quote_rejected(self):
        candidate = {
            "type": "late_penalty",
            "page_number": 1,
            "source_quote": "Late assignments receive no penalty.",
            "verified": False,
        }

        self.assertFalse(
            review.validate_policy_candidate(
                candidate,
                self.document,
            )
        )

    def test_policy_wrong_page_rejected(self):
        candidate = {
            "type": "late_penalty",
            "page_number": 2,
            "source_quote": "Homework: 20%",
            "verified": False,
        }

        self.assertFalse(
            review.validate_policy_candidate(
                candidate,
                self.document,
            )
        )

    def test_unknown_policy_type_rejected(self):
        candidate = {
            "type": "unknown_policy",
            "page_number": 1,
            "source_quote": "Homework: 20%",
            "verified": False,
        }

        self.assertFalse(
            review.validate_policy_candidate(
                candidate,
                self.document,
            )
        )


    def test_policy_approval_preserves_existing_weights(self):
        output = (
            self.reviewed
            / "syllabus_zz123_20263_test.json"
        )

        existing = {
            "document_id": self.document["id"],
            "source_file_hash": self.document["file_hash"],
            "items": [{
                "name": "Homework",
                "source_label": "Homework",
                "weight_percent": 20,
                "page_number": 1,
                "source_quote": "Homework: 20%",
                "verified": True,
            }],
        }

        output.write_text(
            json.dumps(existing),
            encoding="utf-8",
        )

        self.document["pages"][0]["text"] += (
            " Late assignments receive a 50% deduction."
        )

        document_path = self.docs / "zz123_20263_test.json"
        document_path.write_text(
            json.dumps(self.document),
            encoding="utf-8",
        )

        self.candidate_data["policies"] = [{
            "type": "late_penalty",
            "page_number": 1,
            "source_quote": (
                "Late assignments receive a 50% deduction."
            ),
            "verified": False,
        }]

        candidate_path = (
            self.candidates
            / "syllabus_zz123_20263_test.json"
        )

        candidate_path.write_text(
            json.dumps(self.candidate_data),
            encoding="utf-8",
        )

        with patch(
            "builtins.input",
            side_effect=["s", "a"],
        ):
            review.review_document(
                "syllabus_zz123_20263_test"
            )

        result = json.loads(
            output.read_text(encoding="utf-8")
        )

        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(len(result["policies"]), 1)

        self.assertEqual(
            result["policies"][0]["type"],
            "late_penalty",
        )
        self.assertTrue(
            result["policies"][0]["verified"]
        )


    def test_policy_cancel_preserves_existing_file(self):
        output = (
            self.reviewed
            / "syllabus_zz123_20263_test.json"
        )

        existing = {
            "document_id": self.document["id"],
            "source_file_hash": self.document["file_hash"],
            "items": [],
            "policies": [],
        }

        output.write_text(
            json.dumps(existing),
            encoding="utf-8",
        )

        original = output.read_bytes()

        self.document["pages"][0]["text"] += (
            " Late assignments receive a 50% deduction."
        )

        (self.docs / "zz123_20263_test.json").write_text(
            json.dumps(self.document),
            encoding="utf-8",
        )

        self.candidate_data["policies"] = [{
            "type": "late_penalty",
            "page_number": 1,
            "source_quote": (
                "Late assignments receive a 50% deduction."
            ),
            "verified": False,
        }]

        (
            self.candidates
            / "syllabus_zz123_20263_test.json"
        ).write_text(
            json.dumps(self.candidate_data),
            encoding="utf-8",
        )

        with patch(
            "builtins.input",
            side_effect=["s", "q"],
        ):
            review.review_document(
                "syllabus_zz123_20263_test"
            )

        self.assertEqual(output.read_bytes(), original)

    def test_duplicate_policy_not_added(self):
        output = (
            self.reviewed
            / "syllabus_zz123_20263_test.json"
        )

        quote = "Late assignments receive a 50% deduction."

        self.document["pages"][0]["text"] += " " + quote

        (self.docs / "zz123_20263_test.json").write_text(
            json.dumps(self.document),
            encoding="utf-8",
        )

        existing = {
            "document_id": self.document["id"],
            "source_file_hash": self.document["file_hash"],
            "items": [],
            "policies": [{
                "type": "late_penalty",
                "page_number": 1,
                "source_quote": quote,
                "verified": True,
            }],
        }

        output.write_text(
            json.dumps(existing),
            encoding="utf-8",
        )

        original = output.read_bytes()

        self.candidate_data["policies"] = [{
            "type": "late_penalty",
            "page_number": 1,
            "source_quote": quote,
            "verified": False,
        }]

        (
            self.candidates
            / "syllabus_zz123_20263_test.json"
        ).write_text(
            json.dumps(self.candidate_data),
            encoding="utf-8",
        )

        with patch(
            "builtins.input",
            side_effect=["s", "a"],
        ):
            review.review_document(
                "syllabus_zz123_20263_test"
            )

        self.assertEqual(output.read_bytes(), original)

if __name__ == "__main__":
    unittest.main()
