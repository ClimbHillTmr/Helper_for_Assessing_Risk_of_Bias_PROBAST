#!/usr/bin/env python3
"""Regression tests for literature.py. Fully offline: adapters are synthetic
python argv reading stdin JSON and emitting canned responses. No network, no
real model calls. Run: python3 test_literature.py"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / 'literature.py'

JATS = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
<front><article-meta>
<article-id pub-id-type="doi">{doi}</article-id>
<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"><license-p>CC BY</license-p></license></permissions>
</article-meta></front>
<body>
<sec><title>Methods</title>
<p>We enrolled a cohort of 1200 patients admitted to hospital between 2015 and 2019 for prognostic prediction of mortality.</p>
<sec><title>Splitting</title>
<p>Data were randomly split into training and test partitions; imputation and feature selection were performed within training folds only.</p>
</sec></sec>
<sec><title>Predictors</title>
<p>Predictor variables were measured at baseline before admission; the outcome endpoint was ascertained within 30 days of follow-up.</p>
<p>Model discrimination was assessed by internal validation using bootstrap and cross-validation; AUC and calibration were reported on the validation set.</p>
</sec>
</body>
<back><ref-list><ref><mixed-citation>Data were randomly split into training and test partitions; imputation and feature selection were performed within training folds only.</mixed-citation></ref></ref-list></back>
</article>"""

NOBODY = JATS.replace('<body>', '').replace('</body>', '')

RESP = {'applicability': 'applicable', 'finding': 'reported_risk',
        'summary': 's', 'citations': [], 'missing_materials': []}


def adapter_source(kind):
    """Generate a synthetic adapter script. kind controls canned behavior."""
    body = """
import json, sys
req = json.load(sys.stdin)
ev = req['task']['evidence']
out = {KIND}
out['model'] = req['model']; out['question_id'] = req['task']['question_id']
json.dump(out, sys.stdout)
"""
    canned = dict(RESP)
    cite = {'id': 'EVID', 'quote': 'QUOTE'}
    if kind == 'valid':
        canned['citations'] = [cite]
    elif kind == 'forged_quote':
        canned['citations'] = [{'id': 'EVID', 'quote': 'FABRICATED QUOTE NOT IN SOURCE'}]
    elif kind == 'unknown_id':
        canned['citations'] = [{'id': 'bogus/p9999', 'quote': 'QUOTE'}]
    elif kind == 'insufficient':
        canned['finding'] = 'insufficient'
    elif kind == 'disagree':
        canned['finding'] = 'no_risk_identified'
        canned['citations'] = [cite]
    elif kind == 'extra_key':
        canned['citations'] = [cite]
        canned['confidence'] = 0.9
    elif kind == 'wrong_model':
        canned['citations'] = [cite]
    elif kind == 'unhashable_cite':
        canned['citations'] = [{'id': ['x'], 'quote': 'QUOTE'}]
    elif kind == 'crash':
        return "import sys; sys.exit(3)\n"
    else:
        raise AssertionError(kind)
    import json as _j
    dumped = (_j.dumps(canned)
              .replace('"EVID"', "ev[0]['id'] if ev else 'x'")
              .replace('"QUOTE"', "ev[0]['text'][:24] if ev else 'x'"))
    return body.replace('{KIND}', dumped)


def make_workspace(root, xml_text=JATS, doi='10.1234/test.1',
                   license_url='https://creativecommons.org/licenses/by/4.0/',
                   adapter_kinds=('valid', 'valid'), max_requests=30, extra=None,
                   reviewer_same_model=False):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / 'paper.xml').write_text(xml_text.replace('{doi}', doi), encoding='utf-8')
    sha = hashlib.sha256((root / 'paper.xml').read_bytes()).hexdigest()
    manifest = {'format_version': 1, 'sources': [{
        'id': 's1', 'doi': doi, 'title': 'T', 'license_url': license_url,
        'rights_basis': 'CC BY 4.0 declared in article permissions.',
        'path': 'paper.xml', 'sha256': sha}]}
    if extra:
        manifest['sources'][0].update(extra)
    (root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    adapters = []
    for i, kind in enumerate(adapter_kinds):
        path = root / f'adapter{i}.py'
        path.write_text(adapter_source(kind), encoding='utf-8')
        adapters.append([sys.executable, str(path)])
    config = {'format_version': 1, 'max_requests': max_requests,
              'timeout_seconds': 30,
              'models': {'analysis': {'provider': 'p', 'model': 'm-a',
                                      'command': adapters[0]},
                         'reviewer': {'provider': 'p', 'model': 'm-r',
                                      'command': adapters[1]}}}
    if reviewer_same_model:
        config['models']['reviewer'] = dict(config['models']['analysis'])
        config['models']['reviewer']['command'] = adapters[1]  # different argv, same model
    (root / 'config.json').write_text(json.dumps(config), encoding='utf-8')
    return root


def run(root, name, *flags):
    out = Path(root) / name
    proc = subprocess.run([sys.executable, str(SCRIPT), '--manifest', str(Path(root) / 'manifest.json'),
                           '--config', str(Path(root) / 'config.json'), '--out', str(out), *flags],
                          capture_output=True, text=True)
    report = json.loads((out / 'report.json').read_text()) if (out / 'report.json').exists() else None
    return proc, report, out


def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond:
        FAILURES.append(name)


FAILURES = []
with tempfile.TemporaryDirectory() as tmp:

    # 1. dry-run indexes real paragraphs, dedupes back-matter, never calls models
    ws = make_workspace(Path(tmp) / 't1')
    proc, rep, out = run(ws, 'out')
    check('dryrun exit0', proc.returncode == 0)
    check('dryrun state', rep['state'] == 'DRY_RUN')
    check('run state completed', rep['run_state'] == 'COMPLETED'
          and json.loads((out / 'run_state.json').read_text())['state'] == 'COMPLETED')
    paras = json.loads((out / 'index.s1.json').read_text())['paragraphs']
    check('index 4 unique paras', len(paras) == 4)
    check('back-matter not indexed', all('ref-list' not in p['id'] for p in paras))
    src = rep['sources'][0]
    check('dryrun no requests', rep['request_count'] == 0)
    check('all NOT_REQUESTED', all(q['state'] == 'NOT_REQUESTED' for q in src['questions']))
    check('completion exists', (out / 'completion.json').exists())

    # 2. real execute path: analysis + blind review agree
    ws = make_workspace(Path(tmp) / 't2')
    proc, rep, out = run(ws, 'out', '--execute-models', '--allow-public-egress')
    check('exec exit0', proc.returncode == 0 and rep['state'] == 'AWAITING_SCIENTIFIC_REVIEW')
    assessed = [q for q in rep['sources'][0]['questions'] if q['state'] == 'ASSESSED']
    check('exec some assessed', len(assessed) >= 1)
    check('exec flags recorded', rep['public_egress']['executed'] is True)
    check('exec authorizations false',
          rep['execution_authorized'] is False and rep['scientific_acceptance'] is False)

    # 3. forged citation -> attempt invalid, source partial
    ws = make_workspace(Path(tmp) / 't3', adapter_kinds=('forged_quote', 'valid'))
    proc, rep, out = run(ws, 'out', '--execute-models', '--allow-public-egress')
    errors = [a.get('error') for s in rep['sources'] for a in s['attempts'] if a['role'] == 'analysis']
    check('forged quote rejected', 'quote_not_verbatim' in errors)
    check('forged partial', rep['state'] == 'PARTIAL' and rep['exit_code'] == 1)

    # 4. DOI mis-binding: manifest DOI != XML DOI
    ws = make_workspace(Path(tmp) / 't4', doi='10.9999/wrong',
                        xml_text=JATS.replace('{doi}', '10.1234/real'))
    proc, rep, out = run(ws, 'out', '--execute-models', '--allow-public-egress')
    check('doi mismatch blocked', rep['state'] == 'BLOCKED'
          and rep['sources'][0].get('diagnostic') == 'doi_mismatch'
          and rep['request_count'] == 0)

    # 5. license missing -> blocked before models
    ws = make_workspace(Path(tmp) / 't5', xml_text=JATS.replace('xlink:href="https://creativecommons.org/licenses/by/4.0/"', 'xlink:href="https://example.com/proprietary"'))
    proc, rep, out = run(ws, 'out')
    check('license mismatch blocked', rep['state'] == 'BLOCKED'
          and rep['sources'][0].get('diagnostic') == 'license_missing_or_mismatch')

    # 6. oversized XML rejected
    ws = make_workspace(Path(tmp) / 't6')
    big = JATS.replace('</body>', ('<p>' + 'x' * 2000 + '</p>') * 5000 + '</body>')
    (ws / 'paper.xml').write_text(big, encoding='utf-8')
    sha = hashlib.sha256((ws / 'paper.xml').read_bytes()).hexdigest()
    manifest = json.loads((ws / 'manifest.json').read_text())
    manifest['sources'][0]['sha256'] = sha
    (ws / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    proc, rep, out = run(ws, 'out')
    check('oversize blocked', rep['state'] == 'BLOCKED'
          and rep['sources'][0].get('diagnostic') in ('xml_size_limit', 'paragraph_count_limit', 'element_count_limit'))

    # 7. no body -> blocked
    ws = make_workspace(Path(tmp) / 't7', xml_text=NOBODY)
    proc, rep, out = run(ws, 'out')
    check('no body blocked', rep['sources'][0].get('diagnostic') == 'no_body')

    # 8. budget exhaustion: max_requests=1 means analysis only, review unrequested
    ws = make_workspace(Path(tmp) / 't8', max_requests=1)
    proc, rep, out = run(ws, 'out', '--execute-models', '--allow-public-egress')
    check('budget exhausted flagged',
          'request_budget_exhausted' in rep['sources'][0]['errors'])
    check('budget respected', rep['request_count'] <= 1 * len(rep['sources'][0]['questions']))
    check('unresolved on review unavailable',
          any(q['state'] == 'UNRESOLVED' for q in rep['sources'][0]['questions']))

    # 9. failing model adapter -> blocked question, partial state, no fake success
    ws = make_workspace(Path(tmp) / 't9', adapter_kinds=('crash', 'valid'))
    proc, rep, out = run(ws, 'out', '--execute-models', '--allow-public-egress')
    states = {q['question_id']: q['state'] for q in rep['sources'][0]['questions']}
    check('failed model blocked questions', all(s in ('BLOCKED', 'INSUFFICIENT') for s in states.values()))
    check('failed model partial', rep['state'] == 'PARTIAL' and rep['exit_code'] == 1)

    # 10. disagreement preserved as UNRESOLVED, no voting
    ws = make_workspace(Path(tmp) / 't10', adapter_kinds=('valid', 'disagree'))
    proc, rep, out = run(ws, 'out', '--execute-models', '--allow-public-egress')
    un = [q for q in rep['sources'][0]['questions'] if q['state'] == 'UNRESOLVED']
    check('disagreement unresolved', len(un) >= 1
          and all(q.get('reviewer_finding') == 'no_risk_identified' for q in un))
    check('disagreement not overridden', rep['state'] == 'PARTIAL')

    # 11. egress switch required: --execute-models alone blocks
    ws = make_workspace(Path(tmp) / 't11')
    proc, rep, out = run(ws, 'out', '--execute-models')
    check('egress required', rep['state'] == 'BLOCKED' and rep['request_count'] == 0)

    # 12. extra response key rejected (strict schema)
    ws = make_workspace(Path(tmp) / 't12', adapter_kinds=('extra_key', 'valid'))
    proc, rep, out = run(ws, 'out', '--execute-models', '--allow-public-egress')
    errors = [a.get('error') for s in rep['sources'] for a in s['attempts'] if a['role'] == 'analysis']
    check('extra key rejected', 'invalid_response_schema' in errors)

    # 13. ENTITY / internal-subset DOCTYPE rejected byte-wise
    ws = make_workspace(Path(tmp) / 't13',
                        xml_text='<!DOCTYPE article [<!ENTITY x "y">]>' + JATS)
    proc, rep, out = run(ws, 'out')
    check('entity rejected', rep['sources'][0].get('diagnostic') == 'entity_not_allowed')
    ws = make_workspace(Path(tmp) / 't13b',
                        xml_text='<!DOCTYPE article [<!ATTLIST article>]>' + JATS)
    proc, rep, out = run(ws, 'out')
    check('internal subset rejected',
          rep['sources'][0].get('diagnostic') in
          ('entity_not_allowed', 'doctype_internal_subset_not_allowed', 'invalid_xml'))

    # 14. standard external DOCTYPE (pmc-articleset) is allowed; identity
    # comes only from the article's article-meta, never from ref-list DOIs
    wrapped = ('<?xml version="1.0"?><!DOCTYPE pmc-articleset PUBLIC '
               '"-//NLM//DTD ARTICLE SET 2.0//EN" '
               '"https://dtd.nlm.nih.gov/ncbi/pmc/articleset/nlm-articleset-2.0.dtd">'
               '<pmc-articleset>' + JATS.split('?>', 1)[1] + '</pmc-articleset>')
    ws = make_workspace(Path(tmp) / 't14', xml_text=wrapped)
    proc, rep, out = run(ws, 'out')
    check('external doctype allowed', rep['state'] == 'DRY_RUN'
          and rep['sources'][0].get('diagnostic') is None)
    # back-matter ref with a different article-id doi must not bind
    ref_doi = JATS.replace('</mixed-citation>',
                           '<article-id pub-id-type="doi">10.6666/ref.doi</article-id></mixed-citation>')
    ws = make_workspace(Path(tmp) / 't14b', xml_text=ref_doi)
    proc, rep, out = run(ws, 'out')
    check('ref doi not bound', rep['state'] == 'DRY_RUN'
          and rep['sources'][0].get('diagnostic') is None)

    # 15. license via ext-link href and literal license-p / ali:license_ref text
    lic_extlink = JATS.replace(
        '<license xlink:href="https://creativecommons.org/licenses/by/4.0/">',
        '<license><ext-link xlink:href="https://creativecommons.org/licenses/by/4.0/">x</ext-link>')
    ws = make_workspace(Path(tmp) / 't15', xml_text=lic_extlink)
    proc, rep, out = run(ws, 'out')
    check('license ext-link ok', rep['state'] == 'DRY_RUN')
    lic_text = JATS.replace(
        'xlink:href="https://creativecommons.org/licenses/by/4.0/"', '')
    ws = make_workspace(Path(tmp) / 't15b',
                        license_url='http://creativecommons.org/licenses/by/4.0/',
                        xml_text=lic_text.replace(
        '<license-p>CC BY</license-p>',
        '<license-p>Open access http://creativecommons.org/licenses/by/4.0/</license-p>'))
    proc, rep, out = run(ws, 'out')
    check('license literal text ok', rep['state'] == 'DRY_RUN')
    # forged similar domain must not count
    ws = make_workspace(Path(tmp) / 't15c', xml_text=JATS.replace(
        'https://creativecommons.org/licenses/by/4.0/',
        'https://creativecommons.org.evil.example/licenses/by/4.0/'))
    proc, rep, out = run(ws, 'out')
    check('forged license domain blocked', rep['state'] == 'BLOCKED')

    # 16. missing XML file -> BLOCKED report+completion, no traceback
    ws = make_workspace(Path(tmp) / 't16')
    (ws / 'paper.xml').unlink()
    proc, rep, out = run(ws, 'out')
    check('missing file blocked', rep['state'] == 'BLOCKED' and rep['exit_code'] == 2)
    check('missing file completion', (out / 'completion.json').exists())
    check('missing file diagnostic', rep['sources'][0].get('diagnostic', '').startswith('source_unreadable'))

    # 17. insufficient must never be laundered: agreed insufficient stays
    # UNRESOLVED-adjacent (INSUFFICIENT) and reviewer failure leaves UNRESOLVED
    ws = make_workspace(Path(tmp) / 't17', adapter_kinds=('insufficient', 'insufficient'))
    proc, rep, out = run(ws, 'out', '--execute-models', '--allow-public-egress')
    states = {q['question_id']: q['state'] for q in rep['sources'][0]['questions']}
    check('agreed insufficient not assessed',
          all(s in ('INSUFFICIENT', 'UNRESOLVED') for s in states.values()))
    ws = make_workspace(Path(tmp) / 't17b', adapter_kinds=('insufficient', 'crash'))
    proc, rep, out = run(ws, 'out', '--execute-models', '--allow-public-egress')
    q = [q for q in rep['sources'][0]['questions']
         if q['question_id'] == 'FIT_SCOPE' and q.get('analysis')]
    check('insufficient w/o review unresolved',
          all(x['state'] == 'UNRESOLVED' for x in q))

    # 18. same_model judged by provider+model, not argv
    ws = make_workspace(Path(tmp) / 't18', reviewer_same_model=True)
    proc, rep, out = run(ws, 'out', '--execute-models', '--allow-public-egress')
    reviews = [q['review'] for q in rep['sources'][0]['questions'] if q.get('review')]
    check('same_model by identity', reviews
          and all(r['same_model_independent_context'] is True for r in reviews))

    # 19. unhashable citation id caught, traced, no traceback
    ws = make_workspace(Path(tmp) / 't19', adapter_kinds=('unhashable_cite', 'valid'))
    proc, rep, out = run(ws, 'out', '--execute-models', '--allow-public-egress')
    check('no traceback', proc.returncode != 2 or 'Traceback' not in proc.stderr)
    errors = [a.get('error') for s in rep['sources'] for a in s['attempts']
              if a['role'] == 'analysis']
    check('unhashable cite caught',
          any(e and 'adapter_or_json_error' in e for e in errors))

    # 20. report.md is human-readable: summaries + verbatim citation offsets;
    # attempts keep evidence ids and verified raw responses
    _, rep20, out20 = run(Path(tmp) / 't2', 'out2', '--execute-models', '--allow-public-egress')
    md = (out20 / 'report.md').read_text()
    check('report md has summary', 'summary: s' in md)
    check('report md has citations', '/p' in md and '"' in md)
    att = rep20['sources'][0]['attempts']
    check('attempt evidence ids', all('evidence_ids' in a for a in att))
    valid = [a for a in att if a['status'] == 'valid']
    check('raw response kept', valid and all('raw_response' in a for a in valid)
          and all(c['start'] >= 0 for a in valid
                  for c in a['raw_response']['citations']))
    check('raw request response artifacts kept',
          valid and all((out20 / a['request_path']).is_file()
                        and (out20 / a['response_path']).is_file()
                        and hashlib.sha256((out20 / a['request_path']).read_bytes()).hexdigest()
                        == a['request_sha256']
                        and hashlib.sha256((out20 / a['response_path']).read_bytes()).hexdigest()
                        == a['response_sha256']
                        for a in valid))
    completion20 = json.loads((out20 / 'completion.json').read_text())
    check('attempt artifacts in completion',
          all(a['response_path'] in completion20['artifacts']
              and a['request_path'] in completion20['artifacts'] for a in valid))

print()
if FAILURES:
    print(f'{len(FAILURES)} FAILURES')
    raise SystemExit(1)
print('ALL TESTS PASSED')
