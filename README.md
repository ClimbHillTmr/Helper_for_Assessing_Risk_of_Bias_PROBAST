# Medical Research Harness

**Version:** `v0.2.0` | **Runtime:** Python 3.10+ Standard Library Only (`dependencies = []`) | **License:** [MIT](LICENSE)

**Medical Research Harness** (`medical-research-harness`) is an open-source, zero-dependency Python 3.10+ command-line toolkit and coding-agent skill for **protocol locking, deterministic cohort/fold manifest auditing, planned-vs.-executed fit reconciliation, read-only multi-language static code inspection, and coordinate-locked JATS XML evidence indexing** in clinical prediction research.

> **Language Navigation / 语言导航:** English documentation for users and JOSS reviewers appears first below. Complete Chinese documentation is preserved in full under [中文说明（Chinese Documentation）](#中文说明chinese-documentation).

---

## 1. Statement of Need & Epistemic Safety Boundary

Systematic reviews under **PROBAST** and **PROBAST+AI** consistently find that clinical prediction model studies suffer from silent data-hygiene and provenance defects rather than model-class limitations:
- **Patient-level partition leakage**: repeated encounters from the same `patient_id` crossing train, validation, and holdout splits (`patient_overlap`, `fold_patient_overlap`, `holdout_in_development_fold`).
- **Clinical temporal lookahead**: predictor extraction timestamps exceeding the clinical prediction anchor (`feature_max_time > index_time`) or outcome windows crossing chronological split boundaries (`feature_after_index`, `label_window_crosses_split`).
- **Out-of-fold preprocessing/selection leakage**: imputation, scaling, encoding, resampling, or feature selection fitted outside each training fold (`fit_outside_training_fold`), or divergence between pre-execution `planned` fit permissions and post-execution `executed` runtime logs.
- **Selective run reporting**: omitting failed, aborted, or negative runs from study summaries.

### Non-Bypassable Privacy & Epistemic Boundaries

1. **Local Metadata and Aggregate Diagnostics**: Core deterministic checks operate strictly on local row-level metadata manifests (`rows.csv`, `folds.csv`, `fits.csv`) and SHA-256 file digests. The toolkit never ingests raw patient feature tables, row-level predictions, clinical embeddings, or credentials.
2. **Non-Bypassable Human-in-the-Loop Gates**: Reconciliation withholds execution authorization and reports `scientific_validity: not_assessed`; workflow artifacts also withhold scientific acceptance. Passing software hygiene invariants proves deterministic manifest/file consistency—it **never** grants clinical validity, low overall PROBAST risk of bias, or scientific approval.
3. **Zero Model Training or Clinical Serving**: This package is a methodological provenance and audit harness, not an AutoML trainer, clinical decision-support system, or automated data cleaner.

---

## 2. Installation

Requires **Python 3.10 or newer** on Linux, macOS, or Windows. Core execution uses **only the Python standard library** (`ast`, `csv`, `hashlib`, `json`, `re`, `xml.parsers.expat`, `zipfile`) with **zero third-party runtime dependencies**, making it suitable for air-gapped hospital and biostatistics environments.

### Option A — Installable CLI Package (`pip`, Recommended)

```bash
git clone https://github.com/ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST.git
cd Helper_for_Assessing_Risk_of_Bias_PROBAST
python3 -m pip install .
```

Installing registers both `medical-research-harness` and the short alias `mrh`, including the following core subcommands:
`study`, `workflow`, `check-bundle`, `project-audit`, `literature`, and `selftest`.

### Option B — Zero-Install Direct Repository Execution

Every module can also be executed directly from a repository checkout without installing a Python package:

```bash
git clone --branch v0.2.0 --depth 1 https://github.com/ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST.git
cd Helper_for_Assessing_Risk_of_Bias_PROBAST
python3 skills/medical-research-harness/scripts/study.py --help
```

### Option C — Coding Agent Skill (`SKILL.md`)

To install `skills/medical-research-harness/` as an Agent Skill (e.g., in Codex or compatible agent harnesses):

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST \
  --path skills/medical-research-harness --ref v0.2.0
```

---

## 3. CLI Quickstart & End-to-End Working Example

### 3.1 Self-Contained End-to-End Demo (`selftest`)

Run a complete synthetic clinical prediction study lifecycle—protocol compilation, deterministic manifest fault injection, `planned` vs. `executed` fit auditing, and multi-run registry reconciliation—into a fresh directory (`--out` must not already exist):

```bash
# Installed CLI (or short alias: mrh selftest --out build/demo)
medical-research-harness selftest --out build/demo

# Zero-install equivalent
python3 skills/medical-research-harness/scripts/test_study.py --out build/demo
```

Inspect the generated artifacts in `build/demo/`:
- `checks.json`: pass/fail ledger across 24 deterministic operational invariants.
- `audit-violations.json`: structured diagnostic counts for injected patient overlap, temporal lookahead, and out-of-fold fit violations.
- `summary-final/summary.md` & `summary-final/summary.json`: complete run reconciliation preserving `SUCCEEDED`, `FAILED`, `ABORTED`, and `NOT_RUN` tasks alongside `scientific_acceptance: false`.

### 3.2 Core Subcommand Reference

```bash
# 1. Governance & Evidence Bundle Verification (design | preflight | results)
medical-research-harness check-bundle path/to/evidence_bundle.json

# 2. Study Task Compilation, Deterministic Manifest Audit & Run Reconciliation
medical-research-harness study plan --out build/plan-v1 path/to/study.json

medical-research-harness study audit \
  --mode planned \
  --rows path/to/rows.csv \
  --folds path/to/folds.csv \
  --fits path/to/planned-fits.csv \
  --out build/audit-planned \
  build/plan-v1/plan.json

medical-research-harness study audit \
  --mode executed \
  --experiment-id exp_baseline \
  --run-id run_001 \
  --rows path/to/rows.csv \
  --folds path/to/folds.csv \
  --fits path/to/executed-fits.csv \
  --out build/audit-run-001 \
  build/plan-v1/plan.json

medical-research-harness study summarize \
  --runs path/to/registry/runs \
  --out build/summary-v1 \
  build/plan-v1/plan.json

# 3. Single-Command Cross-Phase Workflow Orchestration & Handoff
medical-research-harness workflow \
  --plan build/plan-v1/plan.json \
  --phase results \
  --bundle path/to/evidence_bundle.json \
  --runs path/to/registry/runs \
  --out build/workflow-check-001

# 4. Read-Only Target Repository Audit (Python AST + R/SAS Static Scan + Tree Hash Lock)
medical-research-harness project-audit \
  --spec path/to/project_audit_spec.json \
  --out build/project-audit-001

# 5. Offline JATS XML Indexing & Coordinate-Locked Span Extraction (Default Dry-Run)
medical-research-harness literature \
  --manifest path/to/manifest.json \
  --config path/to/config.json \
  --out build/literature-dryrun-001
```

> **External Validator Boundary:** `study preflight --lab /abs/path/to/lab.py` delegates lock/approval checks to a site-provided external validator (`validate-task`). Site-specific runners (`ResearchLab`) and optional advisory neural/neuro-symbolic adapters (`laya_decision_adapter.py`, `hermes_decision_adapter.py`) are decoupled from the zero-dependency core runtime.

---

## 4. Automated Verification Suite

Continuous integration runs automatically on GitHub Actions ([`.github/workflows/validate.yml`](.github/workflows/validate.yml)) across Python 3.10 and Python 3.13 with `PYTHONDONTWRITEBYTECODE=1`. The synthetic checks make no model calls; CI setup may download build dependencies.

Run the offline verification suite locally from the repository root:

```bash
# CLI self-test (24 operational checks + governance bundle checks)
medical-research-harness selftest

# Core & module unit suites (pure Python 3.10+ stdlib)
python3 skills/medical-research-harness/scripts/test_check_bundle.py
python3 skills/medical-research-harness/scripts/test_study.py
python3 skills/medical-research-harness/scripts/test_workflow.py
python3 skills/medical-research-harness/scripts/test_project_audit.py -v
python3 skills/medical-research-harness/scripts/test_decision_agent.py
HERMES_ADAPTER_ROOT=/nonexistent python3 skills/medical-research-harness/scripts/test_hermes_decision_adapter.py -v
python3 skills/medical-research-harness/scripts/test_laya_decision_adapter.py -v
python3 skills/medical-research-harness/scripts/test_literature.py
python3 skills/medical-research-harness/scripts/test_literature_design.py -v
python3 skills/medical-research-harness/scripts/test_literature_model_adapter.py
python3 skills/medical-research-harness/scripts/test_literature_recovery.py
python3 tests/test_literature_boundaries.py
python3 tests/test_literature_p2_repairs.py
python3 tests/test_literature_offline_resume.py

# 76 independent-origin adversarial & tamper-rejection regression probes
python3 tests/review_probes.py --out build/review-probes
```

---

## 5. Documentation Map, Contributing, Citation & License

| Resource | Purpose |
|---|---|
| [`skills/medical-research-harness/SKILL.md`](skills/medical-research-harness/SKILL.md) | Skill entrypoint, phase routing, and operational boundaries |
| [`skills/medical-research-harness/references/operations.md`](skills/medical-research-harness/references/operations.md) | Exact CSV/JSON manifest schemas (`rows.csv`, `folds.csv`, `fits.csv`) and audit rules |
| [`skills/medical-research-harness/references/automation.md`](skills/medical-research-harness/references/automation.md) | Cross-phase `workflow` state machine and `completion.json` digest contracts |
| [`skills/medical-research-harness/references/project-audit.md`](skills/medical-research-harness/references/project-audit.md) | Read-only target project AST/regex audit specification and sandbox gate |
| [`skills/medical-research-harness/references/literature.md`](skills/medical-research-harness/references/literature.md) | JATS XML Expat security guards, coordinate masking, and `S001..S008` span verification |
| [`skills/medical-research-harness/references/methodology.md`](skills/medical-research-harness/references/methodology.md) | PROBAST / PROBAST+AI / TRIPOD+AI alignment and applicability notes |
| [`system_design.md`](system_design.md) | Architecture rationale and scope boundaries |
| [`Paper/joss/paper.md`](Paper/joss/paper.md) | Companion *Journal of Open Source Software* (JOSS) manuscript (`750–1750` words) |
| [`Paper/README.md`](Paper/README.md) | Methodological references, license boundaries, and companion manuscripts |

- **Contributing & Issue Reporting**: See [`CONTRIBUTING.md`](CONTRIBUTING.md) for coding guidelines, privacy redlines, offline test requirements, and bug-report templates.
- **Citation**: Metadata is provided in [`CITATION.cff`](CITATION.cff) (and `Paper/joss/paper.bib`). Please also cite the underlying PROBAST, PROBAST+AI, and TRIPOD+AI methodological statements when appraising clinical prediction studies.
- **License**: Released under the [MIT License](LICENSE). Third-party methodological guidelines and open-access articles referenced via DOI links retain their original licenses.

---

## 中文说明（Chinese Documentation）

**当前版本：`v0.2.0`。** 面向临床预测模型研究设计、队列/折清单确定性审计、运行登记对账与逐字引文文献风险筛查的零第三方依赖 Python 工具包与 Agent Skill。

指导医疗数据研究的数据处理、实验设计、偏倚控制和结果汇总。当前可执行路径支持患者互斥、固定外层切分及完整内部折的预测研究。它不提供训练平台或临床服务，软件检查通过不等于低偏倚、科学批准或临床有效（所有输出强制标记 `execution_authorized: false` 与 `scientific_acceptance: false`）。

### 安装 CLI 工具包或 Skill

#### 1. 安装 Python 命令行包（推荐，零第三方运行时依赖）

Python 3.10+，仅依赖标准库：

```bash
git clone https://github.com/ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST.git
cd Helper_for_Assessing_Risk_of_Bias_PROBAST
python3 -m pip install .
```

安装后可直接调用 `medical-research-harness`（或简写别名 `mrh`），支持 `study`、`workflow`、`check-bundle`、`project-audit`、`literature` 与 `selftest` 六个子命令。

#### 2. 安装 Agent Skill

在 Codex 中请求安装：

> 请安装 ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST 仓库中 skills/medical-research-harness 目录的 skill，使用 v0.2.0 标签。

也可使用 Codex 内置安装器：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST \
  --path skills/medical-research-harness --ref v0.2.0
```

安装器会拒绝覆盖已有同名目录；安装后下一轮对话可用。其他支持 Agent Skills 的环境，可下载 Release 中的独立 ZIP，将完整 `medical-research-harness/` 放入该环境的技能目录。ZIP 附带 MIT LICENSE。

调用示例：

> 使用 medical-research-harness 检查当前研究目标、数据契约和证据，生成具体的数据处理与实验任务，审计允许拟合成员，并汇总已登记结果。按已批准协议推进。

### 免安装在仓库中直接运行

Python 3.10+，仅依赖标准库，无需安装 Python 包即可直接运行全部脚本：

```bash
git clone --branch v0.2.0 --depth 1 https://github.com/ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST.git
cd Helper_for_Assessing_Risk_of_Bias_PROBAST
python3 skills/medical-research-harness/scripts/test_check_bundle.py
python3 skills/medical-research-harness/scripts/test_study.py
python3 tests/review_probes.py --out build/review-probes
```

默认运行 24 个操作检查、76 个由独立复核转成的回归探测，以及文档证据检查套件。探测脚本自行生成隔离的合成材料，所有批准、运行记录与指标均为模拟。`--out` 目录必须不存在。没有患者数据或模型训练。

需要保留一次可查看的端到端演示产物时：

```bash
# 已安装 CLI（或 mrh selftest --out build/demo）
medical-research-harness selftest --out build/demo

# 或免安装脚本运行
python3 skills/medical-research-harness/scripts/test_study.py --out build/demo
```

查看生成的 `checks.json`、`audit-violations.json` 和 `summary-final/summary.md`。

### 跨阶段自动化编排（`workflow`）

`workflow.py`（对应 CLI `medical-research-harness workflow`）一次完成计划复用/编译、文档证据检查、计划拟合审计、显式外部预检或实际运行对账，输出 `workflow.json` / `workflow.md` 和可执行的后续工作定位。检查失败保留前序证据；重跑使用新输出目录并重新核对身份。可运行 `python3 skills/medical-research-harness/scripts/test_workflow.py` 执行 18 项集成测试。

```bash
python3 skills/medical-research-harness/scripts/workflow.py \
  --plan /study/plan-v1/plan.json --phase results \
  --bundle /study/evidence-results.json --runs /study/registry/runs \
  --out /study/check-003
```

借鉴 Jev 的结构化判断与分层核验思路，程序处理确定性约束，agent 处理语义和实现修复，科学接受保留独立复核。当前没有 Jev API 集成或其医疗领域效果证据。接口、状态和可选扩展见 [自动化说明](skills/medical-research-harness/references/automation.md)。

### 文献索引与目标项目只读审计入口

文献路径从合法 JATS 全文自动建立段落索引、检索四类工程风险问题、可选调用受约束模型并校验逐字引文。无需用户填写主张。接口见 [文献契约](docs/literature-interface-v1.md)，操作见 [literature.md](skills/medical-research-harness/references/literature.md)。默认 dry-run；真实公开材料调用需显式启用模型和公开外发，报告保留独立上下文复核、分歧与未获取补充材料。只读文献建议不等于真实代码违例或正式 PROBAST 评级。实际运行与限制另行登记，不能以测试通过冒充医学效果。

默认离线测试：

```bash
python3 skills/medical-research-harness/scripts/test_literature.py
python3 skills/medical-research-harness/scripts/test_literature_design.py -v
python3 skills/medical-research-harness/scripts/test_literature_model_adapter.py
python3 skills/medical-research-harness/scripts/test_project_audit.py -v
```

`literature_design.py` 扩展有类型证据层（`body_paragraph`、`table`、`figure_caption` 及已核验 `.docx`/`.txt` 补充材料）、11 项结构化研究设计抽取与章节感知检索；`project_audit.py` 提供目标项目只读审计（静态 AST 代码泄漏探查 + `study.py` 确定性清单与运行对账 + 不可信生成脚本沙箱门禁）。Laya 适配器是解耦的可选插件，不是核心零依赖运行时的前置依赖。

### 功能与外部依赖

| 操作 / CLI 子命令 | 功能 | 依赖 |
|---|---|---|
| `workflow` / `workflow.py` | 自动串联阶段检查、保留诊断与交接；不执行实验 | 本包；preflight 显式提供外部校验器 |
| `project-audit` / `project_audit.py` | 目标项目只读审计：静态 AST 探查、清单/登记对账与四分类报告 | 本包；执行生成脚本需显式 `--sandbox-runner` |
| `literature` / `literature.py` / `literature_design.py` | 公开 JATS 多层索引、11 项研究设计抽取、逐字引文校验与盲复核 | 本包；真实模型调用需显式 `--execute-models --allow-public-egress` |
| `study plan` | 生成任务、固定完整实验集合及协议/队列/折身份 | 本包与研究配置 |
| `study audit` | 计算患者重叠、时间/标签违例、拟合越界及身份变化 | 本包与私有元数据清单 |
| `study summarize` | 对账全部尝试，保留失败、中断和未执行项 | 本包与约定格式的运行记录 |
| `check-bundle` / `check_bundle.py` | 检查文档证据及哈希 | 本包 |
| `study preflight` | 审计身份检查及已有审批/锁校验 | 显式 `--lab` 外部校验器 |
| `selftest` | 运行隔离合成端到端自检与故障注入校验 | 本包（纯标准库） |

ResearchLab 不随本包分发。preflight 通过 `python <lab.py> validate-task <task.json>` 调用受信任的兼容校验器；没有该工具时，plan/audit/summarize 仍可独立使用，但不得声称已完成外部审批校验。完整接口与工作顺序见 [操作说明](skills/medical-research-harness/references/operations.md)。

若环境已有兼容校验器，可额外运行 3 个集成检查：

```bash
python3 skills/medical-research-harness/scripts/test_study.py --lab /absolute/path/to/lab.py
```

此命令只调用 validate-task，不调用 run，不获得真实实验授权。

### 科学与验证边界

新预测协议可采用 PROBAST+AI，同时区分开发质量、评价偏倚与适用性；已批准研究沿用锁定版本。正式逐题评估需要完整官方工具与科学复核。因果、干预、重复患者未来预测和其他不兼容设计需要专用适配。

真实研究需在目标项目导出完整的行/折清单，记录实际 fit 输入，并按批准统计方法计算指标。合成检查不能证明日志真实、注册源完整、审批身份有效或临床适用。

- [技能入口](skills/medical-research-harness/SKILL.md)
- [研究契约模板](skills/medical-research-harness/assets/protocol.md)
- [可复现验证与历史修复](reviews/20261002-operability-review.md)
- [设计与范围](system_design.md)
- [参考文献与伴生论文（JOSS / CMPB）](Paper/README.md)
- [贡献与离线验证指南](CONTRIBUTING.md)
- [引用元数据](CITATION.cff)

### 许可证与分发

项目代码及原创说明采用 [MIT License](LICENSE)。当前版本和独立 skill ZIP 不分发第三方论文 PDF、真实研究填写表、患者数据或本机备份。官方工具与文献通过引用链接获取；其原有使用条件不受本项目 MIT 许可证改变。旧提交历史保留原有内容，本次不重写历史。
