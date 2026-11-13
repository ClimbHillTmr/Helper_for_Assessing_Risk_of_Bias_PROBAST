#!/usr/bin/env python3
"""Restore only hash-verified per-source literature artifacts; never calls models."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/medical-research-harness/scripts'))
from literature_recovery import prepare_resume
import literature_offline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True,
                        help='original literature output directory containing run_state.json')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--config', type=Path,
                        help='required for actual offline continuation')
    parser.add_argument('--restore-only', action='store_true',
                        help='legacy artifact copy only; never claims continuation')
    parser.add_argument('--out', type=Path, required=True,
                        help='new, non-existing recovery directory')
    args = parser.parse_args()
    if not args.restore_only:
        if args.config is None:
            parser.error('--config required for continuation; use --restore-only for a copy')
        return literature_offline.main(['--manifest', str(args.manifest),
            '--config', str(args.config), '--out', str(args.out),
            '--resume-from', str(args.run)])
    try:
        result = prepare_resume(args.run, args.manifest, args.out)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({'state': 'BLOCKED', 'reason': str(exc),
                          'models_called': False, 'network_used': False}))
        return 2
    print(json.dumps({'state': result['run_state'], 'operation': 'artifact_copy_only', 'out': str(args.out.resolve()),
                      'sources': len(result['sources']), 'models_called': False,
                      'network_used': False}))
    return 0 if result['run_state'] == 'COMPLETED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
