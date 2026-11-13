#!/usr/bin/env python3
"""Offline contract tests for resumable literature artifacts."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from literature_recovery import RunCheckpoint, prepare_resume


class RecoveryTests(unittest.TestCase):
    def test_source_state_and_verified_artifact_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / 'run'
            run.mkdir()
            manifest = root / 'manifest.json'
            manifest.write_text('{"format_version":1}')
            artifact = run / 'index.s1.json'
            artifact.write_text('{"source_id":"s1"}')
            checkpoint = RunCheckpoint(run, hashlib.sha256(manifest.read_bytes()).hexdigest(), ['s1'])
            checkpoint.mark_source('s1', 'INDEXED', [artifact])
            checkpoint.finish()
            out = root / 'resume'
            result = prepare_resume(run, manifest, out)
            self.assertEqual(result['run_state'], 'COMPLETED')
            self.assertEqual(result['sources'][0]['state'], 'INDEXED')
            self.assertTrue((out / 'artifacts/index.s1.json').is_file())
            self.assertFalse((out / 'completion.json').exists())

    def test_hash_mismatch_is_not_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / 'run'; run.mkdir()
            manifest = root / 'manifest.json'; manifest.write_text('{}')
            artifact = run / 'index.s1.json'; artifact.write_text('verified')
            cp = RunCheckpoint(run, hashlib.sha256(manifest.read_bytes()).hexdigest(), ['s1'])
            cp.mark_source('s1', 'INDEXED', [artifact]); cp.finish()
            artifact.write_text('tampered')
            out = root / 'resume'
            result = prepare_resume(run, manifest, out)
            self.assertEqual(result['sources'][0]['state'], 'BLOCKED')
            self.assertEqual(result['sources'][0]['reason'], 'artifact_hash_mismatch')
            self.assertFalse((out / 'artifacts/index.s1.json').exists())

    def test_manifest_mismatch_blocks_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / 'run'; run.mkdir()
            old = root / 'old.json'; old.write_text('old')
            new = root / 'new.json'; new.write_text('new')
            RunCheckpoint(run, hashlib.sha256(old.read_bytes()).hexdigest(), ['s1']).finish()
            with self.assertRaisesRegex(ValueError, 'manifest_hash_mismatch'):
                prepare_resume(run, new, root / 'resume')

    def test_interrupt_reason_and_resume_origin_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / 'run'; run.mkdir()
            manifest = root / 'manifest.json'; manifest.write_text('{}')
            cp = RunCheckpoint(run, hashlib.sha256(manifest.read_bytes()).hexdigest(), ['s1'])
            cp.interrupt('SIGTERM', 'source:s1:INDEXED')
            result = prepare_resume(run, manifest, root / 'resume')
            self.assertEqual(result['interrupt'], {
                'reason': 'SIGTERM', 'resume_from': 'source:s1:INDEXED'})
            self.assertEqual(result['run_state'], 'BLOCKED')

    def test_illegal_source_transition_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); root.mkdir(exist_ok=True)
            cp = RunCheckpoint(root, 'a' * 64, ['s1'])
            with self.assertRaisesRegex(ValueError, 'invalid_source_transition'):
                cp.mark_source('s1', 'ANALYZED', [])


if __name__ == '__main__':
    unittest.main()
