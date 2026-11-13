"""Verified requirement edits must change the knowledge fingerprint."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag import knowledge_fingerprint


class TestVerifiedFingerprint(unittest.TestCase):
    def test_all_verified_files_affect_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, courses, verified = root / "raw", root / "courses", root / "verified"
            for directory in (raw, courses, verified):
                directory.mkdir()
            (verified / "ee_20271.json").write_text('{"x":1}', encoding="utf-8")
            (verified / "ee_20263.json").write_text('{"y":1}', encoding="utf-8")
            with patch.object(knowledge_fingerprint, "VERIFIED_DIR", verified):
                initial = knowledge_fingerprint.calculate_fingerprint(raw, courses)
                (verified / "ee_20271.json").write_text('{"x":2}', encoding="utf-8")
                modified_first = knowledge_fingerprint.calculate_fingerprint(raw, courses)
                self.assertNotEqual(initial, modified_first)
                (verified / "ee_20263.json").write_text('{"y":2}', encoding="utf-8")
                modified_second = knowledge_fingerprint.calculate_fingerprint(raw, courses)
                self.assertNotEqual(modified_first, modified_second)

    def test_no_verified_files_still_allows_course_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, courses, verified = root / "raw", root / "courses", root / "verified"
            for directory in (raw, courses, verified):
                directory.mkdir()
            (raw / "policy.json").write_text(json.dumps({"id": "p", "text": "policy"}), encoding="utf-8")
            with patch.object(knowledge_fingerprint, "VERIFIED_DIR", verified):
                value = knowledge_fingerprint.calculate_fingerprint(raw, courses)
            self.assertEqual(len(value), 64)


if __name__ == "__main__":
    unittest.main()
