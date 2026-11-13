#!/usr/bin/env python3
"""Regression check section paths against frozen public-run paragraph identities."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'skills/medical-research-harness/scripts'
sys.path.insert(0, str(SCRIPTS))
import literature

MANIFEST = ROOT / 'build/literature-public-demo-v2/manifest.json'
FROZEN_INDEX = ROOT / 'build/literature-live-v1/output'


def check():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    result = {}
    for source in manifest['sources']:
        raw = (MANIFEST.parent / source['path']).read_bytes()
        meta, paragraphs = literature.parse_jats(raw, source['id'])
        prior = json.loads((FROZEN_INDEX / f"index.{source['id']}.json").read_text())
        prior_by_id = {p['id']: p for p in prior['paragraphs']}
        assert all(p['id'] in prior_by_id for p in paragraphs), source['id']
        assert all(p['sha256'] == prior_by_id[p['id']]['sha256']
                   and p['text'] == prior_by_id[p['id']]['text']
                   for p in paragraphs), source['id']
        assert len({p['id'] for p in paragraphs}) == len(paragraphs)
        assert all(p['text'].strip() not in {
            'Screening flowchart for research subjects.',
            'Patient, fracture characteristics and mortality rates (N = 74,396 a). Values are count (%) unless otherwise specified'
        } for p in paragraphs)
        assert all(isinstance(p.get('section_path'), list) for p in paragraphs)
        assert meta['doi'].lower() == source['doi'].lower()
        result[source['id']] = {
            'paragraphs': len(paragraphs),
            'section_paths': len({tuple(p['section_path']) for p in paragraphs}),
            'without_section': sum(not p['section_path'] for p in paragraphs),
            'supplement_pointers': len(meta['supplement_pointers']),
            'identity_and_text_hashes_unchanged': True,
        }
    return result


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
