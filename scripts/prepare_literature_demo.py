#!/usr/bin/env python3
"""Prepare the attributed public demo from verified existing JATS snapshots.

No downloads or model calls. Output is new; metadata comes from source records,
never the historical hand-authored claims. Reacquire snapshots from the source
retrieval_url if absent and independently recheck their rights/version.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshots', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--provider', default='magpie')
    parser.add_argument('--model', default='codex/gpt-6.1-sol')
    args = parser.parse_args()
    metadata = json.loads((ROOT / 'docs/m1/pilot-v1/materials.json').read_text())
    sources = []
    payloads = []
    for item in metadata['sources']:
        filename = item['id'] + '.xml'
        raw = (args.snapshots / filename).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != item['original_xml_sha256']:
            raise ValueError('public snapshot differs from source registration: ' + item['id'])
        sources.append({
            'id': item['id'], 'doi': item['doi'], 'title': item['title'],
            'license_url': item['license_url'],
            'rights_basis': 'Article JATS permissions CC BY 4.0; attribution in docs/m1/pilot-v1/materials.json. Public prose only; supplements not acquired.',
            'path': filename, 'sha256': digest,
        })
        payloads.append((filename, raw))
    interpreter = str(Path(args.python).absolute())
    adapter = str(ROOT / 'skills/medical-research-harness/scripts/literature_model_adapter.py')
    config = {'format_version': 1, 'max_requests': 30, 'timeout_seconds': 120,
              'models': {role: {'provider': args.provider, 'model': args.model,
                               'command': [interpreter, adapter]}
                         for role in ('analysis', 'reviewer')}}
    args.out.mkdir(parents=True, exist_ok=False)
    for filename, raw in payloads:
        (args.out / filename).write_bytes(raw)
    for filename, value in [('manifest.json', {'format_version': 1, 'sources': sources}),
                            ('config.json', config)]:
        (args.out / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'out': str(args.out.absolute()), 'sources': len(sources),
                      'models_executed': False}))


if __name__ == '__main__':
    main()
