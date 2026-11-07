import unittest

from ingestion.connectors.usc_courses import (
    format_course_requirements
)


class TestPrerequisites(unittest.TestCase):

    def test_single_prerequisite(self):
        data = [{
            "order": 1,
            "requiredCourses": 1,
            "courseOptions": [{
                "prefix": "EE",
                "number": "450",
                "courseSpace": "EE 450",
                "ands": []
            }]
        }]

        result = format_course_requirements(data)

        self.assertEqual(result["operator"], "SINGLE")
        self.assertEqual(result["courses"], ["EE 450"])

    def test_multiple_prerequisites_not_assumed(self):
        data = [
            {
                "order": 1,
                "requiredCourses": 1,
                "courseOptions": [{
                    "courseSpace": "EE 450"
                }]
            },
            {
                "order": 1,
                "requiredCourses": 1,
                "courseOptions": [{
                    "courseSpace": "EE 503"
                }]
            }
        ]

        result = format_course_requirements(data)

        self.assertEqual(result["operator"], "UNVERIFIED")
        self.assertEqual(len(result["groups"]), 2)


if __name__ == "__main__":
    unittest.main()
