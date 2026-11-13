#!/usr/bin/env python3
"""Real subprocess interruption and offline continuation acceptance tests."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/medical-research-harness/scripts'
sys.path.insert(0, str(SCRIPTS))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def workspace(root):
    sources = []
    for sid in ('s1', 's2', 's3'):
        p = root / (sid + '.xml')
        p.write_text('<article><front><article-meta><article-id pub-id-type="doi">10.1234/' + sid + '</article-id><permissions><license xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions></article-meta></front><body><sec><title>Methods</title><p>Training data split by patient before validation.</p></sec></body></article>')
        sources.append(dict(id=sid, doi='10.1234/' + sid, title=sid,
                            license_url='https://creativecommons.org/licenses/by/4.0/',
                            rights_basis='synthetic', path=p.name, sha256=digest(p)))
    (root / 'manifest.json').write_text(json.dumps(dict(format_version=1, sources=sources)))
    model = dict(provider='unused', model='unused', command=['NEVER_EXECUTE'])
    (root / 'config.json').write_text(json.dumps(dict(format_version=1, max_requests=30,
              timeout_seconds=30, models=dict(analysis=model, reviewer=model))))
    return root / 'manifest.json', root / 'config.json'


class OfflineResume(unittest.TestCase):
    def start_interrupted(self, root, signum=signal.SIGTERM):
        manifest, config = workspace(root)
        ready = root / 'ready'
        code = '''import sys,time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import literature as core
import literature_offline as offline
original=core.analyze_source
def pause(source,*args,**kwargs):
    if source['id']=='s2':
        Path(sys.argv[5]).write_text('ready')
        while True: time.sleep(0.05)
    return original(source,*args,**kwargs)
core.analyze_source=pause
raise SystemExit(offline.main(['--manifest',sys.argv[2],'--config',sys.argv[3],'--out',sys.argv[4]]))
'''
        proc = subprocess.Popen([sys.executable, '-c', code, str(SCRIPTS), str(manifest),
                                 str(config), str(root / 'interrupted'), str(ready)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists(), 'child failed to reach checkpoint: ' + str(proc.poll()))
            proc.send_signal(signum)
            stdout, stderr = proc.communicate(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill(); proc.wait()
        self.assertNotEqual(proc.returncode, 0)
        return manifest, config, root / 'interrupted'

    def resume(self, manifest, config, old, out):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/resume_literature_run.py'),
                               '--run', str(old), '--manifest', str(manifest),
                               '--config', str(config), '--out', str(out)],
                              capture_output=True, text=True, timeout=15)

    def test_sigterm_continues_pending_sources_without_rewriting_old_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, config, old = self.start_interrupted(root)
            before = {p.relative_to(old).as_posix(): digest(p) for p in old.rglob('*') if p.is_file()}
            state = json.loads((old / 'run_state.json').read_text())
            self.assertEqual(state['interrupt']['reason'], 'SIGTERM')
            result = self.resume(manifest, config, old, root / 'resumed')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((root / 'resumed/report.json').read_text())
            self.assertEqual(report['run_state'], 'COMPLETED')
            self.assertEqual(report['request_count'], 0)
            self.assertEqual(report['resume']['reused_sources'], ['s1'])
            self.assertEqual(report['resume']['continued_sources'], ['s2', 's3'])
            self.assertEqual(len(report['sources']), 3)
            self.assertEqual(before, {p.relative_to(old).as_posix(): digest(p) for p in old.rglob('*') if p.is_file()})
            completion = json.loads((root / 'resumed/completion.json').read_text())
            self.assertTrue(all(digest(root / 'resumed' / n) == h for n, h in completion['artifacts'].items()))
            self.assertIn('literature_recovery.py', report['identity']['code_sha256'])

    def test_sigkill_infers_unknown_exit_and_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, config, old = self.start_interrupted(root, signal.SIGKILL)
            result = self.resume(manifest, config, old, root / 'resumed')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            state = json.loads((root / 'resumed/run_state.json').read_text())
            self.assertEqual(state['previous_interrupt']['reason'], 'unclean_exit_unknown')

    def test_sigint_records_real_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, config, old = self.start_interrupted(root, signal.SIGINT)
            self.assertEqual(json.loads((old / 'run_state.json').read_text())['interrupt']['reason'], 'SIGINT')
            self.assertEqual(self.resume(manifest, config, old, root / 'resumed').returncode, 0)

    def test_resume_faults_are_persistent_blocked_and_never_recompute(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, config, old = self.start_interrupted(root)
            for fault in ('missing', 'tamper', 'empty', 'blocked', 'identity_code',
                          'identity_questions', 'config', 'source_bytes', 'unregistered', 'manifest'):
                with self.subTest(fault=fault):
                    clone = root / ('old-' + fault); shutil.copytree(old, clone)
                    state = json.loads((clone / 'run_state.json').read_text())
                    if fault == 'missing':
                        (clone / 'index.s1.json').unlink()
                    elif fault == 'tamper':
                        (clone / 'index.s1.json').write_text('tamper')
                    elif fault == 'empty':
                        state['sources']['s1']['artifacts'] = {}
                    elif fault == 'blocked':
                        state['sources']['s1']['state'] = 'BLOCKED'
                    elif fault == 'identity_code':
                        state['identity']['code_sha256']['literature.py'] = '0' * 64
                    elif fault == 'identity_questions':
                        state['identity']['questions_sha256'] = '0' * 64
                    elif fault == 'unregistered':
                        (clone / 'source.s3.json').write_text('{}')
                    (clone / 'run_state.json').write_text(json.dumps(state))
                    changed_config = config
                    if fault == 'config':
                        changed_config = root / 'changed-config.json'
                        changed_config.write_text(config.read_text() + ' ')
                    used_manifest = manifest
                    if fault == 'manifest':
                        used_manifest = root / 'changed-manifest.json'
                        used_manifest.write_text(manifest.read_text() + ' ')
                    source = root / 's3.xml'; original = source.read_bytes()
                    if fault == 'source_bytes': source.write_bytes(original + b' ')
                    out = root / ('out-' + fault)
                    result = self.resume(used_manifest, changed_config, clone, out)
                    source.write_bytes(original)
                    self.assertEqual(result.returncode, 2)
                    report = json.loads((out / 'report.json').read_text())
                    self.assertEqual(report['run_state'], 'BLOCKED')
                    self.assertEqual(report['resume']['continued_sources'], [])
                    self.assertEqual(list(out.glob('index.*')), [])
                    self.assertTrue((out / 'completion.json').is_file())

    def test_existing_destination_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, config, old = self.start_interrupted(root)
            result = self.resume(manifest, config, old, root / 'resumed')
            self.assertEqual(result.returncode, 0)
            before = {p.name: digest(p) for p in (root / 'resumed').iterdir() if p.is_file()}
            self.assertEqual(self.resume(manifest, config, old, root / 'resumed').returncode, 2)
            self.assertEqual(before, {p.name: digest(p) for p in (root / 'resumed').iterdir() if p.is_file()})

    def test_completed_run_cannot_be_downgraded_by_checkpoint_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, config = workspace(root)
            subprocess.run([sys.executable, str(SCRIPTS / 'literature_offline.py'),
                '--manifest', str(manifest), '--config', str(config), '--out', str(root / 'old')],
                check=True, capture_output=True, timeout=15)
            state_path = root / 'old/run_state.json'
            state = json.loads(state_path.read_text())
            state['state'] = 'INDEXED'
            state_path.write_text(json.dumps(state))
            result = self.resume(manifest, config, root / 'old', root / 'out')
            self.assertEqual(result.returncode, 2)
            self.assertIn('completion_artifact_mismatch', (root / 'out/report.json').read_text())

    def test_demo_default_uses_offline_checkpoint_and_records_all_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, config = workspace(root)
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/run_literature_demo.py'),
                '--manifest', str(manifest), '--config', str(config), '--out', str(root / 'demo')],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((root / 'demo/output/report.json').read_text())
            self.assertEqual(report['identity']['mode'], 'offline_preparation_v2')
            ident = json.loads((root / 'demo/identity.json').read_text())
            self.assertTrue(any(p.endswith('/literature_offline.py') for p in ident['code_sha256']))
            self.assertTrue(any(p.endswith('/literature_recovery.py') for p in ident['code_sha256']))


if __name__ == '__main__':
    unittest.main()
