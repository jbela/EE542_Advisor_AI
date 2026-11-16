"""Unit tests for BGE semantic course discovery."""

import unittest
from unittest.mock import patch, MagicMock

import numpy as np

from rag import discovery_retrieve


class TestDiscoveryRetrieval(unittest.TestCase):

    def setUp(self):
        self.documents = [
            {
                "document_id": "course_20271_1",
                "chunk_id": "course_20271_1",
                "course_code": "EE 250",
                "title": "EE 250 - Distributed Systems",
                "term_code": "20271",
                "category": "course",
                "url": "https://classes.usc.edu/term/20271/course/EE250",
                "text": "Distributed systems and networking",
            },
            {
                "document_id": "course_20253_2",
                "chunk_id": "course_20253_2",
                "course_code": "EE 250",
                "title": "EE 250 - Distributed Systems",
                "term_code": "20253",
                "category": "course",
                "url": "https://classes.usc.edu/term/20253/course/EE250",
                "text": "Distributed systems and networking",
            },
            {
                "document_id": "course_20271_3",
                "chunk_id": "course_20271_3",
                "course_code": "EE 547",
                "title": "EE 547 - Cloud Computing",
                "term_code": "20271",
                "category": "course",
                "url": "https://classes.usc.edu/term/20271/course/EE547",
                "text": "Cloud platforms and deployment",
            },
        ]

        self.manifest = {
            "version": "test_version",
            "embedding_model": discovery_retrieve.MODEL_NAME,
            "knowledge_fingerprint": "test_fingerprint",
        }

        self.patchers = [
            patch.object(
                discovery_retrieve,
                "load_manifest",
                return_value=self.manifest,
            ),
            patch.object(
                discovery_retrieve,
                "calculate_discovery_fingerprint",
                return_value="test_fingerprint",
            ),
            patch.object(discovery_retrieve, "load_index"),
            patch.object(discovery_retrieve, "load_model"),
        ]

        mocks = [p.start() for p in self.patchers]

        for patcher in self.patchers:
            self.addCleanup(patcher.stop)

        (
            self.mock_manifest,
            self.mock_fingerprint,
            self.mock_index,
            self.mock_model,
        ) = mocks

        fake_index = MagicMock()
        fake_index.ntotal = len(self.documents)
        fake_index.search.return_value = (
            np.array([[0.9, 0.8, 0.7]], dtype=np.float32),
            np.array([[0, 1, 2]], dtype=np.int64),
        )

        self.mock_index.return_value = (
            fake_index,
            self.documents,
        )

        fake_model = MagicMock()
        fake_model.encode.return_value = np.zeros(
            (1, 768),
            dtype=np.float32,
        )

        self.mock_model.return_value = fake_model

    def test_semester_isolation(self):
        results = discovery_retrieve.retrieve_discovery(
            "distributed systems",
            term_code="20271",
            top_k=5,
        )

        self.assertTrue(results)

        self.assertTrue(
            all(r["term_code"] == "20271" for r in results)
        )

    def test_preserves_metadata(self):
        results = discovery_retrieve.retrieve_discovery(
            "distributed systems",
            term_code="20271",
            top_k=5,
        )

        first = results[0]

        for field in [
            "course_code",
            "term_code",
            "title",
            "url",
            "document_id",
            "category",
        ]:
            self.assertIn(field, first)

        self.assertEqual(
            first["retrieval_method"],
            "semantic_bge",
        )

    def test_stale_index_rejected(self):
        self.mock_fingerprint.return_value = "changed_fingerprint"

        with self.assertRaises(RuntimeError):
            discovery_retrieve.retrieve_discovery(
                "distributed systems",
                term_code="20271",
            )

        self.mock_model.assert_not_called()

    def test_empty_top_k(self):
        results = discovery_retrieve.retrieve_discovery(
            "distributed systems",
            top_k=0,
        )

        self.assertEqual(results, [])
        self.mock_model.assert_not_called()


    def test_course_specific_source_url(self):
        results = discovery_retrieve.retrieve_discovery(
            "distributed systems",
            term_code="20271",
            top_k=5,
        )

        self.assertTrue(results)

        for result in results:
            code = result["course_code"].replace(" ", "")
            term = result["term_code"]

            self.assertEqual(
                result["url"],
                f"https://classes.usc.edu/term/{term}/course/{code}",
            )

if __name__ == "__main__":
    unittest.main()
