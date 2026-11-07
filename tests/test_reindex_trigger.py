import unittest
from unittest.mock import patch

from ingestion import run_sync


class TestReindexTrigger(unittest.TestCase):

    @patch.object(run_sync, "subprocess")
    @patch.object(run_sync, "sync_courses")
    @patch.object(run_sync, "discover_terms")
    @patch.object(run_sync, "CURRENT_FILE")
    def test_rebuild_when_academic_changes(
        self, mock_current, mock_discover, 
        mock_sync, mock_subprocess
    ):
        mock_current.exists.return_value = True

        mock_sync.return_value = {
            "academic_updates": True,
            "failed_terms": []
        }

        run_sync.main()

        mock_subprocess.run.assert_called_once()

    @patch.object(run_sync, "subprocess")
    @patch.object(run_sync, "sync_courses")
    @patch.object(run_sync, "discover_terms")
    @patch.object(run_sync, "CURRENT_FILE")
    def test_skip_when_only_operational_changes(
        self, mock_current,
        mock_discover, mock_sync, mock_subprocess
    ):
        mock_current.exists.return_value = True

        mock_sync.return_value = {
            "academic_updates": False,
            "failed_terms": []
        }

        run_sync.main()

        mock_subprocess.run.assert_not_called()

    @patch.object(run_sync, "subprocess")
    @patch.object(run_sync, "sync_courses")
    @patch.object(run_sync, "discover_terms")
    def test_failed_sync_does_not_rebuild(
        self, mock_discover, mock_sync, mock_subprocess
    ):
        mock_sync.return_value = {
            "academic_updates": True,
            "failed_terms": ["20271"]
        }

        with self.assertRaises(RuntimeError):
            run_sync.main()

        mock_subprocess.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
