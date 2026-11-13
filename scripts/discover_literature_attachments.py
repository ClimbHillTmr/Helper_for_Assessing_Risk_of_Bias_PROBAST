#!/usr/bin/env python3
"""Discover public-article supplementary asset pointers without downloading assets.

The report is an acquisition gate, not a license decision. Article CC BY metadata
never automatically grants a supplementary file the same rights. Asset bodies are
never sent to a model by this script.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from xml.parsers import expat

MAX_OAI_BYTES = 4 * 1024 * 1024
XLINK = '{http://www.w3.org/1999/xlink}href'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def localname(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def parse_safe(raw):
    if b'<!entity' in raw.lower():
        raise ValueError('entity_not_allowed')
    guard = expat.ParserCreate()

    def reject_subset(name, system_id, public_id, has_internal_subset):
        if has_internal_subset:
            raise ValueError('doctype_internal_subset_not_allowed')

    guard.StartDoctypeDeclHandler = reject_subset
    guard.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    guard.ExternalEntityRefHandler = lambda *args: 1
    try:
        guard.Parse(raw, True)
        return ET.fromstring(raw)
    except ValueError:
        raise
    except (expat.ExpatError, ET.ParseError) as exc:
        raise ValueError('invalid_oai_xml') from exc


def article_from_oai(root):
    articles = [node for node in root.iter() if localname(node.tag) == 'article']
    if len(articles) != 1:
        raise ValueError('oai_article_count:' + str(len(articles)))
    return articles[0]


def text(node):
    return ' '.join(''.join(node.itertext()).split()) if node is not None else ''


def extract_oai(raw, source):
    article = article_from_oai(parse_safe(raw))
    meta = next((n for n in article.iter() if localname(n.tag) == 'article-meta'), None)
    if meta is None:
        raise ValueError('no_article_meta')
    dois = [n.text.strip() for n in meta.iter()
            if localname(n.tag) == 'article-id'
            and n.attrib.get('pub-id-type') == 'doi' and n.text and n.text.strip()]
    if source['doi'].strip().lower() not in {d.lower() for d in dois}:
        raise ValueError('doi_mismatch')
    licenses = []
    for node in meta.iter():
        if localname(node.tag) != 'license':
            continue
        for child in node.iter():
            href = child.attrib.get(XLINK, '')
            if href:
                licenses.append(href.strip())
            if child.text:
                licenses.extend(re.findall(
                    r'https?://creativecommons\\.org/licenses/[^\\s)<>\"\']+',
                    child.text, flags=re.IGNORECASE))
    refs = []
    for node in article.iter():
        if localname(node.tag) != 'supplementary-material':
            continue
        for media in node.iter():
            if localname(media.tag) != 'media' or not media.attrib.get(XLINK):
                continue
            href = media.attrib[XLINK].strip()
            if not href or href.startswith(('http://', 'https://')):
                resolved = href
            else:
                resolved = None
            refs.append({'id': node.attrib.get('id'), 'href': href,
                         'label': text(node), 'resolved_from_article': resolved})
    return {'article_doi': dois[0] if dois else None,
            'article_license_urls': sorted(set(licenses)),
            'attachment_refs': refs}


def oai_url(source_id):
    number = source_id.removeprefix('PMC')
    return ('https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi?verb=GetRecord&'
            f'identifier=oai:pubmedcentral.nih.gov:{quote(number)}&metadataPrefix=pmc')


def fetch(url):
    req = Request(url, headers={'User-Agent': 'medical-research-harness/0.2 public metadata audit'})
    with urlopen(req, timeout=30) as response:
        raw = response.read(MAX_OAI_BYTES + 1)
    if len(raw) > MAX_OAI_BYTES:
        raise ValueError('oai_size_limit')
    return raw


def probe(url):
    req = Request(url, method='HEAD', headers={'User-Agent': 'medical-research-harness/0.2 public metadata audit'})
    try:
        with urlopen(req, timeout=20) as response:
            return {'status': response.status, 'url': response.geturl(),
                    'content_type': response.headers.get('Content-Type'),
                    'content_length': response.headers.get('Content-Length'),
                    'asset_content_validated': response.status == 200
                    and not (response.headers.get('Content-Type') or '').lower().startswith('text/html')
                    and response.headers.get('Content-Length') not in (None, '0')}
    except HTTPError as exc:
        return {'status': exc.code, 'url': exc.geturl(),
                'error': 'http_error', 'asset_content_validated': False}
    except (URLError, OSError, TimeoutError) as exc:
        return {'status': None, 'error': type(exc).__name__}


def discover(manifest, out, allow_public_egress=False, probe_assets=False, oai_dir=None):
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    (out / 'oai').mkdir(mode=0o700)
    records = []
    for source in manifest['sources']:
        sid = source['id']
        url = oai_url(sid)
        record = {'id': sid, 'doi': source['doi'], 'oai_url': url,
                  'oai_sha256': None, 'attachment_refs': [],
                  'rights_status': 'not_independently_verified', 'probe': []}
        try:
            if oai_dir is not None:
                raw = (oai_dir / f'{sid}.xml').read_bytes()
            elif allow_public_egress:
                raw = fetch(url)
            else:
                raise ValueError('public_egress_not_authorized')
            record['oai_sha256'] = digest(raw)
            (out / 'oai' / f'{sid}.xml').write_bytes(raw)
            parsed = extract_oai(raw, source)
            record.update(parsed)
            for ref in record['attachment_refs']:
                href = ref['href']
                if ref['resolved_from_article'] is None:
                    candidates = [
                        f'https://pmc.ncbi.nlm.nih.gov/articles/{sid}/bin/{quote(href, safe="")}',
                        f'https://www.ncbi.nlm.nih.gov/pmc/articles/{sid}/bin/{quote(href, safe="")}',
                    ]
                    ref['candidate_urls'] = candidates
                    if probe_assets and allow_public_egress:
                        ref['probes'] = [probe(candidate) for candidate in candidates]
                        ref['asset_retrieval_status'] = (
                            'header_candidate_only' if any(
                                item.get('asset_content_validated') for item in ref['probes'])
                            else 'not_validated')
            if not record['attachment_refs']:
                record['status'] = 'no_attachment_pointer_found'
            else:
                record['status'] = 'attachment_pointer_found_needs_rights_review'
        except (OSError, ValueError, HTTPError, URLError) as exc:
            record['status'] = 'blocked:' + (str(exc) or type(exc).__name__)
        records.append(record)
    report = {'format_version': 1, 'asset_bodies_downloaded': False,
              'models_called': False, 'sources': records,
              'limitations': ['Pointer discovery does not verify attachment license.',
                              'Candidate URLs are not proof that an asset is publicly retrievable.',
                              'No attachment body was downloaded or sent to a model.']}
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Supplementary asset discovery', '',
             'asset_bodies_downloaded: false', 'models_called: false', '']
    for rec in records:
        lines += [f"## {rec['id']} ({rec['doi']})", f"status: {rec['status']}",
                  f"oai_sha256: {rec['oai_sha256']}",
                  f"article_license_urls: {', '.join(rec.get('article_license_urls', [])) or 'not found'}"]
        for ref in rec.get('attachment_refs', []):
            lines.append(f"- attachment pointer: `{ref['href']}`; rights: not independently verified")
            for candidate in ref.get('candidate_urls', []):
                lines.append(f"  candidate: {candidate}")
                for result in ref.get('probes', []):
                    if result.get('url') == candidate or result.get('status') is not None:
                        lines.append(f"  probe: {result}")
        lines.append('')
    (out / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--oai-dir', type=Path)
    parser.add_argument('--allow-public-egress', action='store_true')
    parser.add_argument('--probe-assets', action='store_true')
    args = parser.parse_args()
    if args.probe_assets and not args.allow_public_egress:
        parser.error('--probe-assets requires --allow-public-egress')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    report = discover(manifest, args.out, args.allow_public_egress, args.probe_assets, args.oai_dir)
    print(json.dumps({'out': str(args.out.resolve()), 'sources': len(report['sources']),
                      'asset_bodies_downloaded': False}))


if __name__ == '__main__':
    main()
