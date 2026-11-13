---
title: 'Medical Research Harness: A Zero-Dependency Python Toolkit for Protocol Locking, Executed-Fit Auditing, and Verbatim-Citation Literature Screening in Clinical Prediction Research'
tags:
  - Python
  - clinical prediction models
  - risk of bias
  - PROBAST
  - PROBAST+AI
  - data leakage
  - reproducible research
  - software provenance
authors:
  - name: "Qi Guo"
    orcid: 0000-0002-4069-9819
    corresponding: true
    affiliation: 1
affiliations:
  - name: "College of Semiconductors (National Graduate College for Engineers), Southern University of Science and Technology, Shenzhen, China"
    index: 1
date: 13 November 2026
bibliography: paper.bib
---

# Summary

**Medical Research Harness** (`medical-research-harness`) is an open-source, zero-dependency Python 3.10+ command-line toolkit and coding-agent skill that enforces auditable software provenance and data-hygiene invariants in clinical prediction research. Built exclusively on the Python standard library (`ast`, `csv`, `hashlib`, `json`, `re`, `xml.parsers.expat`, `zipfile`), it installs cleanly via `pip install .` (`medical-research-harness` and `mrh` entrypoints with `study`, `workflow`, `check-bundle`, `project-audit`, `literature`, and `selftest` subcommands) or runs directly from source without installation. It compiles study protocols into SHA-256-locked task specifications, audits cohort and fold manifests across 14 deterministic invariants, reconciles `planned` fit permissions against `executed` runtime logs, statically inspects Python, R, and SAS scripts in read-only mode, and extracts coordinate-locked evidence spans from JATS XML articles—operating solely on local aggregate manifests without accessing patient rows, predictions, embeddings, or credentials (`execution_authorized: false`, `scientific_acceptance: false`).

# Statement of Need

Systematic reviews show that most published clinical prediction models carry high or unclear risk of bias under PROBAST and PROBAST+AI [@wolff2019probast; @moons2025probastai; @wynants2020covid; @andaur2021risk]. Optimistic performance estimates frequently stem from silent pipeline defects rather than estimator choice [@kapoor2023leakage]: repeated encounters from one patient (`patient_id`) crossing train/validation/test partitions; predictor timestamps exceeding the clinical prediction anchor (`feature_max_time > index_time`) or outcome windows crossing chronological splits; preprocessing, imputation, or feature selection fitting outside each training fold (`fit_outside_training_fold`); and selective omission of failed or aborted runs from final summaries. Clinical modeling teams, methodology reviewers, and air-gapped hospital environments need lightweight, dependency-free command-line tooling that binds protocol documents, split manifests, runtime fit memberships, and static code checks into tamper-evident audit artifacts prior to human scientific review.

# State of the Field

Existing tools address isolated parts of this workflow without providing an integrated, zero-dependency provenance harness:

1. **Methodological Standards**: PROBAST [@wolff2019probast], PROBAST+AI [@moons2025probastai], and TRIPOD+AI [@collins2024tripodai] define authoritative clinical prediction standards as prose checklists, without executable command-line locks over cohort manifests or modeling scripts.
2. **General MLOps and Tabular Validators**: MLflow, DVC, Great Expectations, and Deepchecks track parameters or schema shifts, yet require third-party SDK stacks and lack native semantics for clinical temporal anchors (`index_time`, `feature_max_time`, `label_start_time`), patient-grouped fold disjointness, or strict separation between pre-execution `planned` fit scopes and post-execution `executed` runtime fit logs.
3. **Trial Risk-of-Bias Extractors**: RobotReviewer [@marshall2016robotreviewer] automates Cochrane Risk-of-Bias screening on randomized trial PDFs, rather than auditing clinical prediction manifests, multi-language Python/R/SAS repositories, or exact JATS XML character slices.

# Software Design

**Medical Research Harness** structures local provenance verification and JATS XML evidence indexing into a four-stage standard-library pipeline (Figure 1).

![Workflow architecture of Medical Research Harness.](figures/fig1_harness_workflow.png)

- **Stage 1 — Governance & Protocol Lock (`check-bundle`, `study plan`, `study preflight`)**: Verifies phase-cumulative governance documents (`protocol.md`, `sap.md`, `audit-plan.md`, `review-report.md`) against role locators, compiles `study.json` into immutable `DRAFT` task specs bound by a `design_sha256` digest over `study.json`, `rows.csv`, and `folds.csv`, and optionally delegates preflight lock checks to an explicit external `--lab` validator.
- **Stage 2 — 14-Invariant Manifest Audit (`study audit`)**: Audits relational manifests (`rows.csv`, `folds.csv`, `fits.csv`) in `--mode planned` or `--mode executed` across 14 deterministic invariants covering outer and internal fold patient disjointness (`patient_overlap`, `fold_patient_overlap`, `holdout_in_development_fold`, `incomplete_fold_membership`), clinical temporal ordering (`feature_after_index`, `invalid_label_start`, `invalid_label_window`, `nonchronological_split`, `label_window_crosses_split`), training-fold fit containment (`fit_outside_training_fold`, `missing_fit_operation`, `unexpected_fit_operation`, plus empty-fit checks for `zero_fit_experiments`), and manifest hash integrity (`frozen_rows_changed`, `frozen_folds_changed`).
- **Stage 3 — Read-Only Code & JATS XML Audit (`project-audit`, `literature`)**: Enforces target-tree immutability via before/after SHA-256 snapshots, statically inspects Python (`ast`), R, and SAS scripts (halting untrusted execution at `AWAITING_SANDBOX_RUNNER`), blocks XML DTD/entity injection via Expat handlers, masks tables and figures with equal-length whitespace, supports signal-safe (`SIGTERM`/`SIGINT`/`SIGKILL`) checkpoint resume, and locks numbered spans (`S001..S008`) to exact character slices $T[a_k : a_k + L_k] \equiv q_k$.
- **Stage 4 — Registry Reconciliation & Safety Gate (`study summarize`, `workflow`)**: Recomputes `executed` audits freshly from source manifests, preserves `FAILED`, `ABORTED`, `RUNNING`, and `NOT_RUN` runs, binds artifact digests in `completion.json`, and stamps every output with `execution_authorized: false` and `scientific_acceptance: false`.

All deterministic invariants are verified offline via synthetic fault-injection suites (`selftest`, unit modules, and `tests/review_probes.py`) without network calls or clinical data. This paper covers the standalone zero-dependency standard-library provenance and evidence-indexing toolkit (`medical-research-harness`); optional neural or neuro-symbolic scoring adapters (`laya_decision_adapter.py`) operate strictly as decoupled advisory plugins outside the core zero-dependency runtime.

# AI Usage Disclosure

In accordance with JOSS generative-AI policies, LLM-based coding and editorial assistants were used under human maintainer supervision for CLI refactoring, synthetic fault-injection test authoring, read-only code review, and manuscript editing. Every deterministic invariant, CLI contract, and automated test was inspected and verified by the author. At runtime, core `medical-research-harness` commands execute deterministically in Python 3.10+ with zero LLM calls.

# Acknowledgements

The author thanks the authors of the PROBAST, PROBAST+AI, and TRIPOD+AI statements for establishing the methodological standards operationalized by this software.

# References
