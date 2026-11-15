import unittest
from unittest.mock import patch

from rag import build_index


class TestIndexConsistency(unittest.TestCase):

    @patch.object(build_index, "publish_index")
    @patch.object(build_index, "calculate_fingerprint")
    @patch.object(build_index, "SentenceTransformer")
    @patch.object(build_index, "load_course_documents")
    @patch.object(build_index, "load_policy_documents")
    def test_source_change_prevents_publication(
        self,
        mock_policies,
        mock_courses,
        mock_model,
        mock_fingerprint,
        mock_publish
    ):
        import numpy as np

        mock_policies.return_value = [{
            "chunk_id": "test_1",
            "document_id": "test",
            "text": "Example academic information",
            "title": "Test",
            "url": "https://example.edu",
            "category": "shared"
        }]

        mock_courses.return_value = []

        mock_model.return_value.encode.return_value = (
            np.ones((1, 384), dtype=np.float32)
        )

        # Simulate a change during indexing.
        mock_fingerprint.side_effect = [
            "original_fingerprint",
            "changed_fingerprint"
        ]

        with patch.object(
            build_index,
            "load_syllabus_documents",
            return_value=[],
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Academic source data changed"
            ):
                build_index.main()

        # No new index should be published.
        mock_publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
