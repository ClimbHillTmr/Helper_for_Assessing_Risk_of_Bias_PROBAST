#!/usr/bin/env python3
"""Offline unit and end-to-end literature integration tests for laya_decision_adapter.py."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import laya_decision_adapter as lda
import literature as lit
import literature_design as ldes
import project_audit as paudit


MOCK_LAYA_SCRIPT = """\
import json, sys
req = json.load(sys.stdin)
mode = sys.argv[1]
kind = req.get('kind', 'laya_typed_decisions_request')

if kind == 'laya_study_design_request':
    val_opts = list(req['questions'][0]['options'].keys())
    cit_opts = [k for k in req['questions'][1]['options'] if k != 'NONE']
    target_val = val_opts[0]
    first_s = cit_opts[0] if cit_opts else 'NONE'
    val_p = {k: (0.90 if k == target_val else 0.10 / max(len(val_opts) - 1, 1)) for k in val_opts}
    cit_p = {k: (0.88 if k == first_s else 0.12 / max(len(cit_opts), 1)) for k in req['questions'][1]['options']}
    json.dump({
        'model': 'medbias-laya-mock',
        'answers': {
            'field_value': {'probabilities': val_p},
            'citation_span': {'probabilities': cit_p},
        }
    }, sys.stdout)
    raise SystemExit(0)

if kind == 'laya_code_audit_request':
    rule_opts = list(req['questions'][0]['options'].keys())
    cit_opts = [k for k in req['questions'][1]['options'] if k != 'NONE']
    first_s = cit_opts[0] if cit_opts else 'NONE'
    target_rule = 'UNSCOPED_PREPROCESSING_FIT'
    rule_p = {k: (0.91 if k == target_rule else 0.09 / max(len(rule_opts) - 1, 1)) for k in rule_opts}
    cit_p = {k: (0.89 if k == first_s else 0.11 / max(len(cit_opts), 1)) for k in req['questions'][1]['options']}
    json.dump({
        'model': 'medbias-laya-mock',
        'answers': {
            'risk_rule': {'probabilities': rule_p},
            'citation_span': {'probabilities': cit_p},
        }
    }, sys.stdout)
    raise SystemExit(0)

cit_opts = [k for k in req['questions'][2]['options'] if k != 'NONE']
first_s = cit_opts[0] if cit_opts else 'NONE'

if mode == 'high_conf_risk':
    app_p = {'applicable': 0.92, 'unclear': 0.05, 'not_applicable': 0.03}
    fnd_p = {'reported_risk': 0.88, 'no_risk_identified': 0.07, 'insufficient': 0.05}
    cit_p = {k: (0.85 if k == first_s else 0.15 / max(len(cit_opts), 1)) for k in req['questions'][2]['options']}
elif mode == 'low_conf_clearance':
    app_p = {'applicable': 0.90, 'unclear': 0.05, 'not_applicable': 0.05}
    # 0.78 is above min_confidence (0.70) but below clearance_min_confidence (0.85)
    fnd_p = {'reported_risk': 0.12, 'no_risk_identified': 0.78, 'insufficient': 0.10}
    cit_p = {k: (0.80 if k == first_s else 0.20 / max(len(cit_opts), 1)) for k in req['questions'][2]['options']}
elif mode == 'missing_pointer':
    app_p = {'applicable': 0.90, 'unclear': 0.05, 'not_applicable': 0.05}
    fnd_p = {'reported_risk': 0.86, 'no_risk_identified': 0.07, 'insufficient': 0.07}
    cit_p = {k: (0.85 if k == 'NONE' else 0.15 / max(len(cit_opts), 1)) for k in req['questions'][2]['options']}
else:
    raise SystemExit(3)

json.dump({
    'model': 'laya-multilingual-mock',
    'answers': {
        'applicability': {'probabilities': app_p},
        'finding': {'probabilities': fnd_p},
        'citation_span': {'probabilities': cit_p},
    }
}, sys.stdout)
"""

MOCK_REASONER_SCRIPT = """\
import json, sys
req = json.load(sys.stdin)
ev = req['task']['evidence'][0]
quote = ev['text'].split('.')[0].strip() + '.'
json.dump({
    'model': req['model'],
    'question_id': req['task']['question_id'],
    'applicability': 'applicable',
    'finding': 'no_risk_identified',
    'summary': 'Escalated to reasoner: verified training-fold isolation.',
    'citations': [{'id': ev['id'], 'quote': quote}],
    'missing_materials': []
}, sys.stdout)
"""


class LayaDecisionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.mock_laya = self.root / 'mock_laya.py'
        self.mock_laya.write_text(MOCK_LAYA_SCRIPT, encoding='utf-8')
        self.mock_reasoner = self.root / 'mock_reasoner.py'
        self.mock_reasoner.write_text(MOCK_REASONER_SCRIPT, encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def sample_request(self):
        return {
            'format_version': 1,
            'provider': 'local-laya',
            'model': 'medbias-laya-0.1',
            'task': {
                'question_id': 'FIT_SCOPE',
                'question': 'Were preprocessing steps fitted on training folds only?',
                'evidence': [
                    {
                        'id': 's1/p0001',
                        'text': 'Median imputation was fitted on the entire dataset before splitting. Then 5-fold cross-validation was run.',
                    }
                ],
            },
            'instruction': lit.INSTRUCTION,
        }

    def test_sentence_segmentation_and_verbatim_citation_mapping(self):
        req = self.sample_request()
        policy = {
            'format_version': 1,
            'laya_command': [sys.executable, str(self.mock_laya), 'high_conf_risk'],
            'min_confidence': 0.70,
            'clearance_min_confidence': 0.85,
            'citation_min_confidence': 0.60,
        }
        resp = lda.process_request(json.dumps(req).encode('utf-8'), policy)
        # Validate against literature.py's exact validator!
        validated = lit.validate_response(
            json.dumps(resp).encode('utf-8'),
            {'model': 'medbias-laya-0.1'},
            {'id': 'FIT_SCOPE'},
            req['task']['evidence'],
        )
        self.assertEqual(validated['finding'], 'reported_risk')
        self.assertEqual(validated['applicability'], 'applicable')
        self.assertEqual(len(validated['citations']), 1)
        self.assertEqual(
            validated['citations'][0]['quote'],
            'Median imputation was fitted on the entire dataset before splitting.',
        )
        self.assertEqual(validated['citations'][0]['start'], 0)

    def test_asymmetrical_clearance_threshold_abstains_or_escalates(self):
        req = self.sample_request()
        # 1. Without reasoner_command: abstains to insufficient
        policy_no_reasoner = {
            'format_version': 1,
            'laya_command': [sys.executable, str(self.mock_laya), 'low_conf_clearance'],
            'min_confidence': 0.70,
            'clearance_min_confidence': 0.85,
        }
        resp_abstain = lda.process_request(json.dumps(req).encode('utf-8'), policy_no_reasoner)
        self.assertEqual(resp_abstain['finding'], 'insufficient')
        self.assertIn('selective_abstention:low_confidence_on_clearance', resp_abstain['missing_materials'])

        # 2. With reasoner_command: escalates to reasoner and returns verified response
        policy_cascade = dict(
            policy_no_reasoner,
            reasoner_command=[sys.executable, str(self.mock_reasoner)],
        )
        resp_escalated = lda.process_request(json.dumps(req).encode('utf-8'), policy_cascade)
        self.assertEqual(resp_escalated['finding'], 'no_risk_identified')
        self.assertIn('Escalated to reasoner', resp_escalated['summary'])

    def test_temperature_scaling_softens_and_sharpens_simplex(self):
        probs = {'a': 0.80, 'b': 0.15, 'c': 0.05}
        soft, choice_s, conf_s = lda.apply_temperature(probs, 2.0)
        sharp, choice_h, conf_h = lda.apply_temperature(probs, 0.5)
        self.assertEqual(choice_s, 'a')
        self.assertEqual(choice_h, 'a')
        self.assertLess(conf_s, 0.80)
        self.assertGreater(conf_h, 0.80)
        self.assertAlmostEqual(sum(soft.values()), 1.0, places=6)
        self.assertAlmostEqual(sum(sharp.values()), 1.0, places=6)

    def test_end_to_end_literature_py_with_laya_adapter_cli(self):
        jats = (
            '<?xml version="1.0"?><article xmlns:xlink="http://www.w3.org/1999/xlink">'
            '<front><article-meta><article-id pub-id-type="doi">10.1234/laya.e2e</article-id>'
            '<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>'
            '</article-meta></front><body><sec><title>Methods</title>'
            '<p>Patients were randomly split by patient-level group into training and test sets. '
            'Imputation and scaling were fitted on training folds only before final evaluation of AUC on the test set. '
            'All predictor features were measured at admission before the prediction time endpoint follow-up.</p>'
            '</sec></body></article>'
        )
        xml_path = self.root / 'paper.xml'
        xml_path.write_text(jats, encoding='utf-8')
        sha = hashlib.sha256(xml_path.read_bytes()).hexdigest()
        manifest_path = self.root / 'manifest.json'
        manifest_path.write_text(json.dumps({
            'format_version': 1,
            'sources': [{
                'id': 's1',
                'doi': '10.1234/laya.e2e',
                'title': 'Laya E2E Test',
                'license_url': 'https://creativecommons.org/licenses/by/4.0/',
                'rights_basis': 'CC BY 4.0',
                'path': 'paper.xml',
                'sha256': sha,
            }],
        }), encoding='utf-8')

        laya_policy = self.root / 'laya_policy.json'
        laya_policy.write_text(json.dumps({
            'format_version': 1,
            'laya_command': [sys.executable, str(self.mock_laya), 'high_conf_risk'],
            'min_confidence': 0.70,
            'clearance_min_confidence': 0.85,
            'citation_min_confidence': 0.60,
        }), encoding='utf-8')

        adapter_cmd = [
            sys.executable,
            str(HERE / 'laya_decision_adapter.py'),
            '--policy',
            str(laya_policy),
        ]
        config_path = self.root / 'config.json'
        config_path.write_text(json.dumps({
            'format_version': 1,
            'max_requests': 20,
            'timeout_seconds': 30,
            'models': {
                'analysis': {'provider': 'laya', 'model': 'medbias-laya-v1', 'command': adapter_cmd},
                'reviewer': {'provider': 'laya-rev', 'model': 'medbias-laya-rev-v1', 'command': adapter_cmd},
            },
        }), encoding='utf-8')

        out_dir = self.root / 'lit-out'
        proc = subprocess.run(
            [sys.executable, str(HERE / 'literature.py'),
             '--manifest', str(manifest_path),
             '--config', str(config_path),
             '--out', str(out_dir),
             '--execute-models', '--allow-public-egress'],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads((out_dir / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['state'], 'AWAITING_SCIENTIFIC_REVIEW')
        self.assertEqual(report['request_count'], 8)
        for q in report['sources'][0]['questions']:
            self.assertEqual(q['state'], 'ASSESSED')
            self.assertEqual(q['finding'], 'reported_risk')

    def test_task_t2_study_design_extraction_sentence_anchored(self):
        # Non-standard phrasing without standard regex keywords
        candidates = [
            {
                'id': 's1/p0001',
                'layer': 'body_paragraph',
                'text': 'Consecutive octogenarians presenting after ground-level falls were followed until discharge. '
                        'Derivation records from 2019-2021 were separated from 2022-2023 verification records.',
                'evidence_text': 'Consecutive octogenarians presenting after ground-level falls were followed until discharge. '
                                 'Derivation records from 2019-2021 were separated from 2022-2023 verification records.',
                'order': 1,
                'section_path': ['Methods'],
            }
        ]
        policy = {
            'format_version': 1,
            'laya_command': [sys.executable, str(self.mock_laya), 'design'],
            'min_confidence': 0.60,
        }
        design = ldes.extract_study_design_laya(candidates, policy)
        self.assertEqual(design['extraction_mode'], 'medbias_laya_sentence_anchored')
        self.assertEqual(design['fields']['study_purpose']['status'], 'extracted_laya')
        self.assertEqual(design['fields']['study_purpose']['value'], 'prediction')
        cite = design['fields']['study_purpose']['citations'][0]
        self.assertEqual(
            candidates[0]['text'][cite['start']:cite['start'] + cite['length']],
            cite['quote'],
        )

    def test_task_t3_cross_language_r_and_sas_code_audit(self):
        r_script = (
            "# R tidymodels pipeline\n"
            "rec_prep <- recipe(outcome ~ ., data = full_cohort) %>%\n"
            "  step_impute_knn(all_predictors()) %>%\n"
            "  prep(training = full_cohort)\n"
            "split_obj <- initial_split(full_cohort, prop = 0.8)\n"
        )
        sas_script = (
            "/* SAS pipeline */\n"
            "PROC STDIZE DATA=full_cohort OUT=norm_cohort METHOD=STD;\n"
            "  VAR lactate crp wbc;\n"
            "RUN;\n"
            "PROC SURVEYSELECT DATA=norm_cohort OUT=split_ds METHOD=SRS SAMPRATE=0.7;\n"
            "RUN;\n"
        )
        policy = {
            'format_version': 1,
            'laya_command': [sys.executable, str(self.mock_laya), 'code'],
            'min_confidence': 0.60,
            'clearance_min_confidence': 0.85,
        }
        r_inds = paudit.analyze_code_file(r_script, 'pipeline.R', laya_policy=policy)
        sas_inds = paudit.analyze_code_file(sas_script, 'pipeline.sas', laya_policy=policy)
        self.assertTrue(any(i['rule_id'] == 'UNSCOPED_PREPROCESSING_FIT' for i in r_inds))
        self.assertTrue(any(i['rule_id'] == 'UNGROUPED_ROW_SPLIT' for i in r_inds))
        self.assertTrue(any(i['rule_id'] == 'UNSCOPED_PREPROCESSING_FIT' for i in sas_inds))
        self.assertTrue(any(i['rule_id'] == 'UNGROUPED_ROW_SPLIT' for i in sas_inds))
        laya_r = [i for i in r_inds if i.get('detection_mode') == 'medbias_laya_code_span']
        self.assertTrue(len(laya_r) >= 1)
        self.assertEqual(
            r_script[laya_r[0]['start']:laya_r[0]['start'] + laya_r[0]['length']],
            laya_r[0]['quote'],
        )

    def test_decimal_and_abbreviation_safe_sentence_segmentation(self):
        para = (
            'Although all three models exhibited good predictive performances (AUC > 0.85, p < 0.001), '
            'the RF model demonstrated the strongest performance (Fig. 1 and Table. 2). '
            'Following Smith et al. (2024), e.g. median imputation was fitted inside each training fold.'
        )
        ordered_ids, cands = lda.segment_evidence_sentences([{'id': 'p1', 'text': para}])
        self.assertEqual(len(ordered_ids), 2)
        self.assertIn('AUC > 0.85', cands['S001']['quote'])
        self.assertIn('(Fig. 1 and Table. 2).', cands['S001']['quote'])
        self.assertIn('Smith et al.', cands['S002']['quote'])
        for sid in ordered_ids:
            c = cands[sid]
            self.assertEqual(para[c['start']:c['start'] + c['length']], c['quote'])


if __name__ == '__main__':
    unittest.main()
