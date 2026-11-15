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

    def test_archived_term_selection(self):
        with patch.object(backfill_history, "datetime") as mock_date:
            mock_date.now.return_value.year = 2026

            selected = backfill_history.select_archived_terms(
                self.terms, years=5
            )

        codes = [term["term_code"] for term in selected]

        self.assertEqual(codes, ["20211", "20253"])

    def test_skip_existing_semesters(self):
        (self.course_dir / "ee_20211.json").write_text(
            "{}", encoding="utf-8"
        )

        with (
            patch.object(backfill_history, "load_known_terms",
                         return_value=self.terms),
            patch.object(backfill_history, "COURSES_DIR",
                         self.course_dir),
            patch.object(backfill_history, "backfill_term") as mock_collect,
            patch.object(backfill_history, "sync_index") as mock_index,
        ):
            backfill_history.backfill_history(
                years=5, delay=0, dry_run=True
            )

        mock_collect.assert_not_called()
        mock_index.assert_not_called()

    def test_all_failed_collection_skips_index(self):
        with (
            patch.object(backfill_history, "load_known_terms",
                         return_value=self.terms),
            patch.object(backfill_history, "COURSES_DIR",
                         self.course_dir),
            patch.object(backfill_history, "backfill_term",
                         side_effect=RuntimeError("API failure")),
            patch.object(backfill_history, "sync_index") as mock_index,
            patch.object(backfill_history.time, "sleep"),
        ):
            result = backfill_history.backfill_history(
                years=5, delay=0
            )

        self.assertEqual(result["status"], "partial_failure")
        mock_index.assert_not_called()

    
    def test_successful_batch_indexes_once(self):
        with (
            patch.object(
                backfill_history,
                "load_known_terms",
                return_value=self.terms
            ),
            patch.object(
                backfill_history,
                "COURSES_DIR",
                self.course_dir
            ),
            patch.object(
                backfill_history,
                "backfill_term",
                return_value={"status": "collected"}
            ) as mock_collect,
            patch.object(
                backfill_history,
                "sync_index",
                return_value={
                    "rebuilt": True,
                    "version": "test_index_version",
                    "knowledge_fingerprint": "test_fingerprint"
                }
            ) as mock_index,
            patch.object(
                backfill_history.time,
                "sleep"
            ),
        ):
            result = backfill_history.backfill_history(
                years=5,
                delay=0
            )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["collected_terms"], 2)
        self.assertEqual(mock_collect.call_count, 2)
        mock_index.assert_called_once_with()

        self.assertTrue(result["index"]["rebuilt"])
        self.assertEqual(
            result["index"]["version"],
            "test_index_version"
        )

if __name__ == "__main__":
    unittest.main()
