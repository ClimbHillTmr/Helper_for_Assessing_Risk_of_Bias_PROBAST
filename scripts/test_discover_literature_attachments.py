#!/usr/bin/env python3
"""Offline tests for supplementary pointer discovery."""
import json
from pathlib import Path
import tempfile
import unittest

import discover_literature_attachments as mod

OAI = b'''<OAI-PMH><GetRecord><record><metadata><article>
<front><article-meta><article-id pub-id-type="doi">10.1234/test</article-id>
<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/" xmlns:xlink="http://www.w3.org/1999/xlink"/></permissions>
</article-meta></front><body><sec sec-type="supplementary-material"><supplementary-material id="s1"><media xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="file.pdf"/></supplementary-material></sec></body>
</article></metadata></record></GetRecord></OAI-PMH>'''


class DiscoveryTests(unittest.TestCase):
    def test_pointer_is_found_without_download_or_rights_upgrade(self):
        source = {'id': 'PMC1', 'doi': '10.1234/test'}
        record = mod.extract_oai(OAI, source)
        self.assertEqual(record['attachment_refs'][0]['href'], 'file.pdf')
        self.assertEqual(record['article_license_urls'],
                         ['https://creativecommons.org/licenses/by/4.0/'])

    def test_internal_subset_rejected(self):
        with self.assertRaisesRegex(ValueError, 'doctype_internal_subset_not_allowed'):
            mod.extract_oai(b'<!DOCTYPE article [<!ATTLIST article x CDATA "y">]>' + OAI,
                            {'id': 'PMC1', 'doi': '10.1234/test'})

    def test_offline_run_records_missing_oai_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {'format_version': 1, 'sources': [{'id': 'PMC1', 'doi': '10.1234/test'}]}
            oai = root / 'oai'; oai.mkdir(); (oai / 'PMC1.xml').write_bytes(OAI)
            report = mod.discover(manifest, root / 'out', oai_dir=oai)
            self.assertFalse(report['asset_bodies_downloaded'])
            self.assertEqual(report['sources'][0]['status'],
                             'attachment_pointer_found_needs_rights_review')
            self.assertTrue((root / 'out/report.json').is_file())


if __name__ == '__main__':
    unittest.main()
