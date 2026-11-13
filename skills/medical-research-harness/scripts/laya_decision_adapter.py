#!/usr/bin/env python3
"""Sentence-anchored Laya adapter and selective cascade for literature.py.

Bridges non-generative Laya `choice` heads with `literature.py`'s verbatim
citation contract:
  1. Deterministically segments retrieved evidence paragraphs into numbered
     sentence candidates (S001..Snnn) with exact character offsets.
  2. Compiles three typed `choice` questions (`applicability`, `finding`,
     `citation_span`) for a single-pass Laya encoder backend.
  3. Applies optional post-hoc temperature scaling and asymmetrical selective
     thresholds (stricter on `no_risk_identified` to prevent false clearance).
  4. Maps the selected sentence ID (`S00k`) back to an exact verbatim quote,
     or escalates uncertain / conflicting cases to a fallback reasoner adapter.

Core implementation uses only the Python 3.10+ standard library.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

from decision_agent import ContractError, bounded_adapter, need, strict_json, token

MAX_SENTENCES = 64
MIN_SENTENCE_CHARS = 8
APPLICABILITY_OPTIONS = {
    'applicable': 'The engineering risk question applies to this study design.',
    'unclear': 'Applicability cannot be determined from the provided method window.',
    'not_applicable': 'The study design makes this specific engineering risk question inapplicable.',
}
FINDING_OPTIONS = {
    'reported_risk': 'The text reports or implies a methodological risk or leakage violation.',
    'no_risk_identified': 'The text explicitly describes a valid control preventing this leakage risk.',
    'insufficient': 'The provided evidence window does not contain enough information to decide.',
}

DESIGN_FIELD_OPTIONS = {
    'study_purpose': {
        'prediction': 'Develop or validate a clinical diagnostic or prognostic prediction model.',
        'causal_or_intervention': 'Estimate causal treatment effect or evaluate a clinical intervention/trial.',
        'descriptive': 'Describe epidemiological prevalence, incidence, or unmodeled cohort characteristics.',
        'unknown': 'Study purpose is not determinable from the provided evidence window.',
    },
    'unit_of_analysis': {
        'patient': 'One record per unique individual patient or participant.',
        'admission_or_visit': 'Hospital admission, ICU stay, clinical encounter, or treatment cycle (potentially repeated per patient).',
        'sample_or_image': 'Lesion, biopsy, pathology slide, imaging slice, or laboratory specimen.',
        'unknown': 'Unit of analysis is not stated in the provided evidence window.',
    },
    'validation_type': {
        'internal_only': 'Internal validation only (random split, cross-validation, or bootstrap within one cohort).',
        'temporal': 'Temporal validation using chronologically separated development and test periods.',
        'geographic_or_external': 'External validation only on an independent center or registry cohort.',
        'internal_and_external': 'Both internal validation and independent external/multicenter validation.',
        'unknown': 'Validation strategy is not stated in the provided evidence window.',
    },
    'split_strategy': {
        'patient_grouped_split': 'Partitioned at the unique patient/cluster level so repeated encounters never cross splits.',
        'temporal_split': 'Partitioned by calendar timestamp or admission date.',
        'random_or_stratified_split': 'Random or outcome-stratified row-level train/test split without explicit patient clustering.',
        'cross_validation_or_bootstrap': 'Internal k-fold cross-validation or bootstrap resampling.',
        'unknown': 'Partitioning strategy is not determinable from the provided evidence window.',
    },
    'preprocessing_scope': {
        'in_fold_training_only': 'Imputation, scaling, feature selection, and resampling are fitted strictly inside each training fold/split.',
        'full_cohort_before_split': 'Preprocessing transformations are fitted on the full combined dataset prior to splitting.',
        'not_applicable_complete_or_locked': 'No data-driven preprocessing fitted (complete-case analysis or locked bedside score).',
        'unknown': 'Preprocessing fit boundary is not stated in the provided evidence window.',
    },
    'tuning_strategy': {
        'inner_cv_or_validation_only': 'Hyperparameters and thresholds are tuned strictly within training/inner-CV or validation folds.',
        'test_set_used_for_selection': 'Held-out test set is used to select the best model architecture, hyperparameters, or threshold.',
        'no_hyperparameter_tuning': 'Fixed pre-specified model specification with no hyperparameter search.',
        'unknown': 'Hyperparameter tuning scope is not stated in the provided evidence window.',
    },
    '_span_anchor_default': {
        'reported_in_window': 'The target study design attribute is explicitly stated in one of the candidate sentences.',
        'unknown': 'The target study design attribute is absent or cannot be determined from the window.',
    },
}

CODE_RISK_OPTIONS = {
    'NO_STRUCTURAL_LEAKAGE_DETECTED': 'Code properly scopes preprocessing to training folds, groups splits by patient, and isolates the test set.',
    'UNSCOPED_PREPROCESSING_FIT': 'Imputation, scaling, encoding, feature selection, or SMOTE is fitted on the full dataset or outside training folds.',
    'UNGROUPED_ROW_SPLIT': 'Repeated patient encounters or longitudinal records are split row-wise without grouping by patient identifier.',
    'TEST_SET_REUSE_IN_FIT_OR_SELECTION': 'Held-out test partition is used for model fitting, early stopping, threshold tuning, or best-model selection.',
    'POST_INDEX_FEATURE_LEAKAGE': 'Feature extraction queries measurements recorded after the prediction index time or uses post-outcome variables.',
}


_ABBREV_WORDS = {
    'fig', 'figs', 'table', 'tab', 'eq', 'eqs', 'ref', 'refs', 'al', 'vs',
    'dr', 'prof', 'mr', 'mrs', 'ms', 'no', 'nos', 'vol', 'pp', 'inc', 'ltd',
    'st', 'approx', 'ca', 'sec', 'supp', 'suppl', 'dept', 'univ', 'jr', 'sr',
}


def _iter_sentence_spans(text):
    """Yield (start_idx, end_idx) spans in `text` without splitting decimals or scientific abbreviations."""
    n = len(text)
    seg_start = 0
    i = 0
    while i < n:
        ch = text[i]
        if ch == '\n':
            if i > seg_start:
                yield seg_start, i
            seg_start = i + 1
            i += 1
            continue
        if ch in '.!?':
            # Consume consecutive punctuation (e.g. '...', '?!')
            j = i + 1
            while j < n and text[j] in '.!?)"\']':
                j += 1
            # Only consider boundary if followed by whitespace or end of string
            if j < n and not text[j].isspace():
                # e.g., decimal 0.85 or e.g. without space -> not a sentence boundary
                i = j
                continue
            if ch == '.':
                # Check preceding token before '.'
                prev_slice = text[max(0, seg_start):i].rstrip()
                prev_word_match = re.search(r'([A-Za-z0-9.]+)$', prev_slice)
                prev_word = prev_word_match.group(1).lower().rstrip('.') if prev_word_match else ''
                # Look ahead to first non-space char
                k = j
                while k < n and text[k].isspace() and text[k] != '\n':
                    k += 1
                next_ch = text[k] if k < n else ''
                # Do not split after known abbreviations (Fig. 1, et al., e.g., i.e., vs.)
                if prev_word in _ABBREV_WORDS or prev_word in ('e.g', 'i.e'):
                    i = j
                    continue
                # Do not split if period is preceded by digits and followed by digits (e.g., "0. 85")
                if prev_word.isdigit() and next_ch.isdigit():
                    i = j
                    continue
                # Do not split on single uppercase initial (e.g., "J. Smith")
                if len(prev_word) == 1 and prev_slice and prev_slice[-1].isupper() and next_ch.isupper():
                    i = j
                    continue
            yield seg_start, j
            seg_start = j
            i = j
            continue
        i += 1
    if seg_start < n:
        yield seg_start, n


def segment_evidence_sentences(evidence_items):
    """Split evidence items into numbered sentence candidates with exact offsets."""
    need(isinstance(evidence_items, list) and bool(evidence_items), 'empty_evidence_items')
    candidates = {}
    ordered_ids = []
    seq = 0
    for item in evidence_items:
        need(isinstance(item, dict) and {'id', 'text'} <= set(item), 'invalid_evidence_item')
        pid = item['id']
        text = item['text']
        need(isinstance(pid, str) and pid.strip() and isinstance(text, str) and text.strip(),
             'empty_evidence_text')
        for span_start, span_end in _iter_sentence_spans(text):
            raw_span = text[span_start:span_end]
            stripped = raw_span.strip()
            if len(stripped) < MIN_SENTENCE_CHARS:
                continue
            lead_ws = len(raw_span) - len(raw_span.lstrip())
            start = span_start + lead_ws
            length = len(stripped)
            need(text[start:start + length] == stripped, 'sentence_offset_mismatch')
            seq += 1
            if seq > MAX_SENTENCES:
                break
            sid = f'S{seq:03d}'
            candidates[sid] = {
                'sentence_id': sid,
                'paragraph_id': pid,
                'quote': stripped,
                'start': start,
                'length': length,
            }
            ordered_ids.append(sid)
        if seq > MAX_SENTENCES:
            break
    # Fallback if a paragraph had no punctuation or was shorter than MIN_SENTENCE_CHARS
    if not candidates:
        first = evidence_items[0]
        stripped = first['text'].strip()
        start = first['text'].index(stripped)
        candidates['S001'] = {
            'sentence_id': 'S001',
            'paragraph_id': first['id'],
            'quote': stripped,
            'start': start,
            'length': len(stripped),
        }
        ordered_ids.append('S001')
    return ordered_ids, candidates


def segment_code_blocks(source_text, file_id):
    """Split Python, R, or SAS source text into numbered statement blocks S001..Snnn with line and char offsets."""
    need(isinstance(source_text, str) and bool(source_text.strip()), 'empty_code_text')
    need(isinstance(file_id, str) and bool(file_id.strip()), 'invalid_file_id')
    candidates = {}
    ordered_ids = []
    seq = 0
    lines = source_text.splitlines(keepends=True)
    idx = 0
    char_cursor = 0
    while idx < len(lines) and seq < MAX_SENTENCES:
        raw_line = lines[idx]
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(('#', '//', '/*', '*')):
            char_cursor += len(raw_line)
            idx += 1
            continue
        start_line = idx + 1
        block_start = char_cursor + (len(raw_line) - len(raw_line.lstrip()))
        block_raw_len = len(raw_line)
        end_line = start_line
        idx += 1
        char_cursor += len(raw_line)
        # Group continuation lines (indented block, R pipe %>% / |>, SAS semicolon statement, or open parens)
        while idx < len(lines):
            nxt = lines[idx]
            nxt_s = nxt.strip()
            if not nxt_s:
                char_cursor += len(nxt)
                idx += 1
                break
            prev_text = source_text[block_start:char_cursor].rstrip()
            is_continuation = (
                prev_text.endswith((',', '(', '[', '{', '\\', '%>%', '|>', '+', '='))
                or (file_id.lower().endswith('.sas') and not prev_text.endswith(';'))
                or (nxt.startswith(('    ', '\t')) and (end_line - start_line) < 6)
            )
            if not is_continuation:
                break
            end_line = idx + 1
            char_cursor += len(nxt)
            idx += 1
        quote = source_text[block_start:char_cursor].rstrip()
        length = len(quote)
        if length < 4:
            continue
        need(source_text[block_start:block_start + length] == quote, 'code_block_offset_mismatch')
        seq += 1
        sid = f'S{seq:03d}'
        candidates[sid] = {
            'sentence_id': sid,
            'paragraph_id': file_id,
            'quote': quote,
            'start': block_start,
            'length': length,
            'start_line': start_line,
            'end_line': end_line,
        }
        ordered_ids.append(sid)
    if not candidates:
        stripped = source_text.strip()
        start = source_text.index(stripped)
        candidates['S001'] = {
            'sentence_id': 'S001',
            'paragraph_id': file_id,
            'quote': stripped,
            'start': start,
            'length': len(stripped),
            'start_line': 1,
            'end_line': max(1, len(lines)),
        }
        ordered_ids.append('S001')
    return ordered_ids, candidates


def get_design_field_options(field_name):
    return DESIGN_FIELD_OPTIONS.get(field_name, DESIGN_FIELD_OPTIONS['_span_anchor_default'])


def build_design_laya_payload(field_name, field_prompt, ordered_ids, candidates):
    """Build a single-pass Laya typed-decision payload for 11-field study design extraction (Task T2)."""
    state_lines = [
        f"Task: Structured Clinical Study Design Extraction ({field_name})",
        f"Design Attribute Prompt: {field_prompt}",
        '',
        'Segmented Evidence Sentences:',
    ]
    citation_options = {}
    for sid in ordered_ids:
        cand = candidates[sid]
        preview = cand['quote'][:110]
        state_lines.append(f"[{sid}] ({cand['paragraph_id']}): {cand['quote']}")
        citation_options[sid] = f"Sentence {sid} from {cand['paragraph_id']}: {preview}"
    citation_options['NONE'] = 'No sentence in the window defines or states this study design attribute.'

    return {
        'format_version': 1,
        'kind': 'laya_study_design_request',
        'field_name': field_name,
        'state': '\n'.join(state_lines),
        'questions': [
            {
                'id': 'field_value',
                'type': 'choice',
                'prompt': field_prompt,
                'options': get_design_field_options(field_name),
            },
            {
                'id': 'citation_span',
                'type': 'choice',
                'prompt': f'Which sentence explicitly states `{field_name}` ({field_prompt})?',
                'options': citation_options,
            },
        ],
    }


def validate_design_laya_response(raw_bytes, field_name, ordered_ids, temperatures):
    """Validate Laya Task T2 study design response and apply temperature scaling."""
    payload = strict_json(raw_bytes)
    need(isinstance(payload, dict) and {'model', 'answers'} <= set(payload),
         'invalid_laya_design_response')
    answers = payload['answers']
    need(isinstance(answers, dict) and set(answers) == {'field_value', 'citation_span'},
         'missing_laya_design_heads')
    valid_options = {
        'field_value': set(get_design_field_options(field_name)),
        'citation_span': set(ordered_ids) | {'NONE'},
    }
    calibrated = {}
    for head_name, allowed in valid_options.items():
        head = answers[head_name]
        need(isinstance(head, dict) and 'probabilities' in head, f'invalid_head:{head_name}')
        probs = head['probabilities']
        need(isinstance(probs, dict) and set(probs) == allowed, f'option_mismatch:{head_name}')
        temp = temperatures.get(head_name, 1.0)
        norm_probs, best_choice, best_conf = apply_temperature(probs, temp)
        calibrated[head_name] = {
            'choice': best_choice,
            'confidence': round(best_conf, 6),
            'probabilities': norm_probs,
        }
    return payload['model'], calibrated


def build_code_audit_laya_payload(file_id, language, ordered_ids, candidates):
    """Build a single-pass Laya typed-decision payload for cross-language code leakage audit (Task T3)."""
    state_lines = [
        f"Task: Clinical Modeling Code Pipeline Leakage Audit ({language})",
        f"File: {file_id}",
        '',
        'Segmented Code Blocks:',
    ]
    citation_options = {}
    for sid in ordered_ids:
        cand = candidates[sid]
        preview = ' '.join(cand['quote'].split())[:120]
        state_lines.append(
            f"[{sid}] ({file_id}:L{cand['start_line']}-L{cand['end_line']}): {cand['quote']}"
        )
        citation_options[sid] = (
            f"Block {sid} (L{cand['start_line']}-L{cand['end_line']}): {preview}"
        )
    citation_options['NONE'] = 'No code block exhibits a structural data leakage pattern.'

    return {
        'format_version': 1,
        'kind': 'laya_code_audit_request',
        'file_id': file_id,
        'language': language,
        'state': '\n'.join(state_lines),
        'questions': [
            {
                'id': 'risk_rule',
                'type': 'choice',
                'prompt': 'Does this clinical modeling script contain a structural data leakage or evaluation reuse defect?',
                'options': CODE_RISK_OPTIONS,
            },
            {
                'id': 'citation_span',
                'type': 'choice',
                'prompt': 'Which code block contains the primary structural leakage call or statement?',
                'options': citation_options,
            },
        ],
    }


def validate_code_audit_laya_response(raw_bytes, ordered_ids, temperatures):
    """Validate Laya Task T3 code audit response and apply temperature scaling."""
    payload = strict_json(raw_bytes)
    need(isinstance(payload, dict) and {'model', 'answers'} <= set(payload),
         'invalid_laya_code_response')
    answers = payload['answers']
    need(isinstance(answers, dict) and set(answers) == {'risk_rule', 'citation_span'},
         'missing_laya_code_heads')
    valid_options = {
        'risk_rule': set(CODE_RISK_OPTIONS),
        'citation_span': set(ordered_ids) | {'NONE'},
    }
    calibrated = {}
    for head_name, allowed in valid_options.items():
        head = answers[head_name]
        need(isinstance(head, dict) and 'probabilities' in head, f'invalid_head:{head_name}')
        probs = head['probabilities']
        need(isinstance(probs, dict) and set(probs) == allowed, f'option_mismatch:{head_name}')
        temp = temperatures.get(head_name, 1.0)
        norm_probs, best_choice, best_conf = apply_temperature(probs, temp)
        calibrated[head_name] = {
            'choice': best_choice,
            'confidence': round(best_conf, 6),
            'probabilities': norm_probs,
        }
    return payload['model'], calibrated


def build_laya_payload(req, ordered_ids, candidates):
    """Build a single-pass Laya typed-decision payload using `choice` primitives."""
    task = req['task']
    state_lines = [
        f"Question ID: {task['question_id']}",
        f"Methodology Question: {task['question']}",
        '',
        'Segmented Evidence Sentences:',
    ]
    citation_options = {}
    for sid in ordered_ids:
        cand = candidates[sid]
        preview = cand['quote'][:110]
        state_lines.append(f"[{sid}] ({cand['paragraph_id']}): {cand['quote']}")
        citation_options[sid] = f"Sentence {sid} from {cand['paragraph_id']}: {preview}"
    citation_options['NONE'] = 'No sentence in the window supports a definitive risk or clearance claim.'

    return {
        'format_version': 1,
        'kind': 'laya_typed_decisions_request',
        'question_id': task['question_id'],
        'state': '\n'.join(state_lines),
        'questions': [
            {
                'id': 'applicability',
                'type': 'choice',
                'prompt': 'Is this engineering risk question applicable to the study?',
                'options': APPLICABILITY_OPTIONS,
            },
            {
                'id': 'finding',
                'type': 'choice',
                'prompt': task['question'],
                'options': FINDING_OPTIONS,
            },
            {
                'id': 'citation_span',
                'type': 'choice',
                'prompt': f"Which sentence provides the strongest verbatim evidence for ({task['question_id']}): {task['question']}",
                'options': citation_options,
            },
        ],
    }


def apply_temperature(probs, temperature):
    """Apply post-hoc temperature scaling T > 0 to a probability dictionary."""
    need(isinstance(temperature, (int, float)) and math.isfinite(temperature) and temperature > 0,
         'invalid_temperature')
    need(isinstance(probs, dict) and bool(probs), 'empty_probabilities')
    raw_vals = []
    for k, v in probs.items():
        need(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0.0, 'invalid_probability_value')
        raw_vals.append((k, float(v)))
    total = sum(v for _, v in raw_vals)
    need(0.99 <= total <= 1.01, 'probabilities_do_not_sum_to_one')
    if abs(temperature - 1.0) < 1e-6:
        normed = {k: v / total for k, v in raw_vals}
    else:
        eps = 1e-12
        logits = {k: math.log(max(v / total, eps)) / float(temperature) for k, v in raw_vals}
        max_logit = max(logits.values())
        exps = {k: math.exp(val - max_logit) for k, val in logits.items()}
        denom = sum(exps.values())
        normed = {k: val / denom for k, val in exps.items()}
    best_key = max(normed.items(), key=lambda kv: kv[1])[0]
    return normed, best_key, normed[best_key]


def validate_laya_response(raw_bytes, ordered_ids, temperatures):
    """Validate Laya backend JSON and compute calibrated choices and confidences."""
    payload = strict_json(raw_bytes)
    need(isinstance(payload, dict) and {'model', 'answers'} <= set(payload),
         'invalid_laya_response_schema')
    answers = payload['answers']
    need(isinstance(answers, dict)
         and set(answers) == {'applicability', 'finding', 'citation_span'},
         'missing_laya_decision_heads')

    valid_options = {
        'applicability': set(APPLICABILITY_OPTIONS),
        'finding': set(FINDING_OPTIONS),
        'citation_span': set(ordered_ids) | {'NONE'},
    }
    calibrated = {}
    for head_name, allowed in valid_options.items():
        head = answers[head_name]
        need(isinstance(head, dict) and 'probabilities' in head, f'invalid_head:{head_name}')
        probs = head['probabilities']
        need(isinstance(probs, dict) and set(probs) == allowed,
             f'option_mismatch:{head_name}')
        temp = temperatures.get(head_name, 1.0)
        norm_probs, best_choice, best_conf = apply_temperature(probs, temp)
        calibrated[head_name] = {
            'choice': best_choice,
            'confidence': round(best_conf, 6),
            'probabilities': norm_probs,
        }
    return payload['model'], calibrated


def should_escalate(calibrated, policy):
    """Check asymmetrical selective routing thresholds."""
    app = calibrated['applicability']
    fnd = calibrated['finding']
    cit = calibrated['citation_span']

    min_conf = policy.get('min_confidence', 0.70)
    clearance_conf = policy.get('clearance_min_confidence', 0.85)
    citation_conf = policy.get('citation_min_confidence', 0.60)

    if fnd['choice'] == 'no_risk_identified' and fnd['confidence'] < clearance_conf:
        return True, 'low_confidence_on_clearance'
    if fnd['confidence'] < min_conf or app['confidence'] < min_conf:
        return True, 'below_confidence_threshold'
    if (fnd['choice'] != 'insufficient' or app['choice'] == 'not_applicable'):
        if cit['choice'] == 'NONE':
            return True, 'non_insufficient_without_sentence_pointer'
        if cit['confidence'] < citation_conf:
            return True, 'low_citation_pointer_confidence'
    return False, None


def format_literature_response(model_name, question_id, calibrated, candidates, abstained_reason=None):
    """Convert calibrated Laya choices + sentence ID into literature.py stdout JSON."""
    if abstained_reason is not None:
        return {
            'model': model_name,
            'question_id': question_id,
            'applicability': 'unclear',
            'finding': 'insufficient',
            'summary': (
                f'[MedBias-Laya selective abstention: {abstained_reason}] '
                'Evidence window requires escalation or additional material.'
            ),
            'citations': [],
            'missing_materials': [f'selective_abstention:{abstained_reason}'],
        }

    app_choice = calibrated['applicability']['choice']
    fnd_choice = calibrated['finding']['choice']
    cit_choice = calibrated['citation_span']['choice']
    fnd_conf = calibrated['finding']['confidence']

    citations = []
    if cit_choice != 'NONE' and cit_choice in candidates:
        cand = candidates[cit_choice]
        citations.append({'id': cand['paragraph_id'], 'quote': cand['quote']})

    if fnd_choice == 'insufficient' and app_choice != 'not_applicable':
        citations = []

    summary = (
        f"[MedBias-Laya choice={fnd_choice} (conf={fnd_conf:.3f}), "
        f"applicability={app_choice}, anchor={cit_choice}] "
        f"{FINDING_OPTIONS[fnd_choice]}"
    )
    return {
        'model': model_name,
        'question_id': question_id,
        'applicability': app_choice,
        'finding': fnd_choice,
        'summary': summary,
        'citations': citations,
        'missing_materials': [],
    }


def process_design_request(req, policy):
    """Process a Task T2 11-field study design extraction request through Laya."""
    task = req.get('task', {})
    need(isinstance(task, dict) and {'field_name', 'prompt', 'evidence'} <= set(task),
         'invalid_design_task_payload')
    field_name = task['field_name']
    ordered_ids, candidates = segment_evidence_sentences(task['evidence'])
    laya_req = build_design_laya_payload(field_name, task['prompt'], ordered_ids, candidates)
    laya_bytes = json.dumps(laya_req, ensure_ascii=False).encode('utf-8')
    meta = {}
    raw_laya = bounded_adapter(policy['laya_command'], laya_bytes, policy.get('timeout_seconds', 60), meta)
    need(meta.get('returncode') == 0, 'laya_backend_failed')
    temperatures = policy.get('temperatures', {})
    model_name, calibrated = validate_design_laya_response(raw_laya, field_name, ordered_ids, temperatures)
    val_choice = calibrated['field_value']['choice']
    val_conf = calibrated['field_value']['confidence']
    cit_choice = calibrated['citation_span']['choice']
    cit_conf = calibrated['citation_span']['confidence']
    min_conf = policy.get('min_confidence', 0.60)

    if val_choice == 'unknown' or val_conf < min_conf or cit_choice == 'NONE' or cit_choice not in candidates:
        return {
            'model': req.get('model', model_name),
            'field_name': field_name,
            'status': 'unknown',
            'value': 'unknown',
            'confidence': val_conf,
            'extraction_mode': 'medbias_laya_sentence_anchored',
            'citations': [],
        }
    cand = candidates[cit_choice]
    out_value = cand['quote'] if val_choice == 'reported_in_window' else val_choice
    return {
        'model': req.get('model', model_name),
        'field_name': field_name,
        'status': 'extracted_laya',
        'value': out_value,
        'category_choice': val_choice,
        'confidence': val_conf,
        'citation_confidence': cit_conf,
        'extraction_mode': 'medbias_laya_sentence_anchored',
        'citations': [
            {
                'id': cand['paragraph_id'],
                'sentence_id': cand['sentence_id'],
                'quote': cand['quote'],
                'start': cand['start'],
                'length': cand['length'],
            }
        ],
    }


def process_code_audit_request(req, policy):
    """Process a Task T3 cross-language code risk audit request through Laya."""
    task = req.get('task', {})
    need(isinstance(task, dict) and {'file_id', 'language', 'source_text'} <= set(task),
         'invalid_code_audit_task_payload')
    file_id = task['file_id']
    language = task['language']
    source_text = task['source_text']
    ordered_ids, candidates = segment_code_blocks(source_text, file_id)
    laya_req = build_code_audit_laya_payload(file_id, language, ordered_ids, candidates)
    laya_bytes = json.dumps(laya_req, ensure_ascii=False).encode('utf-8')
    meta = {}
    raw_laya = bounded_adapter(policy['laya_command'], laya_bytes, policy.get('timeout_seconds', 60), meta)
    need(meta.get('returncode') == 0, 'laya_backend_failed')
    temperatures = policy.get('temperatures', {})
    model_name, calibrated = validate_code_audit_laya_response(raw_laya, ordered_ids, temperatures)
    rule_choice = calibrated['risk_rule']['choice']
    rule_conf = calibrated['risk_rule']['confidence']
    cit_choice = calibrated['citation_span']['choice']
    cit_conf = calibrated['citation_span']['confidence']
    min_conf = policy.get('min_confidence', 0.60)
    clearance_conf = policy.get('clearance_min_confidence', 0.85)

    if rule_choice == 'NO_STRUCTURAL_LEAKAGE_DETECTED':
        if rule_conf < clearance_conf:
            return {
                'model': req.get('model', model_name),
                'file': file_id,
                'language': language,
                'status': 'ABSTAINED_LOW_CLEARANCE_CONFIDENCE',
                'rule_id': 'NO_STRUCTURAL_LEAKAGE_DETECTED',
                'confidence': rule_conf,
                'indicators': [],
            }
        return {
            'model': req.get('model', model_name),
            'file': file_id,
            'language': language,
            'status': 'CHECKED_NO_VIOLATION',
            'rule_id': 'NO_STRUCTURAL_LEAKAGE_DETECTED',
            'confidence': rule_conf,
            'indicators': [],
        }

    if rule_conf < min_conf or cit_choice == 'NONE' or cit_choice not in candidates:
        return {
            'model': req.get('model', model_name),
            'file': file_id,
            'language': language,
            'status': 'ABSTAINED_BELOW_THRESHOLD',
            'rule_id': rule_choice,
            'confidence': rule_conf,
            'indicators': [],
        }

    cand = candidates[cit_choice]
    return {
        'model': req.get('model', model_name),
        'file': file_id,
        'language': language,
        'status': 'INDICATOR_DETECTED',
        'rule_id': rule_choice,
        'confidence': rule_conf,
        'citation_confidence': cit_conf,
        'indicators': [
            {
                'rule_id': rule_choice,
                'category': 'code_risk_indicator',
                'detection_mode': 'medbias_laya_code_span',
                'file': file_id,
                'line': cand['start_line'],
                'end_line': cand['end_line'],
                'start': cand['start'],
                'length': cand['length'],
                'symbol_or_call': cand['sentence_id'],
                'quote': cand['quote'],
                'confidence': rule_conf,
                'rationale': f"[MedBias-Laya {language} audit conf={rule_conf:.3f}] {CODE_RISK_OPTIONS[rule_choice]}",
                'suggested_action': 'Scope preprocessing and tuning strictly inside patient-disjoint training folds and log fitted row_ids to fits.csv.',
            }
        ],
    }


def process_request(raw_stdin, policy):
    """Process one adapter stdin request through Laya (Tasks T1, T2, or T3)."""
    req = strict_json(raw_stdin)
    need(isinstance(req, dict) and req.get('format_version') == 1, 'invalid_adapter_request_version')
    kind = req.get('kind', 'literature_evidence_analysis')
    if kind == 'study_design_extraction':
        return process_design_request(req, policy)
    if kind == 'code_risk_audit':
        return process_code_audit_request(req, policy)

    need({'provider', 'model', 'task', 'instruction'} <= set(req),
         'invalid_literature_adapter_request')
    task = req['task']
    need(isinstance(task, dict) and {'question_id', 'question', 'evidence'} <= set(task),
         'invalid_task_payload')

    ordered_ids, candidates = segment_evidence_sentences(task['evidence'])
    laya_req = build_laya_payload(req, ordered_ids, candidates)
    laya_bytes = json.dumps(laya_req, ensure_ascii=False).encode('utf-8')

    laya_cmd = policy['laya_command']
    timeout = policy.get('timeout_seconds', 60)
    meta = {}
    raw_laya = bounded_adapter(laya_cmd, laya_bytes, timeout, meta)
    need(meta.get('returncode') == 0, 'laya_backend_failed')

    temperatures = policy.get('temperatures', {'applicability': 1.0, 'finding': 1.0, 'citation_span': 1.0})
    _, calibrated = validate_laya_response(raw_laya, ordered_ids, temperatures)

    escalate, reason = should_escalate(calibrated, policy)
    if escalate:
        reasoner_cmd = policy.get('reasoner_command')
        if reasoner_cmd:
            r_meta = {}
            raw_reasoner = bounded_adapter(reasoner_cmd, raw_stdin, timeout, r_meta)
            need(r_meta.get('returncode') == 0, 'reasoner_backend_failed')
            reasoner_resp = strict_json(raw_reasoner)
            # Preserve requested model identifier required by literature.py contract
            reasoner_resp['model'] = req['model']
            return reasoner_resp
        return format_literature_response(req['model'], task['question_id'], calibrated, candidates, reason)

    return format_literature_response(req['model'], task['question_id'], calibrated, candidates)


def load_policy(path):
    raw = Path(path).read_bytes()
    need(len(raw) <= 256 * 1024, 'policy_size_limit')
    policy = strict_json(raw)
    need(isinstance(policy, dict) and policy.get('format_version') == 1, 'invalid_laya_policy')
    need(isinstance(policy.get('laya_command'), list) and bool(policy['laya_command']),
         'missing_laya_command')
    return policy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path, required=True,
                        help='Path to Laya adapter & selective routing policy JSON')
    args = parser.parse_args(argv)
    try:
        policy = load_policy(args.policy)
        raw_stdin = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
        need(len(raw_stdin) <= 2 * 1024 * 1024, 'stdin_size_limit')
        response = process_request(raw_stdin, policy)
    except Exception as exc:
        code = str(exc) if isinstance(exc, ContractError) else type(exc).__name__
        sys.stderr.write(f'laya_adapter_error:{code}\n')
        return 2
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
