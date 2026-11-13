# 分层语义决策 agent

该组件与 workflow.py 分工：workflow.py 检查确定性研究证据；decision_agent.py 对显式输入的主张与证据片段提出语义建议。二者不能互相替代，语义建议不改变任何技术门禁、协议、批准或实验登记。

## 运行

通过宿主 `terminal` 调用：

```bash
python3 <skill>/scripts/decision_agent.py --input /study/approved-cases.json \
  --policy /study/agent-policy.json --out /study/decision-001
```

默认仅验证输入并输出 DRY_RUN / NOT_EVALUATED，不调用适配器。使用真实模型需显式增加 `--execute-models`，输出目录必须不存在。策略模板见 `assets/agent_policy.example.json`；其中 provider、model 和 command 均为待替换占位符，不能把模板称作可用模型配置。

输入契约：`format_version: 1`、`data_scope: synthetic | approved_external`、`cases: [{id, claim, evidence: [{id, text}]}]`。真实材料还需 `external_approval`，包含 `approved: true`、`reference`、`cases_sha256` 和 `policy_sha256`。后两者分别绑定 cases 和完整 policy 的规范化 JSON（UTF-8、排序对象键、紧凑分隔符、不转义 Unicode），使用 decision_agent.canonical_sha256 计算；不是输入文件字节哈希。接收方、模型、命令或材料变化会使旧批准失效。这是调用者对材料外发的声明，不认证批准者身份；必须在目标研究中另行核对接收方、用途与允许内容，不把实验批准等同外发批准。不得输入患者行、逐行预测、嵌入或凭据。

## 模型分工

策略明确配置 `light` 与 `reasoner`，各有 provider、model、可信命令 argv。子进程通过 stdin 收到 JSON，stdout 返回单个严格 JSON。命令来自维护者配置，不来自模型输出；没有 shell 拼接。可信适配器仍有本机进程权限，不是沙箱。

轻量模型先判断 supports / contradicts / insufficient。低置信度、uncertain、证据不足、格式或引文错误触发至多一次 reasoner 复核；后者仍无有效依据则 BLOCKED。没有循环调用直到得到支持答案。空证据由程序直接判 insufficient，不花模型调用。`max_requests` 是整个批次上限，`timeout_seconds` 是单次适配器时间限制，不代表已实现货币预算。

返回字段严格限定为 model、decision、confidence、uncertain、evidence。引文必须是已有证据 ID 下的非空逐字子串；程序仅保存引文哈希及位置，不把原始模型正文写进报告。逐字命中不证明语义正确，候选来源本身的真实性和完整性也需审查。

模型名称必须匹配配置，但此契约中的返回身份由适配器报告，不能证明供应商底层权重。两个 tier 使用相同 model 时，不得声称已验证不同模型；独立 subagent 上下文也不等于独立模型。

## 输出与限制

`decision.json` 保留输入/策略哈希、每次调用、升级原因、请求计数、响应哈希及最终建议。最后发布 `completion.json`；消费前核对其产物哈希。只有有效建议的批次为 AWAITING_SCIENTIFIC_REVIEW，存在未解决项则 BLOCKED。输出恒为 shadow，execution_authorized 与 scientific_approval 恒为 false。

confidence 是模型自报且未校准；模板阈值仅用于软件演示。正式效果需在专家标注、按论文/研究项目隔离的测试集比较规则、单模型与分层模型，报告错误放行、漏检、覆盖率、弃权率、升级率、延迟和实际成本。所有模型一致仍不构成科学证据。

## Hermes 适配器

`hermes_decision_adapter.py` 是可选的 Linux 适配器，依赖已安装且 API 兼容的 Hermes；核心决策组件仍仅标准库。通过 `HERMES_ADAPTER_ROOT` 指定安装源码位置，默认查找用户目录下的 `.hermes/hermes-agent`。启动子进程前关闭插件/MCP发现、提供空工具集合并封锁分派，所需接口缺失时拒绝运行；这不是操作系统沙箱。不要使用 `-t 空字符串` 代替隔离，该参数会回退默认工具。

策略 command 填 Python 解释器及本适配器的绝对路径，provider/model 填实际可用的精确标识；外层 timeout_seconds 至少 90 秒，适配器内部上限 65 秒。当前真实核验成功的是 magpie / codex/gpt-6-astra；gpt-5.6-luna 请求超时，尚未验证双模型可用性。CLI 启动模型字段不是供应商响应身份，不证明底层权重。

输入上限 1 MiB、policy 256 KiB、适配器请求 2 MiB；stdout 1 MiB、stderr 64 KiB。超限/超时清理子进程，清理失败停止批次后续调用。通用可信命令仍负责其自身后代进程和路由；Hermes adapter 另有 Linux 父进程退出与进程组清理保护。

### 测试分层

默认检查不依赖 Hermes 安装、配置或凭据，也不调用真实模型：

```bash
python3 <skill>/scripts/test_decision_agent.py
HERMES_ADAPTER_ROOT=/nonexistent python3 <skill>/scripts/test_hermes_decision_adapter.py -v
```

适配器单元/契约测试在临时目录创建仅含 `hermes_cli/main.py` 标记文件的合成源码树，保留真实 argv 构造与请求/响应校验，仅模拟 CLI 传输；不导入合成文件。另用本机 Python 子进程验证输出上限、超时与清理。缺 root 必须在调用 CLI 前失败；非零退出测试必须实际走到模拟传输并得到 `hermes_failed`，不能被缺安装错误误判为通过。CI 明确设无效安装路径并关闭集成，确保不依赖维护者环境。

真实安装集成测试单独位于 `HermesIntegrationTests`，默认有明确 skip 原因；只在显式设置 `HERMES_ADAPTER_INTEGRATION=1` 后启用。Linux 上用兼容 Hermes 的 Python/依赖环境执行：

```bash
HERMES_ADAPTER_INTEGRATION=1 HERMES_ADAPTER_ROOT=/path/to/hermes-agent \
  python3 <skill>/scripts/test_hermes_decision_adapter.py -v
```

该集成仅导入已安装 Hermes API，检查工具分派封锁及非空工具清单拒绝，不联系供应商。启用后安装不存在或接口不兼容必须非零退出，不得静默 skip/PASS；例如 root 设为 `/nonexistent` 应报告 `tool_isolation_unavailable` 并失败。Hermes bootstrap 的父进程退出保护及 `/proc` 后代观察依赖 Linux，在其他平台明确 skip；通用进程组/超时测试要求 POSIX，否则明确 skip。

测试通过仅证明对应软件契约，不证明模型语义质量、供应商身份或科学有效性。真实模型调用和其结果须另行登记，不能用模拟测试或本机 API 集成测试替代。

## 句锚定 Laya 适配器（`laya_decision_adapter.py`）

`laya_decision_adapter.py` 是纯标准库适配器，把 `literature.py`（`literature_evidence_analysis`）或 `decision_agent.py` 的请求编译为单次前向编码器（如 `LayaTypedDecisions`）的结构化选择任务：

1. **零幻觉句锚定引文重构**：将候选证据段落确定性切分为编号句子 `S001..Snnn`（保留精确 `[start, length)` 偏移），由 `citation_span` choice 头在 `{S001, ..., Snnn, NONE}` 中单选，再由适配器映射回原文精确逐字子串，消除生成式模型改写引文导致的偏移校验失败。
2. **显式温度校准与非对称选择性升级**：支持通过 `--temperature-file` 注入在独立校准折拟合的 `T_choice`，并对放行类判定（`addressed` / `supports`）执行高于风险/弃权判定的非对称置信度门禁（`--clearance-min-confidence`，默认 `0.85`）；未达门禁或 `citation_span=NONE` 时确定性升级至 `--reasoner-command` 或返回 `insufficient` / `uncertain: true`。

离线验证（不依赖 PyTorch 或模型权重）：

```bash
python3 <skill>/scripts/test_laya_decision_adapter.py -v
```
