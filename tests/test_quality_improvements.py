"""Focused tests without Ollama or live indexes.
Run: python -m unittest tests.test_quality_improvements -v
"""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.quality_improvements import (
    catalog_availability_answer, clearance_evidence_answer,
    course_discovery_answer, citation_problems,
)
from backend.answer_quality import check_citations, citation_coverage, course_citation_issues


def doc(code='EE 547', title='Applied and Cloud Computing', desc='Cloud applications, APIs, databases, and scalability.', idx=1):
    return {'id': str(idx), 'title': f'{code} - {title}',
            'course_code': code, 'text': f'Course: {code}\nDescription: {desc}',
            'retrieval_method': 'semantic_bge', 'term_code': '20271',
            'url': f'https://classes.usc.edu/term/20271/course/{code.replace(" ", "")}',
            'category': 'course'}


class QualityHelpers(unittest.TestCase):
    def test_course_recommendations_filter_irrelevant_candidates(self):
        docs = [doc(), doc('EE 541', 'Deep Learning', 'Neural networks and optimization.', 2)]
        answer = course_discovery_answer("I'm interested in cloud computing. Which classes explore it?", docs)
        self.assertIn('EE 547', answer)
        self.assertNotIn('EE 541', answer)
        self.assertIn('[1]', answer)
        self.assertIn('Cloud applications', answer)

    def test_discovery_lists_prerequisites_when_asked(self):
        verified = dict(doc(), catalog_record={
            'term_code': '20271',
            'prerequisites': {'operator': 'SINGLE', 'courses': ['EE 538']}})
        unverified = dict(doc('EE 512', 'Cloud Signal Methods', 'Cloud computing for signals.', 2),
                          catalog_record={'term_code': '20271', 'prerequisites': {
                              'operator': 'UNVERIFIED', 'groups': [
                                  {'operator': 'SINGLE', 'courses': ['EE 503']},
                                  {'operator': 'UNVERIFIED', 'courses': ['EE 441', 'EE 510']}]}})
        missing = dict(doc('EE 541', 'Cloud Deep Learning', 'Cloud computing with GPUs.', 3),
                       catalog_record={'term_code': '20271', 'prerequisites': None})
        answer = course_discovery_answer(
            'What cloud computing courses are there and what are their prerequisites?',
            [verified, unverified, missing])
        self.assertIn('Spring 2027 listing): EE 538* [1]', answer)
        self.assertIn('EE 503, EE 441, EE 510; the exact AND/OR logic is not verified', answer)
        self.assertIn('does not mean none are required', answer)

    def test_discovery_omits_prerequisites_when_not_asked(self):
        d = dict(doc(), catalog_record={'term_code': '20271', 'prerequisites': None})
        answer = course_discovery_answer('Which classes cover cloud computing?', [d])
        self.assertNotIn('prerequisites', answer.lower())

    def test_syllabus_page_without_url_is_citable(self):
        syllabus = {'source_type': 'syllabus', 'document_id': 'syllabus_ee510_20263_unspecified',
                    'page_number': 2, 'url': None, 'retrieval_method': 'hybrid'}
        no_page = dict(syllabus, page_number=None)
        cleaned, invalid = check_citations('Not listed [1]. Other [2].', [syllabus, no_page])
        self.assertIn('[1]', cleaned)
        self.assertEqual(invalid, [2])
        self.assertFalse(citation_coverage('Not listed [1].', [syllabus], required=True)['missing_citations'])

    def test_no_relevant_discovery_returns_none(self):
        self.assertIsNone(course_discovery_answer('Which courses teach robotics?', [doc()]))

    def test_course_list_uses_actual_description(self):
        answer = course_discovery_answer('Which EE courses cover machine learning?', [
            doc('EE 559', 'Machine Learning I', 'Machine learning methods and classification.')])
        self.assertIn('classification', answer)
        self.assertNotIn('guarantee', answer.lower().split('these are exploratory')[0])

    def test_listed_availability(self):
        d = {'retrieval_method': 'availability', 'course_code': 'EE 542',
             'requested_term': '20271', 'availability_status': 'listed',
             'requested_term_checked': True, 'url': 'https://example.edu/course'}
        answer = catalog_availability_answer([d])
        self.assertIn('Spring 2027', answer)
        self.assertIn('appears', answer)
        self.assertIn('[1]', answer)
        self.assertIn('does not confirm open seats', answer)

    def test_not_listed_availability_is_not_absolute(self):
        d = {'retrieval_method': 'availability', 'course_code': 'EE 542',
             'requested_term': '20271', 'availability_status': 'not_listed',
             'requested_term_checked': True, 'url': 'https://example.edu'}
        answer = catalog_availability_answer([d])
        self.assertIn('not found in the collected', answer)
        self.assertNotIn('will not be offered', answer)

    def test_term_uncollected_is_unknown(self):
        d = {'retrieval_method': 'availability', 'course_code': 'EE 542',
             'requested_term': '20271', 'availability_status': 'term_not_collected',
             'requested_term_checked': False, 'url': None}
        answer = catalog_availability_answer([d])
        self.assertIn('have not been collected', answer)
        self.assertNotIn('[1]', answer)

    def test_clearance_quotes_actual_evidence_only(self):
        docs = [{'url': 'https://example.edu/policy', 'title': 'ECE instructions',
                 'text': 'D-clearance requests for ECE graduate courses are handled by the department.',
                 'retrieval_method': 'hybrid'}]
        answer = clearance_evidence_answer("What is USC's D-Clearance policy?", docs)
        self.assertIn('handled by the department', answer)
        self.assertIn('[1]', answer)
        self.assertNotIn('placement', answer)
        self.assertNotIn('prerequisites', answer)

    def test_clearance_without_evidence_does_not_invent(self):
        docs = [{'url': 'https://example.edu/policy', 'title': 'Unrelated',
                 'text': 'Course registration is online.', 'retrieval_method': 'hybrid'}]
        answer = clearance_evidence_answer('How do I get D-Clearance?', docs)
        self.assertIn('could not verify', answer)
        self.assertNotIn('[1]', answer)

    def test_invalid_citation_never_counts_as_success(self):
        docs = [{'url': 'https://example.edu', 'retrieval_method': 'hybrid'}]
        clean, invalid, coverage, issues = citation_problems(
            'Unverified [9]', docs, True,
            check_citations, citation_coverage, course_citation_issues)
        self.assertEqual(invalid, [9])
        self.assertTrue(coverage['missing_citations'])


class QualityAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_discovery_skips_llm_and_filters_irrelevance(self):
        with patch('backend.main.get_context', return_value=[
            doc(), doc('EE 541', 'Deep Learning', 'Neural networks only.', 2)
        ]), patch('backend.main.httpx.AsyncClient') as llm:
            response = self.client.post('/ask', json={'question': 'Which classes explore cloud computing?'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('EE 547', response.json()['answer'])
        self.assertNotIn('EE 541', response.json()['answer'])
        llm.assert_not_called()

    def test_availability_skips_llm(self):
        docs = [{'id': 'a', 'title': 'EE 542', 'text': 'Not listed',
                 'url': 'https://example.edu', 'category': 'course',
                 'retrieval_method': 'availability', 'course_code': 'EE 542',
                 'requested_term': '20271', 'availability_status': 'not_listed',
                 'requested_term_checked': True}]
        with patch('backend.main.get_context', return_value=docs), \
             patch('backend.main.httpx.AsyncClient') as llm:
            res = self.client.post('/ask', json={'question': 'Is EE 542 offered in Spring 2027?'})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIn('not found', res.json()['answer'])
        llm.assert_not_called()

    def test_retry_repairs_missing_policy_citation(self):
        class FakeResponse:
            def __init__(self, content): self.content = content
            def raise_for_status(self): pass
            def json(self): return {'message': {'content': self.content}}
        class FakeClient:
            calls = 0
            def __init__(self, *args, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def post(self, *args, **kwargs):
                FakeClient.calls += 1
                return FakeResponse('The documented process is explained.' if FakeClient.calls == 1
                                    else 'The documented process is explained [1].')
        FakeClient.calls = 0
        docs = [{'id': 'p1', 'title': 'USC procedure',
                 'text': 'The documented process is explained.',
                 'url': 'https://example.edu', 'category': 'policy',
                 'retrieval_method': 'hybrid'}]
        with patch('backend.main.get_context', return_value=docs), \
             patch('backend.main.httpx.AsyncClient', FakeClient):
            res = self.client.post('/ask', json={'question': 'Explain USC registration procedure.'})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(FakeClient.calls, 2)
        self.assertIn('[1]', res.json()['answer'])
        self.assertFalse(res.json()['missing_citations'])

    def test_failed_retry_falls_back_to_quoted_source(self):
        class FakeResponse:
            def raise_for_status(self): pass
            def json(self): return {'message': {'content': 'Unsupported answer.'}}
        class FakeClient:
            calls = 0
            def __init__(self, *args, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def post(self, *args, **kwargs):
                FakeClient.calls += 1
                return FakeResponse()
        FakeClient.calls = 0
        docs = [{'id': 'p1', 'title': 'Policy', 'text': 'The department provides a documented registration procedure for enrolled students.',
                 'url': 'https://example.edu', 'category': 'policy', 'retrieval_method': 'hybrid'}]
        with patch('backend.main.get_context', return_value=docs), \
             patch('backend.main.httpx.AsyncClient', FakeClient):
            res = self.client.post('/ask', json={'question': 'What is the registration procedure?'})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(FakeClient.calls, 2)
        self.assertIn('documented registration procedure', res.json()['answer'])
        self.assertIn('[1]', res.json()['answer'])


if __name__ == '__main__':
    unittest.main()
