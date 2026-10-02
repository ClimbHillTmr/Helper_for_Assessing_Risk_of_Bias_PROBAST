# Medical Research Harness

**v0.1.0-alpha — 实验性开源版本。** Agent skill for clinical prediction research planning, manifest audits and reproducible run reporting.

指导医疗数据研究的数据处理、实验设计、偏倚控制和结果汇总。当前可执行路径支持患者互斥、固定外层切分及完整内部折的预测研究。它不提供训练平台或临床服务，软件检查通过不等于低偏倚、科学批准或临床有效。

## 安装 skill

在 Codex 中请求安装：

> 请安装 ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST 仓库中 skills/medical-research-harness 目录的 skill，使用 v0.1.0-alpha 标签。

也可使用 Codex 内置安装器：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST \
  --path skills/medical-research-harness --ref v0.1.0-alpha
```

安装器会拒绝覆盖已有同名目录；安装后下一轮对话可用。其他支持 Agent Skills 的环境，可下载 Release 中的独立 ZIP，将完整 `medical-research-harness/` 放入该环境的技能目录。ZIP 附带 MIT LICENSE。

调用示例：

> 使用 medical-research-harness 检查当前研究目标、数据契约和证据，生成具体的数据处理与实验任务，审计允许拟合成员，并汇总已登记结果。按已批准协议推进。

## 在仓库中运行

Python 3.10+，仅依赖标准库，无需安装 Python 包。

```bash
git clone --branch v0.1.0-alpha --depth 1 https://github.com/ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST.git
cd Helper_for_Assessing_Risk_of_Bias_PROBAST
python3 skills/medical-research-harness/scripts/test_check_bundle.py
python3 skills/medical-research-harness/scripts/test_study.py
python3 tests/review_probes.py --out build/review-probes
```

默认运行 24 个操作检查、76 个由独立复核转成的回归探测，以及文档证据检查套件。探测脚本自行生成隔离的合成材料，所有批准、运行记录与指标均为模拟。`--out` 目录必须不存在。没有患者数据或模型训练。

需要保留一次可查看的演示时：

```bash
python3 skills/medical-research-harness/scripts/test_study.py --out build/demo
```

查看生成的 `checks.json`、`audit-violations.json` 和 `summary-final/summary.md`。

## 功能与外部依赖

| 操作 | 功能 | 依赖 |
|---|---|---|
| `plan` | 生成任务、固定完整实验集合及协议/队列/折身份 | 本包与研究配置 |
| `audit` | 计算患者重叠、时间/标签违例、拟合越界及身份变化 | 本包与私有元数据清单 |
| `summarize` | 对账全部尝试，保留失败、中断和未执行项 | 本包与约定格式的运行记录 |
| `check_bundle.py` | 检查文档证据及哈希 | 本包 |
| `preflight` | 审计身份检查及已有审批/锁校验 | 显式 `--lab` 外部校验器 |

ResearchLab 不随本包分发。preflight 通过 `python <lab.py> validate-task <task.json>` 调用受信任的兼容校验器；没有该工具时，前三项核心操作仍可独立使用，但不得声称已完成外部审批校验。完整接口与工作顺序见 [操作说明](skills/medical-research-harness/references/operations.md)。

若环境已有兼容校验器，可额外运行 3 个集成检查：

```bash
python3 skills/medical-research-harness/scripts/test_study.py --lab /absolute/path/to/lab.py
```

此命令只调用 validate-task，不调用 run，不获得真实实验授权。

## 科学与验证边界

新预测协议可采用 PROBAST+AI，同时区分开发质量、评价偏倚与适用性；已批准研究沿用锁定版本。正式逐题评估需要完整官方工具与科学复核。因果、干预、重复患者未来预测和其他不兼容设计需要专用适配。

真实研究需在目标项目导出完整的行/折清单，记录实际 fit 输入，并按批准统计方法计算指标。合成检查不能证明日志真实、注册源完整、审批身份有效或临床适用。

- [技能入口](skills/medical-research-harness/SKILL.md)
- [研究契约模板](skills/medical-research-harness/assets/protocol.md)
- [可复现验证与历史修复](reviews/20261002-operability-review.md)
- [设计与范围](system_design.md)
- [参考文献与附件说明](Paper/README.md)

## 许可证与分发

项目代码及原创说明采用 [MIT License](LICENSE)。当前版本和独立 skill ZIP 不分发第三方论文 PDF、真实研究填写表、患者数据或本机备份。官方工具与文献通过引用链接获取；其原有使用条件不受本项目 MIT 许可证改变。旧提交历史保留原有内容，本次不重写历史。
