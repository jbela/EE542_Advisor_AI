import unittest
from unittest.mock import patch

from ingestion import run_sync


class TestReindexTrigger(unittest.TestCase):

    def setUp(self):
        self.patchers = [
            patch.object(run_sync, "discover_terms"),
            patch.object(run_sync, "sync_courses"),
            patch.object(run_sync, "sync_policies"),
            patch.object(run_sync, "sync_index"),
        ]

        mocks = [p.start() for p in self.patchers]

        for patcher in self.patchers:
            self.addCleanup(patcher.stop)

        (
            self.mock_discover,
            self.mock_courses,
            self.mock_policies,
            self.mock_index,
        ) = mocks

        self.mock_courses.return_value = {
            "academic_updates": False,
            "failed_terms": [],
        }

        self.mock_policies.return_value = {
            "academic_updates": False,
            "changed_sources": [],
            "failed_sources": [],
        }

        self.mock_index.return_value = {
            "rebuilt": False,
            "knowledge_fingerprint": "fingerprint_123",
        }

    def test_successful_sync_checks_index(self):
        result = run_sync.main()

        self.mock_index.assert_called_once_with()
        self.assertFalse(result["index_result"]["rebuilt"])

    def test_academic_changes_check_index(self):
        self.mock_courses.return_value["academic_updates"] = True

        run_sync.main()

        self.mock_index.assert_called_once_with()

    def test_failed_course_sync_does_not_rebuild(self):
        self.mock_courses.return_value["failed_terms"] = ["20271"]

        with self.assertRaises(RuntimeError):
            run_sync.main()

        self.mock_index.assert_not_called()

    def test_failed_policy_sync_does_not_rebuild(self):
        self.mock_policies.return_value["failed_sources"] = [
            "ois_maintaining_status"
        ]

        with self.assertRaises(RuntimeError):
            run_sync.main()

        self.mock_index.assert_not_called()


if __name__ == "__main__":
    unittest.main()
