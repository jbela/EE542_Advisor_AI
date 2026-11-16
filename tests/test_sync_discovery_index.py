"""Unit tests for BGE discovery index synchronization."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag import sync_discovery_index


class TestSyncDiscoveryIndex(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.root = Path(self.temp_dir.name)
        self.index_dir = self.root / "discovery"
        self.index_dir.mkdir()

        self.current_file = self.index_dir / "current.json"

        self.fingerprint = "fingerprint_123"
        self.version = "test_version"

        version_dir = self.index_dir / "versions" / self.version
        version_dir.mkdir(parents=True)

        (version_dir / "faiss.index").write_bytes(b"test")
        (version_dir / "chunks.json").write_text(
            "[]",
            encoding="utf-8"
        )

        self.write_manifest(
            fingerprint=self.fingerprint
        )

        self.patchers = [
            patch.object(
                sync_discovery_index,
                "INDEX_DIR",
                self.index_dir
            ),
            patch.object(
                sync_discovery_index,
                "CURRENT_FILE",
                self.current_file
            ),
            patch.object(
                sync_discovery_index,
                "calculate_discovery_fingerprint",
                return_value=self.fingerprint
            ),
            patch.object(
                sync_discovery_index.subprocess,
                "run"
            )
        ]

        self.mocks = [
            patcher.start()
            for patcher in self.patchers
        ]

        for patcher in self.patchers:
            self.addCleanup(patcher.stop)

        self.mock_fingerprint = self.mocks[2]
        self.mock_run = self.mocks[3]

    def write_manifest(self, fingerprint):
        manifest = {
            "version": self.version,
            "embedding_model": sync_discovery_index.MODEL_NAME,
            "knowledge_fingerprint": fingerprint
        }

        self.current_file.write_text(
            json.dumps(manifest),
            encoding="utf-8"
        )

    def test_matching_fingerprint_skips_rebuild(self):
        result = sync_discovery_index.sync_discovery_index()

        self.assertFalse(result["rebuilt"])
        self.mock_run.assert_not_called()

    def test_changed_fingerprint_triggers_rebuild(self):
        self.mock_fingerprint.return_value = "fingerprint_456"

        def simulate_rebuild(*args, **kwargs):
            self.write_manifest("fingerprint_456")

        self.mock_run.side_effect = simulate_rebuild

        result = sync_discovery_index.sync_discovery_index()

        self.assertTrue(result["rebuilt"])
        self.mock_run.assert_called_once()

    def test_missing_index_triggers_rebuild(self):
        self.current_file.unlink()

        def simulate_rebuild(*args, **kwargs):
            self.write_manifest(self.fingerprint)

        self.mock_run.side_effect = simulate_rebuild

        result = sync_discovery_index.sync_discovery_index()

        self.assertTrue(result["rebuilt"])
        self.mock_run.assert_called_once()

    def test_failed_rebuild_preserves_active_manifest(self):
        import subprocess

        self.mock_fingerprint.return_value = "fingerprint_456"

        self.mock_run.side_effect = subprocess.CalledProcessError(
            1,
            ["python", "-m", "rag.build_discovery_index"]
        )

        original = self.current_file.read_text(
            encoding="utf-8"
        )

        with self.assertRaises(subprocess.CalledProcessError):
            sync_discovery_index.sync_discovery_index()

        self.assertEqual(
            self.current_file.read_text(encoding="utf-8"),
            original
        )


if __name__ == "__main__":
    unittest.main()
