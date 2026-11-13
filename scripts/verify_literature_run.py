#!/usr/bin/env python3
"""Offline consistency check of a recorded demo run; not a semantic assessment."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(root):
    report = json.loads((root / 'output/report.json').read_text())
    completion = json.loads((root / 'output/completion.json').read_text())
    checks = []

    def check(name, passed):
        checks.append({'check': name, 'passed': bool(passed)})

    for name, expected in completion['artifacts'].items():
        path = root / 'output' / name
        check('artifact:' + name, path.is_file() and sha(path.read_bytes()) == expected)
    check('completion_state', completion['state'] == report['state'])
    check('completion_exit_code', completion['exit_code'] == report['exit_code'])
    counts = {'sources': 0, 'questions': 0, 'attempts': 0, 'valid_attempts': 0,
              'citations': 0, 'assessed': 0, 'insufficient': 0}
    for source in report['sources']:
        counts['sources'] += 1
        if source.get('diagnostic'):
            continue
        index = json.loads((root / 'output' / ('index.' + source['id'] + '.json')).read_text())
        paragraphs = {p['id']: p.get('evidence_text', p['text']) for p in index['paragraphs']}
        for para in index['paragraphs']:
            check('paragraph:' + para['id'], sha(para['text'].encode()) == para['sha256'])
            if 'evidence_text' in para:
                check('evidence_view:' + para['id'],
                      len(para['evidence_text']) == len(para['text'])
                      and sha(para['evidence_text'].encode()) == para['evidence_sha256'])
        check('source_request_count:' + source['id'], source['request_count'] == len(source['attempts']))
        for question in source['questions']:
            counts['questions'] += 1
            counts['assessed'] += question['state'] == 'ASSESSED'
            counts['insufficient'] += question['state'] == 'INSUFFICIENT'
        for number, attempt in enumerate(source['attempts']):
            label = source['id'] + '/' + str(number)
            counts['attempts'] += 1
            check('evidence:' + label, all(e in paragraphs for e in attempt['evidence_ids']))
            if attempt['status'] != 'valid':
                continue
            counts['valid_attempts'] += 1
            request_path = root / 'output' / attempt.get('request_path', '')
            response_path = root / 'output' / attempt.get('response_path', '')
            check('request_bytes:' + label,
                  request_path.is_file()
                  and sha(request_path.read_bytes()) == attempt.get('request_sha256'))
            check('response_bytes:' + label,
                  response_path.is_file()
                  and sha(response_path.read_bytes()) == attempt.get('response_sha256'))
            # raw_response is the parsed, citation-enriched response. The original
            # adapter bytes are retained separately and checked above.
            response = attempt['raw_response']
            check('question:' + label, response['question_id'] == attempt['question_id'])
            check('model:' + label, response['model'] == attempt['requested_model'])
            for cite in response['citations']:
                counts['citations'] += 1
                text = paragraphs.get(cite['id'], '')
                start, length, quote = cite['start'], cite['length'], cite['quote']
                check('citation:' + label + '/' + str(counts['citations']),
                      cite['id'] in attempt['evidence_ids'] and bool(quote.strip())
                      and length == len(quote) and start >= 0
                      and text[start:start + length] == quote)
    check('total_requests', report['request_count'] == counts['attempts'])
    check('egress_attempt_recorded', counts['attempts'] == 0 or report['public_egress']['executed'])
    return {'format_version': 1, 'run': str(root.resolve()),
            'report_sha256': sha((root / 'output/report.json').read_bytes()),
            'passed': all(c['passed'] for c in checks), 'counts': counts,
            'checks': checks, 'scientific_acceptance': False,
            'limitations': ['Checks locations and recorded consistency, not semantic truth.',
                            'Response bytes are checked against the recorded response_sha256; provider delivery is not independently authenticated.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.run)
    with args.out.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('passed', 'counts', 'scientific_acceptance')}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
