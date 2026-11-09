import json
import unittest
from unittest.mock import patch

from ingestion import run_sync


class TestReindexTrigger(unittest.TestCase):

    def setUp(self):
        self.patchers = [
            patch.object(run_sync, "discover_terms"),
            patch.object(run_sync, "sync_courses"),
            patch.object(run_sync, "sync_policies"),
            patch.object(run_sync, "calculate_fingerprint"),
            patch.object(run_sync, "subprocess"),
            patch.object(run_sync, "CURRENT_FILE")
        ]

        mocks = [p.start() for p in self.patchers]

        for p in self.patchers:
            self.addCleanup(p.stop)

        (
            self.mock_discover,
            self.mock_courses,
            self.mock_policies,
            self.mock_fingerprint,
            self.mock_subprocess,
            self.mock_current
        ) = mocks

        self.mock_courses.return_value = {
            "academic_updates": False,
            "failed_terms": []
        }

        self.mock_policies.return_value = {
            "academic_updates": False,
            "changed_sources": [],
            "failed_sources": []
        }

        self.mock_fingerprint.return_value = "fingerprint_123"

        self.mock_current.exists.return_value = True
        self.mock_current.read_text.return_value = json.dumps({
            "version": "working_version",
            "knowledge_fingerprint": "fingerprint_123"
        })

    def test_matching_fingerprint_skips_rebuild(self):
        run_sync.main()
        self.mock_subprocess.run.assert_not_called()

    def test_different_fingerprint_triggers_rebuild(self):
        self.mock_fingerprint.return_value = "fingerprint_456"

        run_sync.main()

        self.mock_subprocess.run.assert_called_once()

    def test_missing_fingerprint_triggers_rebuild(self):
        self.mock_current.read_text.return_value = json.dumps({
            "version": "old_version"
        })

        run_sync.main()

        self.mock_subprocess.run.assert_called_once()

    def test_missing_index_triggers_rebuild(self):
        self.mock_current.exists.return_value = False

        run_sync.main()

        self.mock_subprocess.run.assert_called_once()

    def test_failed_course_sync_does_not_rebuild(self):
        self.mock_courses.return_value = {
            "academic_updates": True,
            "failed_terms": ["20271"]
        }

        with self.assertRaises(RuntimeError):
            run_sync.main()

        self.mock_subprocess.run.assert_not_called()

    def test_failed_policy_sync_does_not_rebuild(self):
        self.mock_policies.return_value = {
            "academic_updates": True,
            "changed_sources": [],
            "failed_sources": ["ois_maintaining_status"]
        }

        with self.assertRaises(RuntimeError):
            run_sync.main()

        self.mock_subprocess.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
