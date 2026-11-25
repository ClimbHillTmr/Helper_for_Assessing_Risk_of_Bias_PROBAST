"""Offline rejection tests for manuscript structure and explicit readiness gates."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('joss', ROOT / 'Paper/joss/check_joss_ready.py')
joss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(joss)

class ReadinessTests(unittest.TestCase):
    def test_current_structure(self):
        self.assertEqual(joss.run_checks(ROOT, False, False)[1], [])

    def test_pending_evidence_is_not_ready(self):
        self.assertEqual(joss.main([]), 1)
        self.assertEqual(joss.main(['--structural-only']), 0)

    def test_reject_missing_impact_and_short_body(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'Paper/joss', root / 'Paper/joss')
            for rel in joss.REQUIRED_GOVERNANCE_FILES:
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, target)
            paper = root / 'Paper/joss/paper.md'
            original = paper.read_text()
            paper.write_text(original.replace('# Research Impact Statement', '# Applications'))
            self.assertTrue(any('[3/8]' in x for x in joss.run_checks(root, False, False)[1]))
            front = original.split('---', 2)[1]
            paper.write_text('---' + front + '---\n' + 'word ' * 749)
            self.assertTrue(any('[2/8]' in x for x in joss.run_checks(root, False, False)[1]))

if __name__ == '__main__':
    unittest.main()
