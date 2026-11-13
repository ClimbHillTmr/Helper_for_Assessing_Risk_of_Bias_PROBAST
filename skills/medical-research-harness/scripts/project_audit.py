#!/usr/bin/env python3
"""Read-only target project audit MVP: static AST code probe + deterministic manifest/run checks.

Enforces read-only immutability on authorized_root, inspects declared Python
scripts via stdlib ast (never importing or executing untrusted project code),
reuses study.py for deterministic manifest and run-registry reconciliation,
gates any generated check scripts behind static safety checks and an explicit
external sandbox runner, and separates findings into:
  1. confirmed_violations
  2. code_risk_indicators
  3. insufficient_evidence
  4. checked_no_violation_found
"""
import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from check_bundle import reject_constant, sha256, unique_object
import laya_decision_adapter as lda
import study

MAX_SPEC_BYTES = 512 * 1024
MAX_CODE_BYTES = 2 * 1024 * 1024

PREPROCESSOR_CLASSES = {
    'SimpleImputer', 'IterativeImputer', 'KNNImputer',
    'StandardScaler', 'MinMaxScaler', 'RobustScaler', 'MaxAbsScaler',
    'OneHotEncoder', 'OrdinalEncoder', 'TargetEncoder',
    'SelectKBest', 'SelectFromModel', 'RFE', 'PCA',
    'SMOTE', 'ADASYN', 'RandomOverSampler', 'RandomUnderSampler',
}
TRANSDUCTIVE_OR_HAZARD_CALLS = {
    'kneighbors_graph', 'radius_neighbors_graph', 'knn_graph', 'radius_graph',
    'build_graph', 'build_patient_graph', 'compute_baseline_hazards',
    'BreslowEstimator', 'KaplanMeierFitter', 'NelsonAalenFitter',
}
UNGROUPED_SPLITTERS = {'train_test_split', 'KFold', 'StratifiedKFold', 'ShuffleSplit'}
GROUPED_SPLITTERS = {'GroupKFold', 'GroupShuffleSplit', 'StratifiedGroupKFold'}
FORBIDDEN_UNTRUSTED_IMPORTS = {
    'socket', 'urllib', 'http', 'ftplib', 'telnetlib', 'requests', 'httpx',
    'subprocess', 'multiprocessing', 'pty', 'ctypes', 'webbrowser',
}
FORBIDDEN_UNTRUSTED_CALLS = {'eval', 'exec', 'compile', '__import__', 'system', 'popen', 'rmtree', 'unlink', 'remove'}

ALL_DETERMINISTIC_RULES = (
    'patient_overlap',
    'fold_patient_overlap',
    'feature_after_index',
    'invalid_label_window',
    'invalid_label_start',
    'nonchronological_split',
    'label_window_crosses_split',
    'holdout_in_development_fold',
    'incomplete_fold_membership',
    'fit_outside_training_fold',
    'missing_fit_operation',
    'unexpected_fit_operation',
    'frozen_rows_changed',
    'frozen_folds_changed',
)


class AuditContractError(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise AuditContractError(code)


def read_bounded(path, limit, code):
    with Path(path).open('rb') as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, code)
    return raw


def load_strict_json(path, limit=MAX_SPEC_BYTES):
    raw = read_bounded(path, limit, 'json_size_limit')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object, parse_constant=reject_constant)


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def snapshot_tree(root):
    root = Path(root).resolve()
    return {
        p.relative_to(root).as_posix(): sha256(p)
        for p in sorted(root.rglob('*'))
        if p.is_file()
    }


def resolve_inside(root, rel_path):
    need(isinstance(rel_path, str) and bool(rel_path.strip()), 'invalid_relative_path')
    root_resolved = Path(root).resolve()
    target = (root_resolved / rel_path).resolve()
    need(target.is_relative_to(root_resolved), 'path_outside_authorized_root')
    return target


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ''


def analyze_python_ast(source_text, rel_path):
    """Static AST inspection for clinical ML pipeline engineering risk patterns."""
    try:
        tree = ast.parse(source_text, filename=rel_path)
    except SyntaxError as exc:
        raise AuditContractError(f'code_syntax_error:{rel_path}:line_{exc.lineno}') from exc

    indicators = []
    preproc_vars = {}
    ungrouped_splits = []
    grouped_splits = []
    split_lines = []
    fit_calls = []
    transductive_calls = []
    mentions_fits_log = ('fits.csv' in source_text or 'actual-fits' in source_text or 'planned-fits' in source_text)

    # Track variable assignments of preprocessor instances and loop nesting
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            cname = call_name(node.value.func)
            if cname in PREPROCESSOR_CLASSES:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        preproc_vars[target.id] = cname

    def walk_stmt(node, in_loop=False):
        curr_loop = in_loop or isinstance(node, (ast.For, ast.AsyncFor, ast.While))
        if isinstance(node, ast.Call):
            fn = call_name(node.func)
            lineno = getattr(node, 'lineno', 0)
            if fn in UNGROUPED_SPLITTERS:
                ungrouped_splits.append((lineno, fn))
                split_lines.append(lineno)
            elif fn in GROUPED_SPLITTERS:
                grouped_splits.append((lineno, fn))
                split_lines.append(lineno)
            elif fn in TRANSDUCTIVE_OR_HAZARD_CALLS:
                transductive_calls.append((lineno, fn, curr_loop, ast.unparse(node)))
            elif fn in ('fit', 'fit_transform'):
                receiver = ''
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        receiver = preproc_vars.get(node.func.value.id, node.func.value.id)
                    elif isinstance(node.func.value, ast.Call):
                        receiver = call_name(node.func.value.func)
                fit_calls.append((lineno, fn, receiver, curr_loop, ast.unparse(node)))
        for child in ast.iter_child_nodes(node):
            walk_stmt(child, curr_loop)

    walk_stmt(tree, in_loop=False)

    first_split_line = min(split_lines) if split_lines else None
    for lineno, fn, receiver, in_loop, expr_src in fit_calls:
        is_preproc = receiver in PREPROCESSOR_CLASSES or any(
            p.lower() in receiver.lower() for p in ('imputer', 'scaler', 'encoder', 'selector', 'pca', 'smote')
        )
        before_split = first_split_line is not None and lineno < first_split_line
        arg_text = expr_src.lower()
        uses_full_or_test = any(tok in arg_text for tok in ('full', 'all_data', 'df', 'x_all', 'x_test', 'test'))
        if is_preproc and (before_split or (not in_loop and uses_full_or_test)):
            indicators.append({
                'rule_id': 'UNSCOPED_PREPROCESSING_FIT',
                'category': 'code_risk_indicator',
                'file': rel_path,
                'line': lineno,
                'symbol_or_call': f'{receiver}.{fn}',
                'rationale': (
                    f'Call `{expr_src}` on preprocessor `{receiver}` occurs '
                    + ('before dataset splitting' if before_split else 'outside fold loop on full/test-referencing data')
                    + ', risking preprocessing data leakage across partitions.'
                ),
                'suggested_action': 'Fit preprocessing strictly inside each training fold after patient-disjoint splitting.',
            })
        elif any(tok in arg_text for tok in ('x_test', 'y_test', 'test_df', 'test_data')):
            indicators.append({
                'rule_id': 'TEST_SET_REUSE_IN_FIT_OR_SELECTION',
                'category': 'code_risk_indicator',
                'file': rel_path,
                'line': lineno,
                'symbol_or_call': f'{receiver or fn}.{fn}',
                'rationale': f'Call `{expr_src}` references held-out test data inside a fit operation.',
                'suggested_action': 'Restrict held-out test set exclusively to locked final evaluation.',
            })

    if ungrouped_splits and not grouped_splits:
        lineno, fn = ungrouped_splits[0]
        indicators.append({
            'rule_id': 'UNGROUPED_ROW_SPLIT',
            'category': 'code_risk_indicator',
            'file': rel_path,
            'line': lineno,
            'symbol_or_call': fn,
            'rationale': f'`{fn}` is used without patient-grouped splitting (`GroupKFold`/`GroupShuffleSplit`).',
            'suggested_action': 'Split by `patient_id` so repeated records from the same patient cannot cross partitions.',
        })

    if fit_calls and not mentions_fits_log:
        indicators.append({
            'rule_id': 'MISSING_FIT_MEMBERSHIP_LOGGING',
            'category': 'code_risk_indicator',
            'file': rel_path,
            'line': fit_calls[0][0],
            'symbol_or_call': fit_calls[0][1],
            'rationale': 'Script invokes `.fit()`/`.fit_transform()` without recording actual fitted `row_id` memberships (`fits.csv`).',
            'suggested_action': 'Emit `actual-fits.csv` (`experiment_id,operation,fold_id,row_id`) for every executed fit operation.',
        })

    for lineno, fn, in_loop, expr_src in transductive_calls:
        before_split = first_split_line is not None and lineno < first_split_line
        arg_text = expr_src.lower()
        uses_full_or_test = any(tok in arg_text for tok in ('full', 'all_data', 'df', 'x_all', 'x_test', 'test'))
        if before_split or (not in_loop and uses_full_or_test):
            indicators.append({
                'rule_id': 'GLOBAL_SURVIVAL_OR_GRAPH_LEAKAGE',
                'category': 'code_risk_indicator',
                'file': rel_path,
                'line': lineno,
                'symbol_or_call': fn,
                'rationale': (
                    f'Call `{expr_src}` constructs patient/sample graph edges or baseline survival hazards '
                    + ('before dataset splitting' if before_split else 'outside training fold loop on full/test data')
                    + ', risking transductive or baseline hazard leakage (PROBAST+AI Domain 4).'
                ),
                'suggested_action': 'Construct kNN/patient graphs and fit baseline survival hazards strictly inside training partitions.',
            })

    return indicators


def detect_code_language(rel_path):
    lower = str(rel_path).lower()
    if lower.endswith('.py'):
        return 'python'
    if lower.endswith('.r'):
        return 'r'
    if lower.endswith('.sas'):
        return 'sas'
    return 'other'


def analyze_r_or_sas_static(source_text, rel_path, language):
    """Static line-level probe for R (caret/tidymodels) and SAS (PROC MI/STDIZE/SURVEYSELECT) scripts."""
    indicators = []
    lines = source_text.splitlines()
    split_line = None
    for idx, line in enumerate(lines, start=1):
        low = line.lower()
        if any(tok in low for tok in ('initial_split', 'createdatapartition', 'group_initial_split', 'proc surveyselect')):
            split_line = split_line or idx
            if ('initial_split(' in low or 'createdatapartition(' in low or 'proc surveyselect' in low) and not any(
                g in low for g in ('group', 'patient_id', 'subject_id', 'cluster', 'samplingunit')
            ):
                indicators.append({
                    'rule_id': 'UNGROUPED_ROW_SPLIT',
                    'category': 'code_risk_indicator',
                    'detection_mode': f'static_{language}_probe',
                    'file': rel_path,
                    'line': idx,
                    'symbol_or_call': line.strip()[:80],
                    'rationale': f'{language.upper()} partitioning statement lacks explicit patient/cluster grouping.',
                    'suggested_action': 'Use `group_initial_split(..., group = patient_id)` in R or `SAMPLINGUNIT patient_id` in SAS.',
                })
    for idx, line in enumerate(lines, start=1):
        low = line.lower()
        if any(tok in low for tok in ('preprocess(', 'prep(', 'mice(', 'proc stdize', 'proc mi ')):
            if (split_line is not None and idx < split_line) or any(tok in low for tok in ('full_cohort', 'all_data', 'full_df', 'data=full', 'data = full')):
                indicators.append({
                    'rule_id': 'UNSCOPED_PREPROCESSING_FIT',
                    'category': 'code_risk_indicator',
                    'detection_mode': f'static_{language}_probe',
                    'file': rel_path,
                    'line': idx,
                    'symbol_or_call': line.strip()[:80],
                    'rationale': f'{language.upper()} preprocessing/imputation occurs before splitting or on the unsplit full cohort.',
                    'suggested_action': 'Estimate imputation and scaling strictly inside training partitions.',
                })
        if any(tok in low for tok in ('test_df', 'test_data', 'testing(', 'role="test"')) and any(
            fit_tok in low for fit_tok in ('tune_grid', 'train(', 'glm(', 'coxph(', 'proc logistic', 'proc phreg')
        ):
            indicators.append({
                'rule_id': 'TEST_SET_REUSE_IN_FIT_OR_SELECTION',
                'category': 'code_risk_indicator',
                'detection_mode': f'static_{language}_probe',
                'file': rel_path,
                'line': idx,
                'symbol_or_call': line.strip()[:80],
                'rationale': f'{language.upper()} modeling or tuning statement references held-out test data.',
                'suggested_action': 'Keep held-out test data isolated from model fitting and hyperparameter tuning.',
            })
    return indicators


def analyze_code_file(source_text, rel_path, laya_policy=None):
    """Run static AST/multi-language inspection and optional MedBias-Laya code-span audit."""
    lang = detect_code_language(rel_path)
    if lang == 'python':
        indicators = analyze_python_ast(source_text, rel_path)
    elif lang in ('r', 'sas'):
        indicators = analyze_r_or_sas_static(source_text, rel_path, lang)
    else:
        indicators = []

    if laya_policy is not None:
        req = {
            'format_version': 1,
            'kind': 'code_risk_audit',
            'model': 'medbias-laya-v1',
            'task': {
                'file_id': rel_path,
                'language': lang,
                'source_text': source_text,
            },
        }
        laya_res = lda.process_code_audit_request(req, laya_policy)
        existing_rules = {(ind['rule_id'], ind['line']) for ind in indicators}
        for ind in laya_res.get('indicators', []):
            start = ind.get('start', -1)
            length = ind.get('length', 0)
            quote = ind.get('quote', '')
            need(0 <= start and source_text[start:start + length] == quote, 'laya_code_offset_mismatch')
            if (ind['rule_id'], ind['line']) not in existing_rules:
                indicators.append(ind)
    return indicators


def verify_untrusted_check_script(source_text, rel_path):
    """Static AST check for untrusted generated audit scripts before sandbox runner."""
    try:
        tree = ast.parse(source_text, filename=rel_path)
    except SyntaxError as exc:
        return False, [f'syntax_error:line_{exc.lineno}']
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split('.')[0]
                if top in FORBIDDEN_UNTRUSTED_IMPORTS:
                    violations.append(f'forbidden_import:{top}@line_{node.lineno}')
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or '').split('.')[0]
            if top in FORBIDDEN_UNTRUSTED_IMPORTS:
                violations.append(f'forbidden_import_from:{top}@line_{node.lineno}')
        elif isinstance(node, ast.Call):
            fn = call_name(node.func)
            if fn in FORBIDDEN_UNTRUSTED_CALLS:
                violations.append(f'forbidden_call:{fn}@line_{node.lineno}')
    return not violations, violations


def render_markdown(report):
    lines = [
        '# Target Project Read-Only Audit Report',
        '',
        f"study_id: {report['study_id']}  state: {report['state']}  exit_code: {report['exit_code']}",
        f"authorized_root_unchanged: {report['authorized_root_unchanged']}  "
        f"execution_authorized: {report['execution_authorized']}  "
        f"scientific_acceptance: {report['scientific_acceptance']}",
        '',
        '## 1. Confirmed Deterministic Violations (`confirmed_violations`)',
    ]
    if report['confirmed_violations']:
        for item in report['confirmed_violations']:
            lines.append(
                f"- **{item['rule_id']}** (scope={item['scope']}, count={item.get('count', 1)}): "
                f"{item['detail']} -> Action: {item['suggested_action']}"
            )
    else:
        lines.append('- None detected in supplied manifests/runs.')

    lines.extend(['', '## 2. Static Code Risk Indicators (`code_risk_indicators`)'])
    if report['code_risk_indicators']:
        for ind in report['code_risk_indicators']:
            lines.append(
                f"- **{ind['rule_id']}** (`{ind['file']}:{ind['line']}`, `{ind['symbol_or_call']}`): "
                f"{ind['rationale']}"
            )
    else:
        lines.append('- None detected in declared code files.')

    lines.extend(['', '## 3. Insufficient Evidence & Pending Gates (`insufficient_evidence`)'])
    if report['insufficient_evidence']:
        for ins in report['insufficient_evidence']:
            lines.append(f"- **{ins['item_id']}** [{ins['status']}]: {ins['reason']}")
    else:
        lines.append('- None.')

    lines.extend(['', '## 4. Checked Rules With Zero Violations (`checked_no_violation_found`)'])
    if report['checked_no_violation_found']:
        lines.append('- ' + ', '.join(report['checked_no_violation_found']))
    else:
        lines.append('- None.')

    lines.extend(['', '## Limitations'])
    for lim in report['limitations']:
        lines.append(f'- {lim}')
    return '\n'.join(lines) + '\n'


def run_audit(args):
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError('output_dir_exists')
    started = time.monotonic()
    report = {
        'format_version': 1,
        'study_id': None,
        'state': 'BLOCKED',
        'exit_code': 2,
        'read_only_enforced': True,
        'authorized_root_unchanged': None,
        'execution_authorized': False,
        'scientific_acceptance': False,
        'confirmed_violations': [],
        'code_risk_indicators': [],
        'insufficient_evidence': [],
        'checked_no_violation_found': [],
        'generated_scripts_gate': [],
        'manifest_audit_summary': None,
        'run_reconciliation_summary': None,
        'diagnostics': [],
        'elapsed_seconds': None,
        'limitations': [
            'Confirmed violations apply only to the supplied manifests and run registry; exporter completeness must be verified separately.',
            'Static AST code risk indicators identify structural leakage patterns without executing project code.',
            'Generated check scripts are treated as untrusted: without an explicit external OS sandbox runner, they stop at AWAITING_SANDBOX_RUNNER.',
            'Zero violations in checked rules do not establish overall low risk of bias or clinical validity.',
        ],
    }

    before_snapshot = None
    auth_root = None
    try:
        spec = load_strict_json(args.spec)
        need(isinstance(spec, dict) and spec.get('format_version') == 1, 'invalid_spec_version')
        need(spec.get('read_only') is True, 'read_only_must_be_true')
        need(study.ident(spec.get('study_id')), 'invalid_study_id')
        report['study_id'] = spec['study_id']

        raw_root = spec.get('authorized_root')
        need(isinstance(raw_root, str) and bool(raw_root.strip()), 'missing_authorized_root')
        auth_root = (args.spec.resolve().parent / raw_root).resolve()
        need(auth_root.is_dir(), 'authorized_root_not_found')
        need(not out.is_relative_to(auth_root) and not auth_root.is_relative_to(out),
             'output_dir_overlaps_authorized_root')
        out.mkdir(parents=True, exist_ok=False, mode=0o700)

        before_snapshot = snapshot_tree(auth_root)

        # 1. Static AST / Multi-language + optional MedBias-Laya code probe on declared code_files
        laya_pol = lda.load_policy(args.laya_policy) if getattr(args, 'laya_policy', None) is not None else None
        code_files = spec.get('code_files', [])
        need(isinstance(code_files, list), 'invalid_code_files')
        for cf in code_files:
            need(isinstance(cf, dict) and {'path', 'sha256'} <= set(cf), 'invalid_code_file_entry')
            cpath = resolve_inside(auth_root, cf['path'])
            need(cpath.is_file(), f"code_file_missing:{cf['path']}")
            raw_code = read_bounded(cpath, MAX_CODE_BYTES, 'code_file_size_limit')
            need(hashlib.sha256(raw_code).hexdigest() == cf['sha256'],
                 f"code_file_hash_mismatch:{cf['path']}")
            indicators = analyze_code_file(raw_code.decode('utf-8'), cf['path'], laya_policy=laya_pol)
            report['code_risk_indicators'].extend(indicators)

        # 2. Untrusted generated scripts safety gate
        gen_scripts = spec.get('generated_check_scripts', [])
        need(isinstance(gen_scripts, list), 'invalid_generated_check_scripts')
        for gs in gen_scripts:
            need(isinstance(gs, dict) and {'id', 'path', 'sha256'} <= set(gs),
                 'invalid_generated_script_entry')
            gpath = resolve_inside(auth_root, gs['path'])
            need(gpath.is_file(), f"generated_script_missing:{gs['path']}")
            raw_gs = read_bounded(gpath, MAX_CODE_BYTES, 'generated_script_size_limit')
            need(hashlib.sha256(raw_gs).hexdigest() == gs['sha256'],
                 f"generated_script_hash_mismatch:{gs['path']}")
            safe, ast_issues = verify_untrusted_check_script(raw_gs.decode('utf-8'), gs['path'])
            if not safe:
                gate_entry = {
                    'id': gs['id'],
                    'path': gs['path'],
                    'execution_state': 'REJECTED_STATIC_SAFETY',
                    'static_violations': ast_issues,
                }
                report['generated_scripts_gate'].append(gate_entry)
                report['confirmed_violations'].append({
                    'rule_id': 'UNSAFE_GENERATED_CHECK_SCRIPT',
                    'scope': 'generated_script',
                    'count': len(ast_issues),
                    'detail': f"Generated script `{gs['path']}` failed static safety check: {', '.join(ast_issues)}",
                    'suggested_action': 'Remove network, subprocess, dynamic eval/exec, and destructive filesystem calls.',
                })
            elif args.sandbox_runner is None:
                gate_entry = {
                    'id': gs['id'],
                    'path': gs['path'],
                    'execution_state': 'AWAITING_SANDBOX_RUNNER',
                    'static_violations': [],
                    'note': 'Subprocess timeout is not an OS sandbox; stopping at AWAITING_SANDBOX_RUNNER.',
                }
                report['generated_scripts_gate'].append(gate_entry)
                report['insufficient_evidence'].append({
                    'item_id': f"generated_script:{gs['id']}",
                    'status': 'AWAITING_SANDBOX_RUNNER',
                    'reason': f"Script `{gs['path']}` passed static AST checks but no external OS sandbox runner (`--sandbox-runner`) was provided.",
                })
            else:
                runner_path = args.sandbox_runner.resolve()
                need(runner_path.is_file(), 'sandbox_runner_not_found')
                script_out = out / 'sandbox-runs' / gs['id']
                script_out.mkdir(parents=True, exist_ok=False)
                proc = subprocess.run(
                    [sys.executable, str(runner_path), 'run-readonly-check',
                     str(gpath), '--authorized-root', str(auth_root), '--out', str(script_out)],
                    capture_output=True, text=True, timeout=30, check=False,
                )
                gate_entry = {
                    'id': gs['id'],
                    'path': gs['path'],
                    'execution_state': 'EXECUTED_IN_SANDBOX' if proc.returncode == 0 else 'SANDBOX_CHECK_FAILED',
                    'returncode': proc.returncode,
                    'static_violations': [],
                }
                report['generated_scripts_gate'].append(gate_entry)
                if proc.returncode != 0:
                    report['confirmed_violations'].append({
                        'rule_id': 'SANDBOX_CHECK_SCRIPT_FAILED',
                        'scope': 'generated_script',
                        'count': 1,
                        'detail': f"Sandbox check `{gs['id']}` exited with code {proc.returncode}.",
                        'suggested_action': 'Inspect sandbox output in dedicated output directory.',
                    })

        # 3. Deterministic study.py plan + planned manifest audit
        planned_fits_path = resolve_inside(auth_root, spec['planned_fits'])
        need(planned_fits_path.is_file(), 'planned_fits_missing')
        if spec.get('plan'):
            plan_path = resolve_inside(auth_root, spec['plan'])
            need(plan_path.is_file(), 'plan_missing')
        else:
            study_cfg_path = resolve_inside(auth_root, spec['study_config'])
            need(study_cfg_path.is_file(), 'study_config_missing')
            plan_dir = out / 'compiled-plan'
            study.compile_plan(study_cfg_path, plan_dir)
            plan_path = plan_dir / 'plan.json'

        plan_obj, _ = study.read_plan(plan_path)
        need(plan_obj['study_id'] == spec['study_id'], 'study_id_mismatch_with_study_json')

        rows_path = (
            resolve_inside(auth_root, spec['rows'])
            if spec.get('rows')
            else Path(plan_obj['frozen_manifests']['rows']['path'])
        )
        folds_path = (
            resolve_inside(auth_root, spec['folds'])
            if spec.get('folds')
            else Path(plan_obj['frozen_manifests']['folds']['path'])
        )
        need(rows_path.resolve().is_relative_to(auth_root) and folds_path.resolve().is_relative_to(auth_root),
             'manifest_outside_authorized_root')
        need(rows_path.is_file() and folds_path.is_file(), 'manifest_file_missing')

        audit_res = study.audit(plan_path, rows_path, folds_path, planned_fits_path, mode='planned')
        save_json(out / 'planned-audit.json', audit_res)
        report['manifest_audit_summary'] = {
            'ok': audit_res['ok'],
            'records': audit_res['records'],
            'split_counts': audit_res['split_counts'],
            'violations': audit_res['violations'],
        }
        for rule_id, count in audit_res['violations'].items():
            report['confirmed_violations'].append({
                'rule_id': rule_id,
                'scope': 'manifest_audit',
                'count': count,
                'detail': f'Deterministic manifest audit detected {count} violation(s) for `{rule_id}`.',
                'suggested_action': audit_res['next_actions'].get(rule_id, 'Fix manifest/pipeline per study contract.'),
            })
        for rule_id in ALL_DETERMINISTIC_RULES:
            if rule_id not in audit_res['violations']:
                report['checked_no_violation_found'].append(rule_id)

        # 4. Run registry reconciliation (if runs_dir provided)
        if spec.get('runs_dir'):
            runs_dir = resolve_inside(auth_root, spec['runs_dir'])
            need(runs_dir.is_dir(), 'runs_dir_not_found')
            recon = study.reconcile(plan_path, runs_dir)
            save_json(out / 'run-reconciliation.json', recon)
            report['run_reconciliation_summary'] = {
                'ok': recon['ok'],
                'attempts': recon['attempts'],
                'issues': recon['issues'],
            }
            for att in recon['attempts']:
                if att['status'] == 'NOT_RUN':
                    report['insufficient_evidence'].append({
                        'item_id': f"task:{att['task_id']}",
                        'status': 'NOT_RUN',
                        'reason': f"Planned experiment `{att['task_id']}` has no registered execution attempt.",
                    })
                    report['confirmed_violations'].append({
                        'rule_id': 'omitted_planned_run',
                        'scope': 'run_reconciliation',
                        'count': 1,
                        'detail': f"Planned task `{att['task_id']}` is NOT_RUN in the supplied registry.",
                        'suggested_action': 'Execute or explicitly account for the omitted planned experiment before reporting results.',
                    })
                elif att['status'] == 'RUNNING':
                    report['insufficient_evidence'].append({
                        'item_id': f"run:{att['run_id']}",
                        'status': 'RUNNING',
                        'reason': f"Run `{att['run_id']}` for `{att['task_id']}` lacks a terminal finish.json.",
                    })
                elif att['status'] in {'FAILED', 'ABORTED', 'INVALID'}:
                    report['confirmed_violations'].append({
                        'rule_id': f"non_succeeded_run:{att['status']}",
                        'scope': 'run_reconciliation',
                        'count': 1,
                        'detail': f"Run `{att['run_id']}` for `{att['task_id']}` ended in status `{att['status']}` (exit_code={att['exit_code']}).",
                        'suggested_action': 'Retain failed/aborted attempt in reconciliation table; do not silently omit.',
                    })
                for iss in att.get('issues', []):
                    if iss != 'planned task has no registered attempt':
                        report['confirmed_violations'].append({
                            'rule_id': 'run_reconciliation_issue',
                            'scope': 'run_reconciliation',
                            'count': 1,
                            'detail': f"{att['run_id'] or att['task_id']}: {iss}",
                            'suggested_action': 'Resolve executed audit, lock, or metric discrepancy.',
                        })
        else:
            report['insufficient_evidence'].append({
                'item_id': 'runs_dir',
                'status': 'NOT_PROVIDED',
                'reason': 'No run registry (`runs_dir`) was supplied; executed fit logs and run reconciliation were not evaluated.',
            })

        after_snapshot = snapshot_tree(auth_root)
        report['authorized_root_unchanged'] = (before_snapshot == after_snapshot)
        need(report['authorized_root_unchanged'], 'authorized_root_modified_during_readonly_audit')

        has_findings = bool(
            report['confirmed_violations']
            or report['code_risk_indicators']
            or report['insufficient_evidence']
        )
        report['state'] = 'FINDINGS_REPORTED' if has_findings else 'AWAITING_SCIENTIFIC_REVIEW'
        report['exit_code'] = 1 if report['confirmed_violations'] else 0

    except (AuditContractError, study.InputError) as exc:
        if auth_root is not None and before_snapshot is not None:
            report['authorized_root_unchanged'] = (before_snapshot == snapshot_tree(auth_root))
        report.update(state='BLOCKED', exit_code=2)
        report['diagnostics'].append(str(exc))
    except Exception as exc:
        if auth_root is not None and before_snapshot is not None:
            report['authorized_root_unchanged'] = (before_snapshot == snapshot_tree(auth_root))
        report.update(state='BLOCKED', exit_code=2)
        report['diagnostics'].append('audit_error:' + type(exc).__name__)

    report['elapsed_seconds'] = round(time.monotonic() - started, 4)
    if out.is_dir():
        save_json(out / 'project_audit.json', report)
        (out / 'project_audit.md').write_text(render_markdown(report), encoding='utf-8')
        artifacts = {
            p.relative_to(out).as_posix(): sha256(p)
            for p in sorted(out.rglob('*'))
            if p.is_file() and p.name not in {'.completion.tmp', 'completion.json'}
        }
        save_json(
            out / '.completion.tmp',
            {'format_version': 1, 'state': report['state'], 'exit_code': report['exit_code'], 'artifacts': artifacts},
        )
        (out / '.completion.tmp').replace(out / 'completion.json')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True, help='Path to project_audit_spec.json')
    parser.add_argument('--out', type=Path, required=True, help='New output directory outside authorized_root')
    parser.add_argument('--sandbox-runner', type=Path, help='Optional explicit external OS sandbox runner')
    parser.add_argument('--laya-policy', type=Path, help='Optional MedBias-Laya policy JSON for span-anchored multi-language code risk auditing')
    args = parser.parse_args(argv)
    try:
        report = run_audit(args)
    except (OSError, ValueError):
        print(json.dumps({'state': 'BLOCKED', 'error': 'input_or_output_error', 'exit_code': 2}))
        return 2
    print(json.dumps({
        'state': report['state'],
        'exit_code': report['exit_code'],
        'confirmed_violations': len(report['confirmed_violations']),
        'code_risk_indicators': len(report['code_risk_indicators']),
        'authorized_root_unchanged': report['authorized_root_unchanged'],
    }))
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
