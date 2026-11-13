#!/usr/bin/env python3
"""Parent adversarial regressions; no network or model calls."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'skills/medical-research-harness/scripts'))
import literature as core


class BoundaryTests(unittest.TestCase):
    def test_late_internal_subset_rejected(self):
        prefix = b'<!--' + b'x' * 9000 + b'-->'
        dtd = b'<!DOCTYPE article [<!ATTLIST license xlink:href CDATA "https://creativecommons.org/licenses/by/4.0/">]>'
        xml = b'<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><article-id pub-id-type="doi">10.1234/test</article-id><permissions><license>proprietary</license></permissions></article-meta></front><body><p>Training data.</p></body></article>'
        with self.assertRaisesRegex(ValueError, 'doctype_internal_subset_not_allowed'):
            core.parse_jats(prefix + dtd + xml, 's1')

    def test_quoted_doctype_delimiter_cannot_inject_license(self):
        dtd = '<!DOCTYPE article SYSTEM "http://x/y>z" [<!ATTLIST license xlink:href CDATA "https://creativecommons.org/licenses/by/4.0/">]>'
        article = '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><article-id pub-id-type="doi">10.1234/test</article-id><permissions><license>proprietary</license></permissions></article-meta></front><body><p>Training data.</p></body></article>'
        for encoding in ('utf-8', 'utf-16'):
            with self.subTest(encoding=encoding):
                raw = ('<?xml version="1.0" encoding="' + encoding + '"?>' + dtd + article).encode(encoding)
                with self.assertRaisesRegex(ValueError, 'doctype_internal_subset_not_allowed'):
                    core.parse_jats(raw, 's1')

    def test_paragraphs_keep_section_path_and_exclude_tables_figures(self):
        raw = b'''<article><front><article-meta/></front><body>
        <p>Intro.</p><sec><title>Methods</title><p>Methods text.</p>
        <sec><p>Nested unnamed.</p></sec>
        <table-wrap><p>Table caption.</p></table-wrap><fig><p>Figure caption.</p></fig>
        </sec></body></article>'''
        _, paragraphs = core.parse_jats(raw, 's1')
        self.assertEqual([p['text'] for p in paragraphs],
                         ['Intro.', 'Methods text.', 'Nested unnamed.'])
        self.assertEqual([p['section_path'] for p in paragraphs],
                         [[], ['Methods'], ['Methods', None]])

    def test_supplementary_pointer_is_collected_from_selected_article_back(self):
        raw = b'''<pmc-articleset xmlns:xlink="http://www.w3.org/1999/xlink">
        <article><front><article-meta><article-id pub-id-type="doi">10.1234/test</article-id></article-meta></front>
        <body><p>Training data.</p></body><back><supplementary-material id="mmc1"><label>Multimedia component 1</label><media xlink:href="mmc1.docx"/></supplementary-material></back></article>
        </pmc-articleset>'''
        meta, paragraphs = core.parse_jats(raw, 's1')
        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(meta['supplement_pointers'],
                         [{'id': 'mmc1', 'href': 'mmc1.docx', 'label': 'Multimedia component 1'}])

    def test_plain_external_doctype_does_not_fetch(self):
        # Successful parsing with an unreachable external identifier proves no
        # external DTD is needed, while quoted delimiters remain legal XML.
        raw = b'<!DOCTYPE article SYSTEM "file:///unavailable/quoted>[identifier.dtd"><article><front><article-meta/></front><body><p>Training data.</p></body></article>'
        meta, paragraphs = core.parse_jats(raw, 's1')
        self.assertEqual(meta['license_urls'], [])
        self.assertEqual(len(paragraphs), 1)

    def test_egress_recorded_when_later_source_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            sources = [{'id': name, 'doi': '10.1234/test', 'license_url': 'https://creativecommons.org/licenses/by/4.0/', 'rights_basis': 'public'} for name in ['s1', 's2']]
            (d / 'manifest.json').write_text(json.dumps({'format_version': 1, 'sources': sources}))
            model = {'provider': 'p', 'model': 'm', 'command': ['unused']}
            (d / 'config.json').write_text(json.dumps({'format_version': 1, 'max_requests': 30, 'timeout_seconds': 120, 'models': {'analysis': model, 'reviewer': model}}))
            outcome = {'paragraphs_indexed': 1, 'truncated_paragraphs': 0, 'request_count': 1, 'unresolved': [], 'errors': [], 'questions': [], 'attempts': []}
            args = SimpleNamespace(manifest=d/'manifest.json', config=d/'config.json', out=d/'out', execute_models=True, allow_public_egress=True)
            with mock.patch.object(core, 'verify_source', side_effect=[([{'id': 's1/p0001', 'text': 'text'}], {'doi': '10.1234/test'}), ValueError('bad source')]), mock.patch.object(core, 'analyze_source', return_value=outcome):
                report = core.run(args)
            self.assertEqual(report['state'], 'BLOCKED')
            self.assertEqual(report['request_count'], 1)
            self.assertTrue(report['public_egress']['executed'])

    def test_license_lookalikes_rejected(self):
        for url in ['https://creativecommons.org/licenses/by/4.0/evil',
                    'https://creativecommons.org/licenses/by/4.00/',
                    'https://creativecommons.org.evil/licenses/by/4.0/']:
            self.assertEqual(core.extract_cc_by_4_urls(ET.fromstring('<license>' + url + '</license>')), [])

    def test_ali_license_ref_retained(self):
        xml = '<license><license_ref>https://creativecommons.org/licenses/by/4.0/</license_ref><p>Other text</p></license>'
        self.assertIn('https://creativecommons.org/licenses/by/4.0', core.extract_cc_by_4_urls(ET.fromstring(xml)))

    def test_multiple_articles_rejected(self):
        with self.assertRaisesRegex(ValueError, 'multiple_articles_not_supported'):
            core.parse_jats(b'<pmc-articleset><article/><article/></pmc-articleset>', 's1')

    def test_no_hits_is_unresolved(self):
        source = {'id': 's1', 'meta': {'truncated_paragraphs': 0},
                  'paragraphs': [{'id': 's1/p0001', 'text': 'zzz', 'order': 1}]}
        models = {r: {'provider': 'p', 'model': 'm', 'command': ['unused']} for r in ('analysis', 'reviewer')}
        out = core.analyze_source(source, [{'id': 'Q', 'keywords': ['train']}], models, 30, 120, True)
        self.assertEqual(out['unresolved'], ['Q'])
        self.assertEqual(out['request_count'], 0)

    def test_empty_citations_rejected(self):
        response = {'model': 'm', 'question_id': 'Q', 'applicability': 'applicable',
                    'finding': 'reported_risk', 'summary': 'summary',
                    'citations': [{'id': 'e', 'quote': ' '}], 'missing_materials': []}
        with self.assertRaisesRegex(ValueError, 'quote_not_verbatim'):
            core.validate_response(json.dumps(response), {'model': 'm'}, {'id': 'Q'}, [{'id': 'e', 'text': 'a b'}])


if __name__ == '__main__':
    unittest.main()
