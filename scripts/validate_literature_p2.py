#!/usr/bin/env python3
"""Run offline P2 acceptance with persistent real-interruption and fault evidence.

No network or model backend is used. Synthetic subprocesses are signalled;
public JATS snapshots are only read from the existing local manifest.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_literature_offline_resume import OfflineResume, digest
sys.path.insert(0, str(ROOT / 'skills/medical-research-harness/scripts'))
import literature as core
import literature_offline as offline


def snapshot(root):
    return {p.relative_to(root).as_posix(): digest(p)
            for p in sorted(root.rglob('*')) if p.is_file()}


def check_completion(root):
    c = json.loads((root / 'completion.json').read_text())
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
              and p != root / 'completion.json'}
    assert set(c['artifacts']) == actual, root
    assert all(digest(root / name) == expected for name, expected in c['artifacts'].items()), root
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--manifest', type=Path,
                        default=ROOT / 'build/literature-public-demo-v2/manifest.json')
    parser.add_argument('--config', type=Path,
                        default=ROOT / 'build/literature-public-demo-v2/config-two-routes.json')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    out = args.out.resolve()
    frozen = ROOT / 'build/literature-live-v1'
    frozen_before = snapshot(frozen)
    checks = []
    commands = []

    def command(argv, name, expected=0):
        run = subprocess.run([sys.executable, *map(str, argv)], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        (out / (name + '.stdout.log')).write_text(run.stdout)
        (out / (name + '.stderr.log')).write_text(run.stderr)
        commands.append(dict(command=[sys.executable, *map(str, argv)], returncode=run.returncode))
        assert run.returncode == expected, (name, run.stdout, run.stderr)
        return run

    test_commands = [
        'skills/medical-research-harness/scripts/test_check_bundle.py',
        'skills/medical-research-harness/scripts/test_study.py',
        'skills/medical-research-harness/scripts/test_workflow.py',
        'skills/medical-research-harness/scripts/test_decision_agent.py',
        'skills/medical-research-harness/scripts/test_hermes_decision_adapter.py',
        'skills/medical-research-harness/scripts/test_literature.py',
        'skills/medical-research-harness/scripts/test_literature_model_adapter.py',
        'skills/medical-research-harness/scripts/test_literature_recovery.py',
        'tests/test_literature_boundaries.py', 'tests/test_literature_p2_repairs.py',
        'tests/test_literature_offline_resume.py',
        'skills/medical-research-harness/scripts/test_literature_real_snapshots.py',
    ]
    for i, test in enumerate(test_commands):
        command([test], 'test-' + str(i))
        checks.append(dict(check=test, passed=True))
    command(['tests/review_probes.py', '--out', out / 'review-probes'], 'review-probes')
    checks.append(dict(check='review_probes', passed=True))
    helper = OfflineResume()
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGKILL):
        root = out / signal.Signals(signum).name; root.mkdir()
        manifest, config, old = helper.start_interrupted(root, signum)
        before = snapshot(old)
        resumed = root / 'resumed'
        result = helper.resume(manifest, config, old, resumed)
        (root / 'resume.stdout.log').write_text(result.stdout)
        (root / 'resume.stderr.log').write_text(result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads((resumed / 'report.json').read_text())
        assert report['resume']['reused_sources'] == ['s1']
        assert report['resume']['continued_sources'] == ['s2', 's3']
        assert report['resume']['restored_index_sources'] == ['s1', 's2']
        assert report['run_state'] == 'COMPLETED' and report['request_count'] == 0
        assert snapshot(old) == before
        check_completion(resumed)
        if signum != signal.SIGKILL: check_completion(old)
        checks.append(dict(check='real_interrupt:' + signal.Signals(signum).name,
                           passed=True, reused=['s1'], continued=['s2', 's3'], old_unchanged=True))
    # Persistent failure demonstrations; input clones are deliberately mutated.
    base = out / 'SIGTERM'
    for fault in ('missing', 'tamper', 'empty', 'identity', 'unregistered'):
        clone = out / ('fault-input-' + fault); shutil.copytree(base / 'interrupted', clone)
        state = json.loads((clone / 'run_state.json').read_text())
        (clone / 'completion.json').unlink()  # emulate a non-finalized interrupted run
        if fault == 'missing': (clone / 'index.s1.json').unlink()
        elif fault == 'tamper': (clone / 'index.s1.json').write_text('tampered')
        elif fault == 'empty': state['sources']['s1']['artifacts'] = {}
        elif fault == 'identity': state['identity']['questions_sha256'] = '0' * 64
        else: (clone / 'source.s3.json').write_text('{}')
        (clone / 'run_state.json').write_text(json.dumps(state))
        result = helper.resume(base / 'manifest.json', base / 'config.json', clone, out / ('fault-output-' + fault))
        assert result.returncode == 2, fault
        report = json.loads((out / ('fault-output-' + fault) / 'report.json').read_text())
        assert report['run_state'] == 'BLOCKED' and not report['resume']['continued_sources']
        assert not list((out / ('fault-output-' + fault)).glob('index.*.json'))
        check_completion(out / ('fault-output-' + fault))
        checks.append(dict(check='fault:' + fault, passed=True, diagnostic=report['diagnostics']))
    demo = out / 'public-demo'
    command(['scripts/run_literature_demo.py', '--manifest', args.manifest,
             '--config', args.config, '--out', demo], 'public-demo')
    command(['scripts/verify_literature_run.py', '--run', demo,
             '--out', out / 'public-parent-verification.json'], 'public-verification')
    command(['scripts/resume_literature_run.py', '--run', demo / 'output',
             '--manifest', args.manifest, '--config', args.config,
             '--out', out / 'public-resumed'], 'public-resume')
    check_completion(demo / 'output'); check_completion(out / 'public-resumed')
    assert frozen_before == snapshot(frozen), 'frozen_run_changed'
    checks.append(dict(check='frozen_literature_live_v1_all_files_unchanged', passed=True,
                       files=len(frozen_before)))
    summary = dict(format_version=1, state='COMPLETED', scope='offline_preparation_only',
                   models_called=False, attachments_downloaded=False, network_used=False,
                   scientific_acceptance=False, checks=checks, commands=commands,
                   code_identity=offline.identity(args.manifest, args.config),
                   public_sources=json.loads((demo / 'output/report.json').read_text())['sources'])
    (out / 'validation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (out / 'validation.md').write_text('# P2 offline acceptance\n\n'
        'Real SIGTERM/SIGINT/SIGKILL interruption and continuation passed. '
        'Synthetic faults remained BLOCKED. No model/network/attachment execution.\n\n'
        + '\n'.join('- PASS ' + c['check'] for c in checks) + '\n')
    (out / 'completion.json').write_text(json.dumps(dict(format_version=1, state='COMPLETED',
        artifacts=snapshot(out)), indent=2) + '\n')
    check_completion(out)
    print(json.dumps(dict(out=str(out), passed=True, checks=len(checks), models_called=False,
                          frozen_unchanged=True)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
