---
title: 'Medical Research Harness: A Python Toolkit for Provenance and Leakage Auditing in Clinical Prediction Studies'
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
date: 25 November 2026
bibliography: paper.bib
---

# Summary

**Medical Research Harness** (`medical-research-harness`, short alias `mrh`) is an MIT-licensed, open-source Python 3.10+ toolkit that helps researchers verify whether a clinical prediction study followed its declared data and analysis boundaries. Prediction studies frequently involve repeated encounters from the same patient, measurements available at different clinical times, and multiple modeling attempts. Reproducible methodological appraisal requires connecting these pipeline details to the study protocol and to what was actually executed. The toolkit checks those connections and emits structured evidence for human review. It does not train predictive models, provide clinical recommendations, or assign an automatic PROBAST risk-of-bias rating.

The deterministic core depends solely on the Python standard library and runs either directly from source or as an installed command-line package exposing subcommands including `study`, `workflow`, `check-bundle`, `project-audit`, `literature`, and `selftest`. A companion coding-agent skill supplies operational guidance alongside the scripts. Private inputs remain in the local research environment: manifest auditing reads row-level metadata containing identifiers, split memberships, and timestamps, and exports aggregate diagnostics. Because these local manifests contain row-level identifiers and timestamps, they are not aggregate data and require site-appropriate access controls. Raw feature tables, individual predictions, and clinical embeddings are not required by the manifest audit interface.

# Statement of Need

Systematic reviews consistently document high or unclear risk of bias in clinical prediction studies [@wynants2020covid; @andaur2021risk]. PROBAST and PROBAST+AI provide structured methodological assessment frameworks [@wolff2019probast; @moons2025probastai], while TRIPOD+AI addresses transparent reporting [@collins2024tripodai]. Operationalizing these standards requires verifiable evidence of actual data handling rather than a prose checklist alone, because silent leakage can invalidate evaluation even when the modeling estimator is appropriate [@kapoor2023leakage].

The intended users are clinical modeling teams, biostatistical collaborators, and methodology reviewers who need inspectable evidence about patient separation, temporal availability, training-fold membership, and completeness of reported runs. The toolkit binds a declared protocol to immutable input identities, distinguishes pre-execution permitted fits from post-execution recorded fits, and reconciles successful, failed, interrupted, and unexecuted tasks. This narrows the gap between methodological intent and reviewable implementation evidence. Software checks cannot establish whether an exported log faithfully represents the originating computation; exporter integrity and scientific interpretation remain responsibilities of the study team and human reviewers.

# State of the Field

PROBAST, PROBAST+AI, and TRIPOD+AI define methodological criteria as prose guidance rather than executable file-integrity or fold-membership checks. RobotReviewer targets automated risk-of-bias extraction for randomized controlled trials [@marshall2016robotreviewer], whereas Medical Research Harness focuses on clinical prediction workflows and execution provenance.

General machine-learning platforms such as [MLflow](https://mlflow.org/), [DVC](https://dvc.org/), [Great Expectations](https://greatexpectations.io/), and [Deepchecks](https://www.deepchecks.com/) provide experiment tracking, data versioning, or tabular schema checks, while standard statistical libraries handle cross-validation and model fitting. Medical Research Harness complements those ecosystems through a lightweight contract linking clinical time anchors and patient-grouped partitions with separate `planned` and `executed` fit records. Rather than requiring a dedicated tracking server, it accepts explicit CSV and JSON exports from existing pipelines. A standalone Python standard-library implementation was chosen to keep the audit contract inspectable and portable across restricted hospital and biostatistics environments. This design trades ecosystem integrations and large-scale distributed processing for a minimal dependency surface and is not a claim of superiority over general MLOps tools.

# Software Design

![Workflow architecture of Medical Research Harness.](figures/fig1_harness_workflow.png)

The toolkit separates provenance verification into four modular stages (Figure 1). First, governance and protocol compilation (`check-bundle`, `study plan`, `study preflight`) verify phase-specific document locators and bind task specifications to SHA-256 digests of the protocol, cohort, and fold manifests. Compiled tasks begin in `DRAFT` state. Preflight checks delegate approval and lock validation to an explicitly supplied external validator (`--lab`); compilation alone never authorizes execution.

Second, deterministic manifest auditing (`study audit --mode planned|executed`) evaluates patient separation across outer and internal partitions, clinical temporal ordering between predictor timestamps, index anchors, and outcome windows, fold completeness, and training-fold fit containment. Planned records specify allowed operations prior to execution, whereas executed records must identify a specific experiment and run. Separating these modes prevents a valid plan from substituting for runtime execution evidence. The current contract assumes patient-disjoint partitions and complete internal folds; alternative designs require a reviewed adapter rather than an undocumented change to the scientific question.

Third, read-only project inspection and literature indexing (`project-audit`, `literature`, `literature-design`, `literature-offline`) combine static code scanning with deterministic manifest and text checks. Python syntax trees and R/SAS pattern scans surface risk indicators rather than formal proofs of semantic correctness, and before/after directory SHA-256 snapshots detect unintended writes without replacing an operating-system sandbox. A decoupled literature path parses JATS XML with Expat DTD/entity guards, masks tables and figures with equal-length whitespace, locks extracted quotes to exact character slices, and supports signal-safe offline checkpoint resume. Checkpoint recovery verifies persisted artifact hashes rather than interrupted external model calls or clinical validity.

Fourth, registry reconciliation and cross-phase orchestration (`study summarize`, `workflow`) retain all registered attempts—including `FAILED`, `ABORTED`, `RUNNING`, and `NOT_RUN` tasks—and recompute executed audits freshly from referenced manifests rather than trusting stale `PASS` summaries. Workflow completion records bind output hashes, while reconciliation reports withhold execution authorization (`scientific_validity: not_assessed`) and workflow outputs explicitly stamp `scientific_acceptance: false`. Hashing detects changes relative to recorded identities without authenticating signers, and exact quote matching establishes textual location rather than semantic truth. Offline synthetic fault-injection suites (`selftest` and `tests/review_probes.py`) exercise rejection paths without clinical data or external models.

# Research Impact Statement

Existing use is developer-led and exploratory. A documented two-article public-literature pilot exercised JATS XML indexing, model-assisted analysis, a separate review context, and verbatim quotation checks. That historical run remained `PARTIAL`: six of eight questions lacked sufficient reported evidence, and raw model-response bytes were not retained; it serves as workflow usage documentation rather than a validated clinical appraisal.

The repository also documents historical use of manifest auditing and run reconciliation in the internal `MedBias-Laya` workflow. A retained local reconciliation summary records passing structural checks, while a linked project-audit artifact is absent and the end-to-end chain has not been freshly re-audited. No model performance claim is made here. The public [research-use evidence register](https://github.com/ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST/blob/main/Paper/joss/RESEARCH_USE_EVIDENCE.md) separates historical usage records from current synthetic regression results and tracks remaining verification work. External adoption, clinical validity, and expert-level appraisal accuracy have not yet been established; ongoing development integrates the toolkit into authorized clinical prediction studies to provide complete, privacy-safe aggregate provenance records.

# AI Usage Disclosure

Generative AI coding and editorial assistants (Antigravity with Gemini/Claude models and OpenAI Codex in ChatGPT) were used during software refactoring, synthetic fault-injection test authoring, documentation cleanup, and manuscript editing. Historical literature-pilot logs also record `magpie/codex/gpt-6.1-sol` and `magpie/codex/gpt-6-astra` as runtime analysis and review model identifiers for those exploratory experiments. Core deterministic `medical-research-harness` commands execute purely in the Python standard library with zero LLM calls; optional literature and advisory adapters invoke models only when explicitly enabled. Prior to final submission, the author personally reviews, edits, and verifies all AI-assisted code, tests, and manuscript text and takes full responsibility for the work.

# Acknowledgements

The author acknowledges the methodological foundations established by the PROBAST, PROBAST+AI, and TRIPOD+AI working groups. This work received no external funding. The author declares no competing financial or personal interests.

# References
