# Laya 来源审查 v1

审查时间：2026-10-20（Asia/Taipei）。只读调研，未下载权重、未安装包、未运行模型。
所有"作者声称"均为一手页面自述，**未在本仓库复现**，不当作实测。

## 父代理核查与纠正（优先于下面原始调研记录）

- 实际读取 receptron/laya 的 main/package.json：version 为 `0.1.2`（不是下文0.2.0），dependencies 为 `@huggingface/tokenizers ^0.2.0` 与 `onnxruntime-node ^1.22.0`（不是 @huggingface/transformers）。main 可变，完整版本锁仍待完成。
- 实际读取多语 rl_agent_config.json，确认为 temperature `[1.0,1.0,1.0]`，temperature_by_options `{}`；只能确认发布配置未施加温度修正，不据此断定训练本身毫无校准。
- 实际读取 Python main/pyproject.toml：version `0.4.12`，基础依赖 torch>=2.0、transformers>=4.48、safetensors>=0.4、huggingface_hub>=0.20、numpy>=1.20。尚未安装与复现。
- 自有参考不足时不能声称完成目标域温度拟合。目标是工程语义判断，不是患者风险预测；不能把 PROBAST 对预测模型校准的要求直接当本判断器的验证依据。
- `from_pretrained` 不会仅因存在py文件就执行远程代码；是否开启动态代码加载取决于实际调用和auto_map，尚未查明。`head_max_len`/窗口上限是推理组件约束；并无证据支持“官方条目通常超过512 token”的概括。

以上来源同本文末 URL 的 package.json / pyproject.toml / rl_agent_config.json；本轮是配置/依赖核查，非模型运行。

## 1. 仓库与 checkpoint 清单

| 来源 | 地址 | 固定 revision | 许可 | 权重 |
|---|---|---|---|---|
| Node.js/TS 包装器 | github.com/receptron/laya | HEAD `60d5ee6`（2026-10-17 push） | MIT | 无权重，下载 HF checkpoint |
| HF 英文 checkpoint | huggingface.co/convaiinnovations/laya | 最新 commit `7b928d8`（"17 days ago"，页面抓取于 2026-10-20） | Apache-2.0 | `model.safetensors` 843 MB（xet） |
| HF 多语 checkpoint | huggingface.co/convaiinnovations/laya-multilingual | 最新 commit `1720e3e`（同上） | Apache-2.0 | `model.safetensors` 644 MB（xet） |
| Python 参考实现/文档主仓 | github.com/NandhaKishorM/laya | main（未固定 commit） | Apache-2.0 | 代码仓，权重走 HF |

注意：`convaiinnovations/laya` 仓库**同时**在 `multilingual/` 与 `typed-decisions/` 子目录捆绑了另外两个 checkpoint（仓库总 2.37 GB）。`laya-multilingual` 独立仓是同一 checkpoint 的独立发布。

## 2. 架构与配置（一手文件）

`convaiinnovations/laya` 根 `config.json` 仅为 Hub 下载追踪桩：`{"model_type":"laya","architectures":["LayaTypedDecisions"]}`，160 B。`laya-multilingual` 根 `config.json` 完全相同。真正的运行时配置在 `rl_agent_config.json`：

- **laya（英文）**：encoder `answerdotai/ModernBERT-large`，`max_len=512`，`head_max_len=192`，`head_layers=2`，`amp_dtype=bf16`，训练 7313 updates / 1 epoch / ~1.96 h，fine_tuned_from_checkpoint=true。**出厂带校准**：`temperature=[1.637,1.251,1.983]`，另有按 (question type, option count) 分桶的 `temperature_by_options`（含 `choice:11+` 温度 0.1006，偏低）。
- **laya-multilingual**：encoder `jhu-clsp/mmBERT-base`（307M 编码器 + 决策头 = 322M 总参数），`max_len=1024`（作者称可 `max_len=8192`），`head_max_len=256`，训练 15987 updates / 4 epochs / ~4.97 h，从头训练。**出厂未校准**：`temperature=[1.0,1.0,1.0]`，`temperature_by_options={}`。模型卡自述过自信，自报 mean ECE 0.314，"refit 温度后 0.106"——这是**作者数据**，非我们实测。

参数量为作者标注（421M / 322M），未从权重文件核算。

## 3. 推理依赖与 trust_remote_code

- HF 页面把两个 checkpoint 标记为 `transformers` + `safetensors` + 自定义 `laya` 库。根 `config.json` 的 `architectures` 是 `LayaTypedDecisions`，**不是 transformers 内置类**；标准 `transformers` 版本里没有该类，实际加载依赖 `pip install laya`（Python 包）或 `@receptron/laya`（TS 包，ONNX Runtime）。是否需要 `trust_remote_code=True`：**未知**——repo 中未见独立 modeling 文件被页面列出，Python 包 `laya` 看起来是经 `hf_hub_download`+自写加载路径而非 transformers auto-class，但本审查未读 Python 包源码逐行确认。
- 仓库根有 `rl_agent_api.py`、`rl_common.py`、`email_utils.py` 等 .py 文件；若以 transformers `from_pretrained` + remote code 路径加载则会执行它们——这支持"可能走 trust_remote_code 或等价自写加载"的判断，具体机制待查源码。
- Node.js 侧：npm 包 `@receptron/laya` v0.2.0，依赖 `@huggingface/transformers`/ONNX Runtime 路径（package.json 自述 onnxruntime），从 HF 下载 ONNX bundle（repo 有 `onnx/`、`export/` 目录）。Node ≥20。
- Python 包：PyPI `laya`，Python ≥3.10；可选 extras：`serve/mcp/langchain/llamaindex/crewai/onnx/fast(structured)`。`pip install laya` 首次调用即下载 checkpoint。
- 已知运行时坑（模型卡自述）：装了 TensorFlow 时 `laya.load()` 可能因 transformers 探测 TF+abseil 死锁，需 `USE_TF=0`。

## 4. Python 接口（作者文档口径）与校准/评估陷阱

接口：`from laya import Router; router = Router(); router.predict(state, questions, model=..., max_len=..., lang_guess=...)`。问题类型：`choice`（选项 dict）、`score`（有序等级）、`noul`（是/否概率）。返回 `answers` + `routing` 元数据。

作者模型卡**自己**列出的陷阱（全部未经我们复现）：

1. **英文 checkpoint 在非英文上崩塌且自信**：Khmer 自报 acc 0.000 @ conf 0.952；置信度门控无法兜底 → 必须走 Router 或显式 `model="multilingual"`。
2. **`noul` 可能忽略 state 跟标签走**（issue #156），英文 checkpoint 最明显；建议改写为中性键 A/B 的双选 `choice`。
3. **`action.act_probability` 基本无信号**（issue #185），自报几乎恒 1.0，AUROC 0.30（反向）；门控应看 `confidence`（AUROC 0.77，作者口径）。
4. **过自信/未校准**：英文出厂有温度但作者仍报 mean ECE 0.466 → 分桶重标 0.081；多语出厂温度全 1.0，报 0.314 → 0.106。**用它的概率前必须在自有数据上做温度拟合**——这正好契合本仓库 PROBAST 风险偏倚评估对校准的要求。
5. **高基数 choice**：默认 `head_max_len`（英文 192 / 多语 256）下，~77 选项只剩 3–4 token/label，作者自报 Banking77 acc 0.425。需调 `head_max_len`/`max_len` 或分层选择。
6. **`score` 是最弱 primitive**：多语 checkpoint 有实测位置偏（几乎从不选第一档，issue #131）。
7. **长文档**：多语默认 1024 截断；`max_len=8192` 后作者自报 ~4k token 内 16–18/20 正确，之外波动大。
8. 英文 checkpoint `max_len=512` 是本仓库文献全文场景的硬约束——PROBAST 条目通常超 512 token，只能用多语 checkpoint 或自行切块/截断，行为需自测。

## 5. 网络状况与未知项

- 本机直连 `huggingface.co` REST API（`/api/models/...`）两次超时/不可达（Errno 101 Network unreachable）；`HEAD` 探测曾返回 200。文件树、配置与模型卡均经网页提取层取得，**精确 sha 只拿到页面显示的短 hash（7b928d8 / 1720e3e），完整 sha 未核**。
- 未知：pip 包 `laya` 的加载路径是否用 `trust_remote_code`；ONNX bundle 文件名与大小；`laya-typed-decisions` 的配置细节（未拉取）；`noul` 的具体打分头实现。
- 所有 benchmark 数字（MASSIVE/XNLI/ECE/延迟）均为作者在 HF 模型卡与 GitHub README 的自报值，附 issue 编号（#131、#156、#185）可回查，但**不是独立复现**。本仓库不应引用其为实测。

## 6. 来源 URL

- https://github.com/receptron/laya（+ api.github.com repos/commits，2026-10-20 取）
- https://huggingface.co/convaiinnovations/laya（模型卡、/tree/main、/raw/main/config.json、/raw/main/rl_agent_config.json，2026-10-20 取）
- https://huggingface.co/convaiinnovations/laya-multilingual（同上路径）
- https://github.com/NandhaKishorM/laya 与 raw README（2026-10-20 取）
- 作者 docs 站 https://nandhakishorm.github.io/laya/（模型卡引用，未逐一核对）
