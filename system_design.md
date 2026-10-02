# Medical Research Harness：设计与范围

版本：0.1.0-alpha。产品是 `skills/medical-research-harness/`，用于将研究问题和偏倚风险转成数据操作、可执行任务以及可复核结果。

## 工作顺序

```mermaid
flowchart LR
    A[目标项目协议与数据契约] --> B[队列和固定折清单]
    B --> C[plan：冻结任务及数据身份]
    C --> D[audit：检查计划拟合成员]
    D --> E[外部批准与 preflight]
    E --> F[目标项目执行并登记]
    F --> G[audit：核验实际拟合]
    G --> H[summarize：对账全部尝试]
    H --> I[逐题偏倚判断与科学复核]
```

数据准备与实验均遵守目标项目已有授权。plan 生成 DRAFT，不给予执行许可。计划成员表与实际 fit 日志分开；实际审计绑定具体任务和运行。队列与折身份进入任务指纹及协议锁，改变它们需按原研究流程修订。

## 最小实现

| 职责 | 实现 |
|---|---|
| Agent 入口 | AGENTS.md 与 SKILL.md |
| 科学指导 | workflow.md、methodology.md、protocol.md |
| 执行接口 | operations.md 与 study.py |
| 文档完整性 | check_bundle.py |
| 实验运行/审批 | 外部环境的现有工具，通过明确接口接入 |
| 可复现软件验证 | test_study.py、test_check_bundle.py、tests/review_probes.py |

核心脚本只依赖 Python 标准库。preflight 的外部校验器必须显式指定；不假设维护者的目录或服务存在。默认测试可在没有 ResearchLab 的环境运行。

## 迁移与范围

早期应用中的训练算法库、自动清洗、患者风险预测、警报、治疗建议、解释界面和后台设施已移出活动实现。旧实现与迁移材料由维护者在仓库外归档。第三方 PDF 在 Alpha 分发中用引用链接替代；旧 Git 历史未重写。

当前程序支持患者互斥、固定外层切分、完整内部折及约定运行记录格式的预测研究。研究目标、临床变量含义、统计方法、完整官方题目集合和最终判断仍需要专业审查。不能通过改变研究问题来迎合输入接口。

研究数据和训练实现属于目标研究仓库。本项目没有真实临床验证证据，也不声称自动完成正式 PROBAST 评价。验证历史及第一轮拒绝后修复的记录见 [可操作性复核](reviews/20261002-operability-review.md)。
