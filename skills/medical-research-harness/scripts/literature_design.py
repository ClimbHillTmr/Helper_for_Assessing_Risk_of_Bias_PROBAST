#!/usr/bin/env python3
"""Multi-layer literature indexing, study-design extraction, and section-aware audit.

Extends literature.py without modifying legacy body-paragraph IDs or v1/v2
checkpoint contracts. Separates typed evidence layers (body_paragraph, table,
figure_caption, supplement_paragraph), extracts an 11-field structured study
design with verbatim quote offset verification, performs section-aware
retrieval for the four engineering risk questions, and optionally compares
against a prior run report.

Core implementation uses only the Python 3.10+ standard library.
"""
import argparse
import io
import json
import re
import time
import xml.etree.ElementTree as ET
from xml.parsers import expat
import zipfile
from pathlib import Path

from decision_agent import ContractError, bounded_adapter, digest, need, strict_json, token
import laya_decision_adapter as lda
import literature as base

MAX_SUPPLEMENT_BYTES = 4 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 16 * 1024 * 1024
MAX_DOCX_MEMBERS = 256

DESIGN_FIELDS = (
    'study_purpose',
    'target_population',
    'unit_of_analysis',
    'prediction_target',
    'prediction_time_anchor',
    'feature_availability_time',
    'split_strategy',
    'preprocessing_scope',
    'tuning_strategy',
    'evaluation_metrics',
    'validation_type',
)

STUDY_PURPOSE_ENUM = {'prediction', 'causal_or_intervention', 'descriptive', 'other', 'unknown'}
UNIT_OF_ANALYSIS_ENUM = {'patient', 'admission_or_visit', 'sample_or_image', 'other', 'unknown'}
VALIDATION_TYPE_ENUM = {
    'internal_only', 'temporal', 'geographic_or_external',
    'internal_and_external', 'unknown',
}

DESIGN_KEYWORDS = {
    'study_purpose': ['predict', 'prediction', 'prognostic', 'diagnostic', 'risk model', 'machine learning', 'develop', 'validate'],
    'target_population': ['patients', 'cohort', 'enrolled', 'included', 'inclusion', 'exclusion', 'eligible', 'participants', 'diagnosed'],
    'unit_of_analysis': ['patient', 'patients', 'admission', 'encounter', 'visit', 'record', 'episode', 'eye', 'lesion'],
    'prediction_target': ['outcome', 'endpoint', 'mortality', 'death', 'complication', 'readmission', 'occurrence', 'defined as'],
    'prediction_time_anchor': ['baseline', 'admission', 'preoperative', 'postoperative', 'index', 'at the time of', 'prior to'],
    'feature_availability_time': ['predictor', 'variable', 'feature', 'measured', 'collected', 'recorded', 'available', 'baseline', 'before'],
    'split_strategy': ['split', 'divided', 'training', 'validation', 'test set', 'ratio', '7:3', '8:2', 'fold', 'cross-validation', 'partition'],
    'preprocessing_scope': ['imputation', 'missing', 'scaling', 'normalization', 'standardization', 'encoding', 'feature selection', 'smote', 'oversampling', 'complete-case', 'mice'],
    'tuning_strategy': ['hyperparameter', 'tuning', 'grid search', 'random search', 'bayesian', 'cross-validation', 'optimal', 'early stopping', 'optuna'],
    'evaluation_metrics': ['auc', 'auroc', 'roc', 'c-index', 'calibration', 'calibration slope', 'intercept', 'ici', 'brier', 'sensitivity', 'specificity', 'accuracy', 'f1', 'dca', 'decision curve', 'net benefit'],
    'validation_type': ['internal validation', 'external validation', 'bootstrap', 'cross-validation', 'hold-out', 'holdout', 'temporal', 'multicenter', 'recalibration', 'model updating', 'domain adaptation'],
}

METHODS_SECTION_HINTS = (
    'method', 'material', 'patient', 'participant', 'cohort', 'population',
    'data', 'variable', 'predictor', 'outcome', 'statistical', 'model',
    'development', 'validation', 'preprocessing', 'feature', 'training',
)
RESULTS_SECTION_HINTS = ('result', 'characteristic', 'performance', 'baseline')
LOW_PRIORITY_SECTION_HINTS = ('introduction', 'background', 'discussion', 'conclusion', ' limitation')


def parse_xml_safe(raw, error_code='invalid_xml'):
    """Parse XML bytes after rejecting any ENTITY or internal DOCTYPE subset."""
    need(b'<!entity' not in raw.lower(), 'entity_not_allowed')
    guard = expat.ParserCreate()

    def reject_internal_subset(name, system_id, public_id, has_internal_subset):
        need(not has_internal_subset, 'doctype_internal_subset_not_allowed')

    guard.StartDoctypeDeclHandler = reject_internal_subset
    guard.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    guard.ExternalEntityRefHandler = lambda *args: 1
    try:
        guard.Parse(raw, True)
        root = ET.fromstring(raw)
    except (expat.ExpatError, ET.ParseError) as exc:
        raise ContractError(error_code) from exc
    base.count_elements(root)
    return root


def extract_jats_layers(raw, source_id):
    """Return (meta, layers) where layers has body_paragraphs, tables, figure_captions."""
    meta, body_paragraphs = base.parse_jats(raw, source_id)
    root = parse_xml_safe(raw)
    articles = [root] if base.localname(root.tag) == 'article' else [
        el for el in root.iter() if base.localname(el.tag) == 'article'
    ]
    article = articles[0]
    body = base.first_child(article, 'body')
    tables = []
    figures = []
    t_seq = 0
    f_seq = 0

    def walk_layers(element, section_path=()):
        nonlocal t_seq, f_seq
        name = base.localname(element.tag)
        path = section_path
        if name == 'sec':
            title = base.first_child(element, 'title')
            title_text = base.paragraph_text(title) if title is not None else ''
            path = section_path + (title_text or None,)
        elif name == 'table-wrap':
            t_seq += 1
            label = base.child_text(element, 'label') or ''
            caption = base.child_text(element, 'caption') or ''
            full_text = base.paragraph_text(element)[:base.MAX_PARAGRAPH_CHARS]
            if full_text:
                tables.append({
                    'id': f'{source_id}/t{t_seq:04d}',
                    'layer': 'table',
                    'label': label,
                    'caption': caption,
                    'text': full_text,
                    'evidence_text': full_text,
                    'sha256': digest(full_text.encode('utf-8')),
                    'evidence_sha256': digest(full_text.encode('utf-8')),
                    'order': t_seq,
                    'section_path': list(path),
                })
            return
        elif name == 'fig':
            f_seq += 1
            label = base.child_text(element, 'label') or ''
            caption = base.child_text(element, 'caption') or ''
            full_text = base.paragraph_text(element)[:base.MAX_PARAGRAPH_CHARS]
            if full_text:
                figures.append({
                    'id': f'{source_id}/f{f_seq:04d}',
                    'layer': 'figure_caption',
                    'label': label,
                    'caption': caption,
                    'text': full_text,
                    'evidence_text': full_text,
                    'sha256': digest(full_text.encode('utf-8')),
                    'evidence_sha256': digest(full_text.encode('utf-8')),
                    'order': f_seq,
                    'section_path': list(path),
                })
            return
        for child in element:
            walk_layers(child, path)

    if body is not None:
        walk_layers(body)
    typed_body = []
    for para in body_paragraphs:
        item = dict(para)
        item['layer'] = 'body_paragraph'
        typed_body.append(item)
    return meta, {
        'body_paragraphs': typed_body,
        'tables': tables,
        'figure_captions': figures,
    }


def parse_docx_paragraphs(raw, prefix):
    """Safely extract paragraphs from a .docx archive using stdlib zipfile + expat."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise ContractError('invalid_docx_zip') from exc
    with zf:
        infos = zf.infolist()
        need(len(infos) <= MAX_DOCX_MEMBERS, 'docx_member_count_limit')
        total_uncompressed = sum(info.file_size for info in infos)
        need(total_uncompressed <= MAX_DOCX_UNCOMPRESSED_BYTES, 'docx_uncompressed_size_limit')
        need('word/document.xml' in zf.namelist(), 'docx_missing_document_xml')
        with zf.open('word/document.xml') as doc_stream:
            doc_xml = doc_stream.read(MAX_SUPPLEMENT_BYTES + 1)
    need(len(doc_xml) <= MAX_SUPPLEMENT_BYTES, 'docx_xml_size_limit')
    root = parse_xml_safe(doc_xml, error_code='invalid_docx_xml')
    paragraphs = []
    seq = 0
    for node in root.iter():
        if base.localname(node.tag) == 'p':
            text = base.paragraph_text(node)[:base.MAX_PARAGRAPH_CHARS]
            if text:
                seq += 1
                need(seq <= base.MAX_PARAGRAPHS, 'supplement_paragraph_limit')
                sha = digest(text.encode('utf-8'))
                paragraphs.append({
                    'id': f'{prefix}/p{seq:04d}',
                    'layer': 'supplement_paragraph',
                    'text': text,
                    'evidence_text': text,
                    'sha256': sha,
                    'evidence_sha256': sha,
                    'order': seq,
                    'section_path': ['Supplement'],
                })
    need(paragraphs, 'empty_supplement_paragraphs')
    return paragraphs


def parse_text_paragraphs(raw, prefix):
    try:
        content = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ContractError('invalid_supplement_utf8') from exc
    blocks = [
        ' '.join(chunk.split())
        for chunk in re.split(r'\n\s*\n', content)
        if chunk.strip()
    ]
    need(blocks, 'empty_supplement_paragraphs')
    paragraphs = []
    for idx, text in enumerate(blocks, start=1):
        need(idx <= base.MAX_PARAGRAPHS, 'supplement_paragraph_limit')
        clipped = text[:base.MAX_PARAGRAPH_CHARS]
        sha = digest(clipped.encode('utf-8'))
        paragraphs.append({
            'id': f'{prefix}/p{idx:04d}',
            'layer': 'supplement_paragraph',
            'text': clipped,
            'evidence_text': clipped,
            'sha256': sha,
            'evidence_sha256': sha,
            'order': idx,
            'section_path': ['Supplement'],
        })
    return paragraphs


def resolve_supplements(source, manifest_dir, declared_pointers):
    """Verify and parse declared local supplements; keep unverified pointers explicit."""
    declared_list = source.get('supplements', [])
    need(isinstance(declared_list, list), 'invalid_supplements_field')
    by_href = {}
    records = []
    supplement_paragraphs = []
    seen_ids = set()

    for supp in declared_list:
        need(isinstance(supp, dict)
             and {'id', 'href'} <= set(supp), 'invalid_supplement_entry')
        sid = supp['id']
        need(isinstance(sid, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', sid)
             and sid not in seen_ids, 'invalid_or_duplicate_supplement_id')
        seen_ids.add(sid)
        href = str(supp.get('href', '')).strip()
        rec = {
            'id': sid,
            'href': href,
            'media_type': supp.get('media_type', 'unknown'),
            'rights_verified': bool(supp.get('rights_verified', False)),
            'license_url': supp.get('license_url'),
            'status': 'UNACQUIRED',
            'paragraphs_indexed': 0,
            'sha256': None,
        }
        by_href[href] = rec
        if not supp.get('path'):
            rec['status'] = 'UNACQUIRED'
            records.append(rec)
            continue
        if not rec['rights_verified'] or base.norm_url(str(supp.get('license_url', ''))) not in base.CC_BY_4_URLS:
            rec['status'] = 'RIGHTS_UNVERIFIED'
            records.append(rec)
            continue
        path = (manifest_dir / str(supp['path'])).resolve()
        need(path.is_relative_to(manifest_dir.resolve()), 'supplement_path_outside_manifest_dir')
        if not path.is_file():
            rec['status'] = 'FILE_MISSING'
            records.append(rec)
            continue
        raw = base.read_bounded(path, MAX_SUPPLEMENT_BYTES, 'supplement_size_limit')
        actual_sha = digest(raw)
        need(isinstance(supp.get('sha256'), str) and actual_sha == supp['sha256'],
             'supplement_hash_mismatch:' + sid)
        rec['sha256'] = actual_sha
        prefix = f"{source['id']}/supp/{sid}"
        lower_path = path.name.lower()
        if lower_path.endswith('.docx'):
            paras = parse_docx_paragraphs(raw, prefix)
        elif lower_path.endswith(('.txt', '.md')):
            paras = parse_text_paragraphs(raw, prefix)
        else:
            rec['status'] = 'UNSUPPORTED_FORMAT_NOT_PARSED'
            records.append(rec)
            continue
        rec['status'] = 'PARSED_AND_VERIFIED'
        rec['paragraphs_indexed'] = len(paras)
        supplement_paragraphs.extend(paras)
        records.append(rec)

    for ptr in declared_pointers:
        href = ptr.get('href', '')
        if href and href not in by_href:
            records.append({
                'id': ptr.get('id') or href,
                'href': href,
                'label': ptr.get('label', ''),
                'media_type': 'unknown',
                'rights_verified': False,
                'license_url': None,
                'status': 'POINTER_DISCOVERED_UNACQUIRED',
                'paragraphs_indexed': 0,
                'sha256': None,
            })
    return records, supplement_paragraphs


def section_priority(section_path):
    """Assign deterministic section priority weight for retrieval."""
    if not section_path:
        return 1
    joined = ' '.join(str(part or '').lower() for part in section_path)
    if any(hint in joined for hint in METHODS_SECTION_HINTS):
        return 3
    if any(hint in joined for hint in RESULTS_SECTION_HINTS):
        return 2
    if any(hint in joined for hint in LOW_PRIORITY_SECTION_HINTS):
        return 0
    return 1


def retrieve_section_aware(keywords, candidates, k=base.EVIDENCE_K):
    """Score candidate evidence items combining keyword hits with section priority."""
    scored = []
    for idx, item in enumerate(candidates):
        text = item.get('evidence_text', item['text']).lower()
        hits = sum(1 for kw in keywords if kw.lower() in text)
        if hits > 0:
            sec_weight = section_priority(item.get('section_path', []))
            bonus = 2 if sec_weight == 3 else (0 if sec_weight >= 1 else -1)
            effective_score = hits + bonus
            scored.append((effective_score, sec_weight, hits, -idx, item))
    scored.sort(key=lambda entry: (entry[0], entry[1], entry[2], entry[3]), reverse=True)
    results = []
    for eff_score, sec_weight, hits, _, item in scored[:k]:
        ev = base.evidence_item(item)
        ev['layer'] = item.get('layer', 'body_paragraph')
        ev['section_path'] = item.get('section_path', [])
        ev['keyword_hits'] = hits
        ev['section_priority'] = sec_weight
        ev['effective_score'] = eff_score
        results.append(ev)
    return results


def best_verbatim_quote(evidence_list, keywords):
    """Extract a deterministic verbatim sentence/window with verified offsets."""
    for ev in evidence_list:
        text = ev['text']
        ref_text = ev.get('reference_text', text)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        for sent in sentences:
            lower = sent.lower()
            if any(kw.lower() in lower for kw in keywords):
                start = text.find(sent)
                if start >= 0 and ref_text[start:start + len(sent)] == sent:
                    return {
                        'id': ev['id'],
                        'layer': ev.get('layer', 'body_paragraph'),
                        'quote': sent,
                        'start': start,
                        'length': len(sent),
                    }
        # Fallback to first 240 chars of the evidence item if it does not cross mask
        snippet = text[:240].strip()
        if snippet:
            start = text.find(snippet)
            if start >= 0 and ref_text[start:start + len(snippet)] == snippet:
                return {
                    'id': ev['id'],
                    'layer': ev.get('layer', 'body_paragraph'),
                    'quote': snippet,
                    'start': start,
                    'length': len(snippet),
                }
    return None


def classify_study_purpose(quote_text):
    lower = quote_text.lower()
    if any(w in lower for w in ('predict', 'prediction', 'prognostic', 'diagnostic', 'risk model', 'nomogram', 'classifier', 'machine learning')):
        return 'prediction'
    if any(w in lower for w in ('randomized', 'intervention', 'causal', 'treatment effect', 'trial')):
        return 'causal_or_intervention'
    if any(w in lower for w in ('prevalence', 'incidence', 'descriptive', 'cross-sectional survey')):
        return 'descriptive'
    return 'unknown'


def classify_unit_of_analysis(quote_text):
    lower = quote_text.lower()
    if any(w in lower for w in ('patient', 'patients', 'participant', 'participants', 'subject', 'subjects')):
        return 'patient'
    if any(w in lower for w in ('admission', 'visit', 'encounter', 'hospitalization', 'episode')):
        return 'admission_or_visit'
    if any(w in lower for w in ('image', 'slide', 'lesion', 'sample', 'biopsy')):
        return 'sample_or_image'
    return 'unknown'


def classify_validation_type(quote_text):
    lower = quote_text.lower()
    has_ext = 'external validation' in lower or 'external test' in lower or 'independent cohort' in lower
    has_int = any(w in lower for w in ('internal validation', 'cross-validation', 'fold', 'bootstrap', 'random split', 'training and test', 'training set', 'test set', '7:3', '8:2'))
    has_temp = 'temporal validation' in lower or 'temporal split' in lower
    if has_ext and has_int:
        return 'internal_and_external'
    if has_ext:
        return 'geographic_or_external'
    if has_temp:
        return 'temporal'
    if has_int:
        return 'internal_only'
    return 'unknown'


DESIGN_PROMPTS = {
    'study_purpose': 'What is the primary methodological purpose of this study (prediction model development/validation vs causal/descriptive)?',
    'target_population': 'Which sentence defines the target clinical cohort, inclusion/exclusion criteria, or study setting?',
    'unit_of_analysis': 'What is the unit of analysis for modeling rows (individual patient vs hospital admission/visit vs specimen/image)?',
    'prediction_target': 'Which sentence defines the primary clinical outcome or prediction endpoint?',
    'prediction_time_anchor': 'Which sentence defines the prediction time origin (T0 / index time) at which risk is estimated?',
    'feature_availability_time': 'Which sentence specifies when predictor variables were measured or restricted relative to T0?',
    'split_strategy': 'How was the cohort partitioned into training, validation, and test sets?',
    'preprocessing_scope': 'How and within which data partition were missing-value imputation, scaling, and feature selection fitted?',
    'tuning_strategy': 'How were model hyperparameters and decision thresholds tuned or selected?',
    'evaluation_metrics': 'Which sentence states the discrimination, calibration, and clinical utility metrics used to evaluate the model?',
    'validation_type': 'What type of model validation was performed (internal only, temporal, geographic/external, or both)?',
}


def extract_study_design_deterministic(candidates):
    """Extract structured 11-field study design with verbatim quote verification."""
    prose_candidates = [c for c in candidates if c.get('layer', 'body_paragraph') != 'table']
    fields = {}
    for field in DESIGN_FIELDS:
        kws = DESIGN_KEYWORDS[field]
        pool = prose_candidates if prose_candidates else candidates
        ev_items = retrieve_section_aware(kws, pool, k=3)
        if not ev_items and pool is not candidates:
            ev_items = retrieve_section_aware(kws, candidates, k=3)
        cite = best_verbatim_quote(ev_items, kws)
        if cite is None:
            fields[field] = {
                'status': 'unknown',
                'value': 'unknown',
                'extraction_mode': 'deterministic_candidate',
                'citations': [],
                'evidence_ids': [],
            }
            continue
        if field == 'study_purpose':
            val = classify_study_purpose(cite['quote'])
        elif field == 'unit_of_analysis':
            val = classify_unit_of_analysis(cite['quote'])
        elif field == 'validation_type':
            val = classify_validation_type(cite['quote'])
        else:
            val = cite['quote']
        fields[field] = {
            'status': 'extracted_candidate' if val != 'unknown' else 'unknown',
            'value': val,
            'extraction_mode': 'deterministic_candidate',
            'citations': [cite],
            'evidence_ids': [item['id'] for item in ev_items],
        }
    return {
        'format_version': 1,
        'extraction_mode': 'deterministic_candidate',
        'tool_mapping': {
            'engineering_questions': ['FIT_SCOPE', 'EVAL_ROLE', 'GROUP_SPLIT', 'FEATURE_TIME'],
            'formal_probast_mapping_enabled': False,
            'reason': 'Full official PROBAST/PROBAST+AI signaling item text and license terms are not bundled; outputs remain engineering-risk drafts.',
        },
        'fields': fields,
    }


def extract_study_design_laya(candidates, laya_policy):
    """Extract 11-field study design using sentence-anchored MedBias-Laya (Task T2) with fallback to Methods paragraphs."""
    prose_candidates = [c for c in candidates if c.get('layer', 'body_paragraph') != 'table']
    pool = prose_candidates if prose_candidates else candidates
    methods_fallback = [
        base.evidence_item(c)
        for c in sorted(pool, key=lambda item: (section_priority(item.get('section_path', [])), -item.get('order', 0)), reverse=True)[:4]
    ]
    by_id = {c['id']: c for c in candidates}
    fields = {}
    for field in DESIGN_FIELDS:
        kws = DESIGN_KEYWORDS[field]
        ev_items = retrieve_section_aware(kws, pool, k=3)
        if not ev_items:
            ev_items = methods_fallback
        if not ev_items:
            fields[field] = {
                'status': 'unknown',
                'value': 'unknown',
                'extraction_mode': 'medbias_laya_sentence_anchored',
                'citations': [],
                'evidence_ids': [],
            }
            continue
        req = {
            'format_version': 1,
            'kind': 'study_design_extraction',
            'model': 'medbias-laya-v1',
            'task': {
                'field_name': field,
                'prompt': DESIGN_PROMPTS[field],
                'evidence': [{'id': it['id'], 'text': it['text']} for it in ev_items],
            },
        }
        res = lda.process_design_request(req, laya_policy)
        verified_cites = []
        for c in res.get('citations', []):
            src_item = by_id.get(c['id'])
            if src_item:
                ref_text = src_item.get('text', '')
                start = c['start']
                length = c['length']
                if 0 <= start and ref_text[start:start + length] == c['quote']:
                    verified_cites.append({
                        'id': c['id'],
                        'layer': src_item.get('layer', 'body_paragraph'),
                        'quote': c['quote'],
                        'start': start,
                        'length': length,
                    })
        status = res['status'] if verified_cites else 'unknown'
        val = res['value'] if verified_cites else 'unknown'
        fields[field] = {
            'status': status,
            'value': val,
            'category_choice': res.get('category_choice', 'unknown'),
            'confidence': res.get('confidence'),
            'extraction_mode': 'medbias_laya_sentence_anchored',
            'citations': verified_cites,
            'evidence_ids': [item['id'] for item in ev_items],
        }
    return {
        'format_version': 1,
        'extraction_mode': 'medbias_laya_sentence_anchored',
        'tool_mapping': {
            'engineering_questions': ['FIT_SCOPE', 'EVAL_ROLE', 'GROUP_SPLIT', 'FEATURE_TIME'],
            'formal_probast_mapping_enabled': False,
            'reason': 'Full official PROBAST/PROBAST+AI signaling item text and license terms are not bundled; outputs remain engineering-risk drafts.',
        },
        'fields': fields,
    }


def validate_ManifestV2(manifest):
    need(isinstance(manifest, dict) and manifest.get('format_version') in (1, 2)
         and isinstance(manifest.get('sources'), list) and bool(manifest['sources']),
         'invalid_manifest_contract')
    ids = set()
    for src in manifest['sources']:
        need(isinstance(src, dict) and token(src.get('id')) and src['id'] not in ids,
             'invalid_or_duplicate_source_id')
        ids.add(src['id'])
        allowed = {'id', 'doi', 'title', 'license_url', 'rights_basis', 'path', 'sha256', 'supplements'}
        need({'id', 'doi', 'title', 'license_url', 'rights_basis', 'path', 'sha256'} <= set(src)
             and set(src) <= allowed, 'invalid_source_contract')


def compare_with_prior(current_sources, prior_report):
    """Compare current per-source findings/coverage with a prior report.json."""
    prior_by_id = {s['id']: s for s in prior_report.get('sources', []) if isinstance(s, dict) and 'id' in s}
    comparisons = []
    for src in current_sources:
        sid = src['id']
        prior = prior_by_id.get(sid)
        if not prior:
            comparisons.append({'source_id': sid, 'status': 'new_source_not_in_prior'})
            continue
        prior_q = {q['question_id']: q for q in prior.get('questions', [])}
        q_diffs = []
        for q in src.get('questions', []):
            qid = q['question_id']
            pq = prior_q.get(qid, {})
            cur_ev = [e['id'] for e in q.get('retrieved_evidence', [])]
            has_non_body = any('/t' in eid or '/f' in eid or '/supp/' in eid for eid in cur_ev)
            if pq.get('state') != q.get('state') or pq.get('finding') != q.get('finding'):
                if prior_report.get('state') != 'DRY_RUN' and q.get('state') == 'NOT_REQUESTED':
                    cause = 'execution_mode_difference_dry_run_vs_live'
                elif has_non_body:
                    cause = 'typed_evidence_layer_addition'
                else:
                    cause = 'section_aware_retrieval_or_model_difference'
            else:
                cause = 'unchanged_state'
            q_diffs.append({
                'question_id': qid,
                'prior_state': pq.get('state'),
                'prior_finding': pq.get('finding'),
                'current_state': q.get('state'),
                'current_finding': q.get('finding'),
                'retrieved_evidence_ids': cur_ev,
                'includes_non_body_layer': has_non_body,
                'attribution': cause,
            })
        comparisons.append({
            'source_id': sid,
            'prior_paragraphs_indexed': prior.get('coverage', {}).get('paragraphs_indexed'),
            'current_body_paragraphs': src.get('coverage', {}).get('body_paragraphs_indexed'),
            'current_tables_indexed': src.get('coverage', {}).get('tables_indexed'),
            'current_figure_captions_indexed': src.get('coverage', {}).get('figure_captions_indexed'),
            'current_supplement_paragraphs_indexed': src.get('coverage', {}).get('supplement_paragraphs_indexed'),
            'question_comparisons': q_diffs,
        })
    return comparisons


def render_markdown(report):
    lines = [
        '# Literature Study-Design & Multi-Layer Audit Report',
        '',
        f"state: {report['state']}  exit_code: {report['exit_code']}  "
        f"requests: {report['request_count']}  elapsed: {report['elapsed_seconds']}s",
        f"include_tables_in_retrieval: {report['include_tables_in_retrieval']}  "
        f"execution_authorized: {report['execution_authorized']}  "
        f"scientific_acceptance: {report['scientific_acceptance']}",
        '',
    ]
    for src in report['sources']:
        lines.append(f"## {src['id']} ({src.get('doi', 'n/a')})")
        if src.get('diagnostic'):
            lines.append(f"BLOCKED: {src['diagnostic']}")
            lines.append('')
            continue
        cov = src['coverage']
        lines.append(
            f"- Evidence layers: body_paragraphs={cov['body_paragraphs_indexed']}, "
            f"tables={cov['tables_indexed']}, figure_captions={cov['figure_captions_indexed']}, "
            f"supplement_paragraphs={cov['supplement_paragraphs_indexed']}"
        )
        lines.append('### Structured Study Design (11 fields)')
        for field_name, info in src['study_design']['fields'].items():
            cites = ', '.join(f"{c['id']}@{c['start']}" for c in info['citations']) or 'none'
            val_preview = str(info['value'])
            if len(val_preview) > 120:
                val_preview = val_preview[:117] + '...'
            lines.append(f"- **{field_name}** [{info['status']}]: {val_preview} (citations: {cites})")
        lines.append('### Supplementary Material Status')
        for supp in src['supplements']:
            lines.append(
                f"- `{supp['href']}` (id={supp['id']}): status={supp['status']}, "
                f"rights_verified={supp['rights_verified']}, paragraphs={supp['paragraphs_indexed']}"
            )
        lines.append('### Engineering Risk Questions (Section-Aware Retrieval)')
        for q in src['questions']:
            ev_summary = ', '.join(
                f"{e['id']}[{e['layer']},sec_prio={e['section_priority']},hits={e['keyword_hits']}]"
                for e in q.get('retrieved_evidence', [])
            ) or 'none'
            lines.append(f"- **{q['question_id']}**: state={q['state']} evidence=({ev_summary})")
        lines.append('')
    if report.get('prior_comparison'):
        lines.append('## Comparison with Prior Run')
        for comp in report['prior_comparison']:
            lines.append(f"### {comp['source_id']}")
            for qd in comp.get('question_comparisons', []):
                lines.append(
                    f"- {qd['question_id']}: prior=({qd['prior_state']}/{qd['prior_finding']}) "
                    f"-> current=({qd['current_state']}/{qd['current_finding']}) "
                    f"[{qd['attribution']}]"
                )
        lines.append('')
    return '\n'.join(lines) + '\n'


def run(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    started = time.monotonic()
    report = {
        'format_version': 2,
        'state': 'DRY_RUN',
        'exit_code': 0,
        'execution_authorized': False,
        'scientific_acceptance': False,
        'include_tables_in_retrieval': bool(args.include_tables),
        'public_egress': {
            'requested': bool(args.allow_public_egress),
            'executed': False,
            'scope': 'manifest-declared public CC BY 4.0 full texts and verified supplements only',
        },
        'hashes': {
            'manifest_sha256': None,
            'config_sha256': None,
            'questions_sha256': None,
            'script_sha256': digest(Path(__file__).read_bytes()),
            'base_literature_sha256': digest(Path(base.__file__).read_bytes()),
        },
        'sources': [],
        'prior_comparison': None,
        'request_count': 0,
        'diagnostics': [],
        'elapsed_seconds': None,
        'limitations': [
            'Study design extraction in dry-run mode uses deterministic section-aware candidate selection with verbatim offset checks.',
            'Tables, figure captions, and supplements are stored in separate typed evidence layers and never silently overwrite body paragraph IDs.',
            'Supplements without verified CC BY 4.0 rights and matching SHA-256 remain UNACQUIRED or RIGHTS_UNVERIFIED.',
            'Outputs remain engineering-risk and study-design drafts; formal PROBAST/PROBAST+AI ratings require official instruments and human scientific review.',
        ],
    }
    try:
        raw_manifest = base.read_bounded(args.manifest, base.MAX_MANIFEST_BYTES, 'manifest_size_limit')
        raw_config = base.read_bounded(args.config, base.MAX_CONFIG_BYTES, 'config_size_limit')
        raw_questions = base.read_bounded(base.QUESTIONS_PATH, base.MAX_CONFIG_BYTES, 'questions_size_limit')
        report['hashes']['manifest_sha256'] = digest(raw_manifest)
        report['hashes']['config_sha256'] = digest(raw_config)
        report['hashes']['questions_sha256'] = digest(raw_questions)
        manifest = strict_json(raw_manifest)
        config = strict_json(raw_config)
        questions = strict_json(raw_questions)
        validate_ManifestV2(manifest)
        base.validate_config(config)
    except Exception as exc:
        report.update(state='BLOCKED', exit_code=2)
        report['diagnostics'].append(str(exc) if isinstance(exc, ContractError) else 'invalid_manifest_or_config')
        manifest = config = questions = None

    execute = bool(args.execute_models and args.allow_public_egress)
    if args.execute_models and not args.allow_public_egress:
        report.update(state='BLOCKED', exit_code=2)
        report['diagnostics'].append('egress_requires_allow_public_egress')
        manifest = None

    if manifest is not None:
        (out / 'attempts').mkdir(mode=0o700)
        manifest_dir = args.manifest.parent
        any_error = False
        for src in manifest['sources']:
            sid = src['id']
            entry = {'id': sid, 'doi': src.get('doi'), 'license_url': src.get('license_url')}
            try:
                base_src = {k: src[k] for k in ('id', 'doi', 'title', 'license_url', 'rights_basis', 'path', 'sha256')}
                path = base.validate_source(base_src, manifest_dir)
                raw = base.read_bounded(path, base.MAX_XML_BYTES, 'xml_size_limit')
                need(digest(raw) == src['sha256'], 'source_hash_mismatch')
                meta, layers = extract_jats_layers(raw, sid)
                need(meta['doi'] is not None and meta['doi'].lower() == src['doi'].strip().lower(), 'doi_mismatch')
                need(base.norm_url(src['license_url']) in set(meta['license_urls']), 'license_missing_or_mismatch')
                supp_records, supp_paragraphs = resolve_supplements(
                    src, manifest_dir, meta.get('supplement_pointers', [])
                )
            except Exception as exc:
                entry.update(
                    state='BLOCKED',
                    diagnostic=str(exc) if isinstance(exc, ContractError) else 'source_error:' + type(exc).__name__,
                )
                report['sources'].append(entry)
                report.update(state='BLOCKED', exit_code=2)
                continue

            layers['supplement_paragraphs'] = supp_paragraphs
            layers_index = {
                'format_version': 2,
                'source_id': sid,
                'doi': meta['doi'],
                'source_sha256': src['sha256'],
                'supplement_pointers': meta.get('supplement_pointers', []),
                'supplements': supp_records,
                'layers': layers,
            }
            base.save(out / f'layers.{sid}.json', layers_index)

            candidates = list(layers['body_paragraphs'])
            if args.include_tables:
                candidates.extend(layers['tables'])
            candidates.extend(layers['supplement_paragraphs'])

            if execute and getattr(args, 'design_laya_policy', None) is not None:
                laya_pol = lda.load_policy(args.design_laya_policy)
                design = extract_study_design_laya(candidates, laya_pol)
            else:
                design = extract_study_design_deterministic(candidates)
            base.save(out / f'design.{sid}.json', design)

            q_entries = []
            attempts = []
            errors = []
            unresolved = []
            req_count = 0
            same_model = (
                (config['models']['analysis']['provider'], config['models']['analysis']['model'])
                == (config['models']['reviewer']['provider'], config['models']['reviewer']['model'])
            )
            artifact_dir = out / 'attempts' / sid
            budget = config['max_requests']
            timeout = config['timeout_seconds']

            for q in questions['questions']:
                ev_items = retrieve_section_aware(q['keywords'], candidates, k=base.EVIDENCE_K)
                q_entry = {
                    'question_id': q['id'],
                    'state': 'NOT_REQUESTED' if ev_items else 'INSUFFICIENT',
                    'finding': None if ev_items else 'insufficient',
                    'evidence_count': len(ev_items),
                    'retrieved_evidence': [
                        {
                            'id': item['id'],
                            'layer': item['layer'],
                            'section_path': item['section_path'],
                            'keyword_hits': item['keyword_hits'],
                            'section_priority': item['section_priority'],
                        }
                        for item in ev_items
                    ],
                    'analysis': None,
                    'review': None,
                }
                if not ev_items:
                    q_entry['note'] = 'no_evidence_retrieved'
                    unresolved.append(q['id'])
                    q_entries.append(q_entry)
                    continue
                if not execute:
                    q_entries.append(q_entry)
                    continue

                if req_count >= budget:
                    errors.append('request_budget_exhausted')
                    q_entry.update(state='BLOCKED', note='request_budget_exhausted')
                    unresolved.append(q['id'])
                    q_entries.append(q_entry)
                    continue

                attempt = {
                    'source_id': sid,
                    'role': 'analysis',
                    'question_id': q['id'],
                    'attempt_index': len(attempts) + 1,
                    'requested_model': config['models']['analysis']['model'],
                    'status': 'error',
                }
                attempts.append(attempt)
                req_count += 1
                response, error = base.call_model(
                    config['models']['analysis'], q, ev_items, timeout, attempt, artifact_dir
                )
                if error:
                    attempt['error'] = error
                if response is None:
                    q_entry.update(state='BLOCKED', note='analysis_failed')
                    errors.append('analysis_failed:' + q['id'])
                    unresolved.append(q['id'])
                    q_entries.append(q_entry)
                    continue
                q_entry['analysis'] = {
                    'finding': response['finding'],
                    'applicability': response['applicability'],
                    'summary': response['summary'],
                    'citations': response['citations'],
                    'missing_materials': response['missing_materials'],
                }
                if req_count >= budget:
                    errors.append('request_budget_exhausted')
                    q_entry.update(
                        state='UNRESOLVED',
                        finding=response['finding'],
                        applicability=response['applicability'],
                        note='reviewer_failed_or_unrequested',
                    )
                    unresolved.append(q['id'])
                    q_entries.append(q_entry)
                    continue

                rev_attempt = {
                    'source_id': sid,
                    'role': 'reviewer',
                    'question_id': q['id'],
                    'blind': True,
                    'attempt_index': len(attempts) + 1,
                    'requested_model': config['models']['reviewer']['model'],
                    'status': 'error',
                }
                attempts.append(rev_attempt)
                req_count += 1
                rev_response, rev_error = base.call_model(
                    config['models']['reviewer'], q, ev_items, timeout, rev_attempt, artifact_dir
                )
                if rev_error:
                    rev_attempt['error'] = rev_error
                    q_entry.update(
                        state='UNRESOLVED',
                        finding=response['finding'],
                        applicability=response['applicability'],
                        note='reviewer_failed_or_unrequested',
                    )
                    unresolved.append(q['id'])
                    q_entries.append(q_entry)
                    continue
                q_entry['review'] = {
                    'finding': rev_response['finding'],
                    'applicability': rev_response['applicability'],
                    'summary': rev_response['summary'],
                    'citations': rev_response['citations'],
                    'same_model_independent_context': same_model,
                }
                if (rev_response['finding'] != response['finding']
                        or rev_response['applicability'] != response['applicability']):
                    q_entry.update(
                        state='UNRESOLVED',
                        finding=response['finding'],
                        applicability=response['applicability'],
                        reviewer_finding=rev_response['finding'],
                        reviewer_applicability=rev_response['applicability'],
                        note='analysis_review_disagreement_preserved',
                    )
                    unresolved.append(q['id'])
                elif response['finding'] == 'insufficient':
                    q_entry.update(
                        state='INSUFFICIENT',
                        finding='insufficient',
                        applicability=response['applicability'],
                        note='agreed_insufficient',
                    )
                    unresolved.append(q['id'])
                else:
                    q_entry.update(
                        state='ASSESSED',
                        finding=response['finding'],
                        applicability=response['applicability'],
                    )
                q_entries.append(q_entry)

            entry.update(
                state='INDEXED' if not execute else ('BLOCKED' if errors else 'ANALYZED'),
                coverage={
                    'body_paragraphs_indexed': len(layers['body_paragraphs']),
                    'tables_indexed': len(layers['tables']),
                    'figure_captions_indexed': len(layers['figure_captions']),
                    'supplement_paragraphs_indexed': len(supp_paragraphs),
                    'supplements_declared_or_discovered': len(supp_records),
                    'supplements_parsed': sum(1 for r in supp_records if r['status'] == 'PARSED_AND_VERIFIED'),
                },
                study_design=design,
                supplements=supp_records,
                request_count=req_count,
                questions=q_entries,
                attempts=attempts,
                errors=errors,
                unresolved=unresolved,
            )
            report['request_count'] += req_count
            if errors or unresolved:
                any_error = True
            report['sources'].append(entry)

        if report['state'] != 'BLOCKED':
            if execute:
                report['state'] = 'PARTIAL' if any_error else 'AWAITING_SCIENTIFIC_REVIEW'
                report['exit_code'] = 1 if any_error else 0
            else:
                report['state'] = 'DRY_RUN'
        report['public_egress']['executed'] = report['request_count'] > 0

        if args.compare_run and report['state'] != 'BLOCKED':
            try:
                prior_raw = base.read_bounded(args.compare_run, base.MAX_MANIFEST_BYTES, 'compare_run_size_limit')
                prior_report = strict_json(prior_raw)
                report['prior_comparison'] = compare_with_prior(report['sources'], prior_report)
            except Exception as exc:
                report.update(state='BLOCKED', exit_code=2)
                report['diagnostics'].append('invalid_compare_run:' + str(exc))

    report['elapsed_seconds'] = round(time.monotonic() - started, 4)
    base.save(out / 'report.json', report)
    (out / 'report.md').write_text(render_markdown(report), encoding='utf-8')
    artifacts = {
        str(p.relative_to(out)): digest(p.read_bytes())
        for p in sorted(out.rglob('*'))
        if p.is_file() and p.name not in {'.completion.tmp', 'completion.json'}
    }
    base.save(
        out / '.completion.tmp',
        {'format_version': 1, 'state': report['state'], 'exit_code': report['exit_code'], 'artifacts': artifacts},
    )
    (out / '.completion.tmp').replace(out / 'completion.json')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--include-tables', action='store_true',
                        help='Include typed table-wrap layer in candidate evidence retrieval')
    parser.add_argument('--compare-run', type=Path,
                        help='Optional path to prior report.json for question-by-question comparison')
    parser.add_argument('--design-laya-policy', type=Path,
                        help='Optional path to MedBias-Laya policy JSON for sentence-anchored 11-field study design extraction')
    parser.add_argument('--execute-models', action='store_true')
    parser.add_argument('--allow-public-egress', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = run(args)
    except (OSError, ValueError):
        print(json.dumps({'state': 'BLOCKED', 'error': 'input_or_output_error', 'exit_code': 2}))
        return 2
    print(json.dumps({
        'state': report['state'],
        'exit_code': report['exit_code'],
        'sources': len(report['sources']),
    }))
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
