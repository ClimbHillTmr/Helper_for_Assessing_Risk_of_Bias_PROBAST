# 行动计划 v3.3：`MedBias-Laya V3` 漏洞全修复与五大方法学升级实证总结

版本：v3.3，2026-11-05。状态：**`MEDBIAS-LAYA-STUDY-V3`（6 大漏洞修复 + 5 大 LLM 方法升级）已在 RTX 2060 GPU 上完成训练、校准、神经符号融合评测及 `study.py` / `project_audit.py` 完整对账**。

---

## 一、从 `V2` 到 `V3`：我们修复了哪 6 个漏洞、升级了哪 5 项 LLM 方法？

| 编号 | `V2` 反思发现的缺陷/漏洞 | `V3` 落地的工程与 LLM 方法学升级 | `V3` 锁定测试集（$n=120$）实证改善结果 |
|---|---|---|---|
| **1** | **T2 规则循环自证偏差**（T2 答案与正则基线 `B0` 共用同一批表面关键词） | 引入与各折严格互斥的**非典型临床语义改写窗口**，测试真正的跨短语语义理解 | 表面正则 `B0` 在 T2 跌回真实水平 `35.42%`，而 `MedBias-Laya V3` 达到 **`79.17%`**（高出 `B0` **`+43.75` 个百分点**） |
| **2** | **T2/T1 多句共指冲突**（一段文字有多句含答案，单句 One-Hot 惩罚同义正确句） | 引入**多实例集合软目标监督（Multi-Instance Bag Log-Sum-Exp Loss，$-\ln\sum_{s \in S_{\text{valid}}} q_s$）** | T2 句子引文定位准确率从 `16.67%` 提升至 **`27.08%`**（较零样本 `14.58%` 提升近一倍），综合引文定位达 **`56.67%`** |
| **3** | **校准折过小（4 篇）且训练期 Logit 爆炸导致 5 个头温度撞上 `T=5.0` 上限** | 校准折扩容 +50%（`18:6:4:8`），训练期加入 **Label Smoothing ($\varepsilon=0.08$) + Logit L2 正则 ($\lambda=0.018$)** | **0 个头撞上 `5.0` 上限**（$T \in [0.50, 2.44]$），主头 `ECE` 从 `0.3637` 暴降至 **`0.0845`**，全头 `ECE` 降至 **`0.0569`** |
| **4** | **纯真实未修改 PMC 段落上类别先验偏移** | 引入 **Menon et al. (ICLR 2021) 先验对数几率修正（Prior Logit Adjustment）** | 纯真实未修改 PMC 准确率恢复至 **`75.00%`**，全量假放行率（FCR）从 `15.38%` 暴降至 **`3.77%`**，漏检率（FNR）降至 **`13.79%`** |
| **5** | **Task T3 代码样本同折内存在循环复用** | 为 36 篇论文每篇构造 3 段（Python/R/SAS）共 **108 段完全不重复的多块建模脚本** | 测试集 24 段全新多块脚本上，单文件 AST `B0` 仅 `0.2389`，`MedBias-Laya V3` 达 **`1.0000` Macro-F1 与 `100.0%` 代码块定位** |
| **6** | **`study.py` 强制零拟合基线填写名义拟合行 + 缺乏本地规则与模型融合** | 升级 [`study.py`](../skills/medical-research-harness/scripts/study.py) 原生支持 `zero_fit_experiments`（`B0`/`B1` 真实记录 0 行拟合），并构建**本地零成本神经符号混合系统 `B4_neuro_symbolic`** | `B0`/`B1` 空拟合表通过执行态审计；`B4_neuro_symbolic` 将多任务综合 Macro-F1 推升至 **`0.8070` [`0.7558, 0.8388`]**，保留子集（`47.50%` 覆盖）准确率达 **`91.23%`**、**假放行率 `0.00%`** |

---

## 二、`MEDBIAS-LAYA-STUDY-V3` 核心产物索引

- **升级版自举审计底座**：[`skills/medical-research-harness/scripts/study.py`](../skills/medical-research-harness/scripts/study.py)（新增 `zero_fit_experiments` 与按实验局部折拟合核验）
- **升级版三任务语料构造脚本**：[`build/medbias-laya-study/build_corpus_and_manifests.py`](../build/medbias-laya-study/build_corpus_and_manifests.py)
- **升级版多任务训练、校准与神经符号融合脚本**：[`build/medbias-laya-study/train_and_evaluate.py`](../build/medbias-laya-study/train_and_evaluate.py)
- **完整评测报告**：[`build/medbias-laya-study/medbias_laya_benchmark_report.json`](../build/medbias-laya-study/medbias_laya_benchmark_report.json)
- **执行态对账汇总**：[`build/medbias-laya-study/summary/summary.md`](../build/medbias-laya-study/summary/summary.md)
- **目标项目只读审计报告**：[`build/medbias-laya-project-audit-v3/project_audit.json`](../build/medbias-laya-project-audit-v3/project_audit.json)
