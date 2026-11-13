#!/usr/bin/env python3
"""Offline regressions for the concrete P2 failures; no model/network calls."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/medical-research-harness/scripts'))
import literature as core
import literature_recovery as recovery


class P2Repairs(unittest.TestCase):
    def test_widen_uses_retained_order_with_gapped_ids(self):
        paragraphs = [{'id': 's/p0001', 'order': 1, 'text': 'A'},
                      {'id': 's/p0003', 'order': 2, 'text': 'B'},
                      {'id': 's/p0004', 'order': 3, 'text': 'C'}]
        result = core.widen([{'id': 's/p0003', 'text': 'B'}], paragraphs)
        self.assertEqual({p['id'] for p in result}, {p['id'] for p in paragraphs})

    def test_nested_figure_is_masked_without_changing_reference_text(self):
        raw = b'<article><front><article-meta/></front><body><p>Before.<fig><caption><p>FIGURE_ONLY</p></caption></fig>After.</p></body></article>'
        _, paragraphs = core.parse_jats(raw, 's')
        self.assertEqual(paragraphs[0]['text'], 'Before.FIGURE_ONLYAfter.')
        evidence = core.retrieve({'keywords': ['before']}, paragraphs)
        self.assertNotIn('FIGURE_ONLY', evidence[0]['text'])
        self.assertEqual(len(evidence[0]['text']), len(paragraphs[0]['text']))
        self.assertEqual(core.retrieve({'keywords': ['figure_only']}, paragraphs), [])
        ev = evidence[0]['text']
        self.assertEqual(ev.index('After.'), paragraphs[0]['text'].index('After.'))
        response = dict(model='m', question_id='Q', applicability='applicable',
                        finding='reported_risk', summary='synthetic',
                        citations=[dict(id='s/p0001', quote='After.')], missing_materials=[])
        parsed = core.validate_response(json.dumps(response), {'model': 'm'}, {'id': 'Q'}, evidence)
        self.assertEqual(parsed['citations'][0]['start'], paragraphs[0]['text'].index('After.'))
        response['citations'][0]['quote'] = ev
        with self.assertRaisesRegex(ValueError, 'quote_crosses_masked_content'):
            core.validate_response(json.dumps(response), {'model': 'm'}, {'id': 'Q'}, evidence)

    def test_restore_failure_leaves_no_unregistered_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / 'run'; run.mkdir()
            manifest = root / 'manifest.json'; manifest.write_text('{}')
            a = run / 'a.json'; a.write_text('good')
            b = run / 'b.json'; b.write_text('good')
            cp = recovery.RunCheckpoint(run, hashlib.sha256(manifest.read_bytes()).hexdigest(), ['s'])
            cp.mark_source('s', 'INDEXED', [a, b]); cp.finish()
            b.write_text('bad')
            result = recovery.prepare_resume(run, manifest, root / 'restore')
            self.assertEqual(result['run_state'], 'BLOCKED')
            self.assertFalse(any(p.is_file() for p in (root / 'restore/artifacts').rglob('*')))

    def test_empty_indexed_artifacts_cannot_restore_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / 'run'; run.mkdir()
            manifest = root / 'manifest.json'; manifest.write_text('{}')
            cp = recovery.RunCheckpoint(run, hashlib.sha256(manifest.read_bytes()).hexdigest(), ['s'])
            # Reproduce an old or malformed checkpoint without weakening the writer.
            state = json.loads((run / 'run_state.json').read_text())
            state['sources']['s']['state'] = 'INDEXED'
            (run / 'run_state.json').write_text(json.dumps(state))
            result = recovery.prepare_resume(run, manifest, root / 'restore')
            self.assertEqual(result['run_state'], 'BLOCKED')
            self.assertEqual(result['sources'][0]['reason'], 'artifact_manifest_empty')

    def test_checkpoint_writer_rejects_empty_indexed_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = recovery.RunCheckpoint(Path(tmp), 'a' * 64, ['s'])
            with self.assertRaisesRegex(ValueError, 'artifact_manifest_empty'):
                cp.mark_source('s', 'INDEXED', [])


if __name__ == '__main__':
    unittest.main()
