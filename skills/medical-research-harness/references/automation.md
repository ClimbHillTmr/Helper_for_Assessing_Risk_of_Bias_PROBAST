# 自动化编排与结构化判断

## 使用入口

Python 3.10+，仅标准库。`workflow.py` 自动执行可确定的检查并生成交接，不执行 task.command、训练、数据清洗或外部模型请求。用 agent 的 `terminal` 工具运行下列命令；所有输入来自目标研究已批准的协议和真实导出器。

新研究尚无计划时：

```bash
python3 <skill>/scripts/workflow.py --study /study/study.json \
  --phase preflight --fits /study/planned-fits.csv \
  --bundle /study/evidence-preflight.json --out /study/check-001
```

新建的计划仍是 DRAFT，缺少显式外部校验器时返回阻塞。审批来自研究实际决定，不能填入示例批准来解除阻塞。已有计划优先复用：

```bash
python3 <skill>/scripts/workflow.py --plan /study/plan-v1/plan.json \
  --phase preflight --fits /study/planned-fits.csv \
  --bundle /study/evidence-preflight.json \
  --lab /trusted/lab.py --out /study/check-002
```

结果阶段复用同一计划，自动核验登记记录和实际审计：

```bash
python3 <skill>/scripts/workflow.py --plan /study/plan-v1/plan.json \
  --phase results --bundle /study/evidence-results.json \
  --runs /study/registry/runs --out /study/check-003
```

每次 `--out` 须不存在，且须位于 `--runs` 目录之外；路径解析后检查，拒绝时不创建目录。需要恢复时，保留旧产物，在新输出目录使用 `--plan` 重新检查当前输入；不从旧 PASS 缓存继续，不重置批准，也不自动重新执行已登记实验。这个入口没有常驻轮询、无人值守训练或自动重试；agent 可在收到新增证据后再次调用它。

## 输入与状态

- `--study` / `--plan` 二选一；前者编译新 DRAFT，后者重新核对原配置、协议、全部实验和冻结清单。
- `--phase` 必须显式为 preflight 或 results，避免从文件是否存在猜测用户目标。design 阶段使用协议模板和 `check_bundle.py`，无需为了检查强造数据清单。
- `--bundle` 缺失明确阻塞。证据包阶段、study_id 和协议路径/哈希必须匹配本次计划；文档通过仍不认证审批身份、正文或审查语义。
- preflight 需要 `--fits` 和显式 `--lab`。文档或计划审计失败时不调用外部校验器；有效 runner 仍须核对真实审批、锁和任务。
- results 需要存在的 `--runs` 目录。结果阶段不需要 planned-fits 或当前 preflight；由 reconcile 核验每个实际运行的历史批准快照、锁及 executed 审计。若主动提供 `--fits`，其失败也阻塞本次工作流。
- results 的文档失败不妨碍独立对账，便于同时列出证据缺失和运行问题。缺少目录不是空登记；显式空目录列出所有 NOT_RUN。RUNNING 仅表示缺终态记录，不证明进程存活。

| 状态 | 条件与含义 | 下一步责任 |
|---|---|---|
| BLOCKED | 必要检查缺失、失败或输入错误 | agent 按门禁定位修复已授权实现；科学变更交研究者决定 |
| AWAITING_EXECUTION | 本次 preflight 技术和文档检查通过 | 原 runner 在真实批准、资源预算和唯一写入者约束内执行 |
| AWAITING_SCIENTIFIC_REVIEW | 所提供登记可对账，results 文档检查通过 | 新的独立只读复核；判断偏倚、解释阴性和失败结果、核实登记源完整性 |

不存在自动 ACCEPTED 状态。`execution_authorized=false`、`scientific_validity=not_assessed` 恒定。`ok=true` 只表示该阶段程序检查通过，不能解释成研究成功。所有尝试失败也可以正确完成对账；状态计数仍显式保留 FAILED。

## 输出与交接

`workflow.json` 是机器入口，包含 format_version、phase、state、各 gate 的 pass/blocked/error/skipped、固定词汇诊断、next_actions、attempt_counts、plan 哈希和覆盖限制；`workflow.md` 提供人可读交接。按阶段还生成 documents.json、planned-audit.json、preflight.json 或 summary.json / summary.md。首次编译另有 plan/。

最后原子发布 `completion.json`，列出本次输出文件哈希和退出码。消费方须确认该文件存在、产物哈希匹配且 workflow.json 可解析；缺完成标记表示部分输出，不能据此继续。完成标记可以记录阻塞报告，本身不代表检查通过。

退出码 0 表示该阶段检查通过；1 表示已列明阻塞；2 表示输入错误、身份变化或输出冲突。已预留输出目录后，各检查的常见输入异常写进 workflow.json，保留成功的前序产物；磁盘写入失败或进程被强制终止时可能只有部分产物，不能视为通过。外部校验器的原始 stdout/stderr 不进入共享报告。

报告不复制患者行，但可能包含私有文件路径、研究任务定位和聚合数值，应保存在目标项目的适当访问范围内。每次报告是检查时点快照，不是运行期间的文件锁；真实 runner 必须再次核对身份并负责登记、资源和独占写入。

## 从 Jev 借鉴什么

依据 TypeSafe 当前公开文档，Jev 接收 state 与 questions，返回 Choice / Score / Noul，不生成代码或解释。它适合给确定的程序流程提供窄范围语义判断。当前实现借鉴其分解方式，未安装 SDK、未接入 API、未运行 Jev 性能实验。

| 模式 | 本项目的采用方式 | 可选语义扩展及边界 |
|---|---|---|
| 固定选项与显式状态 | 本地 gate、固定状态和下一步动作 | 研究目的分类可返回 prediction / causal / descriptive / insufficient；不能静默修改研究设计 |
| 两阶段技能建议 | SKILL.md 先选研究类型/阶段，再按需读取具体 reference | 多技能环境可先筛候选再读全文复核，允许 none；单一产品不需要把大技能目录接入远程 API |
| 来源定位后验证语义 | 文件哈希、协议身份、运行与拟合证据由代码检查 | 候选证据正文再判断 supports / contradicts / insufficient；原文中未匹配不直接判定捏造，可能有 OCR、版本或摘录差异 |
| 小模型提取→逐项核验→升级 | 已知错误留具体诊断，科学接受交独立复核 | 用逐项问题检查终点、时点、切分等抽取内容；任一关键字段缺证据就升级，不能平均抵消 |
| 置信度分流 | 硬性门禁始终由程序和批准协议决定 | Choice/Score confidence 是概率分布集中程度，Noul 没有独立 confidence；高值不授予科研批准 |

若以后接入 Jev，把问题、选项、模型版本、阈值和预算放在单独可审查配置中。先用有专家标签的代表性材料做离线评估，再 shadow mode（只建议、不驱动行动），测量错误放行、错误拦截、弃权率、成本和延迟。比较纯规则、现有 agent、agent+Jev；不把 cookbook 的阈值或效果搬成医疗研究证据。外发材料需单独确认数据范围；患者行、预测、嵌入与凭据不作为模型输入。缓存须绑定来源哈希、问题版本和模型版本，来源变化即失效；服务错误按未评估处理。

参考：

- [Jev with coding agents](https://docs.typesafe.ai/introduction/coding-agents)
- [官方 TypeSafe skill](https://github.com/typesafe-ai/skills/blob/main/skills/typesafe-ai/SKILL.md)
- [Skill suggestion](https://docs.typesafe.ai/cookbooks/skill_suggestion)
- [Double-checking citations](https://docs.typesafe.ai/cookbooks/citation_check)
- [SDE cascade](https://docs.typesafe.ai/cookbooks/sde_cascade)
- [Confidence](https://docs.typesafe.ai/confidence)

## 软件验证

使用 `terminal` 运行 `python3 <skill>/scripts/test_workflow.py`。测试只使用隔离合成清单、模拟批准与模拟运行；临时校验器明确限于测试。完整回归仍包括 test_check_bundle.py、test_study.py 和仓库 tests/review_probes.py。合成软件检查与新的代码复核均不代替真实数据审计或科学接受。
