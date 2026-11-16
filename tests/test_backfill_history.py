"""Tests for automated historical semester backfilling."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ingestion import backfill_history


class TestBackfillHistory(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.course_dir = Path(self.temp_dir.name)

        self.terms = {
            "20211": {
                "term_code": "20211",
                "name": "Spring 2021",
                "year": 2021,
                "status": "Archived",
            },
            "20253": {
                "term_code": "20253",
                "name": "Fall 2025",
                "year": 2025,
                "status": "Archived",
            },
            "20271": {
                "term_code": "20271",
                "name": "Spring 2027",
                "year": 2027,
                "status": "Active",
            },
        }

        self.patchers = [
            patch.object(
                backfill_history,
                "load_known_terms",
                return_value=self.terms,
            ),
            patch.object(
                backfill_history,
                "COURSES_DIR",
                self.course_dir,
            ),
            patch.object(
                backfill_history,
                "sync_index",
                return_value={
                    "rebuilt": True,
                    "version": "test_minilm_version",
                    "knowledge_fingerprint": "minilm_fingerprint",
                },
            ),
            patch.object(
                backfill_history,
                "sync_discovery_index",
                return_value={
                    "rebuilt": True,
                    "version": "test_bge_version",
                    "knowledge_fingerprint": "bge_fingerprint",
                },
            ),
            patch.object(
                backfill_history.time,
                "sleep",
            ),
        ]

        mocks = [patcher.start() for patcher in self.patchers]

        for patcher in self.patchers:
            self.addCleanup(patcher.stop)

        (
            self.mock_terms,
            self.mock_courses_dir,
            self.mock_index,
            self.mock_discovery,
            self.mock_sleep,
        ) = mocks

    def test_archived_term_selection(self):
        with patch.object(backfill_history, "datetime") as mock_date:
            mock_date.now.return_value.year = 2026

            selected = backfill_history.select_archived_terms(
                self.terms,
                years=5,
            )

        codes = [term["term_code"] for term in selected]

        self.assertEqual(codes, ["20211", "20253"])

    def test_skip_existing_semesters(self):
        (self.course_dir / "ee_20211.json").write_text(
            "{}",
            encoding="utf-8",
        )

        with patch.object(
            backfill_history,
            "backfill_term",
        ) as mock_collect:

            result = backfill_history.backfill_history(
                years=5,
                delay=0,
                dry_run=True,
            )

        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["missing_terms"], ["20253"])

        mock_collect.assert_not_called()
        self.mock_index.assert_not_called()
        self.mock_discovery.assert_not_called()

    def test_all_failed_collection_skips_indexes(self):
        with patch.object(
            backfill_history,
            "backfill_term",
            side_effect=RuntimeError("API failure"),
        ):
            result = backfill_history.backfill_history(
                years=5,
                delay=0,
            )

        self.assertEqual(result["status"], "partial_failure")
        self.assertEqual(result["collected_terms"], 0)
        self.assertEqual(len(result["failed_terms"]), 2)

        self.mock_index.assert_not_called()
        self.mock_discovery.assert_not_called()

        self.assertIsNone(result["index"])
        self.assertIsNone(result["discovery_index"])

    def test_successful_batch_indexes_once(self):
        with patch.object(
            backfill_history,
            "backfill_term",
            return_value={"status": "collected"},
        ) as mock_collect:

            result = backfill_history.backfill_history(
                years=5,
                delay=0,
            )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["collected_terms"], 2)
        self.assertEqual(mock_collect.call_count, 2)

        self.mock_index.assert_called_once_with()
        self.mock_discovery.assert_called_once_with()

        self.assertTrue(result["index"]["rebuilt"])
        self.assertTrue(result["discovery_index"]["rebuilt"])

        self.assertEqual(
            result["index"]["version"],
            "test_minilm_version",
        )
        self.assertEqual(
            result["discovery_index"]["version"],
            "test_bge_version",
        )

    def test_partial_failure_updates_both_indexes(self):
        def collect_term(code):
            if code == "20211":
                return {"status": "collected"}

            raise RuntimeError("API failure")

        with patch.object(
            backfill_history,
            "backfill_term",
            side_effect=collect_term,
        ):
            result = backfill_history.backfill_history(
                years=5,
                delay=0,
            )

        self.assertEqual(result["status"], "partial_failure")
        self.assertEqual(result["collected_terms"], 1)
        self.assertEqual(len(result["failed_terms"]), 1)

        self.mock_index.assert_called_once_with()
        self.mock_discovery.assert_called_once_with()

        self.assertIsNotNone(result["index"])
        self.assertIsNotNone(result["discovery_index"])

    def test_discovery_failure_is_reported(self):
        self.mock_discovery.side_effect = RuntimeError(
            "BGE synchronization failed"
        )

        with patch.object(
            backfill_history,
            "backfill_term",
            return_value={"status": "collected"},
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "BGE synchronization failed",
            ):
                backfill_history.backfill_history(
                    years=5,
                    delay=0,
                )

        self.mock_index.assert_called_once_with()
        self.mock_discovery.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
