#!/usr/bin/env python3
"""Offline, source-transactional literature preparation and actual continuation.

No execution/egress flags are accepted. A resumed run always owns a new output
directory. Completed source preparation is reused; pending sources continue.
"""
import argparse
import json
from pathlib import Path
import signal
import sys
import time

import literature as core
from literature_recovery import atomic_json, safe_relative, sha

MAX_CHECKPOINT_BYTES = 8 * 1024 * 1024
CODE_FILES = ('literature.py', 'literature_offline.py', 'literature_recovery.py',
              'decision_agent.py')


class Interrupted(BaseException):
    pass


def identity(manifest, config):
    scripts = Path(__file__).resolve().parent
    code_hashes = {name: sha((scripts / name).read_bytes()) for name in CODE_FILES}
    host = scripts.parents[2] / 'scripts'
    for name in ('resume_literature_run.py', 'run_literature_demo.py'):
        if (host / name).is_file():
            code_hashes['host/' + name] = sha((host / name).read_bytes())
    return {'manifest_sha256': sha(core.read_bounded(manifest, core.MAX_MANIFEST_BYTES, 'manifest_size_limit')),
            'config_sha256': sha(core.read_bounded(config, core.MAX_CONFIG_BYTES, 'config_size_limit')),
            'questions_sha256': sha(core.read_bounded(core.QUESTIONS_PATH, core.MAX_CONFIG_BYTES, 'questions_size_limit')),
            'code_sha256': code_hashes,
            'python_version': sys.version,
            'mode': 'offline_preparation_v2'}


def emit_completion(out, report):
    atomic_json(out / 'report.json', report)
    with (out / 'report.md').open('x', encoding='utf-8') as stream:
        stream.write(core.render_markdown(report))
        stream.write('\nResume: ' + json.dumps(report['resume'], ensure_ascii=False) + '\n')
    artifacts = {p.relative_to(out).as_posix(): sha(p.read_bytes())
                 for p in sorted(out.rglob('*')) if p.is_file()
                 and p.name != 'completion.json'}
    atomic_json(out / 'completion.json', {'format_version': 1, 'state': report['state'],
                                        'exit_code': report['exit_code'], 'artifacts': artifacts})


def load_checkpoint(old, expected, sources):
    """Validate every reusable source before returning any bytes to the writer."""
    if (old / 'completion.json').exists():
        completion = core.strict_json(core.read_bounded(old / 'completion.json', MAX_CHECKPOINT_BYTES,
                                                       'completion_size_limit'))
        declared = completion.get('artifacts')
        core.need(isinstance(declared, dict) and 'run_state.json' in declared,
                  'invalid_completion_manifest')
        for name, expected_hash in declared.items():
            rel = safe_relative(name); path = old / Path(*rel.parts)
            core.need(not path.is_symlink() and path.resolve().is_relative_to(old), 'unsafe_completion_path')
            core.need(path.is_file() and sha(path.read_bytes()) == expected_hash,
                      'completion_artifact_mismatch:' + name)
    state = core.strict_json(core.read_bounded(old / 'run_state.json', MAX_CHECKPOINT_BYTES,
                                             'checkpoint_size_limit'))
    core.need(isinstance(state, dict) and state.get('format_version') == 2,
              'checkpoint_v2_required')
    core.need(state.get('identity') == expected, 'resume_identity_mismatch')
    core.need(state.get('state') in {'CREATED', 'INDEXED', 'BLOCKED', 'COMPLETED'},
              'invalid_checkpoint_state')
    core.need(state.get('state') != 'COMPLETED' or (old / 'completion.json').is_file(),
              'completed_checkpoint_without_completion')
    entries = state.get('sources')
    core.need(isinstance(entries, dict) and set(entries) == {s['id'] for s in sources},
              'checkpoint_source_set_mismatch')
    restored = {}
    used_paths = set()
    for source in sources:
        sid = source['id']; entry = entries[sid]
        core.need(isinstance(entry, dict), 'invalid_source_checkpoint')
        status = entry.get('state')
        if status == 'BLOCKED':
            raise ValueError('source_blocked:' + sid + ':' + str(entry.get('reason')))
        core.need(status in {'CREATED', 'INDEXED'}, 'invalid_source_state')
        complete = entry.get('preparation_complete')
        core.need(type(complete) is bool, 'ambiguous_source_phase')
        artifacts = entry.get('artifacts')
        core.need(isinstance(artifacts, dict), 'invalid_artifact_manifest')
        if status == 'CREATED':
            core.need(not artifacts and not complete, 'ambiguous_created_source')
            continue
        required = {f'index.{sid}.json'}
        if complete:
            required.add(f'source.{sid}.json')
        core.need(set(artifacts) == required, 'source_artifact_set_mismatch')
        payloads = {}
        for name, expected_hash in artifacts.items():
            rel = safe_relative(name)
            path = old / Path(*rel.parts)
            core.need(not path.is_symlink() and path.resolve().is_relative_to(old), 'unsafe_artifact_path')
            core.need(name not in used_paths, 'duplicate_artifact_path')
            used_paths.add(name)
            raw = core.read_bounded(path, MAX_CHECKPOINT_BYTES, 'artifact_size_limit')
            core.need(sha(raw) == expected_hash, 'artifact_hash_mismatch:' + name)
            payloads[name] = raw
        index = core.strict_json(payloads[f'index.{sid}.json'])
        core.need(index.get('source_id') == sid and index.get('source_sha256') == source['sha256'],
                  'index_source_mismatch')
        core.need(isinstance(index.get('meta'), dict) and bool(index.get('paragraphs')), 'invalid_index')
        ids = set()
        for p in index['paragraphs']:
            core.need(p['id'] not in ids and p['id'].startswith(sid + '/p'), 'invalid_paragraph_id')
            ids.add(p['id'])
            core.need(sha(p['text'].encode()) == p['sha256'], 'paragraph_hash_mismatch')
            ev = p.get('evidence_text', p['text'])
            core.need(len(ev) == len(p['text']) and sha(ev.encode()) == p['evidence_sha256'],
                      'evidence_hash_mismatch')
        result = None
        if complete:
            result = core.strict_json(payloads[f'source.{sid}.json'])
            core.need(result.get('id') == sid and result.get('state') == 'INDEXED'
                      and result.get('request_count') == 0 and result.get('attempts') == [],
                      'invalid_offline_source_result')
            core.need(len(result['questions']) == 4 and all(q['state'] in {'NOT_REQUESTED', 'INSUFFICIENT'}
                      and q.get('analysis') is None and q.get('review') is None
                      for q in result['questions']), 'invalid_offline_question_state')
        restored[sid] = (entry, payloads, index, result)
    actual_source_files = {p.name for pattern in ('index.*.json', 'source.*.json')
                           for p in old.glob(pattern)}
    core.need(actual_source_files == used_paths, 'unregistered_or_missing_source_artifact')
    return state, restored


def source_result(source, index, config, questions):
    src = dict(source, paragraphs=index['paragraphs'], meta=index['meta'])
    outcome = core.analyze_source(src, questions['questions'], config['models'],
                                  config['max_requests'], config['timeout_seconds'], False)
    paragraphs = index['paragraphs']
    return dict(id=source['id'], doi=source['doi'], license_url=source['license_url'],
                rights_basis=source['rights_basis'], state='INDEXED',
                coverage=dict(paragraphs_indexed=len(paragraphs),
                              truncated_paragraphs=index['meta']['truncated_paragraphs'],
                              section_path_count=len({tuple(p['section_path']) for p in paragraphs}),
                              paragraphs_without_section=sum(not p['section_path'] for p in paragraphs),
                              supplementary_materials='not_retrieved',
                              supplement_pointers=len(index['meta'].get('supplement_pointers', [])),
                              resolved=0, rights_verified=0,
                              evidence_view='length_preserving_mask'),
                request_count=0, questions=outcome['questions'], attempts=[],
                unresolved=outcome['unresolved'], errors=outcome['errors'])


def run(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    started = time.monotonic()
    report: dict = dict(format_version=1, state='BLOCKED', run_state='CREATED', exit_code=2,
                  execution_authorized=False, scientific_acceptance=False,
                  public_egress=dict(requested=False, executed=False, scope='offline only'),
                  identity=None, sources=[], diagnostics=[], request_count=0,
                  elapsed_seconds=None,
                  resume=dict(source_run=str(args.resume_from.resolve()) if args.resume_from else None,
                              reused_sources=[], continued_sources=[], restored_index_sources=[],
                              operation='offline_preparation_continuation'),
                  limitations=['COMPLETED means offline preparation finished; no model analysis occurred. Zero-hit questions remain INSUFFICIENT.',
                               'Original reference text is retained; excluded descendants are space-masked in evidence coordinates.'])
    state = None
    active = None
    phase = 'validation'
    old_handlers = {}

    def interrupted(signum, frame):
        raise Interrupted(signal.Signals(signum).name)

    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            old_handlers[sig] = signal.signal(sig, interrupted)
        manifest = core.strict_json(core.read_bounded(args.manifest, core.MAX_MANIFEST_BYTES, 'manifest_size_limit'))
        config = core.strict_json(core.read_bounded(args.config, core.MAX_CONFIG_BYTES, 'config_size_limit'))
        questions = core.strict_json(core.read_bounded(core.QUESTIONS_PATH, core.MAX_CONFIG_BYTES, 'questions_size_limit'))
        core.validate_manifest(manifest); core.validate_config(config)
        core.need(isinstance(questions, dict) and questions.get('format_version') == 1
                  and {q['id'] for q in questions['questions']} ==
                  {'FIT_SCOPE', 'EVAL_ROLE', 'GROUP_SPLIT', 'FEATURE_TIME'}, 'invalid_questions')
        ident = identity(args.manifest, args.config)
        report['identity'] = ident
        # Revalidate all current source bytes, including sources whose parsed
        # indexes will be reused. No parsing or analysis is needed for reused ones.
        for src in manifest['sources']:
            path = core.validate_source(src, args.manifest.parent)
            core.need(sha(core.read_bounded(path, core.MAX_XML_BYTES, 'xml_size_limit')) == src['sha256'],
                      'source_hash_mismatch:' + src['id'])
        prior = None; restored = {}
        if args.resume_from:
            prior, restored = load_checkpoint(args.resume_from.resolve(), ident, manifest['sources'])
        state = dict(format_version=2, state='CREATED', identity=ident,
                     sources={s['id']: dict(state='CREATED', preparation_complete=False, artifacts={})
                              for s in manifest['sources']},
                     active=None, interrupt=None,
                     resumed_from=report['resume']['source_run'],
                     previous_interrupt=prior.get('interrupt') if prior else None)
        if prior and not prior.get('interrupt') and prior['state'] != 'COMPLETED':
            state['previous_interrupt'] = dict(reason='unclean_exit_unknown', resume_from=prior.get('active'))
        atomic_json(out / 'run_state.json', state)
        for src in manifest['sources']:
            active = src['id']; phase = 'index'
            state['active'] = dict(source_id=active, phase=phase)
            atomic_json(out / 'run_state.json', state)
            if active in restored:
                previous, payloads, index, result = restored[active]
                created = []
                try:
                    for name, raw in payloads.items():
                        created.append(out / name)
                        with (out / name).open('xb') as stream:
                            stream.write(raw)
                        core.need(sha((out / name).read_bytes()) == sha(raw), 'copy_hash_mismatch')
                except (OSError, ValueError, Interrupted):
                    for path in created:
                        path.unlink(missing_ok=True)
                    raise
                state['sources'][active] = dict(previous)
                report['resume']['restored_index_sources'].append(active)
                if result is not None:
                    report['sources'].append(result)
                    report['resume']['reused_sources'].append(active)
                    atomic_json(out / 'run_state.json', state)
                    continue
            else:
                paragraphs, meta = core.verify_source(src, args.manifest.parent)
                index = dict(source_id=active, source_sha256=src['sha256'], doi=meta['doi'],
                             paragraphs=paragraphs, meta=meta,
                             supplement_pointers=meta.get('supplement_pointers', []))
                atomic_json(out / f'index.{active}.json', index)
                state['sources'][active] = dict(state='INDEXED', preparation_complete=False,
                    artifacts={f'index.{active}.json': sha((out / f'index.{active}.json').read_bytes())})
            state['state'] = 'INDEXED'
            phase = 'retrieval'; state['active'] = dict(source_id=active, phase=phase)
            atomic_json(out / 'run_state.json', state)
            result = source_result(src, index, config, questions)
            atomic_json(out / f'source.{active}.json', result)
            state['sources'][active]['artifacts'][f'source.{active}.json'] = sha((out / f'source.{active}.json').read_bytes())
            state['sources'][active]['preparation_complete'] = True
            atomic_json(out / 'run_state.json', state)
            report['sources'].append(result)
            report['resume']['continued_sources'].append(active)
        state['state'] = 'COMPLETED'; state['active'] = None
        atomic_json(out / 'run_state.json', state)
        report.update(state='DRY_RUN', run_state='COMPLETED', exit_code=0)
    except Interrupted as exc:
        report['diagnostics'].append(str(exc))
        if state is not None:
            # Use the last committed snapshot: an interrupted write is not a checkpoint.
            state = core.strict_json((out / 'run_state.json').read_bytes())
            state['interrupt'] = dict(reason=str(exc), resume_from=dict(source_id=active, phase=phase))
            atomic_json(out / 'run_state.json', state)
        report.update(state='BLOCKED', run_state='BLOCKED', exit_code=130)
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        report['diagnostics'].append(str(exc))
        if state is not None:
            state['state'] = 'BLOCKED'
            if active is not None:
                state['sources'][active].update(state='BLOCKED', reason=str(exc))
            atomic_json(out / 'run_state.json', state)
        report.update(state='BLOCKED', run_state='BLOCKED', exit_code=2)
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    report['elapsed_seconds'] = round(time.monotonic() - started, 4)
    emit_completion(out, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--resume-from', type=Path)
    args = parser.parse_args(argv)
    try:
        report = run(args)
    except (OSError, ValueError) as exc:
        print(json.dumps(dict(state='BLOCKED', reason=str(exc))))
        return 2
    print(json.dumps(dict(state=report['state'], run_state=report['run_state'],
                          exit_code=report['exit_code'], request_count=0)))
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
