"""Independent CLI probes; all mutations are scratch synthetic files only."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True, help='New scratch directory; only synthetic files are written')
args = parser.parse_args()
ROOT = args.out.resolve()
ROOT.mkdir(parents=True, exist_ok=False)
REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / 'skills/medical-research-harness/scripts/study.py'
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPT.parent))
from test_study import walkthrough

FIX = ROOT / 'synthetic-tests'
DEMO = ROOT / 'reference-tests'
walkthrough(FIX)
walkthrough(DEMO)
OUT = ROOT / 'independent-probes'
OUT.mkdir()
# These lock-rejection probes must fail BEFORE invoking any external validator.
LAB = ROOT / 'validator-must-not-run.py'
# Simulated approvals and lock belong only to this isolated software fixture.
plan_fixture = json.loads((FIX / 'plan/plan.json').read_text())
(FIX / 'protocol-lock.json').write_text(json.dumps({
    'files': [plan_fixture['protocol'], *plan_fixture['frozen_manifests'].values()],
    'approved_by': 'SYNTHETIC SOFTWARE FIXTURE ONLY'
}))
for entry in plan_fixture['tasks']:
    task_path = FIX / 'plan' / entry['path']
    task_fixture = json.loads(task_path.read_text())
    task_fixture['approval'] = {'status': 'APPROVED', 'by': 'SYNTHETIC FIXTURE ONLY', 'evidence': 'not human approval'}
    task_path.write_text(json.dumps(task_fixture))
PLAN = FIX / 'plan/plan.json'
RUNS = FIX / 'simulated-runs'
START = RUNS / 'synthetic-run-0/start.json'
FINISH = RUNS / 'synthetic-run-1/finish.json'
AUDIT = RUNS / 'synthetic-run-0/audit.json'
LOCK = FIX / 'protocol-lock.json'
TASK = FIX / 'plan/SYNTHETIC-DEMO-baseline.json'
paths = [PLAN, START, FINISH, AUDIT, LOCK, TASK, FIX / 'rows.csv', FIX / 'folds.csv']
originals = {p: p.read_bytes() for p in paths}
records = []
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT))
MARKER = 'SYNTHETIC_DIAGNOSTIC_MUST_REMAIN_PRIVATE'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def monitored():
    files = list((REPO / 'skills/medical-research-harness').rglob('*')) + list(DEMO.rglob('*'))
    files += [REPO / 'AGENTS.md', REPO / 'README.md', REPO / 'system_design.md']
    return {str(p): digest(p) for p in sorted(files) if p.is_file()}

before = monitored()
(ROOT / 'protected-files-before.json').write_text(json.dumps(before, indent=2))

def read(p):
    return json.loads(p.read_text())

def write(p, data):
    assert p.is_relative_to(ROOT)
    p.write_text(json.dumps(data))

def reset():
    for p, data in originals.items():
        p.write_bytes(data)

def run(tag, args, expected, issue=None):
    dest = OUT / tag
    command = [sys.executable, str(SCRIPT), *map(str, args), '--out', str(dest)]
    proc = subprocess.run(command, env=ENV, text=True, capture_output=True, check=False)
    record = dict(case=tag, command=command, expected_exit=expected, exit_code=proc.returncode,
                  stdout=proc.stdout, stderr=proc.stderr)
    records.append(record)
    assert proc.returncode == expected, record
    assert not proc.stderr and MARKER not in proc.stdout, record
    summary = dest / 'summary.json'
    if summary.exists():
        value = read(summary)
        assert MARKER not in summary.read_text() and MARKER not in (dest / 'summary.md').read_text()
        if issue:
            assert any(issue in x for x in value['issues']), record
        return value
    return read(dest) if dest.is_file() else None

def summary(tag, expected=1, issue=None, plan=PLAN, runs=RUNS):
    return run(tag, ['summarize', plan, '--runs', runs], expected, issue)

def preflight(tag, expected):
    result = run(tag, ['preflight', PLAN, '--audit', FIX / 'audit-clean.json', '--lab', LAB], expected)
    assert 'task lock must bind' in json.loads(records[-1]['stdout'])['error']
    return result

try:
    summary('baseline', 0)
    summary('reference-fixture-current-code', 0, plan=DEMO / 'plan/plan.json', runs=DEMO / 'simulated-runs')
    for kind in ('omit', 'add', 'change'):
        reset()
        plan = read(PLAN)
        if kind == 'omit':
            plan['tasks'].pop()
        elif kind == 'add':
            plan['tasks'].append(copy.deepcopy(plan['tasks'][0]))
        else:
            task = read(TASK)
            task['seed'] += 1
            write(TASK, task)
            core = {k: v for k, v in task.items() if k not in {'status', 'approval'}}
            plan['tasks'][0]['design_sha256'] = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        write(PLAN, plan)
        summary('source-experiment-' + kind, 2)
    for key in ('rows', 'folds'):
        reset()
        path = FIX / (key + '.csv')
        path.write_bytes(path.read_bytes() + b'\n')
        summary('frozen-original-' + key + '-drift', 2)
        for action in ('omit', 'wrong-path', 'wrong-hash'):
            reset()
            locked = read(LOCK)
            target = read(PLAN)['frozen_manifests'][key]
            if action == 'omit':
                locked['files'] = [x for x in locked['files'] if x['path'] != target['path']]
            else:
                entry = next(x for x in locked['files'] if x['path'] == target['path'])
                entry['path' if action == 'wrong-path' else 'sha256'] = str(FIX / 'other.csv') if action == 'wrong-path' else '0' * 64
            write(LOCK, locked)
            preflight('preflight-lock-' + key + '-' + action, 2)
            start = read(START)
            start['protocol'] = locked
            write(START, start)
            summary('run-lock-' + key + '-' + action, issue='run lock does not bind')
        reset()
        candidate = OUT / ('alternate-' + key + '.csv')
        if key == 'folds':
            candidate.write_bytes((FIX / 'changed-folds.csv').read_bytes())
        else:
            candidate.write_bytes((FIX / 'rows.csv').read_bytes().replace(b'SYNTHETIC_PRIVATE_P0', b'SYNTHETIC_PRIVATE_P99'))
        report = run('audit-alternate-' + key, ['audit', PLAN, '--mode', 'executed', '--experiment-id', 'baseline', '--run-id', 'synthetic-run-0', '--rows', candidate if key == 'rows' else FIX / 'rows.csv', '--folds', candidate if key == 'folds' else FIX / 'folds.csv', '--fits', FIX / ('changed-fits.csv' if key == 'folds' else 'executed-fits.csv')], 1)
        assert report['violations'] == {'frozen_' + key + '_changed': 1}
        old = read(AUDIT)
        old['inputs'][key] = {'path': str(candidate), 'sha256': digest(candidate)}
        write(AUDIT, old)
        summary('reconcile-alternate-' + key, issue='executed manifest audit is invalid')
    for tag, value in [('missing', None), ('null', None), ('bool', False), ('list', []), ('dict', {}), ('int', 0)]:
        reset()
        start = read(START)
        start.pop('git_status')
        if tag != 'missing':
            start['git_status'] = value
        write(START, start)
        summary('git-status-' + tag, issue='code state is missing or invalid')
    for tag, value in [('missing', None), ('null', None), ('short', 'a'*63), ('long', 'a'*65), ('uppercase', 'A'*64), ('nonhex', 'g'*64), ('list', []), ('valid', 'a'*64)]:
        reset()
        start = read(START)
        start['git_status'] = ' M synthetic.py'
        if tag != 'missing':
            start['code_snapshot_sha256'] = value
        write(START, start)
        summary('dirty-snapshot-' + tag, 0 if tag == 'valid' else 1)
    for status in ('FAILED', 'ABORTED', 'INVALID'):
        for tag, value in [('missing', None), ('null', None), ('bool', True), ('str', '1'), ('float', 1.0), ('zero', 0), ('nonzero', 7), ('signal', -9)]:
            reset()
            finish = {'status': status, 'reason': MARKER}
            if tag != 'missing':
                finish['exit_code'] = value
            write(FINISH, finish)
            good = tag in ('nonzero', 'signal')
            result = summary(status.lower() + '-exit-' + tag, 0 if good else 1)
            row = result['attempts'][1]
            assert row['status'] == status and row['metric'] is None
            if good:
                assert row['exit_code'] == value and row['finish_record'] == str(FINISH) and row['diagnostic']
                assert result['source_sha256']['synthetic-run-1']['finish'] == digest(FINISH)
        for tag, reason in [('missing', None), ('dict', {}), ('null', None), ('string', MARKER)]:
            reset()
            finish = {'status': status, 'exit_code': 1}
            if tag != 'missing':
                finish['reason'] = reason
            write(FINISH, finish)
            summary(status.lower() + '-reason-' + tag, 0 if tag in ('null', 'string') else 1)
    reset()
    FINISH.unlink()
    result = summary('unfinished-preserved')
    assert result['attempts'][1]['status'] == 'RUNNING'
    reset()
    FINISH.write_text('{"reason":"' + MARKER + '", broken}')
    summary('malformed-private-diagnostic', 2)
    reset()
    result = summary('restored-baseline', 0)
finally:
    reset()
    (ROOT / 'probe-results.json').write_text(json.dumps(records, indent=2))
    after = monitored()
    (ROOT / 'protected-files-after.json').write_text(json.dumps(after, indent=2))
    assert before == after, 'Protected repository or persistent synthetic evidence changed'
print(json.dumps({'independent_checks': len(records), 'protected_files_unchanged': len(before)}))
