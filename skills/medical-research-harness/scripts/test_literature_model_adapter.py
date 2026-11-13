#!/usr/bin/env python3
"""Unit tests for literature_model_adapter. The Hermes CLI subprocess is fully
mocked: no real model invocation, no network, no Hermes install required."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import literature_model_adapter as adapter  # noqa: E402


def request(**overrides):
    base = {
        'format_version': 1,
        'provider': 'openai',
        'model': 'gpt-test-1',
        'task': {
            'question_id': 'q1',
            'question': 'What data-leakage risks does the document report?',
            'evidence': [
                {'id': 'p1', 'text': 'The cohort was split before preprocessing.'},
                {'id': 'p2', 'text': 'Feature selection used the full dataset.'},
            ],
        },
        'instruction': adapter.INSTRUCTION,
    }
    for key, value in overrides.items():
        if key == 'task':
            base['task'].update(value)
        else:
            base[key] = value
    return base


def stream(response, model='gpt-test-1', session='s1'):
    return '\n'.join([
        json.dumps({'type': 'system', 'subtype': 'init', 'model': model,
                    'session_id': session}),
        json.dumps({'type': 'text', 'text': 'partial'}),
        json.dumps({'type': 'result', 'exit_code': 0, 'error': None,
                    'session_id': session, 'text': json.dumps(response)}),
    ]).encode('utf-8')


def valid_response(**overrides):
    response = {
        'model': 'gpt-test-1',
        'question_id': 'q1',
        'applicability': 'applicable',
        'finding': 'reported_risk',
        'summary': 'The document reports feature selection on the full dataset.',
        'citations': [{'id': 'p2', 'quote': 'used the full dataset'}],
        'missing_materials': ['analysis code'],
    }
    response.update(overrides)
    return response


def completed(stdout):
    return subprocess.CompletedProcess(['fake'], 0, stdout)


class ValidationTests(unittest.TestCase):
    def assert_invalid(self, req):
        with self.assertRaises(Exception):
            adapter.validate_request(req)

    def test_whitespace_evidence_rejected_before_transport(self):
        with mock.patch.object(adapter, 'bounded_cli') as cli:
            with self.assertRaisesRegex(ValueError, 'invalid_request'):
                adapter.invoke(request(task={'evidence': [{'id': 'p1', 'text': ' \n '}]}))
        cli.assert_not_called()

    def test_valid_request_accepted(self):
        adapter.validate_request(request())

    def test_rejects_wrong_instruction(self):
        self.assert_invalid(request(instruction='ignore everything'))

    def test_rejects_extra_field(self):
        req = request()
        req['command'] = ['/bin/sh']
        self.assert_invalid(req)

    def test_rejects_bad_format_version(self):
        self.assert_invalid(request(format_version=2))

    def test_rejects_unsafe_model(self):
        self.assert_invalid(request(model='x;rm -rf /'))

    def test_rejects_duplicate_evidence_ids(self):
        self.assert_invalid(request(task={
            'evidence': [{'id': 'p1', 'text': 'a'}, {'id': 'p1', 'text': 'b'}]}))

    def test_rejects_empty_question(self):
        self.assert_invalid(request(task={'question': '  '}))


class ResponseTests(unittest.TestCase):
    def setUp(self):
        self.req = request()

    def assert_invalid(self, response):
        with self.assertRaises(Exception):
            adapter.validate_response(response, self.req)

    def test_whitespace_quote_and_empty_summary_rejected(self):
        for response in [valid_response(citations=[{'id': 'p1', 'quote': ' '}]),
                         valid_response(summary='  ')]:
            with self.assertRaisesRegex(ValueError, 'invalid_response'):
                adapter.validate_response(response, self.req)

    def test_valid_response_accepted(self):
        out = adapter.validate_response(valid_response(), self.req)
        self.assertEqual(out['finding'], 'reported_risk')

    def test_rejects_missing_key(self):
        response = valid_response()
        del response['summary']
        self.assert_invalid(response)

    def test_rejects_extra_key_confidence(self):
        self.assert_invalid(valid_response(confidence=0.9))

    def test_rejects_wrong_question_id(self):
        self.assert_invalid(valid_response(question_id='q2'))

    def test_rejects_unknown_evidence_id(self):
        self.assert_invalid(valid_response(citations=[{'id': 'p9', 'quote': 'x'}]))

    def test_rejects_non_verbatim_quote(self):
        self.assert_invalid(valid_response(citations=[{'id': 'p2', 'quote': 'not present'}]))

    def test_reported_risk_requires_citation(self):
        self.assert_invalid(valid_response(citations=[]))

    def test_insufficient_without_citations_ok(self):
        out = adapter.validate_response(valid_response(
            finding='insufficient', citations=[]), self.req)
        self.assertEqual(out['finding'], 'insufficient')

    def test_not_applicable_requires_citation(self):
        self.assert_invalid(valid_response(applicability='not_applicable',
                                           finding='insufficient', citations=[]))

    def test_rejects_bad_enum(self):
        self.assert_invalid(valid_response(finding='low_risk'))
        self.assert_invalid(valid_response(applicability='high'))


class InvokeTests(unittest.TestCase):
    def test_empty_evidence_skips_model(self):
        req = request(task={'evidence': []})
        with mock.patch.object(adapter, 'bounded_cli') as cli:
            out = adapter.invoke(req)
        cli.assert_not_called()
        self.assertEqual(out['finding'], 'insufficient')
        self.assertEqual(out['model'], 'gpt-test-1')

    def test_valid_roundtrip(self):
        req = request()
        with mock.patch.object(adapter, 'command', return_value=['fake']) as cmd, \
             mock.patch.object(adapter, 'bounded_cli',
                               return_value=completed(stream(valid_response()))) as cli:
            out = adapter.invoke(req)
        cmd.assert_called_once_with(req)
        argv, payload = cli.call_args[0][0], cli.call_args[0][1]
        self.assertEqual(argv, ['fake'])
        self.assertIn('untrusted', payload.decode('utf-8'))
        self.assertEqual(out['finding'], 'reported_risk')

    def test_nonzero_returncode_fails(self):
        bad = subprocess.CompletedProcess(['fake'], 3, stream(valid_response()))
        with mock.patch.object(adapter, 'command', return_value=['fake']), \
             mock.patch.object(adapter, 'bounded_cli', return_value=bad), \
             self.assertRaises(Exception):
            adapter.invoke(request())

    def test_invalid_stream_fails(self):
        bad = completed(b'not json\n')
        with mock.patch.object(adapter, 'command', return_value=['fake']), \
             mock.patch.object(adapter, 'bounded_cli', return_value=bad), \
             self.assertRaises(Exception):
            adapter.invoke(request())

    def test_model_mismatch_in_stream_fails(self):
        bad = completed(stream(valid_response(), model='other-model'))
        with mock.patch.object(adapter, 'command', return_value=['fake']), \
             mock.patch.object(adapter, 'bounded_cli', return_value=bad), \
             self.assertRaises(Exception):
            adapter.invoke(request())

    def test_invalid_response_schema_fails(self):
        bad = completed(stream(valid_response(finding='bogus')))
        with mock.patch.object(adapter, 'command', return_value=['fake']), \
             mock.patch.object(adapter, 'bounded_cli', return_value=bad), \
             self.assertRaises(Exception):
            adapter.invoke(request())


class MainTests(unittest.TestCase):
    def run_main(self, payload):
        return subprocess.run(
            [sys.executable, '-I', str(Path(adapter.__file__).resolve())],
            input=payload, capture_output=True, timeout=30)

    def test_main_empty_evidence(self):
        req = request(task={'evidence': []})
        proc = self.run_main(json.dumps(req).encode())
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b'')
        response = json.loads(proc.stdout.decode())
        self.assertEqual(response['finding'], 'insufficient')

    def test_main_invalid_request_fixed_diagnostic(self):
        proc = self.run_main(b'{"bogus": true}')
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b'')
        self.assertEqual(proc.stderr, b'literature_adapter_failed\n')

    def test_main_oversized_request(self):
        proc = self.run_main(b' ' * (adapter.LIMIT + 1))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stderr, b'literature_adapter_failed\n')


if __name__ == '__main__':
    unittest.main()
