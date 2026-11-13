#!/usr/bin/env python3
"""Offline unit and fault-injection tests for literature_design.py."""
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import literature_design as ld

SAMPLE_JATS = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
<front><article-meta>
<article-id pub-id-type="doi">10.1234/design.test.1</article-id>
<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"><license-p>CC BY 4.0</license-p></license></permissions>
</article-meta></front>
<body>
<sec><title>Introduction</title>
<p>Previous studies split data into training and test sets with varying imputation methods.</p>
</sec>
<sec><title>Methods</title>
<sec><title>Participants and Study Design</title>
<p>We retrospectively enrolled 2,400 adult patients admitted to the intensive care unit between 2018 and 2022 to develop a prognostic prediction model for 30-day mortality.</p>
<p>All predictor variables were measured at baseline within 24 hours before index admission; the mortality endpoint was ascertained within 30 days after admission.</p>
<p>Patients were randomly split in a 7:3 ratio into training and test sets at the patient level, and 5-fold cross-validation was used for hyperparameter tuning via grid search.</p>
<p>Model performance was evaluated using AUROC, Brier score, calibration curves, and decision curve analysis in internal validation.</p>
<table-wrap id="T1"><label>Table 1</label><caption><p>Baseline characteristics and preprocessing summary.</p></caption>
<table><tbody><tr><td>Median imputation and standard scaling were fitted on training folds only.</td></tr></tbody></table>
</table-wrap>
<fig id="F1"><label>Figure 1</label><caption><p>Cohort inclusion flowchart.</p></caption></fig>
<supplementary-material id="S1"><label>Supplement 1</label><media xlink:href="supp1.docx"/></supplementary-material>
<supplementary-material id="S2"><label>Supplement 2</label><media xlink:href="unacquired_supp.pdf"/></supplementary-material>
</sec></sec>
</body>
</article>"""


def make_docx_bytes(paragraphs, raw_xml_override=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        if raw_xml_override is not None:
            zf.writestr('word/document.xml', raw_xml_override)
        else:
            body = ''.join(f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in paragraphs)
            xml_str = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f'<w:body>{body}</w:body></w:document>'
            )
            zf.writestr('word/document.xml', xml_str.encode('utf-8'))
    return buf.getvalue()


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


class LiteratureDesignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.xml_path = self.root / 'article.xml'
        self.xml_path.write_text(SAMPLE_JATS, encoding='utf-8')
        self.xml_sha = sha256_bytes(self.xml_path.read_bytes())

        self.docx_bytes = make_docx_bytes([
            'Supplementary Methods: Random forest hyperparameters were tuned strictly inside 5-fold cross-validation on the training partition.',
            'No test set observations were accessed during feature selection or scaling.',
        ])
        self.docx_path = self.root / 'supp1.docx'
        self.docx_path.write_bytes(self.docx_bytes)
        self.docx_sha = sha256_bytes(self.docx_bytes)

        self.config_path = self.root / 'config.json'
        self.config_path.write_text(json.dumps({
            'format_version': 1,
            'max_requests': 20,
            'timeout_seconds': 30,
            'models': {
                'analysis': {'provider': 'p', 'model': 'm-a', 'command': ['NEVER_RUN']},
                'reviewer': {'provider': 'p', 'model': 'm-r', 'command': ['NEVER_RUN']},
            },
        }), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def write_manifest(self, supplements=None):
        src = {
            'id': 'PMC_SYNTH_1',
            'doi': '10.1234/design.test.1',
            'title': 'Synthetic ICU Mortality Prediction Study',
            'license_url': 'https://creativecommons.org/licenses/by/4.0/',
            'rights_basis': 'CC BY 4.0 declared in JATS article-meta.',
            'path': 'article.xml',
            'sha256': self.xml_sha,
        }
        if supplements is not None:
            src['supplements'] = supplements
        manifest_path = self.root / 'manifest.json'
        manifest_path.write_text(json.dumps({'format_version': 2, 'sources': [src]}), encoding='utf-8')
        return manifest_path

    def test_layers_and_study_design_extraction_with_verified_docx(self):
        manifest = self.write_manifest(supplements=[
            {
                'id': 'S1',
                'href': 'supp1.docx',
                'path': 'supp1.docx',
                'sha256': self.docx_sha,
                'media_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'license_url': 'https://creativecommons.org/licenses/by/4.0/',
                'rights_verified': True,
            },
            {
                'id': 'S2_UNVERIFIED',
                'href': 'unacquired_supp.pdf',
                'path': 'supp1.docx',
                'sha256': self.docx_sha,
                'media_type': 'application/pdf',
                'license_url': None,
                'rights_verified': False,
            },
        ])
        out = self.root / 'out-design'
        rc = ld.main(['--manifest', str(manifest), '--config', str(self.config_path),
                      '--out', str(out), '--include-tables'])
        self.assertEqual(rc, 0)
        report = json.loads((out / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['state'], 'DRY_RUN')
        src = report['sources'][0]
        cov = src['coverage']
        self.assertEqual(cov['body_paragraphs_indexed'], 5)
        self.assertEqual(cov['tables_indexed'], 1)
        self.assertEqual(cov['figure_captions_indexed'], 1)
        self.assertEqual(cov['supplement_paragraphs_indexed'], 2)
        self.assertEqual(cov['supplements_parsed'], 1)

        statuses = {s['id']: s['status'] for s in src['supplements']}
        self.assertEqual(statuses['S1'], 'PARSED_AND_VERIFIED')
        self.assertEqual(statuses['S2_UNVERIFIED'], 'RIGHTS_UNVERIFIED')

        design = src['study_design']['fields']
        self.assertEqual(design['study_purpose']['value'], 'prediction')
        self.assertEqual(design['unit_of_analysis']['value'], 'patient')
        self.assertEqual(design['validation_type']['value'], 'internal_only')
        for field, item in design.items():
            self.assertEqual(item['status'], 'extracted_candidate', field)
            self.assertTrue(len(item['citations']) >= 1, field)
            cite = item['citations'][0]
            self.assertGreaterEqual(cite['start'], 0)
            self.assertEqual(cite['length'], len(cite['quote']))

        # Section-aware ranking must put Methods paragraph ahead of Introduction paragraph
        split_q = next(q for q in src['questions'] if q['question_id'] == 'GROUP_SPLIT')
        top_ev = split_q['retrieved_evidence'][0]
        self.assertEqual(top_ev['section_priority'], 3)
        self.assertIn('Methods', top_ev['section_path'])

        # Completion manifest integrity
        comp = json.loads((out / 'completion.json').read_text(encoding='utf-8'))
        for rel, expected_sha in comp['artifacts'].items():
            self.assertEqual(sha256_bytes((out / rel).read_bytes()), expected_sha)

    def test_docx_entity_injection_is_blocked(self):
        malicious_docx = make_docx_bytes(
            [],
            raw_xml_override=b'<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe "boom">]><w:document xmlns:w="urn:w"><w:body><w:p><w:t>&xxe;</w:t></w:p></w:body></w:document>',
        )
        bad_path = self.root / 'bad.docx'
        bad_path.write_bytes(malicious_docx)
        manifest = self.write_manifest(supplements=[{
            'id': 'S_BAD',
            'href': 'supp1.docx',
            'path': 'bad.docx',
            'sha256': sha256_bytes(malicious_docx),
            'media_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'license_url': 'https://creativecommons.org/licenses/by/4.0/',
            'rights_verified': True,
        }])
        out = self.root / 'out-bad-docx'
        rc = ld.main(['--manifest', str(manifest), '--config', str(self.config_path), '--out', str(out)])
        self.assertEqual(rc, 2)
        report = json.loads((out / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['state'], 'BLOCKED')
        self.assertEqual(report['sources'][0]['diagnostic'], 'entity_not_allowed')

    def test_compare_run_attributes_layer_changes(self):
        manifest = self.write_manifest()
        out_body = self.root / 'out-body'
        ld.main(['--manifest', str(manifest), '--config', str(self.config_path), '--out', str(out_body)])
        out_tables = self.root / 'out-tables'
        rc = ld.main([
            '--manifest', str(manifest), '--config', str(self.config_path),
            '--out', str(out_tables), '--include-tables',
            '--compare-run', str(out_body / 'report.json'),
        ])
        self.assertEqual(rc, 0)
        report = json.loads((out_tables / 'report.json').read_text(encoding='utf-8'))
        comp = report['prior_comparison'][0]
        self.assertEqual(comp['source_id'], 'PMC_SYNTH_1')
        fit_comp = next(q for q in comp['question_comparisons'] if q['question_id'] == 'FIT_SCOPE')
        self.assertTrue(fit_comp['includes_non_body_layer'])


if __name__ == '__main__':
    unittest.main()
