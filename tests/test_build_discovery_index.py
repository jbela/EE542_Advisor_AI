"""Tests for BGE discovery document construction."""

import json
import tempfile
import unittest
from pathlib import Path

from rag.build_discovery_index import load_discovery_documents


class TestBuildDiscoveryIndex(unittest.TestCase):

    def test_course_specific_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ee_20271.json"

            data = {
                "term_code": "20271",
                "source_url": (
                    "https://classes.usc.edu/term/20271/"
                    "catalogue/school/ENGV/program/EE"
                ),
                "courses": [
                    {
                        "course_id": 100,
                        "course_code": "EE 547",
                        "title": "Cloud Computing",
                        "description": "Cloud applications and deployment.",
                    },
                    {
                        "course_id": 101,
                        "course_code": "EE 562",
                        "title": "Random Processes",
                        "description": "Stochastic processes.",
                        "source_url": (
                            "https://classes.usc.edu/term/20271/"
                            "course/EE562"
                        ),
                    },
                ],
            }

            path.write_text(
                json.dumps(data),
                encoding="utf-8",
            )

            documents = load_discovery_documents(directory)

        self.assertEqual(len(documents), 2)

        by_code = {
            doc["course_code"]: doc
            for doc in documents
        }

        self.assertEqual(
            by_code["EE 547"]["url"],
            "https://classes.usc.edu/term/20271/course/EE547",
        )

        self.assertEqual(
            by_code["EE 562"]["url"],
            "https://classes.usc.edu/term/20271/course/EE562",
        )

        self.assertEqual(
            by_code["EE 547"]["source_type"],
            "catalog",
        )

        self.assertEqual(
            by_code["EE 562"]["term_code"],
            "20271",
        )


if __name__ == "__main__":
    unittest.main()
