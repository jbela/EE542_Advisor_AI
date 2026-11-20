import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ingestion import verified_requirements


class TestVerifiedRequirements(unittest.TestCase):

    def test_verified_and_relationship(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)

            data = {
                "term_code": "20271",
                "courses": {
                    "EE 597": {
                        "prerequisites_display": {
                            "operator": "AND",
                            "courses": ["EE 450", "EE 503"]
                        },
                        "verification_status": "verified",
                        "verification_source": "official_course_listing",
                        "source_url": "https://classes.usc.edu/term/20271/course/EE597",
                        "source_text": "Prerequisites: EE 450 and EE 503"
                    }
                }
            }

            (directory / "ee_20271.json").write_text(
                json.dumps(data),
                encoding="utf-8"
            )

            with patch.object(
                verified_requirements,
                "VERIFIED_DIR",
                directory
            ):
                course = {
                    "course_code": "EE 597",
                    "prerequisites_display": {
                        "operator": "UNVERIFIED",
                        "groups": []
                    }
                }

                result = verified_requirements.apply_verified_requirements(
                    course, "20271"
                )

                self.assertEqual(
                    result["prerequisites_display"]["operator"],
                    "AND"
                )

                self.assertEqual(
                    result["prerequisites_display"]["courses"],
                    ["EE 450", "EE 503"]
                )

                self.assertEqual(
                    result["prerequisite_verification"]["status"],
                    "verified"
                )

    def test_other_semester_not_overridden(self):
        course = {
            "course_code": "EE 597",
            "prerequisites_display": {
                "operator": "UNVERIFIED",
                "groups": []
            }
        }

        with tempfile.TemporaryDirectory() as temp:
            with patch.object(
                verified_requirements,
                "VERIFIED_DIR",
                Path(temp)
            ):
                result = verified_requirements.apply_verified_requirements(
                    course, "20263"
                )

        self.assertEqual(
            result["prerequisites_display"]["operator"],
            "UNVERIFIED"
        )


    def _course_fixture(self, directory):
        """Use a minimal collected snapshot; Git excludes generated datasets."""
        records = {
            "term_code": "20271",
            "courses": [
                {"course_code": "EE 562", "title": "Random Processes in Engineering", "prerequisites_display": None},
                {"course_code": "EE 597", "title": "Wireless Networks", "prerequisites_display": None},
            ],
        }
        (directory / "ee_20271.json").write_text(json.dumps(records), encoding="utf-8")

    def test_ee562_nested_prerequisites(self):
        from rag import course_lookup

        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self._course_fixture(directory)
            with patch.object(course_lookup, "COURSES_DIR", directory):
                course = course_lookup.lookup_course("EE 562", "20271")

        self.assertIsNotNone(course)
        requirements = course["prerequisites_display"]
        self.assertEqual(requirements["operator"], "AND")
        self.assertEqual(len(requirements["groups"]), 2)
        self.assertEqual(requirements["groups"][0], {
            "operator": "SINGLE", "courses": ["EE 503"]
        })
        self.assertEqual(requirements["groups"][1], {
            "operator": "OR", "courses": ["EE 441", "EE 510"], "required_courses": 1
        })
        self.assertEqual(course["prerequisite_verification"]["status"], "verified")

    def test_ee562_verification_does_not_change_ee597(self):
        from rag import course_lookup

        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self._course_fixture(directory)
            with patch.object(course_lookup, "COURSES_DIR", directory):
                course = course_lookup.lookup_course("EE 597", "20271")

        self.assertIsNotNone(course)
        self.assertEqual(course["prerequisites_display"], {
            "operator": "AND", "courses": ["EE 450", "EE 503"]
        })


if __name__ == "__main__":
    unittest.main()
