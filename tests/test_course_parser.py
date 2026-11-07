import unittest

from ingestion.connectors.usc_courses import normalize_response


class TestCourseParser(unittest.TestCase):

    def test_normalize_course(self):
        sample = {
            "termCode": 20263,
            "courses": [
                {
                    "courseId": 12345,
                    "fullCourseName": "EE 450",
                    "name": "Example Course",
                    "description": "Example description",
                    "courseUnits": [4],
                    "prerequisiteCourseCodes": None,
                    "corequisiteCourseCodes": None,
                    "sections": [
                        {
                            "sisSectionId": "30500",
                            "rnrMode": "Lecture",
                            "registeredSeats": 55,
                            "totalSeats": 100
                        }
                    ]
                }
            ]
        }

        result = normalize_response(sample)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["course_code"], "EE 450")
        self.assertEqual(result[0]["term_code"], "20263")
        self.assertEqual(
            result[0]["sections"][0]["registered_seats"],
            55
        )


if __name__ == "__main__":
    unittest.main()