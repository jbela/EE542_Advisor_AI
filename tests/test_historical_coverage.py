import unittest
from unittest.mock import patch

from rag import advisor_retrieval


class TestHistoricalCoverage(unittest.TestCase):

    @patch.object(advisor_retrieval, "get_term_collection_status")
    def test_missing_historical_catalog(self, mock_status):
        mock_status.return_value = {
            "term_code": "20253",
            "status": "term_not_collected",
            "course_count": None
        }

        results = advisor_retrieval.retrieve_for_advisor(
            "What courses were offered in Fall 2025?",
            term_code="20253"
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["retrieval_method"],
            "historical_catalog"
        )
        self.assertEqual(
            results[0]["status"],
            "term_not_collected"
        )
        self.assertIsNone(results[0]["course_count"])


if __name__ == "__main__":
    unittest.main()
