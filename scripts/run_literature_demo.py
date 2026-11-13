#!/usr/bin/env python3
"""Record exact local code identity, execute literature entry, verify artifacts.

This is a public-demo runner, not a sandbox or scientific approval. Parent
artifacts are immutable: --out and the child's output must not already exist.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--execute-models', action='store_true')
    p.add_argument('--allow-public-egress', action='store_true')
    a = p.parse_args()
    if a.execute_models and not a.allow_public_egress:
        p.error('real calls require --allow-public-egress')
    a.out.mkdir(parents=True, exist_ok=False)
    scripts = ROOT / 'skills/medical-research-harness/scripts'
    entry = 'literature.py' if a.execute_models else 'literature_offline.py'
    cmd = [sys.executable, str(scripts / entry), '--manifest', str(a.manifest.resolve()),
           '--config', str(a.config.resolve()), '--out', str((a.out / 'output').resolve())]
    if a.execute_models:
        cmd.extend(['--execute-models', '--allow-public-egress'])
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    files = [scripts / name for name in ['literature.py', 'decision_agent.py',
              'literature_model_adapter.py', 'hermes_decision_adapter.py',
              'literature_recovery.py', 'literature_offline.py']]
    files += [scripts.parent / 'assets/literature_questions.json', Path(__file__)]
    identity = {'git_commit': git('rev-parse', 'HEAD'), 'git_status': git('status', '--short'),
                'python': sys.executable, 'python_version': sys.version,
                'code_sha256': {str(f.relative_to(ROOT)): sha(f) for f in files},
                'manifest_sha256': sha(a.manifest), 'config_sha256': sha(a.config),
                'command': cmd, 'random_seed': 'not_applicable: deterministic retrieval; model backend sampling not controlled',
                'scientific_acceptance': False, 'status': 'STARTED'}
    (a.out / 'identity.json').write_text(json.dumps(identity, ensure_ascii=False, indent=2) + '\n')
    start = time.monotonic()
    with (a.out / 'stdout.log').open('wb') as stdout, (a.out / 'stderr.log').open('wb') as stderr:
        run = subprocess.run(cmd, cwd=ROOT, stdout=stdout, stderr=stderr)
    verification = {'exit_code': run.returncode, 'elapsed_seconds': time.monotonic() - start,
                    'completion_verified': False, 'scientific_acceptance': False}
    completion_path = a.out / 'output/completion.json'
    if completion_path.exists():
        c = json.loads(completion_path.read_text())
        checks = {name: (a.out / 'output' / name).is_file() and sha(a.out / 'output' / name) == expected
                  for name, expected in c['artifacts'].items()}
        verification.update(artifact_checks=checks, state=c['state'],
                            completion_verified=bool(checks) and all(checks.values()) and c['exit_code'] == run.returncode)
    (a.out / 'finish.json').write_text(json.dumps(verification, indent=2) + '\n')
    print(json.dumps({'out': str(a.out.resolve()), **verification}), flush=True)
    return run.returncode if verification['completion_verified'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
