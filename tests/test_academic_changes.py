import copy
import unittest

from ingestion.collect_courses import (
    calculate_academic_hash,
    calculate_operational_hash
)


class TestAcademicChanges(unittest.TestCase):

    def setUp(self):
        self.courses = [
            {
                "course_id": 12345,
                "course_code": "EE 999",
                "title": "Test Course",
                "description": "Original description",
                "units": [4],
                "prerequisites": None,
                "corequisites": None,
                "sections": [
                    {
                        "section_id": "30001",
                        "registered_seats": 20,
                        "total_seats": 40
                    }
                ]
            }
        ]

    def test_academic_change(self):
        updated = copy.deepcopy(self.courses)
        updated[0]["description"] = "Updated description"

        self.assertNotEqual(
            calculate_academic_hash(self.courses),
            calculate_academic_hash(updated)
        )

    def test_operational_change(self):
        updated = copy.deepcopy(self.courses)
        updated[0]["sections"][0]["registered_seats"] = 21

        self.assertEqual(
            calculate_academic_hash(self.courses),
            calculate_academic_hash(updated)
        )

        self.assertNotEqual(
            calculate_operational_hash(self.courses),
            calculate_operational_hash(updated)
        )


if __name__ == "__main__":
    unittest.main()
