#!/usr/bin/env python3
"""Isolated synthetic subprocess tests; no provider or credentials used."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import io

import decision_agent as agent

SCRIPT = Path(__file__).with_name('decision_agent.py')


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-agent-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = {'format_version': 1, 'data_scope': 'synthetic', 'cases': [
            {'id': 'c1', 'claim': 'Synthetic intervention improves outcome.',
             'evidence': [{'id': 'e1', 'text': 'Synthetic intervention improves outcome.'}]}]}
        self.policy = {'format_version': 1, 'question_version': 'synthetic-v1',
                       'confidence_threshold': 0.8, 'max_requests': 2, 'timeout_seconds': 1,
                       'models': {}}
        self.counter = 0

    def run_agent(self, execute=False):
        self.counter += 1
        source, policy = self.root / 'case.json', self.root / 'policy.json'
        source.write_text(json.dumps(self.case))
        policy.write_text(json.dumps(self.policy))
        out = self.root / ('out-' + str(self.counter))
        result = subprocess.run([sys.executable, str(SCRIPT), '--input', str(source),
                                 '--policy', str(policy), '--out', str(out)] +
                                (['--execute-models'] if execute else []), capture_output=True, text=True)
        self.assertTrue((out / 'completion.json').exists(), result.stderr + result.stdout)
        marker = json.loads((out / 'completion.json').read_text())
        for name, digest in marker['artifacts'].items():
            self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), digest)
        report = json.loads((out / 'decision.json').read_text())
        self.assertFalse(report['execution_authorized'])
        self.assertFalse(report['scientific_approval'])
        self.assertEqual(report['mode'], 'shadow')
        self.assertEqual(report['exit_code'], result.returncode)
        return report

    def adapter(self, tier, behavior='valid'):
        path = self.root / (tier + '.py')
        path.write_text("import json,sys,time\np=json.load(sys.stdin)\n" +
                        "r={'model':p['model'],'decision':'supports','confidence':0.95," +
                        "'uncertain':False,'evidence':[{'id':'e1','quote':'Synthetic intervention'}]}\n" +
                        {'valid': '', 'insufficient': "r['decision']='insufficient'\n",
                         'low': "r['confidence']=0.1\n", 'uncertain': "r['uncertain']=True\n",
                         'quote': "r['evidence'][0]['quote']='INVENTED PRIVATE TEXT'\n",
                         'id': "r['evidence'][0]['id']='absent'\n",
                         'model': "r['model']='different-model'\n",
                         'schema': "r['scientific_approval']=True\n",
                         'failure': "sys.stderr.write('PRIVATE ERROR');sys.exit(7)\n",
                         'timeout': "time.sleep(3)\n",
                         'invalid': "print('PRIVATE INVALID');sys.exit()\n"}[behavior] +
                        "print(json.dumps(r))\n")
        self.policy['models'][tier] = {'provider': 'synthetic-local', 'model': tier + '-synthetic-v1',
                                      'command': [sys.executable, str(path)]}

    def test_two_tier_cascade_and_failures(self):
        for behavior in ['valid', 'insufficient', 'low', 'uncertain', 'quote', 'id', 'model',
                         'schema', 'failure', 'timeout', 'invalid']:
            with self.subTest(behavior=behavior):
                self.adapter('light', behavior)
                self.adapter('reasoner')
                report = self.run_agent(True)
                self.assertEqual(report['state'], 'AWAITING_SCIENTIFIC_REVIEW')
                self.assertEqual(report['request_count'], 1 if behavior == 'valid' else 2)
                self.assertEqual(report['decisions'][0]['decision'], 'supports')
                self.assertNotIn('PRIVATE', json.dumps(report))
                self.assertEqual(report['attempts'][0]['requested_model'], 'light-synthetic-v1')
                if behavior == 'model':
                    self.assertEqual(report['attempts'][0]['returned_model'], 'different-model')
                if behavior != 'valid':
                    self.assertTrue(report['attempts'][0]['escalation_reasons'])

    def test_refuse_unapproved_egress(self):
        self.adapter('light')
        for scope in ['private', 'approved_external']:
            self.case['data_scope'] = scope
            report = self.run_agent(True)
            self.assertEqual(report['state'], 'BLOCKED')
            self.assertEqual(report['request_count'], 0)

    def test_budget_is_global(self):
        self.adapter('light', 'insufficient')
        self.adapter('reasoner')
        self.policy['max_requests'] = 1
        self.case['cases'].append(dict(self.case['cases'][0], id='c2'))
        report = self.run_agent(True)
        self.assertEqual(report['request_count'], 1)
        self.assertEqual(report['state'], 'BLOCKED')
        self.assertEqual(len(report['decisions']), 2)

    def test_no_models_and_failed_reasoner_block(self):
        report = self.run_agent(True)
        self.assertEqual(report['state'], 'BLOCKED')
        self.assertEqual(report['request_count'], 0)
        self.adapter('light', 'quote')
        self.adapter('reasoner', 'quote')
        report = self.run_agent(True)
        self.assertEqual(report['state'], 'BLOCKED')
        self.assertEqual(report['request_count'], 2)

    def test_invalid_contracts_do_not_execute(self):
        self.adapter('light')
        for change in ['argv', 'nan', 'duplicate', 'extra']:
            with self.subTest(change=change):
                old_policy = json.loads(json.dumps(self.policy))
                old_case = json.loads(json.dumps(self.case))
                if change == 'argv':
                    self.policy['models']['light']['command'] = 'echo shell'
                elif change == 'nan':
                    self.policy['confidence_threshold'] = float('nan')
                elif change == 'duplicate':
                    self.case['cases'][0]['evidence'] *= 2
                else:
                    self.case['patient_rows'] = []
                report = self.run_agent(True)
                self.assertEqual(report['state'], 'BLOCKED')
                self.assertEqual(report['request_count'], 0)
                self.policy, self.case = old_policy, old_case

    def approval(self):
        def normalized(value):
            return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                             separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
        self.case['external_approval'] = {
            'approved': True, 'reference': 'synthetic-approval-only',
            'cases_sha256': normalized(self.case['cases']),
            'policy_sha256': normalized(self.policy)}

    def test_approval_cannot_be_replayed(self):
        self.adapter('light')
        self.adapter('reasoner')
        self.case['data_scope'] = 'approved_external'
        for target in ('claim', 'excerpt', 'provider', 'model', 'command', 'reasoner', 'policy'):
            with self.subTest(target=target):
                old_case = json.loads(json.dumps(self.case))
                old_policy = json.loads(json.dumps(self.policy))
                self.approval()
                if target == 'claim':
                    self.case['cases'][0]['claim'] += ' changed'
                elif target == 'excerpt':
                    self.case['cases'][0]['evidence'][0]['text'] += ' changed'
                elif target == 'policy':
                    self.policy['question_version'] = 'changed'
                elif target == 'reasoner':
                    self.policy['models']['reasoner']['provider'] = 'changed'
                elif target == 'command':
                    self.policy['models']['light']['command'].append('changed')
                else:
                    self.policy['models']['light'][target] = 'changed'
                report = self.run_agent(True)
                self.assertEqual(report['request_count'], 0)
                self.assertEqual(report['diagnostics'], ['egress_approval_mismatch'])
                self.case, self.policy = old_case, old_policy

    def test_approved_external_and_dry_handoff(self):
        self.adapter('light')
        self.case['data_scope'] = 'approved_external'
        self.approval()
        report = self.run_agent()
        self.assertEqual(report['request_count'], 0)
        self.assertEqual(report['decisions'][0]['state'], 'NOT_EVALUATED')
        self.assertIn('next_actions', report)
        report = self.run_agent(True)
        self.assertEqual(report['state'], 'AWAITING_SCIENTIFIC_REVIEW')

    def test_existing_output_is_preserved(self):
        self.run_agent()
        out = self.root / 'out-1'
        before = (out / 'completion.json').read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPT), '--input', str(self.root / 'case.json'),
                                 '--policy', str(self.root / 'policy.json'), '--out', str(out)],
                                capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(before, (out / 'completion.json').read_bytes())

    def test_empty_evidence_never_calls_models(self):
        self.adapter('light')
        self.adapter('reasoner')
        self.case['cases'][0]['evidence'] = []
        report = self.run_agent(True)
        self.assertEqual(report['request_count'], 0)
        self.assertEqual(report['decisions'][0]['decision'], 'insufficient')
        self.assertEqual(report['state'], 'BLOCKED')

    def test_reasoner_insufficient_is_explicit(self):
        self.adapter('light', 'insufficient')
        self.adapter('reasoner', 'insufficient')
        report = self.run_agent(True)
        self.assertEqual(report['request_count'], 2)
        self.assertEqual(report['decisions'][0]['decision'], 'insufficient')
        self.assertEqual(report['state'], 'BLOCKED')

    def test_nested_response_is_contained(self):
        self.adapter('light')
        path = self.root / 'light.py'
        path.write_text("print('[' * 2000 + '0' + ']' * 2000)\n")
        self.adapter('reasoner')
        report = self.run_agent(True)
        self.assertEqual(report['request_count'], 2)
        self.assertEqual(report['attempts'][0]['status'], 'error')

    def test_huge_numbers_are_contained(self):
        self.adapter('light')
        for field in ('confidence_threshold', 'timeout_seconds'):
            old = self.policy[field]
            self.policy[field] = 10 ** 400
            report = self.run_agent(True)
            self.assertEqual(report['request_count'], 0)
            self.assertEqual(report['exit_code'], 2)
            self.policy[field] = old
        (self.root / 'light.py').write_text(
            "import json,sys\np=json.load(sys.stdin)\n"
            "print(json.dumps({'model':p['model'],'decision':'insufficient',"
            "'confidence':10**400,'uncertain':False,'evidence':[]}))\n")
        self.adapter('reasoner')
        report = self.run_agent(True)
        self.assertEqual(report['request_count'], 2)
        self.assertEqual(report['attempts'][0]['escalation_reasons'], ['invalid_response_schema'])

    def test_output_streams_are_bounded(self):
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.adapter('light')
                (self.root / 'light.py').write_text(
                    "import sys,time\nsys.stdin.read()\n"
                    f"sys.{stream}.write('PRIVATE' * 300000);sys.{stream}.flush()\n"
                    "time.sleep(3)\n")
                report = self.run_agent(True)
                attempt = report['attempts'][0]
                self.assertEqual(attempt['escalation_reasons'][0], 'adapter_' + stream + '_limit')
                self.assertIsNotNone(attempt['returncode'])
                self.assertNotIn('PRIVATE', json.dumps(report))

    def test_oversized_input_and_policy_are_blocked(self):
        self.adapter('light')
        self.case['cases'][0]['claim'] = 'PRIVATE' * 180000
        report = self.run_agent(True)
        self.assertEqual(report['diagnostics'], ['input_size_limit'])
        self.assertEqual(report['request_count'], 0)
        self.assertNotIn('PRIVATE', json.dumps(report))
        self.case['cases'][0]['claim'] = 'synthetic'
        self.policy['models']['light']['command'].append('PRIVATE' * 50000)
        report = self.run_agent(True)
        self.assertEqual(report['diagnostics'], ['policy_size_limit'])
        self.assertEqual(report['request_count'], 0)

    def test_cleanup_failure_stops_further_requests(self):
        self.adapter('light')
        self.adapter('reasoner')
        self.case['cases'].append(dict(self.case['cases'][0], id='c2'))
        self.run_agent()
        def failed_cleanup(command, payload, timeout, attempt):
            attempt['cleanup_diagnostics'] = ['adapter_wait_failed']
            raise agent.ContractError('adapter_stdout_limit')
        args = mock.Mock(input=self.root / 'case.json', policy=self.root / 'policy.json',
                         out=self.root / 'cleanup-out', execute_models=True)
        with mock.patch.object(agent, 'bounded_adapter', side_effect=failed_cleanup):
            report = agent.run(args)
        self.assertEqual(report['request_count'], 1)
        self.assertEqual(len(report['decisions']), 2)
        self.assertEqual(report['decisions'][1]['diagnostic'], 'adapter_cleanup_failed')

    def test_cleanup_failure_is_recorded_without_output(self):
        proc = mock.Mock()
        proc.stdout = io.BytesIO(b'PRIVATE' * 20)
        proc.stderr = io.BytesIO(b'PRIVATE')
        proc.poll.return_value = None
        proc.returncode = None
        proc.kill.side_effect = OSError('PRIVATE KILL')
        proc.wait.side_effect = subprocess.TimeoutExpired('PRIVATE COMMAND', 1)
        attempt = {}
        with mock.patch.object(agent.subprocess, 'Popen', return_value=proc), \
                mock.patch.object(agent, 'MAX_STDOUT_BYTES', 8):
            with self.assertRaisesRegex(agent.ContractError, '^adapter_stdout_limit$'):
                agent.bounded_adapter(['synthetic'], b'{}', 0.1, attempt)
        proc.kill.assert_called_once()
        proc.wait.assert_called_once_with(timeout=1)
        self.assertEqual(attempt['cleanup_diagnostics'], ['adapter_kill_failed', 'adapter_wait_failed'])
        self.assertNotIn('PRIVATE', json.dumps(attempt))

    def test_output_at_limits_and_concurrent_streams(self):
        attempt = {}
        command = [sys.executable, '-c',
                   "import sys,threading;sys.stdin.read();"
                   "t=threading.Thread(target=lambda:sys.stderr.buffer.write(b'e'*65536));"
                   "t.start();sys.stdout.buffer.write(b'o'*1048576);t.join()"]
        output = agent.bounded_adapter(command, b'{}', 3, attempt)
        self.assertEqual(len(output), agent.MAX_STDOUT_BYTES)
        self.assertEqual(attempt['returncode'], 0)
        self.assertEqual(attempt['cleanup_diagnostics'], [])
        for name in ('stdout', 'stderr'):
            limit = getattr(agent, 'MAX_' + name.upper() + '_BYTES')
            with self.assertRaisesRegex(agent.ContractError, '^adapter_' + name + '_limit$'):
                agent.bounded_adapter([sys.executable, '-c',
                    f"import sys;sys.{name}.buffer.write(b'x'*{limit + 1})"], b'{}', 3, {})

    def test_request_limit_prevents_spawn(self):
        with mock.patch.object(agent.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(agent.ContractError, '^adapter_input_limit$'):
                agent.bounded_adapter(['synthetic'], b'x' * (agent.MAX_REQUEST_BYTES + 1), 1, {})
            spawn.assert_not_called()

    def test_legacy_approval_is_rejected(self):
        self.adapter('light')
        self.case['data_scope'] = 'approved_external'
        self.case['external_approval'] = {'approved': True, 'reference': 'synthetic-approval-only'}
        report = self.run_agent(True)
        self.assertEqual(report['request_count'], 0)
        self.assertEqual(report['diagnostics'], ['egress_not_authorized'])

    def test_canonical_approval_ignores_object_key_order(self):
        self.adapter('light')
        self.case['data_scope'] = 'approved_external'
        self.case['cases'][0]['claim'] = '合成 evidence'
        self.approval()
        self.policy = dict(reversed(list(self.policy.items())))
        self.case['cases'][0] = dict(reversed(list(self.case['cases'][0].items())))
        report = self.run_agent(True)
        self.assertEqual(report['state'], 'AWAITING_SCIENTIFIC_REVIEW')
        self.assertEqual(report['approval_policy_sha256'], self.case['external_approval']['policy_sha256'])
        self.assertEqual(report['cases_sha256'], self.case['external_approval']['cases_sha256'])

    def test_dry_run_without_models(self):
        report = self.run_agent()
        self.assertEqual(report['state'], 'DRY_RUN')
        self.assertEqual(report['attempts'], [])
        self.assertEqual(report['request_count'], 0)


if __name__ == '__main__':
    unittest.main()
