import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import faiss

from rag.index_publisher import publish_index


class TestIndexRollback(unittest.TestCase):

    def test_failed_write_preserves_active_version(self):
        with tempfile.TemporaryDirectory() as temp:
            index_dir = Path(temp)

            # Create a valid working index.
            index = faiss.IndexFlatIP(384)

            original = publish_index(
                index=index,
                documents=[],
                model_name="test-model",
                index_dir=index_dir
            )

            current_file = index_dir / "current.json"

            # Inject a failure during the next index write.
            with patch(
                "rag.index_publisher.faiss.write_index",
                side_effect=OSError("Simulated disk failure")
            ):
                with self.assertRaises(OSError):
                    publish_index(
                        index=index,
                        documents=[],
                        model_name="test-model",
                        index_dir=index_dir
                    )

            # Verify that the previous manifest is unchanged.
            current = json.loads(
                current_file.read_text(encoding="utf-8")
            )

            self.assertEqual(
                current["version"],
                original["version"]
            )

            # Verify the previous FAISS index is readable.
            old_index = (
                index_dir / "versions"
                / original["version"] / "faiss.index"
            )

            restored = faiss.read_index(str(old_index))

            self.assertEqual(restored.ntotal, 0)
            self.assertEqual(restored.d, 384)


if __name__ == "__main__":
    unittest.main()
