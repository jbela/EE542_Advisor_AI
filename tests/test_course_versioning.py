import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ingestion import collect_courses


class TestCourseVersioning(unittest.TestCase):

    def test_versioning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            courses_dir = root / "courses"
            courses_dir.mkdir()

            versions_dir = root / "data" / "versions" / "courses"

            original = {
                "termCode": 20993,
                "schoolPrefix": "ENGV",
                "programPrefix": "EE",
                "courses": [
                    {
                        "courseId": 12345,
                        "fullCourseName": "EE 999",
                        "name": "Test Course",
                        "description": "Original description",
                        "courseUnits": [4],
                        "sections": []
                    }
                ]
            }

            changed = json.loads(json.dumps(original))
            changed["courses"][0]["description"] = (
                "Updated description"
            )

            with patch.object(
                collect_courses, "ROOT", root
            ), patch.object(
                collect_courses, "COURSES_DIR", courses_dir
            ):
                collect_courses.save_course_data(original)

                file_path = courses_dir / "ee_20993.json"
                self.assertTrue(file_path.exists())

                collect_courses.save_course_data(original)
                self.assertFalse(versions_dir.exists())

                collect_courses.save_course_data(changed)

                backups = list(versions_dir.glob("*.json"))
                self.assertEqual(len(backups), 1)

                old_data = json.loads(
                    backups[0].read_text(encoding="utf-8")
                )

                new_data = json.loads(
                    file_path.read_text(encoding="utf-8")
                )

                self.assertEqual(
                    old_data["courses"][0]["description"],
                    "Original description"
                )

                self.assertEqual(
                    new_data["courses"][0]["description"],
                    "Updated description"
                )


if __name__ == "__main__":
    unittest.main()
