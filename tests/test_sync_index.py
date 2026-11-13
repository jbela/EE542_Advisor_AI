import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag import sync_index


class TestSyncIndex(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.index_dir = Path(self.temp_dir.name)
        self.current_file = self.index_dir / "current.json"

        self.patchers = [
            patch.object(sync_index, "CURRENT_FILE", self.current_file),
            patch.object(sync_index, "calculate_fingerprint"),
            patch.object(sync_index.subprocess, "run"),
        ]

        mocks = [p.start() for p in self.patchers]

        for patcher in self.patchers:
            self.addCleanup(patcher.stop)

        (
            self.mock_current,
            self.mock_fingerprint,
            self.mock_run,
        ) = mocks

        self.mock_fingerprint.return_value = "fingerprint_123"

        self.current_file.write_text(
            json.dumps({
                "version": "existing_version",
                "knowledge_fingerprint": "fingerprint_123",
            }),
            encoding="utf-8",
        )

    def test_matching_fingerprint_skips_rebuild(self):
        result = sync_index.sync_index()

        self.assertFalse(result["rebuilt"])
        self.mock_run.assert_not_called()

    def test_different_fingerprint_triggers_rebuild(self):
        self.mock_fingerprint.return_value = "fingerprint_456"

        def publish(*args, **kwargs):
            self.current_file.write_text(
                json.dumps({
                    "version": "new_version",
                    "knowledge_fingerprint": "fingerprint_456",
                }),
                encoding="utf-8",
            )

        self.mock_run.side_effect = publish

        result = sync_index.sync_index()

        self.mock_run.assert_called_once()
        self.assertTrue(result["rebuilt"])
        self.assertEqual(result["version"], "new_version")

    def test_missing_fingerprint_triggers_rebuild(self):
        self.current_file.write_text(
            json.dumps({"version": "old_version"}),
            encoding="utf-8",
        )

        def publish(*args, **kwargs):
            self.current_file.write_text(
                json.dumps({
                    "version": "new_version",
                    "knowledge_fingerprint": "fingerprint_123",
                }),
                encoding="utf-8",
            )

        self.mock_run.side_effect = publish

        result = sync_index.sync_index()

        self.assertTrue(result["rebuilt"])
        self.mock_run.assert_called_once()

    def test_missing_index_triggers_rebuild(self):
        self.current_file.unlink()

        def publish(*args, **kwargs):
            self.current_file.write_text(
                json.dumps({
                    "version": "new_version",
                    "knowledge_fingerprint": "fingerprint_123",
                }),
                encoding="utf-8",
            )

        self.mock_run.side_effect = publish

        result = sync_index.sync_index()

        self.assertTrue(result["rebuilt"])
        self.mock_run.assert_called_once()

    def test_failed_rebuild_does_not_publish(self):
        self.mock_fingerprint.return_value = "fingerprint_456"

        self.mock_run.side_effect = RuntimeError("Index build failed")

        with self.assertRaises(RuntimeError):
            sync_index.sync_index()

        manifest = json.loads(
            self.current_file.read_text(encoding="utf-8")
        )

        self.assertEqual(
            manifest["version"],
            "existing_version",
        )


if __name__ == "__main__":
    unittest.main()
