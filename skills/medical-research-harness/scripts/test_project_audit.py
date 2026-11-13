#!/usr/bin/env python3
"""Offline tests for project_audit.py: planted faults, static AST probes, and sandbox gates."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import project_audit as pa
import test_study


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


DEFECTIVE_PIPELINE_CODE = """\
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression

def train_pipeline(df):
    X = df[['lab_a', 'lab_b']]
    y = df['outcome']
    # BUG 1: Fit imputer and scaler on full dataset before splitting
    imputer = SimpleImputer(strategy='median')
    X_imp = imputer.fit_transform(X)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imp)
    # BUG 2: Ungrouped random row split (ignoring patient_id)
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.3, random_state=42)
    clf = LogisticRegression()
    clf.fit(X_train, y_train)
    # BUG 3: Fitting calibration or threshold on X_test
    clf.fit(X_test, y_test)
    return clf
"""

CLEAN_PIPELINE_CODE = """\
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import LogisticRegression

def train_clean(df, groups):
     splitter = GroupKFold(n_splits=5)
     for fold_id, (tr, va) in enumerate(splitter.split(df, df['y'], groups)):
         imputer = SimpleImputer(strategy='median')
         X_tr = imputer.fit_transform(df.iloc[tr][['x1']])
         # Record fitted row_ids to actual-fits.csv
         with open('actual-fits.csv', 'a', encoding='utf-8') as f:
             f.write(f'baseline,impute,fold{fold_id}\\n')
"""


class ProjectAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build_project_fixture(self, proj_dir, defective=True):
        test_study.walkthrough(proj_dir)
        code_path = proj_dir / 'pipeline.py'
        code_path.write_text(DEFECTIVE_PIPELINE_CODE if defective else CLEAN_PIPELINE_CODE, encoding='utf-8')

        safe_gen = proj_dir / 'check_schema.py'
        safe_gen.write_text("import json\nprint(json.dumps({'ok': True}))\n", encoding='utf-8')

        if defective:
            unsafe_gen = proj_dir / 'unsafe_check.py'
            unsafe_gen.write_text("import socket, subprocess\neval('1+1')\n", encoding='utf-8')
            gen_scripts = [
                {'id': 'safe_check', 'path': 'check_schema.py', 'sha256': sha256_file(safe_gen)},
                {'id': 'unsafe_check', 'path': 'unsafe_check.py', 'sha256': sha256_file(unsafe_gen)},
            ]
            # Create defective-fits.csv with out-of-fold fit (validation row R2 in cv1)
            clean_fits = (proj_dir / 'fits.csv').read_text(encoding='utf-8')
            (proj_dir / 'defective-fits.csv').write_text(
                clean_fits + 'baseline,scaler,cv1,SYNTHETIC_PRIVATE_R2\n', encoding='utf-8'
            )
            # Remove synthetic-run-1 so sensitivity experiment is NOT_RUN (omitted run)
            import shutil
            shutil.rmtree(proj_dir / 'simulated-runs' / 'synthetic-run-1')
            rows_rel = 'candidate-rows.csv'
            fits_rel = 'defective-fits.csv'
        else:
            gen_scripts = []
            rows_rel = 'rows.csv'
            fits_rel = 'fits.csv'

        spec = {
            'format_version': 1,
            'study_id': 'SYNTHETIC-DEMO',
            'authorized_root': str(proj_dir),
            'read_only': True,
            'plan': 'plan/plan.json',
            'rows': rows_rel,
            'folds': 'folds.csv',
            'planned_fits': fits_rel,
            'runs_dir': 'simulated-runs' if defective else None,
            'code_files': [
                {'path': 'pipeline.py', 'sha256': sha256_file(code_path)},
            ],
            'generated_check_scripts': gen_scripts,
        }
        spec_path = self.root / ('spec-defective.json' if defective else 'spec-clean.json')
        spec_path.write_text(json.dumps(spec, indent=2), encoding='utf-8')
        return spec_path

    def test_planted_faults_and_static_ast_indicators_detected(self):
        proj = self.root / 'defective-project'
        spec_path = self.build_project_fixture(proj, defective=True)
        out = self.root / 'audit-out-defective'
        rc = pa.main(['--spec', str(spec_path), '--out', str(out)])
        self.assertEqual(rc, 1)
        report = json.loads((out / 'project_audit.json').read_text(encoding='utf-8'))
        self.assertEqual(report['state'], 'FINDINGS_REPORTED')
        self.assertTrue(report['authorized_root_unchanged'])
        self.assertFalse(report['execution_authorized'])
        self.assertFalse(report['scientific_acceptance'])

        # Verify all 4 planted fault families in confirmed_violations
        violation_rules = {v['rule_id'] for v in report['confirmed_violations']}
        self.assertIn('patient_overlap', violation_rules)
        self.assertIn('feature_after_index', violation_rules)
        self.assertIn('fit_outside_training_fold', violation_rules)
        self.assertIn('omitted_planned_run', violation_rules)
        self.assertIn('UNSAFE_GENERATED_CHECK_SCRIPT', violation_rules)

        # Verify static AST code risk indicators
        ast_rules = {i['rule_id'] for i in report['code_risk_indicators']}
        self.assertIn('UNSCOPED_PREPROCESSING_FIT', ast_rules)
        self.assertIn('UNGROUPED_ROW_SPLIT', ast_rules)
        self.assertIn('TEST_SET_REUSE_IN_FIT_OR_SELECTION', ast_rules)
        self.assertIn('MISSING_FIT_MEMBERSHIP_LOGGING', ast_rules)

        # Verify untrusted script gate stops at AWAITING_SANDBOX_RUNNER when no sandbox runner is given
        gates = {g['id']: g['execution_state'] for g in report['generated_scripts_gate']}
        self.assertEqual(gates['safe_check'], 'AWAITING_SANDBOX_RUNNER')
        self.assertEqual(gates['unsafe_check'], 'REJECTED_STATIC_SAFETY')

        # Verify completion.json hashes
        comp = json.loads((out / 'completion.json').read_text(encoding='utf-8'))
        for rel, h in comp['artifacts'].items():
            self.assertEqual(sha256_file(out / rel), h)

    def test_clean_project_passes_manifest_and_ast_checks(self):
        proj = self.root / 'clean-project'
        spec_path = self.build_project_fixture(proj, defective=False)
        out = self.root / 'audit-out-clean'
        rc = pa.main(['--spec', str(spec_path), '--out', str(out)])
        self.assertEqual(rc, 0)
        report = json.loads((out / 'project_audit.json').read_text(encoding='utf-8'))
        self.assertEqual(report['confirmed_violations'], [])
        self.assertEqual(report['code_risk_indicators'], [])
        self.assertTrue(report['authorized_root_unchanged'])
        self.assertIn('patient_overlap', report['checked_no_violation_found'])
        self.assertIn('fit_outside_training_fold', report['checked_no_violation_found'])

    def test_rejects_non_readonly_or_overlapping_output(self):
        proj = self.root / 'proj-boundary'
        spec_path = self.build_project_fixture(proj, defective=False)
        # Overlap output inside authorized_root must be rejected without creating overlap_out
        overlap_out = proj / 'inside-out'
        rc = pa.main(['--spec', str(spec_path), '--out', str(overlap_out)])
        self.assertEqual(rc, 2)
        self.assertFalse(overlap_out.exists())

        # Non-readonly spec must be rejected
        spec = json.loads(spec_path.read_text(encoding='utf-8'))
        spec['read_only'] = False
        spec_path.write_text(json.dumps(spec), encoding='utf-8')
        out_non_ro = self.root / 'out-non-ro'
        rc2 = pa.main(['--spec', str(spec_path), '--out', str(out_non_ro)])
        self.assertEqual(rc2, 2)
        self.assertFalse(out_non_ro.exists())

    def test_transductive_graph_and_survival_hazard_ast_probe(self):
        code = (
            "from sklearn.neighbors import kneighbors_graph\n"
            "from sklearn.model_selection import GroupKFold\n"
            "def run(df):\n"
            "    adj = kneighbors_graph(df[['x1', 'x2']], n_neighbors=5)\n"
            "    splitter = GroupKFold(n_splits=5)\n"
        )
        indicators = pa.analyze_python_ast(code, 'gnn_survival.py')
        rule_ids = {i['rule_id'] for i in indicators}
        self.assertIn('GLOBAL_SURVIVAL_OR_GRAPH_LEAKAGE', rule_ids)


if __name__ == '__main__':
    unittest.main()
