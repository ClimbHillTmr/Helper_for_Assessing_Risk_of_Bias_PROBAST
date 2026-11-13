# JOSS Turn-Key Submission Checklist / JOSS 五步一键投稿清单

This guide walks you from a clean `v0.2.0` repository checkout to an active submission on the **Journal of Open Source Software (JOSS)** (`$0 APC`, Diamond Open Access) in five deterministic steps.

本清单提供 **Medical Research Harness (`v0.2.0`)** 投递 ***Journal of Open Source Software* (JOSS，零版面费钻石开源)** 的五步交钥匙操作流程。

---

## Step 1 — Fill Real Author, ORCID & Affiliation in One Command / 单命令原子回填作者信息

Run `Paper/joss/check_joss_ready.py` to validate your ORCID checksum (ISO 7064 Mod 11-2), atomically populate `Paper/joss/paper.md`, `CITATION.cff`, and `pyproject.toml`, and verify all 8 JOSS readiness gates:

在仓库根目录执行以下**单条命令**，自动校验 ORCID 校验位并原子更新 `Paper/joss/paper.md`、`CITATION.cff` 与 `pyproject.toml` 中的占位符（若你的 GitHub 仓库路径不同，可追加 `--set-github-repo OWNER/REPO`）：

```bash
python3 Paper/joss/check_joss_ready.py \
  --set-author "Your Full Name" \
  --set-orcid "0000-0002-1825-0097" \
  --set-affiliation "Department of ..., University / Hospital, City, Country"
```

Confirm the script prints **`RESULT: ALL 8 JOSS READINESS CHECKS PASSED`** (exit code `0`). If Pandoc + XeLaTeX are installed locally, optionally refresh `Paper/joss/paper_preview.pdf`, then commit:

确认输出 **`RESULT: ALL 8 JOSS READINESS CHECKS PASSED`** 后提交变更：

```bash
git add Paper/joss/paper.md CITATION.cff pyproject.toml
git commit -m "chore(release): set author metadata for v0.2.0 JOSS submission"
```

---

## Step 2 — Push `main` & Tag `v0.2.0` to Public GitHub / 推送公开仓库与 `v0.2.0` 标签

Ensure the target GitHub repository is set to **Public** (JOSS requires public repository access, an open issue tracker, and a tagged release):

确保 GitHub 仓库可见性为 **Public** 且已启用 **Issues**（JOSS 公开审稿机器人 `@editorialbot` 需要公开读取仓库并检索发布标签）：

```bash
git tag -a v0.2.0 -m "Medical Research Harness v0.2.0 (JOSS submission release)"
git push origin main --follow-tags
```

Create a GitHub Release from tag `v0.2.0` on GitHub (`Releases -> Draft a new release -> Choose tag v0.2.0 -> Publish release`).

---

## Step 3 — Verify GitHub Actions Green Status / 核验 GitHub Actions 在线全绿

Open the **Actions** tab of your public GitHub repository (`Validate skill` workflow in `.github/workflows/validate.yml`) and confirm both Python `3.10` and `3.13` matrix jobs pass with a green check mark.

打开 GitHub 仓库的 **Actions** 页面，确认 `.github/workflows/validate.yml` 在 Python `3.10` 与 `3.13` 双矩阵下全部通过（绿标）。

---

## Step 4 — (Optional Now, Required Upon Acceptance) Mint Zenodo Archive / 可选：开启 Zenodo 归档绑定

JOSS mints a Zenodo/Figshare archive at final acceptance, or you can enable the [Zenodo–GitHub integration](https://zenodo.org/account/settings/github/) ahead of time so creating the `v0.2.0` GitHub Release automatically archives a permanent software DOI.

可在投稿前提前绑定 [Zenodo–GitHub](https://zenodo.org/account/settings/github/) 自动归档（也可按 JOSS 标准流程在审稿接收阶段生成归档 DOI）。

---

## Step 5 — Submit on OpenJournals (`joss.theoj.org`) / 在 JOSS 官网提交稿件

Open **<https://joss.theoj.org/papers/new>** (sign in with ORCID) and fill the submission form:

登录 **<https://joss.theoj.org/papers/new>**（使用同一 ORCID 账号登录），按以下字段填写并提交：

- **Title**: `Medical Research Harness: A Zero-Dependency Python Toolkit for Protocol Locking, Executed-Fit Auditing, and Verbatim-Citation Literature Screening in Clinical Prediction Research`
- **Repository Address**: `https://github.com/<OWNER>/<REPO>`
- **Software Version**: `v0.2.0`
- **Main Branch / Paper Path**: `main` (auto-detected at `Paper/joss/paper.md`)
- **Submission Type**: `New submission` — Biomedical / Clinical Informatics & Reproducible Research Software
- **Notes to Editor (Suggested)**:
  > `Medical Research Harness (v0.2.0) is a zero-dependency Python 3.10+ standard-library CLI toolkit (pip install . -> medical-research-harness / mrh) and coding-agent skill for SHA-256 protocol locking, 14-invariant cohort/fold manifest auditing, planned-vs.-executed fit reconciliation, read-only multi-language static code auditing, and coordinate-locked JATS XML indexing. Paper path: Paper/joss/paper.md (<900 words, 7 DOI-verified references). Quick verification: medical-research-harness selftest --out build/demo and python3 tests/review_probes.py --out build/probes.`

Once submitted, click **"Compile paper"** in the JOSS pre-review GitHub issue to trigger `@editorialbot generate pdf` (Inara) and `@editorialbot check references`.
