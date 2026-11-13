# 目标项目只读审计（project_audit.py）

`project_audit.py` 实现研究项目只读审计 MVP（P3 / Action Plan v2 第三交付）：在不修改目标研究仓库任何文件、不导入或执行不可信项目代码的前提下，结合静态 AST 代码探查与 `study.py` 确定性清单/运行登记对账，输出四分类证据报告。

## 调用方式

```bash
python3 <skill>/scripts/project_audit.py \
  --spec /path/to/project_audit_spec.json \
  --out /path/to/new_audit_output_dir
```

可选外部沙箱运行器（用于受控执行已通过静态安全检查的生成脚本）：

```bash
python3 <skill>/scripts/project_audit.py \
  --spec /path/to/project_audit_spec.json \
  --sandbox-runner /trusted/sandbox_runner.py \
  --out /path/to/new_audit_output_dir
```

## 输入规格（`project_audit_spec.json`）

- `format_version`: `1`
- `study_id`: 与目标项目 `study.json` / `plan.json` 一致的研究标识
- `authorized_root`: 允许只读访问的目标项目根目录
- `read_only`: 必须显式为 `true`
- `plan` 或 `study_config`: 指向目标项目内的 `plan/plan.json` 或 `study.json`
- `rows` / `folds`（可选）: 指向目标项目内的行清单与折清单（默认读取 `plan.json` 冻结路径）
- `planned_fits`: 指向拟合成员表 CSV
- `runs_dir`（可选）: 指向运行登记目录
- `code_files`: 待静态探查的 Python 脚本列表 `[{"path": "rel/path.py", "sha256": "<64-hex>"}]`
- `generated_check_scripts`（可选）: 候选生成检查脚本列表 `[{"id": "...", "path": "rel/check.py", "sha256": "<64-hex>"}]`

## 只读与安全边界

1. **输出目录隔离**：`--out` 必须不存在，且不得位于 `authorized_root` 内部或包含 `authorized_root`。
2. **只读不可变性校验**：执行前后对 `authorized_root` 全文件计算 SHA-256 快照，验证 `authorized_root_unchanged=true`。
3. **静态 AST 代码探查（不执行目标代码）**：使用标准库 `ast.parse` 检查：
   - `UNSCOPED_PREPROCESSING_FIT`：在切分前或折循环外对全量/测试相关数据调用预处理器的 `.fit()` / `.fit_transform()`
   - `UNGROUPED_ROW_SPLIT`：使用 `train_test_split` / `KFold` 而未按患者分组（`GroupKFold` / `GroupShuffleSplit`）
   - `TEST_SET_REUSE_IN_FIT_OR_SELECTION`：在拟合操作中引用 `X_test` / `y_test` / `test_df`
   - `MISSING_FIT_MEMBERSHIP_LOGGING`：脚本包含 `.fit()` 调用但未记录拟合成员日志（`fits.csv` / `actual-fits.csv`）
4. **不可信生成脚本门禁**：先做静态 AST 审查（拒绝 `socket`、`urllib`、`http`、`requests`、`subprocess`、`eval`、`exec` 等危险模块或调用）；即使静态检查通过，未提供 `--sandbox-runner` 时也必须停在 `AWAITING_SANDBOX_RUNNER`，绝不将普通 `subprocess` 超时冒充为操作系统沙箱。

## 四分类报告结构（`project_audit.json` / `project_audit.md`）

1. `confirmed_violations`：由 `study.py` 在所供清单和运行登记上确认的确定性违例（如 `patient_overlap`、`feature_after_index`、`fit_outside_training_fold`、`omitted_planned_run`）。
2. `code_risk_indicators`：从目标项目源码静态 AST 识别的工程风险模式（仅作代码结构提示，不単独等同于运行时违例）。
3. `insufficient_evidence`：未执行任务（`NOT_RUN`）、未完成运行（`RUNNING`）、缺运行登记或待外部沙箱执行的检查脚本（`AWAITING_SANDBOX_RUNNER`）。
4. `checked_no_violation_found`：在已提供清单范围内检查且违例数为 0 的规则（不代表整体低偏倚或临床有效）。
