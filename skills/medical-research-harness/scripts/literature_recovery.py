#!/usr/bin/env python3
"""Hash-bound checkpoint and conservative artifact restoration for literature runs.

Restoration copies only artifacts named by a source checkpoint whose recorded
hash still matches. This module never invokes a model or network operation.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil

RUN_STATES = {'CREATED', 'INDEXED', 'ANALYZED', 'BLOCKED', 'COMPLETED'}
SOURCE_STATES = {'CREATED', 'INDEXED', 'ANALYZED', 'BLOCKED'}
SOURCE_TRANSITIONS = {
    'CREATED': {'INDEXED', 'BLOCKED'},
    'INDEXED': {'INDEXED', 'ANALYZED', 'BLOCKED'},
    'ANALYZED': set(),
    'BLOCKED': set(),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    if tmp.exists():
        raise FileExistsError('stale_atomic_temp')
    with tmp.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def safe_relative(path):
    rel = PurePosixPath(path)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError('unsafe_artifact_path')
    return rel


class RunCheckpoint:
    def __init__(self, root, manifest_sha256, source_ids):
        self.root = Path(root).resolve()
        if (not isinstance(manifest_sha256, str) or len(manifest_sha256) != 64
                or any(c not in '0123456789abcdef' for c in manifest_sha256)):
            raise ValueError('invalid_manifest_sha256')
        if len(set(source_ids)) != len(source_ids) or not source_ids:
            raise ValueError('invalid_source_ids')
        self.state_path = self.root / 'run_state.json'
        if self.state_path.exists():
            raise FileExistsError('run_state_exists')
        self.data = {'format_version': 1, 'state': 'CREATED',
                     'manifest_sha256': manifest_sha256,
                     'sources': {sid: {'state': 'CREATED', 'artifacts': []}
                                 for sid in source_ids},
                     'interrupt': None}
        atomic_json(self.state_path, self.data)

    def _save(self):
        atomic_json(self.state_path.with_name('.run_state.next.json'), self.data)
        os.replace(self.state_path.with_name('.run_state.next.json'), self.state_path)

    def mark_source(self, source_id, state, artifacts=(), reason=None):
        if state not in SOURCE_STATES or source_id not in self.data['sources']:
            raise ValueError('invalid_source_state')
        entry = self.data['sources'][source_id]
        if state not in SOURCE_TRANSITIONS[entry['state']]:
            raise ValueError('invalid_source_transition')
        manifest = []
        for artifact in artifacts:
            path = Path(artifact).resolve()
            if not path.is_relative_to(self.root):
                raise ValueError('artifact_outside_run')
            if not path.is_file():
                raise ValueError('artifact_missing')
            rel = path.relative_to(self.root).as_posix()
            manifest.append({'path': rel, 'sha256': sha(path.read_bytes())})
        if state in {'INDEXED', 'ANALYZED'} and not manifest:
            raise ValueError('artifact_manifest_empty')
        entry.update(state=state, artifacts=manifest)
        if reason:
            entry['reason'] = str(reason)
        run_states = [item['state'] for item in self.data['sources'].values()]
        if 'BLOCKED' in run_states:
            self.data['state'] = 'BLOCKED'
        elif 'ANALYZED' in run_states:
            self.data['state'] = 'ANALYZED'
        elif 'INDEXED' in run_states:
            self.data['state'] = 'INDEXED'
        self._save()

    def interrupt(self, reason, resume_from=None):
        self.data['interrupt'] = {'reason': str(reason), 'resume_from': resume_from}
        self._save()

    def finish(self):
        states = [item['state'] for item in self.data['sources'].values()]
        if all(state in {'INDEXED', 'ANALYZED'} for state in states):
            self.data['state'] = 'COMPLETED'
        else:
            self.data['state'] = 'BLOCKED'
        self._save()
        return self.data['state']


def prepare_resume(run_root, manifest_path, out):
    run_root = Path(run_root).resolve()
    manifest_path = Path(manifest_path).resolve()
    out = Path(out).resolve()
    state_path = run_root / 'run_state.json'
    if not state_path.is_file():
        raise ValueError('checkpoint_missing')
    state = json.loads(state_path.read_text(encoding='utf-8'))
    actual_manifest = sha(manifest_path.read_bytes())
    if actual_manifest != state.get('manifest_sha256'):
        raise ValueError('manifest_hash_mismatch')
    if state.get('format_version') != 1 or state.get('state') not in RUN_STATES:
        raise ValueError('invalid_checkpoint')
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    reports = []
    restore_dir = out / 'artifacts'
    for sid, entry in state['sources'].items():
        item = {'source_id': sid, 'state': entry.get('state'), 'restored': [],
                'reason': None}
        if entry.get('state') == 'BLOCKED':
            item['reason'] = entry.get('reason', 'source_blocked')
            item['state'] = 'BLOCKED'
            reports.append(item)
            continue
        try:
            if item['state'] not in {'INDEXED', 'ANALYZED'}:
                raise ValueError('source_not_restorable')
            if not entry.get('artifacts'):
                raise ValueError('artifact_manifest_empty')
            for artifact in entry.get('artifacts', []):
                rel = safe_relative(artifact['path'])
                src = (run_root / Path(*rel.parts)).resolve()
                if not src.is_relative_to(run_root) or not src.is_file():
                    raise ValueError('artifact_missing')
                if sha(src.read_bytes()) != artifact.get('sha256'):
                    raise ValueError('artifact_hash_mismatch')
                dest = restore_dir / Path(*rel.parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    raise ValueError('restore_target_exists')
                item['restored'].append({'path': dest.relative_to(out).as_posix(),
                                         'sha256': artifact['sha256']})
                shutil.copyfile(src, dest)
                if sha(dest.read_bytes()) != artifact['sha256']:
                    raise ValueError('restored_artifact_hash_mismatch')
        except (OSError, KeyError, TypeError, ValueError) as exc:
            for restored in item['restored']:
                (out / restored['path']).unlink(missing_ok=True)
            item.update(state='BLOCKED', reason=str(exc), restored=[])
        reports.append(item)
    result = {'format_version': 1, 'source_run': str(run_root),
              'operation': 'artifact_copy_only', 'continuation_completed': False,
              'source_run_state': state['state'],
              'manifest_sha256': actual_manifest,
              'run_state': 'BLOCKED' if any(x['state'] == 'BLOCKED' for x in reports)
              else 'COMPLETED',
              'resume_from': 'verified_source_artifacts_only',
              'models_called': False, 'network_used': False,
              'interrupt': state.get('interrupt'), 'sources': reports}
    atomic_json(out / 'resume.json', result)
    return result
