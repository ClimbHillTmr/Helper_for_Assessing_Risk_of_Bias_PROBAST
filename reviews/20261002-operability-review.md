# 可操作性复核与公开重现 — 2026-10-02

原来的方法说明和文件完整性检查不足以证明可操作性。补充命令后，独立的 AI 操作复核先给出 REVISION_REQUIRED；修复后，新的复核给出 ACCEPT，范围仅限任务、清单与运行记录接口，不涉及临床有效性。

## 保留的失败发现与修复

| 原问题 | 修复 |
|---|---|
| 同一计划可替换内部折 | 行/折身份进入任务指纹与锁；实际审计及汇总核对身份 |
| 派生计划可遗漏实验 | 从原配置重建预期计划，核对完整实验集合和任务内容 |
| 缺失代码状态被当作干净 | 要求存在字符串 git_status；脏代码须有有效格式的快照 SHA-256 |
| 失败退出证据不完整仍通过 | 所有终态校验退出码及 reason，并保留安全诊断定位 |

受该次操作复核的核心 `study.py` SHA-256：`03b7c4216fa109965a8c8f346453c8a3cba679ff28f1fa043588b46ae1c1acf7`。

历史复核包含 27 个操作检查（24 核心 + 3 外部校验器集成）、76 个独立探测及文档证据套件。Alpha 整理保留核心实现，测试入口改为显式选择外部校验器，且将独立探测脚本适配为公开可重现的回归脚本。重新执行该脚本属于回归验证，不是重新进行独立科学评审。

## 无外部服务的公开验证

在仓库根目录执行：

```bash
python3 skills/medical-research-harness/scripts/test_check_bundle.py
python3 skills/medical-research-harness/scripts/test_study.py
python3 tests/review_probes.py --out build/review-probes
```

默认操作检查为 24 项。回归探测脚本自行创建两个合成研究目录，执行 76 个探测，检查源码和参考材料未改变，并输出逐项结果。输出目录须不存在。

其中的 preflight 负例专门验证坏锁在调用外部校验器之前被拒绝：所给校验器路径刻意不存在，且断言确切的锁拒绝原因。它们不代表外部校验器成功路径已被验证。3 个可选集成检查需要 `test_study.py --lab /absolute/path/to/lab.py`，且仅调用 validate-task，绝不执行研究。

所有模拟批准、指标和记录只属于隔离的软件示例。真实数据完整性、日志真实性、审批来源、注册源完整性、正式偏倚判断与临床适用仍未由这些检查证明。

当前 Alpha 的实际执行摘要与源文件身份见 [alpha-validation.json](alpha-validation.json)。公共 CI 用同样命令在 Python 3.10 与 3.13 上运行；以 CI 的实际状态为准。
