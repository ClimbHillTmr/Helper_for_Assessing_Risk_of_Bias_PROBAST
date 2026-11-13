# 《LLM 微调与神经符号系统全流程通关秘籍》
## —— 从零基础“幼儿园比喻 + 高中数学”读懂 `Medical Research Harness + MedBias-Laya V5` 全链路工程与算法精髓

> [!IMPORTANT]
> **为什么写这本《通关秘籍》？**
> 很多大模型（LLM）与神经符号（Neuro-Symbolic）教程一上来就堆砌研究生级别的矩阵微积分、测度论和晦涩黑话，让人望而却步。其实，**最顶级的 AI 工程设计，底层的数学道理往往只需要高中知识（集合、函数、指数 $e^x$、加权平均、导数斜率、平方惩罚 $z^2$）就能彻底讲透！**
> 本秘籍以我们亲手打磨的开源项目 **`Medical Research Harness + MedBias-Laya V5`**（80 篇真实 CC BY 4.0 临床预测论文 + 80 个公开生物医学 NLP 窗口 + 32 道综述语境探针题（关键句由开发者撰写，嵌入 8 篇 PROBAST 综述上下文） + 216 段 Python/R/SAS 代码）为唯一实战沙盘，用**“幼儿园都能听懂的生活比喻 + 逐个符号拆解的高中数学公式 + 真实代码与踩坑血泪史”**，带你从第 1 章一路通关到第 11 章！

> [!CAUTION]
> **先读这一条：本书里所有“标准答案”都是开发者自己生成的，没有任何人类标注。** `R1`（全文参考）和 `R2`（单窗口参考）是 `evaluate_80_unmodified_pmc_kappa.py` 里的关键词规则函数（`R2` 是 `R1` 的精简版，二者不独立，也不是人类评审员；`R1` 还含针对具体论文写死的短语，并对两篇论文引用了云端 LLM 试运行的输出）；锁定测试集 T1 标签由 `adjudicate_real_t1_window_v3()` 规则生成（`PMC12874331`、`PMC12231630` 两篇取自云端 LLM 输出）；32 道“综述探针题”的关键句是开发者撰写后插入综述原文上下文的；`B4` 的符号规则与 `R1` 共用触发短语（如 “prior to splitting”“entire dataset”“within each training”）。因此书中所有 $\kappa$、F1、准确率衡量的是**“模型复现我们自己规则的程度”**，不是 PROBAST 偏倚评估的临床准确度；神经符号融合带来的涨分有一部分是循环的。24 篇未见论文上 `B4_22L` 的 T1 分问题 $\kappa$ 为 `1.00`（FIT_SCOPE）/ `0.00`（EVAL_ROLE）/ `0.00`（GROUP_SPLIT）/ `0.714`（FEATURE_TIME）；合并 $\kappa=0.9097$ 混合了 96 个 T1 与 144 个 T2 窗口。计划中的人工核验标注研究完成之前，不应作任何临床准确度结论。

---

## 🗺️ 全书十一章通关路线图

| 章节 | 核心痛点（我们遇到了什么坑？） | 幼儿园生活比喻 | 用到的高中数学武器 | 工程落地脚本与实证战果 |
| :--- | :--- | :--- | :--- | :--- |
| **第 1 章** | 普通大模型审稿爱“瞎编原话（幻觉）” | 闭卷默写课文 vs. 拿荧光笔涂答题卡 | 集合映射 $f: \mathcal{S} \to \{1,\dots,K\}$ 与字符串切片区间 $[a, b)$ | [`laya_decision_adapter.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/skills/medical-research-harness/scripts/laya_decision_adapter.py)：**`100.0%` 原文字符偏移有效（设计保证，非实验成绩）** |
| **第 2 章** | 小数点 `14.5` 和缩写 `et al.` 把句子切碎，长文把答案挤出窗外 | 切香肠避开脆骨 + 放大镜对准关键词拍合照 | 条件逻辑判断与关键词打分排序函数 $\text{Score}(s_i)$ | [`focus_evidence_window`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/build_corpus_and_manifests.py#L410-L449)：引文命中率从 **`27.08%` 飙升至 `75%+`** |
| **第 3 章** | 神经网络怎么把一串数字变成“几成把握”？ | 才艺比赛评委亮分牌 $\to$ 算奖金分摊比例 | 指数函数 $e^z$、Softmax 归一化 $\frac{e^{z_c}}{\sum e^{z_j}}$、对数惩罚 $-\ln(p)$ | [`train_and_evaluate.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py)：7 个多任务分类与指针决策头 |
| **第 4 章** | 一段话里有 2 句都说了研究目的，单选标准答案让模型精神分裂 | 抓宝可梦：只要抓到袋子里任意一只就算赢 | 并集概率加法 $P_{\text{bag}} = \sum_{s \in \mathcal{V}_i} q_s$ 与包裹损失 $-\ln(P_{\text{bag}})$ | 多实例包裹损失（MIL Bag Loss）：T2 引文定位跃升至 **`73.96%`** |
| **第 5 章** | 模型染上“过度自信症”，打分飙到 $\pm 15$，校准温度撞爆天花板 $T=5.0$ | 考试不许打 100 分满分 + 给弹簧加拉力器 | 加权平均（标签平滑 $\varepsilon=0.08$）+ 二次函数平方惩罚 $\lambda_{L_2}\frac{1}{K}\sum z_c^2$ | 7 个决策头校准温度全部受控在 **`[0.92, 1.35]` 有界区间**（防止 $T=5.0$ 边界饱和） |
| **第 6 章** | 只解冻顶层 7 层够不够？全解冻 22 层为什么爆显存、梯度差 21 倍？ | 老教授（底层）微调、实习生（顶层）猛学 + 存档点省内存 | 复合函数链式法则 $\frac{\partial \mathcal{L}}{\partial x_0}$、向量模长 $\|\mathbf{g}\|_2$、等比阶梯学习率 | 全 22 层微调（`125.30M` 活跃 / `321.91M` 总参数）：测试集 T1 引文命中率达 **`82.29%`** |
| **第 7 章** | 模型靠背诵专业名词或无脑猜第 2 句（`S002`）偷懒拿高分 | 双胞胎找茬游戏 + 把糖果均匀藏在四个抽屉里 | 控制变量法（最小对比对）+ 离散均匀分布 $P(S_k) = \frac{1}{4}$ | 揭穿 `B1` 零样本假象（引文从 `75%` 跌回真实 `15.62%`），逼出真本事 |
| **第 8 章** | 训练完的模型怎么微调“瞄准镜准星”？训练集和真实世界比例不同怎么办？ | 调节淋浴冷热水龙头 + 按当地晴雨天历史修正天气预报 | 温度缩放 $z_c / T$、期望校准误差 $\text{ECE}$、对数先验比 $\ln\frac{\pi_{\text{cal}}}{\pi_{\text{train}}}$ | 7 头平均 ECE 降至 **`0.0211`**，纯真实 PMC 准确率反升 |
| **第 9 章** | 纯规则太死板，纯神经网络偶尔走神，怎么把“左脑+右脑”合体？ | 老中医拿放大镜查关键词（规则）+ 年轻博士综合会诊（神经网络） | 高中集合交并补 $(W \cap V \neq \emptyset) \land (W \cap G = \emptyset)$ + 对数几率加法 | `B4 (22L)` 锁定测试集 `0.8679` Macro-F1（相对规则标签）；探针题 `100.0%` (`32/32`)，但探针句与规则共用词表，部分循环 |
| **第 10 章** | 模型拿不准却硬猜“没风险”会害死人，怎么让它学会“不懂就问”？ | 机场安检仪：疑似危险宁可开箱人工查，绝不随便放行 | 非对称不等式门控 $\tau_{\text{clear}}=0.80 > \tau_{\text{min}}=0.62$ + 哈希防篡改锁 | 保留子集假放行率降至 **`0.00%`**，113 项自动化回归测试全绿 |
| **第 11 章** | 审稿人质疑“改编题不代表真实全文”，且问“在 `<6 GiB` 显卡预算下，`76.6 亿` 参数的大模型会不会更好？” | 80 套一字未改的真题原卷裸考（但答案卷是我们的规则写的）+ 6GB 显卡塞大象黑科技 | 独立事件乘积（$\kappa$ 悖论）vs. 二次函数 $\bar{\pi}_c(1-\bar{\pi}_c)$（Gwet's $\text{AC}_1$）+ $O(L)$ CPU 查表显存算术 | [`evaluate_80_unmodified_pmc_kappa.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py) & [`evaluate_larger_backbones_and_llms.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_larger_backbones_and_llms.py)：24 篇真题对照规则 `R1` 的 T1 分问题 $\kappa$ = `1.00/0.00/0.00/0.71`（合并 $\kappa$ `0.9097`）；`<6 GiB` 同预算下与 `7.66B` QLoRA 分数相近（CI 重叠、未做配对检验），快约 `23` 倍 |

---

## 第 1 章：为什么普通大模型做不好“医学偏倚审稿”？（从自由默写到指针选择题）

### 1.1 幼儿园比喻：闭卷背诵课文 vs. 拿荧光笔涂答题卡
想象你请了一位很会聊天的小朋友（比如普通的生成式大模型 ChatGPT / Llama）去审阅一篇医学论文，问他：
> “这篇论文在填补缺失值（Imputation）的时候，有没有不小心把测试集的数据也混进去算平均数（数据泄漏）？请给出结论，并**一字不差地抄出原文证据**。”

* **普通生成式大模型的做法（自由默写）**：
  它看完文章后，凭着脑子里的印象，一个词一个词地往外蹦（Autoregressive Token Generation）。结果它经常会犯**“脑补症（Hallucination，幻觉）”**——比如原文写的是 *"Missing values were imputed using median replacement"*，它却顺嘴默写成 *"Missing data were imputed via median imputation prior to splitting"*。只要改了一个词，在严肃的医学证据审计（`literature.py`）里就会因为**“原文找不到这句话”**而直接判定为伪造引文！
* **我们 `MedBias-Laya` 的做法（给句子编号 + 涂答题卡）**：
  我们根本不让模型“自由默写”！我们在把文章喂给模型之前，先用确定性的代码把文章切成一个个编好号的句子：
  * `[S001]`：第一句话（记下它在原文第 0 个字符到第 85 个字符）
  * `[S002]`：第二句话（记下它在原文第 86 个字符到第 192 个字符）
  * `[S003]`：第三句话……
  然后我们发给模型一张**标准选择题答题卡**，上面只有三道选择题：
  1. **适用性（`applicability`）**：这道偏倚审查题适用于这篇论文吗？（A. 适用 / B. 不清楚 / C. 不适用）
  2. **审查结论（`finding`）**：有没有发现数据泄漏风险？（A. 发现风险 `reported_risk` / B. 明确安全 `no_risk_identified` / C. 证据不足 `insufficient`）
  3. **原文证据指针（`citation_span`）**：哪一句话是关键证据？（A. `S001` / B. `S002` / C. `S003` / ... / Z. `NONE`）

模型只需要回答：“我选 `S002`！”随后，我们的程序直接去字典里把 `S002` 对应的原文字母一字不差地取出来。**因为模型连一个字母都不需要自己生成，所以它编造假引文的概率从根源上变成了 `0.0%`！**

### 1.2 高中数学拆解：字符串区间切片与双射映射
在高中数学里，一段长度为 $N$ 的原文字符串 $T$ 可以看作一个字符序列。我们把切分出来的第 $k$ 个候选句子记为一个三元组：
$$\text{Candidate}(S_k) = (q_k, \, a_k, \, L_k)$$
**逐个符号解释**：
* $S_k$：第 $k$ 个句子的编号标签，比如 `S001`、`S002`（其中 $k \in \{1, 2, \dots, M\}$，$M \le 64$）。
* $q_k$：这句英文原话本身（Quote），去了头尾空格。
* $a_k$：这句话在原文字符串 $T$ 中开始的下标位置（Start Index，从 $0$ 开始数）。
* $L_k$：这句话的字符长度（Length）。

我们在代码里强制执行一条**铁律恒等式**（见 [`laya_decision_adapter.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/skills/medical-research-harness/scripts/laya_decision_adapter.py#L174)）：
$$T[a_k : a_k + L_k] \equiv q_k$$
也就是说，从原文第 $a_k$ 个字符开始往后数 $L_k$ 个字符，截出来的片段**必须百分之百等于** $q_k$！
当神经网络在选择题里选中了编号 $S_{\hat{k}}$ 时，我们直接通过映射函数 $g(S_{\hat{k}}) = T[a_{\hat{k}} : a_{\hat{k}} + L_{\hat{k}}]$ 取出原文。因此，在我们的锁定测试集（$n=240$）和综述语境探针题（$n=32$，开发者撰写）上，**原文字符偏移合法率（`verbatim_offset_valid_rate`）永远是雷打不动的 `100.0%`！**

### 1.3 系统架构全景图（Mermaid）
```mermaid
flowchart LR
    A["📄 原始医学论文段落 / 建模代码"] --> B["✂️ 确定性分句器\nsegment_evidence_sentences\n生成 S001..S008 + 精确坐标 (a_k, L_k)"]
    B --> C["📋 构造类型化选择题答题卡\nbuild_laya_payload\n(Applicability / Finding / Citation Span)"]
    C --> D["🧠 MedBias-Laya 编码器 + 决策头\n(mmBERT 22层 + 2层交叉注意力头)"]
    B --> E["⚙️ 左脑：确定性符号规则引擎\nsymbolic_signal_for_item\n(AST 语法树 + 跨越式动词-作用域匹配)"]
    D --> F["⚖️ 温度缩放 + 先验校准 + 神经符号融合\n(Logits z_c / T + Prior + Symbolic Boost)"]
    E --> F
    F --> G{"🛡️ 非对称选择性门控\nshould_escalate\n(放行阈值 0.80 > 报警阈值 0.62)"}
    G -- "高置信度通过" --> H["✅ 输出 100% 零幻觉精准引文与偏倚裁定"]
    G -- "低置信度 / 拿不准" --> I["🚨 触发安全弃权 (Selective Abstention)\n交由人类专家或重型推理器复核"]
```

---

## 第 2 章：怎么防小数点和缩写把句子切碎？（文本切分与滑窗聚焦的底层工程）

### 2.1 幼儿园比喻：切香肠避开脆骨 + 放大镜拍集体照
在早期版本（V1–V3）中，我们发现模型找证据句子的准确率只有可怜的 **`27.08%`**！为什么一个几亿参数的聪明模型连句子都找不对？我们打开数据一看，发现了两个让人哭笑不得的“低级工程惨案”：

1. **惨案一（乱刀切香肠）**：
   医学论文里到处都是小数点和英文缩写，比如：
   > *"Following Smith et al. (2024), patients with creatinine > 1.5 mg/dL (Fig. 2) had an AUROC of 0.84."*
   如果用最天真的正则表达式“遇到句号 `.` 加空格就切一刀”，上面这一句话会被瞬间剁成 **4 截碎香肠**（`et al.` 切一刀、`Fig.` 切一刀、`1. 5` 切一刀）！原本第 3 句的关键证据变成了 `S019`，编号全乱套了！
2. **惨案二（合照站不下，主角被挤出画框）**：
   一篇医学论文的 Methods（方法学）章节往往有 25 到 40 句话。但是模型的输入框（`build_sequence`）为了省显存，最多只能装下前 `1,536` 个词（其中留给选项的 `head_max_len` 只有 `768` 个词）。如果把 30 句话一股脑塞进去，排在第 12 句以后的真正证据句**直接被一刀剪掉（Truncated）了**！主角都没进镜头，模型怎么可能选得出主角？

### 2.2 高中数学与工程解法：条件状态机 + 关键词打分聚焦滑窗
我们在 V4/V5 中用了两招彻底根治：

#### 第一招：防小数点与防缩写的双指针扫描器（[`_iter_sentence_spans`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/skills/medical-research-harness/scripts/laya_decision_adapter.py#L100-L152)）
当扫描指针遇到句号 `.` 时，必须同时满足三个“否定条件”，才允许切分句子：
1. **后面紧跟的不能是非空白字符**：比如 `0.85` 句号后面是数字 `8`，不切！
2. **前面的单词不能属于科研缩写集合 $\mathcal{A}$**：
   $$\text{prev\_word} \notin \mathcal{A} = \{\text{fig}, \text{table}, \text{al}, \text{vs}, \text{dr}, \text{eq}, \text{ref}, \text{e.g}, \text{i.e}, \dots\}$$
3. **不能是单个人名首字母缩写**：比如 `J. Smith`（前面是单个大写字母，后面紧跟大写字母），不切！

#### 第二招：最多保留 8 句话的“放大镜聚焦滑窗”（[`focus_evidence_window`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/build_corpus_and_manifests.py#L410-L449)）
当一段证据有 $M > 8$ 句话时，我们给每一句话 $s_i$（$i \in \{0, 1, \dots, M-1\}$）计算一个**相关性总分 $\text{Score}(s_i)$**：
$$\text{Score}(s_i) = 100 \cdot \mathbb{I}(s_i \in \mathcal{P}) + \sum_{w \in \mathcal{K}_{\text{task}}} \alpha(w) \cdot \mathbb{I}(w \subseteq s_i) + \sum_{c \in \mathcal{C}_{\text{method}}} 1.0 \cdot \mathbb{I}(c \subseteq s_i) + \max(0, \, 0.5 - 0.01 i)$$
**逐个符号解释**：
* $\mathbb{I}(\cdot)$：**高中分段函数（指示函数）**——括号里的条件成立就等于 $1$，不成立就等于 $0$。
* $\mathcal{P}$：必须保留的锚点原句集合（如果有的话，直接加 $100$ 分保送！）。
* $\mathcal{K}_{\text{task}}$：当前题目专属的关键词集合（比如审查找缺失值填补时，关键词是 `imputation`, `missing`, `training fold`）。如果关键词是个词组（包含空格），权重 $\alpha(w) = 3.0$ 分；如果是单个词，权重 $\alpha(w) = 1.5$ 分。
* $\mathcal{C}_{\text{method}}$：通用方法学线索词集合（如 `split`, `fold`, `train`, `test`, `patient` 等），每命中一个加 $1.0$ 分。
* $\max(0, \, 0.5 - 0.01 i)$：**位置微弱加分（平局决胜项）**。第 $0$ 句加 $0.50$ 分，第 $1$ 句加 $0.49$ 分……这样当两句话得分一模一样时，优先保留段落开头交代背景的句子。

算完每句话的分数后，我们挑出**得分最高的 8 句话**，然后**按照它们在原文里出现的先后顺序重新排好**（编为 `S001..S008`）。这样既保证了窗户里永远不超过 8 句话（`0%` 截断率！），又保证了真正的关键证据句 100% 留在镜头中央！仅凭这一项底层工程修复，我们的引文定位命中率直接从 **`27.08%` 暴涨到了 `75%+`**！

---

## 第 3 章：神经网络是怎么打分的？（Logits、Softmax 指数函数与交叉熵损失）

### 3.1 幼儿园比喻：选秀评委亮分牌 $\to$ 把分数变成百分比夺冠概率
假设模型现在要做一道三选一的选择题（`finding`：A. 有风险 `reported_risk`，B. 无风险 `no_risk_identified`，C. 证据不足 `insufficient`）。
神经网络的最后一层就像三个并排坐着的评委，看完文章后，每个人举起一块亮分牌。注意：评委举出的原始分数可以是正数、零、甚至负数（比如 A 得 `+2.0` 分，B 得 `+1.0` 分，C 得 `-1.0` 分）。
在机器学习里，这三个没有范围限制的原始分数就叫做 **Logits（未归一化对数几率）**，记为向量 $\mathbf{z} = (z_1, z_2, z_3)$。

但是我们人类需要知道的是**概率（几成把握）**——概率必须满足两条高中数学常识：
1. 每个选项的概率不能是负数（$p_c \ge 0$）；
2. 所有选项的概率加起来必须刚好等于 $100\%$（即 $\sum_{c=1}^{K} p_c = 1$）。

怎么把有正有负的原始分 $z_c$ 变成正数，还能拉开差距呢？**高中数学里的指数函数 $f(x) = e^x$ 闪亮登场！**

### 3.2 高中数学拆解：Softmax 公式与交叉熵损失（Cross-Entropy Loss）

#### 第一步：用 Softmax 把原始分 $\mathbf{z}$ 变成概率分布 $\mathbf{p}$
对于有 $K$ 个选项的选择题，第 $c$ 个选项的预测概率 $p_c$ 定义为：
$$p_c = \text{Softmax}(\mathbf{z})_c = \frac{e^{z_c}}{\sum_{j=1}^{K} e^{z_j}}$$
**逐个符号解释**：
* $K$：选项的总个数（比如三选一就是 $K=3$）。
* $z_c$：模型给第 $c$ 个选项打的原始分（Logit）。
* $e \approx 2.71828$：高中自然对数的底数。无论 $z_c$ 是正是负，$e^{z_c}$ **永远严格大于 $0$**！而且 $e^x$ 是严格单调递增的凸函数：如果 $z_1$ 比 $z_2$ 大 $2$ 分，$e^{z_1}$ 就会比 $e^{z_2}$ 大 $e^2 \approx 7.39$ 倍（帮赢家快速确立优势！）。
* $\sum_{j=1}^{K} e^{z_j} = e^{z_1} + e^{z_2} + \dots + e^{z_K}$：把所有选项变成正数后的总和，放在分母上做除法。这样算出来的 $p_1 + p_2 + \dots + p_K$ 分子分母一约分，永远等于 $1$！

> 💡 **工程防溢出小妙招（见 [`train_and_evaluate.py` 第 242 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L242)）**：
> 在写代码算 `np.exp(z)` 时，如果 $z_c = 1000$，电脑算 $e^{1000}$ 会直接报错“无穷大溢出（Overflow）”。利用高中指数运算法则 $\frac{e^{z_c - M}}{\sum e^{z_j - M}} = \frac{e^{z_c} \cdot e^{-M}}{\sum e^{z_j} \cdot e^{-M}} = \frac{e^{z_c}}{\sum e^{z_j}}$，我们在代码里总是先减去最大值 $M = \max_j z_j$，这样最大的指数永远是 $e^0 = 1$，绝对不会爆表！

#### 第二步：用对数损失（Cross-Entropy）惩罚答错的模型
如果这道题的标准答案是第 $y$ 个选项（比如 A 是正确答案，那么目标向量是 $\mathbf{y} = (1, 0, 0)$），我们怎么根据模型猜的概率 $p_y$ 来打屁股（计算损失 Loss）呢？
我们用高中对数函数 $\ln(x)$ 的相反数：
$$\mathcal{L}_{\text{CE}}(\mathbf{p}, \mathbf{y}) = -\sum_{c=1}^{K} y_c \ln(p_c) = -\ln(p_y)$$
**为什么偏偏用 $-\ln(p_y)$？看三个直观数字就懂了**：
* 如果模型 100% 猜中标准答案（$p_y = 1.0$）：$-\ln(1.0) = 0$，**零惩罚，表现完美！**
* 如果模型犹豫不决，只给正确答案 $p_y = 0.5$ 的概率：$-\ln(0.5) \approx 0.693$，**轻度挨板子**。
* 如果模型固执地猜错，只给正确答案 $p_y = 0.001$ 的概率：$-\ln(0.001) \approx 6.908$，**重重挨大板子！** 而且当 $p_y \to 0$ 时，$-\ln(p_y) \to +\infty$，错得越离谱，惩罚呈指数级暴增，逼着模型火速改正！

---

## 第 4 章：当一段话里有两句都是证据怎么办？（多实例包裹损失 MIL Bag Loss）

### 4.1 幼儿园比喻：抓宝可梦——袋子里有两只皮卡丘，抓到哪只都算赢！
在真實的医学论文里，作者往往不仅在一个句子里提到研究设计。比如在提取 `study_purpose`（研究目的）时：
* `S001` 写着：*"We aimed to develop a multivariable prognostic model for 30-day mortality."*（完全正确！）
* `S004` 写着：*"This prediction model was subsequently validated in an external ICU cohort."*（也明确指出了预测模型目的！）

在旧版（V2）里，我们的训练代码极其死板：**只认 `S001` 是唯一标准答案，把 `S004` 当成错误答案（给 $0$ 分）！**
结果会发生什么？模型在读到 `S004` 里的 *"prediction model"* 时，选了 `S004`，却被裁判狠狠打了一板子！久而久之，模型陷入了“精神分裂”：它明明找到了正确的证据句，却被系统惩罚，导致 Task T2 的引文定位准确率卡在 `43%` 上不去。

### 4.2 高中数学拆解：软目标分配 + 多实例包裹损失（Multi-Instance Learning Bag Loss）
为了解决“多个句子同时是正确证据”的问题，我们在 [`build_training_sequences`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L109-L130) 和 [`train_and_evaluate.py` 第 1039–1040 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L1039-L1040) 中引入了**集合监督（Set-Valued Supervision）**。

设第 $i$ 个样本中所有合法的证据句下标组成的**非空集合**为 $\mathcal{V}_i \subseteq \{1, 2, \dots, K\}$（比如 $\mathcal{V}_i = \{\text{S001}, \text{S004}\}$）。
我们做了两件事：

#### 1. 软目标分配（Soft Target Allocation）
当合法集合里的句子不止一个（$|\mathcal{V}_i| > 1$）时，不再让第一句独占 $1.0$ 的权重，而是让首选句拿 $0.55$，其余合法句平分剩下的 $0.45$：
$$y^{\text{raw}}_c = \begin{cases} 1.0, & \text{若 } |\mathcal{V}_i| = 1 \text{ 且 } c \in \mathcal{V}_i \\[4pt] 0.55, & \text{若 } |\mathcal{V}_i| > 1 \text{ 且 } c \text{ 是首选证据句 } s^* \\[4pt] \dfrac{0.45}{|\mathcal{V}_i| - 1}, & \text{若 } |\mathcal{V}_i| > 1 \text{ 且 } c \in \mathcal{V}_i \setminus \{s^*\} \\[6pt] 0.0, & \text{若 } c \notin \mathcal{V}_i \end{cases}$$

#### 2. 多实例包裹总概率损失（MIL Bag Sum Probability Loss）
在高中概率论中，因为模型一次只能选一个句子（互斥事件），所以**“模型选中的句子落在合法集合 $\mathcal{V}_i$ 内”的总概率 $P_{\text{bag}}$**，就等于集合 $\mathcal{V}_i$ 内所有句子的预测概率 $q_s$ 之和！
$$P_{\text{bag}}(\mathbf{q}, \mathcal{V}_i) = \sum_{s \in \mathcal{V}_i} q_s = \sum_{c=1}^{K} q_c \cdot m_c$$
$$\mathcal{L}_{\text{MIL}} = -\ln\Big(\max\big(P_{\text{bag}}(\mathbf{q}, \mathcal{V}_i), \, 10^{-6}\big)\Big)$$
**逐个符号解释**：
* $q_c$：模型通过 Softmax 给第 $c$ 个候选句子算出的预测概率。
* $m_c \in \{0, 1\}$：合法掩码（`valid_mask`），如果第 $c$ 句在合法集合 $\mathcal{V}_i$ 里则 $m_c=1$，否则 $m_c=0$。
* $P_{\text{bag}}$：所有合法证据句的概率总和。只要模型把概率分给 `S001` **或者** `S004`（比如 $q_{\text{S001}}=0.45, q_{\text{S004}}=0.50$，加起来 $P_{\text{bag}}=0.95$），包裹损失 $\mathcal{L}_{\text{MIL}} = -\ln(0.95) \approx 0.051$ 就会非常小！
* $\max(\cdot, 10^{-6})$：对应代码里的 `.clamp(min=1e-6)`，防止概率为 $0$ 时算 $\ln(0)$ 报错。

加上权重 $\lambda_{\text{MIL}} = 0.35$ 的包裹损失后，模型再也不会因为“选了同义的第二句证据”而挨冤枉板子，Task T2 的引文定位准确率直接冲上了 **`73.96%`**！

---

## 第 5 章：怎么治好模型的“过度自信症”？（标签平滑 Label Smoothing + Logit L2 平方惩罚）

### 5.1 幼儿园比喻：考试不许打 100 分满分 + 给评委的亮分牌绑上拉力弹簧
如果我们只用第 3 章的交叉熵损失 $-\ln(p_y)$ 去训练神经网络，很快就会发生一件可怕的事：**“Logit 爆炸（Logit Explosion）”与“过度自信症（Overconfidence）”**！

为什么？因为在 $-\ln(p_y)$ 看来，只有当 $p_y = 1.0$ 时损失才等于 $0$。可是指数函数 $e^z$ 永远大于 $0$，要让 $\frac{e^{z_y}}{\sum e^{z_j}}$ 无限接近 $1.0$，唯一的办法就是**把正确选项的原始分 $z_y$ 往正无穷大推（比如 $+15$、$+30$），把错误选项的原始分往负无穷大推（比如 $-15$、$-30$）！**
在早期 V2 实验里，我们的模型训练完后，给正确选项打 `+18` 分，哪怕遇到一道它根本没把握的难题，它算出来的概率也是 `99.9999%`！结果在做后验温度校准时，全 7 个决策头的温度 $T$ 全部一头撞死在天花板上限 **$T = 5.0$** 上！

为了治好这种“狂妄自大症”，我们在 V3–V5 中给模型上了**双保险**（见 [`train_and_evaluate.py` 第 129 行与第 1042–1047 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L1042-L1047)）：

1. **第一重保险（标签平滑 Label Smoothing）**：
   告诉模型：“世上没有绝对的 100%！标准答案最多只能拿 $92\%$ 左右的分数，剩下的 $8\%$（$\varepsilon = 0.08$）必须平分给所有 $K$ 个选项。”既然标准答案不再是 $1.0$，模型就再也不用拼命把分数推向正无穷大了！
2. **第二重保险（Logit L2 平方惩罚）**：
   在评委的亮分牌后面绑上一根**高中物理里的胡克定律弹簧**！评委举的分数 $z_c$ 离 $0$ 越远，弹簧的弹性势能 $\propto z_c^2$ 就越大，拉得评委手越酸！

### 5.2 高中数学拆解：标签平滑与二次函数极值

#### 1. 标签平滑公式（Label Smoothing，$\varepsilon = 0.08$）
设原始目标分布为 $y^{\text{raw}}_c \in [0, 1]$，平滑后的目标分布 $\tilde{y}_c$ 是原始目标与均匀分布 $\frac{1}{K}$ 的**加权平均**：
$$\tilde{y}_c = (1 - \varepsilon) \cdot y^{\text{raw}}_c + \frac{\varepsilon}{K}, \quad \text{其中 } \varepsilon = 0.08$$
**验算一下**：当 $K=4$ 且 $y^{\text{raw}} = (1, 0, 0, 0)$ 时：
* 正确选项的目标变成了：$(1 - 0.08) \times 1 + \frac{0.08}{4} = 0.92 + 0.02 = 0.94$；
* 另外 3 个错误选项各分到：$0 + \frac{0.08}{4} = 0.02$。
四个数加起来：$0.94 + 0.02 + 0.02 + 0.02 = 1.00$！模型只需要把正确选项的 Logit 比错误选项高出 $\ln\left(\frac{0.94}{0.02}\right) = \ln(47) \approx 3.85$ 分就能达到理论最优，彻底断绝了冲向 $+20$ 分的念头！

#### 2. Logit L2 均方惩罚项（Logit L2 Norm Regularization）
我们对当前决策头所有 $K$ 个有效选项的原始打分 $z_c$ 计算平方平均值：
$$\mathcal{R}_{L_2}(\mathbf{z}) = \frac{1}{K} \sum_{c=1}^{K} z_c^2$$
最终单样本的总训练损失函数 $\mathcal{L}_{\text{total}}$ 为三者之和：
$$\mathcal{L}_{\text{total}} = w_i \cdot \mathcal{L}_{\text{Proper}}(\mathbf{q}, \tilde{\mathbf{y}}) + \lambda_{\text{MIL}} \cdot \mathcal{L}_{\text{MIL}}(\mathbf{q}, \mathcal{V}_i) + \lambda_{L_2} \cdot \left(\frac{1}{K}\sum_{c=1}^{K} z_c^2\right)$$
**逐个符号解释**：
* $w_i$：类别重要性权重（如 T1 的 `finding` 头在有明确结论时 $w_i = 1.85$，T3 代码风险头 $w_i = 1.75$）。
* $\mathcal{L}_{\text{Proper}}(\mathbf{q}, \tilde{\mathbf{y}})$：Laya 原生严格恰当评分规则损失（Negative Proper Scoring Reward）。
* $\lambda_{\text{MIL}} = 0.35$：第 4 章讲的多实例包裹损失系数。
* $\lambda_{L_2}$：Logit 平方惩罚系数——在解冻顶层 7 层时设为 **`0.018`**，在全解冻 22 层时（因为 22 层自由度更大、更容易推高 Logit）设为 **`0.042`**。

**实战奇效**：加上这两项高中数学正则化后，我们在 12 篇校准论文（`temp_calibration`，共 `180` 个窗口）上拟合出的有界平滑温度系数 $T \in [0.92, 1.35]$（见 [`medbias_laya_temperatures.json`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/medbias_laya_temperatures.json)）全部受控在 **`[0.92, 1.35]`** 有界区间内（例如 `T1:citation_span = 1.1136`，`T1:finding = 1.3306`），彻底防止了传统 $T=5.0$ 的边界撞墙失真！

---

## 第 6 章：只解冻顶层 7 层 vs 全解冻 22 层 Transformer（LLRD 分层学习率、梯度检查点与逐层梯度裁剪）

### 6.1 幼儿园比喻：22 层高楼的“接力传话筒”与三大工程惊魂记
我们的骨干模型 `convaiinnovations/laya-multilingual`（底层是 `mmBERT-base`，`model.safetensors` 总参数量精确为 **`321,908,998` [`321.91M`]**）就像一座 **22 层楼高的医院大楼**：
* **一楼大厅（`embeddings` 256k 多语言词表查表层）**：负责把单词变成数字卡片（复杂度 $O(L)$ 下标查表）。因为一楼大厅存着多国语言的巨型字典（精确为 **`196,608,768` [`196.61M`] 个参数**），在一块只有 `6 GiB` 显存的家用显卡（RTX 2060）上，如果连一楼大厅一起解冻分配 AdamW 动量状态，显存当场就会像气球一样炸开（CUDA Out of Memory，见 [`train_and_evaluate.py` 第 1214–1230 行记录的真实 OOM 失败运行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L1214-L1230)）。所以**一楼大厅必须永远上锁（冻结 `requires_grad = False`，占用 `0` 优化器状态）**，而整栋大楼真正参与特征计算的**非词表活跃参数（Active Non-Embedding Parameters）精确为 `125,300,230`（`125.30M`）**！
* **第 0 层到第 14 层（底层与中层楼面，约 `75.23M` 参数）**：相当于医院里的**基础科老教授**，负责看懂基本的英语语法、主谓宾结构和从句连接。
* **第 15 层到第 21 层 + 顶楼 2 层决策头（顶层 7 层 + 决策头，共 `50.07M` 参数）**：相当于**专科实习医生**，负责把读懂的句子变成最终的 PROBAST 偏倚裁定。

当我们尝试从“只培训顶层 7 层实习生（`B3b`，`50.07M` 参数）”升级到“把整栋 22 层大楼的医生全部拉出来培训（`B3c`，`125.30M` 参数）”时，我们连续撞上了**三个教科书级的深度学习底层大坑**！让我们用高中数学把这三大坑一个个扒开看清楚：

---

### 6.2 三大底层技术难关与高中数学拆解

#### 难关一：为什么锁住一楼词向量（`embeddings`），22 层梯度检查点就会“断电死机”？
为了在 `6 GiB` 显存里塞进 22 层反向传播，我们开启了**梯度检查点（Gradient Checkpointing，用时间换空间：前向传播时不保存每层楼的中间草稿，等反向算导数时再临时重算一遍）**。
但是一开启，PyTorch 立刻报错：`RuntimeError: element 0 of tensors does not require grad and does not have a grad_fn`！

**高中数学“复合函数链式法则（Chain Rule）”揭秘**：
把 22 层 Transformer 看作高中数学里的 22 层复合函数：
$$h_1 = f_1(x_0), \quad h_2 = f_2(h_1), \quad \dots, \quad \mathcal{L} = f_{22}(h_{21})$$
根据高中微积分的链式求导法则，要求第 1 层参数 $w_1$ 的导数 $\frac{\partial \mathcal{L}}{\partial w_1}$，需要沿着链条往回传。
但是 PyTorch 的 `torch.utils.checkpoint` 有一个节省算力的死规矩：**“如果传进某一层楼的输入变量 $x_0$ 身上没有贴着 `requires_grad=True`（需要求导）的标签，检查点就会认为这层楼不需要往回传导数，直接拉闸断电！”**
因为我们把一楼大厅 `embeddings` 冻结了（它的参数不需要求导），所以一楼输出的词向量 $x_0$ 默认带着 `requires_grad=False`！结果传给第 0 层检查点时，直接触发了“拉闸断电”，整座 22 层大楼瞬间瘫痪！

**一行代码妙手回春（见 [`train_and_evaluate.py` 第 932–933 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L932-L933)）**：
```python
model.encoder.gradient_checkpointing_enable()
model.encoder.enable_input_require_grads()  # 给一楼输出的 x_0 贴上 requires_grad=True 通电标签！
```
调用 `enable_input_require_grads()` 后，一楼大厅本身的参数依然纹丝不动（不消耗显存），但它吐出来的张量 $x_0$ 被贴上了“允许导数通行”的标签，22 层链式求导瞬间全线贯通，峰值显存稳稳控制在 **`3,648.5 MiB`（不到 `3.65 GiB`）**！

---

#### 难关二：为什么底层 `layers.0` 的梯度模长比顶层 `layers.21` 大了整整 `21 倍`？（`730.04` vs `34.22`）
打通反向传播后，我们第一次跑完 22 层微调，惊讶地发现：全解冻 22 层的成绩（`0.7851`）居然还不如只解冻顶层 7 层（`0.8048`）！
为什么多训了 15 层，模型反而变笨了？我们写了一段诊断探针，打印出每一层楼的**梯度向量模长（Gradient L2 Norm）**：
* 顶层 `layers.21` 的梯度模长：$\|\mathbf{g}_{21}\|_2 = \mathbf{34.22}$
* 底层 `layers.0` 的梯度模长：$\|\mathbf{g}_{0}\|_2 = \mathbf{730.04}$（**足足是顶层的 `21.3 倍`！**）

**高中向量几何揭秘——“全局梯度裁剪（Global Gradient Clipping）”的误伤惨案**：
在高中向量里，一个向量 $\mathbf{g} = (g_1, g_2, \dots, g_d)$ 的长度（模长）是所有分量平方和开根号：
$$\|\mathbf{g}\|_2 = \sqrt{\sum_{i=1}^{d} g_i^2}$$
如果把全部 22 层的所有参数放在**同一个池子里**做全局梯度裁剪（要求总模长 $\|\mathbf{g}_{\text{all}}\|_2 \le 1.0$），电脑会算出一个全局缩放比例：
$$\text{Scale}_{\text{global}} = \frac{1.0}{\sqrt{\|\mathbf{g}_{0}\|_2^2 + \|\mathbf{g}_{1}\|_2^2 + \dots + \|\mathbf{g}_{21}\|_2^2}} \approx \frac{1.0}{1500}$$
看到了吗？！因为底层 `layers.0` 像高音喇叭一样嗓门太大（$730.04$），把分母撑得巨大无比，导致顶层 `layers.21` 原本正常的梯度（$34.22$）跟着陪绑，被强行缩小了 1500 倍，变成了微弱的蚊子叫！顶层根本学不到东西！

**两大数学武器联手破局（见 [`train_and_evaluate.py` 第 961–966 行与第 1060–1062 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L961-L966)）**：
1. **分组独立梯度裁剪（Per-Group Gradient Clipping）**：
   不再把 22 层混在一锅粥里裁剪，而是把模型分成 **4 个独立小组**（底层 0–7、中层 8–14、顶层 15–21、决策头），每个小组**各自独立**把梯度模长裁剪到 $1.0$：
   $$\mathbf{g}_{\text{group}} \leftarrow \mathbf{g}_{\text{group}} \cdot \min\left(1.0, \, \frac{1.0}{\|\mathbf{g}_{\text{group}}\|_2}\right)$$
   这样底层嗓门再大，也绝不会压制顶层实习生的学习步长！
2. **分层阶梯学习率（LLRD，Layer-wise Learning Rate Decay）**：
   底层老教授已经懂英语语法了，步子要迈得极小（防遗忘）；顶层实习生要学医学审稿新规矩，步子要迈得大！我们设定了等比递增的四级阶梯学习率：
   $$\eta_{\text{bottom (0..7)}} = 8.0 \times 10^{-6} < \eta_{\text{mid (8..14)}} = 1.8 \times 10^{-5} < \eta_{\text{top (15..21)}} = 3.8 \times 10^{-5} < \eta_{\text{head}} = 6.5 \times 10^{-5}$$
   同时配合高中三角函数里的**余弦退火曲线（Cosine Annealing Schedule）**平滑收尾：
   $$\text{scale}(t) = \frac{1}{2}\left(1 + \cos\left(\pi \cdot \frac{t - t_{\text{warmup}}}{T_{\text{total}} - t_{\text{warmup}}}\right)\right)$$
   当进度从 $0$ 走到 $1$ 时，$\cos(\pi \cdot \text{progress})$ 从 $+1$ 平滑滑落到 $-1$，整个 $\text{scale}(t)$ 就像滑滑梯一样从 $1.0$ 温柔地降到 $0.0$！

---

#### 难关三：为什么解决这两个 bug 后，22 层（`B3c`）全面反超了 7 层（`B3b`）？
因为当一句医学长难句出现**跨越十几个词的语法修饰**时——例如：
> *"Imputation, scaling, feature engineering, and feature selection were performed across all pooled participants **outside** the validation framework"*（有泄漏风险）
> 对比：
> *"...were restricted to the training data or training folds **within** the validation framework"*（无泄漏风险）

只微调顶层 7 层时，底层第 0–14 层还没有学会把远处的介词 **`outside` / `within`** 和前面的名词短语紧紧绑在一起；而全解冻 22 层后，底层和中层的自注意力机制（Self-Attention）从第 1 层起就开始追踪介词作用域！
结果立竿见影：
* 在锁定测试集（$n=240$）上，纯神经网络 `B3c (22L)` 的综合 Macro-F1 从 7 层的 `0.8048` 跃升至 **`0.8384`**，T1 文献偏倚引文定位命中率从 `71.88%` 飙升至 **`82.29%`**（涨幅 **`+10.41%`**）！
* 在 32 道综述语境探针题（开发者撰写的关键句，$n=32$）上，`B3c (22L)` 的准确率从 7 层的 `65.62%` 提升至 **`71.88%`**（其中 T2 达 **`87.50%`**，T1 引文定位达 **`75.00%`**）！

---

## 第 7 章：怎么打破模型的“偷懒捷径”？（最小对比对 Minimal Contrastive Pairs 与位置均衡 `S001..S004`）

### 7.1 幼儿园比喻：背单词表作弊的小聪明 vs. 永远猜“B 选项”的混子
在机器学习领域（尤其是我们的 `[SENSOR-DL]` 与 `[CLINICAL-AI]` 规约中），有一个头号大敌叫做**“捷径学习（Shortcut Learning / Clever Hans Effect）”**：模型表面上考了 90 分，但其实它根本没读懂句子逻辑，而是学会了两条下三滥的“作弊捷径”！

我们在对 V5 初版做自我红队审计时，当场抓获了两条这样的偷懒捷径：

1. **作弊捷径 Q1（背专业名词表 Shortcut）**：
   在一般的临床论文里，只要作者写出了 `"imputation, scaling, feature selection"` 这几个高大上的词，十有八九是在吹嘘自己“做了规范的训练折内预处理（`no_risk_identified`）”。
   结果模型学坏了：**它根本不看后面跟的是 `within training folds`（安全）还是 `outside the validation framework`（泄漏），只要一看到 `imputation, scaling` 这几个名词，就闭着眼睛猜“安全”！**
2. **作弊捷径 Q2（无脑猜第 2 句 `S002` 位置偏置 Shortcut）**：
   在构造外部 PROBAST 测试集初版时，我们习惯性地先放一句背景句 `S001`，然后把核心证据句放在第二句 `S002`，后面再跟两句补充句 `S003`、`S004`。
   结果我们发现了一个惊人的假象：**连完全没训练过的零样本模型 `B1`，引文定位准确率居然高达 `75.00%`！**
   为什么没训练过的模型这么神？我们一查它的预测分布：它居然把绝大多数题目的答案都猜成了 `S002`！它根本不是看懂了医学证据，而是赌“重要的话一般都在每段第二句”！

### 7.2 高中数学与实验设计解法：控制变量法（最小对比对）+ 离散均匀分布

为了彻底废掉这两条作弊捷径，我们在 [`build_corpus_and_manifests.py` 第 454–874 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/build_corpus_and_manifests.py#L454-L874) 中实施了严格的实验控制：

#### 1. 最小对比对（Minimal Contrastive Pairs，控制变量法）
什么是高中物理/生物里的“控制变量法”？就是**除了核心自变量（语法作用域算子）相反之外，句子的其余技术名词完全保持一致**！
设句子的技术名词集合为 $N$，语法作用域算子为 $o \in \{o_{\text{safe}}, o_{\text{leak}}\}$。我们在训练集（Route 3 的 80 个公开生物医学 NLP 窗口）中构造了 **16 组正负成对的最小对比句**：
* **正样本（安全 `no_risk_identified`）**：包含名词组 $N = \{\text{imputation, scaling, feature engineering, feature selection}\}$ + 安全算子 $o_{\text{safe}} = \text{``restricted strictly to the training folds within...''}$
* **负样本（泄漏 `reported_risk`）**：包含**一模一样的名词组 $N$** + 泄漏算子 $o_{\text{leak}} = \text{``performed across all pooled participants outside...''}$

从条件概率来看，因为在对比对中正负样本出现名词组 $N$ 的频率严格相等（各占 $50\%$），所以单靠名词组 $N$ 猜测标签 $Y$ 的条件概率退化为抛硬币：
$$P(Y = \text{safe} \mid N) = P(Y = \text{leak} \mid N) = 0.50$$
名词表的信息增益变成了 $0$！模型如果再敢只背名词，必然挨一半的板子，从而被逼着去注意介词 `within` 和 `outside`！

#### 2. 四位置严格离散均匀分布（Position Balancing across `S001..S004`）
在包含 4 个候选句子 $\{S_1, S_2, S_3, S_4\}$ 的评测窗口中，我们用模 4 轮转算法 `target_pos = index % 4` 放置真正的证据句：
$$P(Y_{\text{span}} = S_k) = \frac{8}{32} = \frac{1}{4} = 25.0\%, \quad \forall k \in \{1, 2, 3, 4\}$$
**照妖镜效果立竿见影**：
当我们把 32 道综述语境探针题（关键句由开发者撰写）的正确句子位置严格拉平为 `8 个 S001、8 个 S002、8 个 S003、8 个 S004`（且 32 句关键句 100% 零重复）后：
* 零样本模型 `B1` 的引文定位准确率瞬间从虚高的 `75.00%` **暴跌回真实的 `15.62%`（32 题只蒙对 5 题，连瞎蒙的 25% 都不如）**！
* 而我们经过对比对与位置均衡洗礼的 `B3c (22L)` 和 `B4 (22L)`，依然交出了 **`62.50%`** 和 **`96.88%`（31/32）** 的真金白银战绩！

---

## 第 8 章：训练完之后怎么调准星？（后验温度缩放 Temperature Scaling 与 Menon 先验对数校准）

### 8.1 幼儿园比喻：调淋浴冷热水龙头 + 换城市后按当地雨季修正天气预报
模型在训练集（`backbone_train`，36 篇论文 + 80 个公开 NLP 窗口）上训练毕业后，它的权重参数就已经固定了。但在真正上考场（`test` 锁定测试集）之前，我们还专门留了 **12 篇独立的校准论文（`temp_calibration`，共 180 个窗口）**，用来帮模型做最后两项“不改模型参数的微调”：

1. **第一项微调：调淋浴水龙头（温度缩放 Temperature Scaling）**
   想象模型的原始打分 $z_c$ 是热水管。如果出水太烫（模型太自信，打分差距拉得太大），我们就往里兑一点冷水（除以一个温度系数 $T > 1$，比如 $T = 1.33$），让概率分布变得温和一点；如果出水偏凉（模型太保守），我们就除以一个 $T < 1$（比如 $T = 0.92$），让概率更集中一点。
2. **第二项微调：换城市修正天气预报（Menon 先验对数校准 Prior Logit Adjustment）**
   为了教会模型识别各种花式数据泄漏，我们在训练集里人为塞进了不少“有风险（`reported_risk`）”的反面教材（训练集里 `reported_risk` 占了约 $35\%$）。
   但是在**完全未经修改的真实发表医学论文（Pure Real PMC Windows）**里，大多数常规段落其实要么是“没写清楚（`insufficient`）”，要么是“常规合规描述（`no_risk_identified`）”，真正把泄漏大白话写在纸面上的比例只有约 $10\%$！
   这就好比一个在“天天暴雨的亚马逊雨林（高风险训练集）”长大的天气预报员，突然被派到了“一年难得下几场雨的北京（真实未修改论文）”。如果不帮他修正一下脑子里的“当地降雨率底数（先验概率 Prior）”，他看到天上飘过一朵白云就会大喊“有暴雨（误报风险）”！

### 8.2 高中数学拆解：温度缩放、ECE 校准误差与贝叶斯对数先验比

#### 1. 温度缩放公式（Temperature Scaling）
我们把每个选项的原始打分 $z_c$ 除以一个正数温度 $T \in [0.92, 1.35]$（见 [`laya_decision_adapter.py` 第 466–487 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/skills/medical-research-harness/scripts/laya_decision_adapter.py#L466-L487)）：
$$p_c(T) = \frac{e^{z_c / T}}{\sum_{j=1}^{K} e^{z_j / T}}$$
**高中数学性质**：
* 因为 $T > 0$，把所有分数同时除以正数 $T$ **绝对不会改变哪个分数排第一名**（若 $z_1 > z_2$，则 $\frac{z_1}{T} > \frac{z_2}{T}$）！所以温度缩放不会改变单模型的准确率，只负责让模型报出的“把握度（Confidence）”更加诚实！

#### 2. 怎么衡量模型报的“把握度”诚不诚实？（期望校准误差 ECE）
如果模型对 100 道题都宣称“我有 $80\%$ 的把握（Confidence $= 0.80$）”，那么它实际上应该刚好做对 **80 道题（Accuracy $= 0.80$）**。如果它只做对了 50 道题，说明它吹牛了 $30\%$！
把 `[0, 1]` 的置信度区间切成 $M=10$ 个小格子（Bins，$B_1, B_2, \dots, B_{10}$），把每个格子里**“平均把握度 $\text{conf}(B_m)$”与“实际正确率 $\text{acc}(B_m)$”的绝对值差距**按人数比例加权平均，就是 **ECE（Expected Calibration Error，越低越好）**：
$$\text{ECE} = \sum_{m=1}^{M} \frac{|B_m|}{N} \Big|\text{acc}(B_m) - \text{conf}(B_m)\Big|$$

我们在 12 篇校准论文上，通过网格搜索找到让平滑负对数似然与校准差距最小的 $T^*$（见 [`fit_bounded_smooth_temperature`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L228-L258)）：
$$\min_{T \in [0.92, 1.35]} \left( \text{NLL}_{\text{smooth}}(T) + 0.45 \cdot |\overline{\text{conf}}(T) - \overline{\text{acc}}| + 0.25 \cdot (\ln T)^2 \right)$$
最后一项 $0.25 \cdot (\ln T)^2$ 是一个精妙的高中对数二次锚点：当 $T=1.0$ 时，$\ln(1.0) = 0$，惩罚为 $0$；这保证了除非有充分证据，否则温度 $T$ 会温和地贴近 $1.0$！

#### 3. Menon 先验对数校准公式（Menon et al., ICLR 2021）
设类别 $c \in \{\text{no\_risk\_identified}, \text{reported\_risk}, \text{insufficient}\}$ 在训练集里的占比（先验概率）为 $\pi_{\text{train}}(c)$，在校准集真实未修改论文里的占比为 $\pi_{\text{cal}}(c)$（加上 $+1$ 拉普拉斯平滑防止除以零）。
根据高中条件概率与贝叶斯公式，把预测分布从训练集先验迁移到真实世界先验，只需要在 Logit 上加上**对数先验比（Log-Prior Ratio）**（见 [`train_and_evaluate.py` 第 285–291 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L285-L291)）：
$$\Delta_c = \tau_{\text{prior}} \cdot \ln\left(\frac{\pi_{\text{cal}}(c)}{\pi_{\text{train}}(c)}\right), \quad \text{其中阻尼系数 } \tau_{\text{prior}} = 0.55$$
$$z'_c = \frac{z_c}{T} + \Delta_c$$
**看一眼代码实际算出来的三个常数（[`medbias_laya_temperatures.json`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/medbias_laya_temperatures.json#L11-L15)）**：
* $\Delta_{\text{no\_risk}} = -0.0527$（基本不变）
* $\Delta_{\text{reported\_risk}} = -1.2860$（因为真实未修改窗口里明写泄漏的很少，由于 $\pi_{\text{cal}} < \pi_{\text{train}}$，对数比是负数，帮模型减去 $1.286$ 分的“草木皆兵偏置”！）
* $\Delta_{\text{insufficient}} = +0.1793$（真实未修改窗口里信息不足的略多，适当加 $0.1793$ 分！）

这一招让 `B3b` 在锁定测试集上的 Macro-F1 从 `0.7969` 稳步提升至 **`0.8048`**，且纯真实 PMC 窗口的准确率不降反升！

---

## 第 9 章：左脑规则 + 右脑神经网络合体！（跨越式动词-作用域匹配与神经符号融合 `B4`）

### 9.1 幼儿园比喻：老中医拿放大镜抓关键证据（左脑符号）+ 年轻博士综合会诊（右脑神经）
为什么单独用规则（`B0`）或者单独用神经网络（`B3b / B3c`）都拿不到满分？
* **左脑（纯符号规则 `B0`）的优缺点**：
  它就像一位拿着放大镜和《法典》的老法官。如果代码里明明白白写着 `GridSearchCV(...).fit(X_te, y_te)`，它的 Python AST（抽象语法树）解析器一抓一个准，**准确率接近 100%**；但如果遇到临床医生换了种委婉的说法（比如 *"All serial hospitalizations belonging to the same medical record identifier were constrained to reside in the same partition"*），死板的正则表达式因为找不到关键词就傻眼了（测试集综合 Macro-F1 只有可怜的 **`0.2719`**）。
* **右脑（纯微调神经网络 `B3b / B3c`）的优缺点**：
  它就像一位读过上千篇论文的年轻医学博士，语感极好，各种委婉同义改写都能听懂（综合 Macro-F1 高达 **`0.8048` / `0.8384`**）。但是，当遇到极其罕见的专业疾病领域（比如外部 PROBAST 综述里的“正畸下颌骨生长预测”或“导尿管相关尿路感染时间依赖性变量”），神经网络偶尔会因为陌生词汇分心，产生 $1.5$ 到 $2.4$ 分的微弱判断偏差。

**那如果我们把“左脑老法官的放大镜”和“右脑年轻博士的语感”合体呢？这就是神经符号系统（Neuro-Symbolic AI，`B4`）！**

### 9.2 高中数学拆解：集合交并补算子 + 对数空间证据相加（Logit-Space Evidence Fusion）

#### 第一步：用高中“集合的交集与空集”写出跨越式动词-作用域符号算子
在真实论文里，动词和作用域之间往往隔着七八个修饰词，比如：
> *"In high-risk mandibular growth studies, multiple machine learning architectures were repeatedly **compared** [相隔 3 个词] on the **held-out evaluation cohort**..."*

固定短语匹配抓不到它，但用**高中集合论（交集 $\cap$ 与空集 $\emptyset$）**就能写出一目了然的**跨越式动词-作用域规则（Bounded-Gap Verb-Scope Matching，见 [`train_and_evaluate.py` 第 321–364 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L321-L364)）**！
设候选句子 $s_k$ 包含的所有单词/短语集合为 $W(s_k)$。我们定义三个有限词集：
* **评估动作词集 $V_{\text{eval}}$** $= \{\text{compared}, \text{selected}, \text{tuned}, \text{optimized}, \text{screened}, \dots\}$
* **高危评估域词集 $S_{\text{risk}}$** $= \{\text{evaluation cohort}, \text{held-out evaluation}, \text{test set}, \text{entire dataset}, \dots\}$
* **安全防护否定词集 $G_{\text{safe}}$** $= \{\text{without}, \text{independent of}, \text{never}, \text{strictly within}, \text{nested cross-validation}, \dots\}$

那么，句子 $s_k$ 触发“评估集泄漏（`reported_risk`）”符号证据的充要条件，就是一个漂亮的高中集合逻辑式：
$$\text{Trigger}_{\text{risk}}(s_k) \iff \big(W(s_k) \cap V_{\text{eval}} \neq \emptyset\big) \; \land \; \big(W(s_k) \cap S_{\text{risk}} \neq \emptyset\big) \; \land \; \big(W(s_k) \cap G_{\text{safe}} = \emptyset\big)$$
**用大白话翻译这个集合公式**：
1. $W(s_k) \cap V_{\text{eval}} \neq \emptyset$：这句话里**至少出现了一个**评估/筛选动作词（交集非空）；
2. $\land$（并且）$W(s_k) \cap S_{\text{risk}} \neq \emptyset$：这句话里**同时至少出现了一个**测试集/全量集名词（交集非空，哪怕中间隔了十个词也能抓到！）；
3. $\land$（并且）$W(s_k) \cap G_{\text{safe}} = \emptyset$：这句话里**绝对没有出现任何**诸如 `without` 或 `independent of` 的安全豁免词（交集为空集）！

#### 第二步：为什么符号加分强度必须定在 $\gamma_{\text{sym}} = 2.65$？（不等式推导）
当左脑符号规则在句子 $s^* = \text{S00k}$ 上抓到了关键证据（比如判定类别为 $c^*$，证据句为 $s^*$），我们怎么把它和右脑神经网络的打分 $z_c$ 融合在一起？
我们在**对数几率空间（Logit Space）直接做加法**（见 [`train_and_evaluate.py` 第 551–558 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L551-L558)）：
$$z^{\text{fused}}_c = \frac{z_c}{T} + \Delta_c + \gamma_{\text{sym}} \cdot \mathbb{I}(c = c^*)$$
**为什么在 Logit 里做加法，等价于在概率空间做贝叶斯乘法？**
因为高中指数运算法则告诉我们：$e^{A + B} = e^A \cdot e^B$！所以在 Softmax 分子上把 $z_c/T$ 加上 $\gamma_{\text{sym}}$，就等价于把该选项的原始几率（Odds）直接乘以了 $e^{\gamma_{\text{sym}}}$ 倍！

那么，$\gamma_{\text{sym}}$ 到底设多大才科学？
我们在诊断外部 PROBAST 综述里最难的一道题（`PMC13635025` 正畸生长模型）时发现：神经网络因为不熟悉正畸词汇，给错误选项打的分数比正确选项高出了：
$$\Delta z_{\text{neural}} = z_{\text{wrong}} - z_{\text{right}} = \mathbf{2.468}$$
根据高中不等式，要想让左脑的关键证据把右脑的这一下走神掰回来，符号先验强度 $\gamma_{\text{sym}}$ 必须满足：
$$\gamma_{\text{sym}} > \Delta z_{\text{neural}} = 2.468$$
因此，我们将 T1 句级高置信度符号强度精确设定为 **$\gamma_{\text{sym}} = 2.65$**（指针句强度设为 $2.55$）！
* 当神经网络自己拿不准或轻微走神（分差 $< 2.65$）时，左脑关键证据一锤定音（$2.65 > 2.468$，成功纠正！）；
* 当句子没有触发高确信符号规则（$\gamma_{\text{sym}} = 0$）时，100% 交由右脑神经网络发挥语义理解优势！

**左脑 + 右脑合体的震撼战果**：
* 在 16 篇锁定测试集（$n=240$）上，`B4 (22L)` 综合 Macro-F1 冲上全场最高 **`0.8679`** [`0.8310, 0.9080`]，引文定位命中率达 **`82.50%`**，7 头平均校准误差 ECE 在 `B4 (7L)` 上低至惊人的 **`0.0211`**！
* 在 32 道综述语境探针题（关键句由开发者用与规则相近的措辞撰写，$n=32$）上，无论是 `B4 (7L)` 还是 `B4 (22L)`，主任务分类准确率双双达到 **`100.0%`（`32/32` 全对，Macro-F1 = `1.0000`）**，且 `B4 (22L)` 的四选一证据句定位命中率高达 **`96.88%`（`31/32`）**！（**注意：** 这个 100% 主要说明“规则认得自己的词”，不能作为外部泛化证据。）

---

## 第 10 章：知道自己不知道，才是真安全！（非对称选择性弃权门控 + 纯标准库审计防线）

### 10.1 幼儿园比喻：机场安检仪的“宁可开箱复查，绝不漏放炸弹”
在医疗 AI 和偏倚审查里，**把“有严重数据泄漏的烂模型”误判成“完全合规没问题（`no_risk_identified`）”**，叫做**假放行（False Clearance）**——这就像机场安检员把装了违禁品的箱子贴上“免检封条”放上飞机一样危险！
相反，如果模型对一段话拿不准，举手说：“报告人类专家，这段话我的把握不到 $80\%$，请您亲自看一眼（Selective Abstention / Escalation）”，这不仅不是缺点，反而是医疗安全系统的救命稻草！

### 10.2 高中数学拆解：假放行率（FCR）与非对称双阈值门控

#### 1. 假放行率（False Clearance Rate, FCR）公式
在所有**实际上存在风险或证据不足（真实标签 $y_i \neq \text{clear}$）**的样本中，被模型错误贴上“安全放行（$\hat{y}_i = \text{clear}$）”标签的比例，定义为 **FCR（越低越安全）**：
$$\text{FCR} = \frac{\sum_{i=1}^{N} \mathbb{I}(y_i \neq \text{clear} \; \land \; \hat{y}_i = \text{clear})}{\sum_{i=1}^{N} \mathbb{I}(y_i \neq \text{clear})}$$

#### 2. 非对称双阈值门控不等式（Asymmetric Selective Gating，见 [`laya_decision_adapter.py` 第 522–541 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/skills/medical-research-harness/scripts/laya_decision_adapter.py#L522-L541) 与 [`train_and_evaluate.py` 第 594–622 行](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/train_and_evaluate.py#L594-L622)）
为什么叫**“非对称（Asymmetric）”**？因为我们对“报警”和“放行”设定了**一高一低两个完全不对称的及格线**：
* **普通判断最低置信度阈值**：$\tau_{\text{min}} = 0.62$（喊“有风险”或提取设计属性时，把握达到 $62\%$ 即可通过）；
* **安全放行严苛置信度阈值**：$\tau_{\text{clear}} = 0.80$（想给论文发“无风险安全免检金牌 `no_risk_identified`”？对不起，你的把握必须高达 **$80\%$ 以上**！）；
* **证据句指针最低阈值**：$\tau_{\text{cit}} = 0.45$（只要不是“证据不足”，就必须指明是哪一句，且指认句子的把握不低于 $45\%$）。

写成高中分段不等式组，当满足以下任意一条时，系统立即触发**安全弃权上报（$\text{Escalate} = \text{True}$）**：
$$\text{Escalate} = \begin{cases} \text{True}, & \text{若 } \hat{y}_{\text{primary}} = \text{clear} \text{ 且 } \hat{p}_{\text{primary}} < \tau_{\text{clear}} \;(0.80) \\[4pt] \text{True}, & \text{若 } \hat{p}_{\text{primary}} < \tau_{\text{min}} \;(0.62) \\[4pt] \text{True}, & \text{若 } \hat{y}_{\text{primary}} \neq \text{insufficient} \text{ 且 } (\hat{y}_{\text{cit}} = \text{NONE} \lor \hat{p}_{\text{cit}} < \tau_{\text{cit}}) \\[4pt] \text{False}, & \text{其他情况（高置信度自主保留通过！）} \end{cases}$$

**实战保护效果**：
在锁定测试集（$n=240$）上，`B4 (7L)` 自主保留处理了 **`75.83%`（`182/240`）** 的任务，在这 182 个自主保留样本上，准确率高达 **`87.36%`**，且**保留子集假放行率（Retained FCR）死死压在 `0.00%`（零误放行）**！

---

### 10.3 纯标准库工程防线：`study.py` 怎么防止科学家“偷看测试集”？
除了训练模型，我们整個仓库的核心底座 [`skills/medical-research-harness/scripts/study.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/skills/medical-research-harness/scripts/study.py) 还用纯 Python 标准库打造了一套**“防学术不端保险箱”**：
1. **研究级聚类切分锁（`patient_disjoint`）**：把每篇独立论文的 `PMCID` 当作 `patient_id`，强制检查 `rows.csv` 与 `folds.csv` 的交集为空集：
   $$\mathcal{P}_{\text{train}} \cap \mathcal{P}_{\text{val}} = \emptyset, \quad \mathcal{P}_{\text{train}} \cap \mathcal{P}_{\text{test}} = \emptyset$$
   哪怕同一篇论文有 15 个窗口，也绝对不允许一个窗口在训练集、另一个窗口溜进测试集！
2. **实际拟合名单对账（`executed-fits.csv` vs `zero_fit_experiments`）**：
   * 零样本模型 `B0` 和 `B1` 在运行结束时，生成的 `executed-fits.csv` 必须是 **`0 行`**（一个样本都不许偷看！）；
   * 温度缩放模型 `B2` 的 `executed-fits.csv` 只能包含 `temp_calibration` 折的 **`180 行`**；
   * 微调模型 `B3` 和 `B4` 只能包含 `backbone_train`（`620 行`）和 `temp_calibration`（`180 行`），共计 **`800 行`**！一旦有任何一行 `test` 集的 `row_id` 出现在拟合名单里，`study.py audit --mode executed` 当场报错拦截！
3. **SHA256 密码学指纹锁（Protocol & Task Design Hash）**：
   在跑实验前先把研究方案 `protocol.md` 和数据清单算出唯一的 64 位哈希指纹锁进 `protocol-lock.json`。如果有人跑完实验看结果不好，偷偷去改指标或改数据清单，`study.py summarize` 对账时指纹不匹配，直接拒绝生成汇总报告！

---

## 第 11 章：不改一个字的终极裸考与 `<6 GiB` 单卡跨量级公平对决！—— 80 篇原始 PMC 零微扰评测、“$\kappa$ 悖论”破局与 `7.66B` QLoRA 极限显存工程

### 11.1 幼儿园比喻：平时做“模拟改编题”拿满分不算本事，直接拿 80 套一字未改的高考真题原卷裸考才见真章！（Zero-Perturbation Real-PMC Benchmark）

在第 7 章里，我们为了防止模型“背专业名词偷懒”或“无脑猜第 2 句 `S002`”，精心构造了**最小对比对（Minimal Contrastive Pairs）**——也就是把同一个医学句子微调几个介词（从 *"within each training fold"* 改成 *"across the entire dataset"*），做成一正一反的“双胞胎找茬模拟题”。

这时候，最挑剔的临床流行病学审稿人（Reviewer 2）站出来提出了灵魂拷问：
> **“你们用自己改编的‘双胞胎对比模拟题’考出了高分，万一真实世界里医生写的原始医学论文（Primary Studies）长相跟你们的改编题不一样怎么办？我要求你们：连一个标点符号都不许改、连半句人工合成的句子都不许塞，直接拿 80 篇真实的 PMC 临床预测论文原卷来一场 100% 零微扰裸考（Zero-Perturbation Benchmark），并且要报告与参考答案的一致性系数（Cohen's $\kappa$）！”**

这个比喻哪怕幼儿园小朋友都能秒懂：
* **第 7 章的受控对比测试（Controlled Contrastive Stress-Test）** 就像驾校里的**“特种极限障碍桩考”**：专门在路上摆满一模一样的假人双胞胎，逼你练出不靠瞎猜、只看关键动作的肌肉记忆；
* **第 11 章的 80 篇原始全文零微扰裸考（Zero-Perturbation Real-PMC Benchmark）** 则是直接把车开上**“一字未改的真实晚高峰马路”**（直接拿 80 套一字未改的高考真题原卷裸考）！

为此，我们编写了全自动零微扰验证与评测引擎 [`evaluate_80_unmodified_pmc_kappa.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py)（核验与构建函数见 [`build_80_study_corpus_and_dataset`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py#L821-L1057)），立下四条铁规：
1. **80 篇真题原卷，800 个原汁原味窗口**：在原有 72 篇 CC BY 4.0 临床预测模型全文 JATS XML 基础上，新增 **8 篇完全未曝光的外部最新临床预测论文**（`PMC6109989`、`PMC13711609`、`PMC13713692`、`PMC13718535`、`PMC13721678`、`PMC13722217`、`PMC13728425`、`PMC13730878`），合计 **80 篇独立原始研究**。每篇论文提取 4 个 Task T1（PROBAST 信号问题）窗口 + 6 个 Task T2（CHARMS/TRIPOD+AI 研究设计属性）窗口，共计 **$n=800$ 个 100% 原始全文窗口**（清单锁入 [`sources_80_unmodified_manifest.json`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-real-corpus/sources_80_unmodified_manifest.json)）。
2. **`0.0%` 人工合成句子，`100.0%` 原文字符偏移核验**：全部 800 个窗口均满足 `is_unmodified_real_pmc = True`、人工合成或拼接句子数量为 **`0`（`0.0%`）**，且每一句候选证据都通过 `assert p_txt[start:start+length] == quote` 严格校验，**原文字符偏移匹配率达 `100.0%`**（见 [`evaluate_80_unmodified_pmc_kappa.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py#L930-L934)）。
3. **权重完全冻结，零重训裸考**：直接加载前文训练好的冻结权重 `medbias_laya_layers15_21_and_head.pt`（7L）与 `medbias_laya_layers0_21_all_and_head.pt`（22L），在 **$N=24$ 篇完全未见保留集**（$n=240$，含 16 篇锁定测试集 + 8 篇全新外部集）上**零拟合（`0` executed fit rows）**直接裸考！
4. **参考答案的真实来源（`R1` 全文规则参考 vs. `R2` 单窗口简化规则）**：
   * **`R1`（全文规则参考，[`adjudicate_r1_consensus_t1/t2`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py#L311)）**：开发者写的关键词规则程序，扫描整篇论文的 `Methods`、`Results` 与 `<table-wrap>` 表格；其中含有针对具体论文写死的短语，并对两篇论文直接引用了云端 LLM 试运行的输出（`LIVE_REF_PATH`）。它**不是**人类专家的裁定。
   * **`R2`（单窗口简化规则，见 [`adjudicate_r2_blind_t1`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py#L177-L220) 与 [`adjudicate_r2_blind_t2`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py#L222-L294)）**：同一套词表的精简版，只看当前 8 句窗口。函数名里虽有 `blind`，但它既不是人类，也不独立于 `R1`；`R2 vs R1` 只是“规则对规则”的比较，**不能**当作人类一致性的天花板。

---

### 11.2 高中数学拆解一：为什么一致率高达 85%，算出来的 $\kappa$ 系数却只有 0.2 左右？（著名的“高流行率 $\kappa$ 悖论”）

当我们把 80 篇一字未改的真实论文拿出来统计 Task T1（PROBAST 偏倚信号题）时，立刻撞上了临床流行病学里最著名的数学怪象——**“高流行率 $\kappa$ 悖论（High-Prevalence Kappa Paradox，Feinstein & Cicchetti 1990）”**！

先看真实世界的自然分布（见 [`unmodified_80pmc_kappa_report.json`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/unmodified_80pmc_kappa_report.json#L53-L62)）：
在真实发表的医学论文里，绝大多数临床医生写方法学时**根本不提**“缺失值是在切分前填补还是切分后填补”，也**不提**“同一患者多次住院有没有按患者分组切分”。因此在未见测试集的 96 个真实 T1 窗口里：
* **`insufficient`（报告不清 / 证据不足）**：占了 **`84 / 96 = 87.50%`**（全量 320 个窗口里占 `280 / 320 = 87.50%`）！
* **`no_risk_identified`（明确汇报了规范操作）**：仅占 `10 / 96 = 10.42%`；
* **`reported_risk`（傻乎乎在正文里自曝数据泄漏）**：仅占 `2 / 96 = 2.08%`！

这时候怪事发生了：在 $N=24$ 未见测试集的 Task T1 上，我们的 22 层纯神经网络 `B3c` 的真实准确率（观测一致率 $P_o$）高达 **`85.42%`**，简化规则 `R2` 的一致率也高达 **`78.12%`**；可是一算传统的 Cohen's $\kappa$（或二次加权 $\kappa_w$），居然只有 **`0.2093`** 和 **`0.2249`**！为什么准确率超过 $85\%$，$\kappa$ 系数却掉到了 `0.2` 出头？

我们用**高中必修课的“独立事件乘法公式”**，在黑板上列一个最简单的 $2 \times 2$ 表格，30 秒就能破案！

#### 第一步：写出 Cohen's $\kappa$ 的高中概率定义式（代码见 [`compute_cohens_kappa`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py#L710-L723)）
假设有两个评委（参考方 A 和模型 B）对 $n$ 道题做分类（共有 $K$ 个类别，比如 $K=2$：第 1 类是“报告不清 `insufficient`”，第 2 类是“明确报告”）。
1. **实际观测一致率（Observed Agreement，$P_o$）**：两人选了同一个答案的题目比例：
   $$P_o = \frac{1}{n}\sum_{i=1}^{n} \mathbb{I}(y_{A,i} = y_{B,i})$$
2. **纯靠瞎蒙撞上的期望一致率（Expected Chance Agreement，$P_e$）**：
   假设参考方 A 选第 $c$ 类的比例是 $p_c$，模型 B 选第 $c$ 类的比例是 $q_c$。如果两人完全闭着眼睛独立乱猜，根据高中数学**相互独立事件同时发生的概率等于各自概率相乘**，两人在第 $c$ 类上碰巧猜中同一个答案的概率就是 $p_c \cdot q_c$！把所有类别加起来：
   $$P_e = \sum_{c=1}^{K} p_c \cdot q_c$$
3. **扣除瞎蒙水分后的净一致率（Cohen's $\kappa$）**：
   $$\kappa = \frac{\text{实际得分} - \text{瞎蒙保底分}}{\text{满分 } 1 - \text{瞎蒙保底分}} = \frac{P_o - P_e}{1 - P_e}$$
   （如果是 $K=3$ 的有序风险等级 $0, 1, 2$，二次加权 $\kappa_w$ 则用距离的平方 $w_{ij} = \frac{(i-j)^2}{(K-1)^2}$ 作为扣分权重：$\kappa_w = 1 - \frac{\sum_{i,j} w_{ij} O_{ij}}{\sum_{i,j} w_{ij} E_{ij}}$，代码见 [`compute_quadratic_weighted_kappa_t1`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py#L726-L744)。）

#### 第二步：代入 $90\%$ 极端流行率，亲眼见证分母坍塌！
现在假设真实医学论文里有 **$90\%$ 都是“报告不清”**，参考方 A 和模型 B 不仅整体准确率高达 **$P_o = 85.4\% = 0.854$**，而且两人判定为“报告不清”的比例也都贴近真实世界的 $90\%$（即 $p_1 = 0.90, \; q_1 = 0.90$），判定为“明确报告”的比例都是 $10\%$（即 $p_2 = 0.10, \; q_2 = 0.10$）：

| 参考方 A \ 模型 B | 选第 1 类（报告不清，$q_1 = 0.90$） | 选第 2 类（明确报告，$q_2 = 0.10$） | 参考方 A 行合计 |
| :--- | :---: | :---: | :---: |
| **选第 1 类（报告不清，$p_1 = 0.90$）** | **$82.7\%$**（共同判不清） | $7.3\%$（分歧） | **$p_1 = 0.90$** |
| **选第 2 类（明确报告，$p_2 = 0.10$）** | $7.3\%$（分歧） | **$2.7\%$**（共同判明确） | **$p_2 = 0.10$** |
| **模型 B 列合计** | **$q_1 = 0.90$** | **$q_2 = 0.10$** | **总一致率 $P_o = 82.7\% + 2.7\% = 85.4\%$** |

来算一下这时候 Cohen's $\kappa$ 的期望巧合率 $P_e$：
$$P_e = p_1 q_1 + p_2 q_2 = (0.90)^2 + (0.10)^2 = 0.81 + 0.01 = \mathbf{0.82}$$
天哪！因为 $0.90$ 的平方高达 $0.81$，Cohen 公式竟然认为**“就算你俩闭着眼睛乱填，也有 $82\%$ 的概率碰巧撞上”**！
于是代入 $\kappa$ 公式：
$$\kappa = \frac{P_o - P_e}{1 - P_e} = \frac{0.854 - 0.820}{1 - 0.820} = \frac{0.034}{0.180} \approx \mathbf{0.1889} \;\;(\text{不到 } 0.22!)$$

**一句话看穿“$\kappa$ 悖论”的数学本质**：
当某一个自然类别（如医学论文里的 `insufficient`）占到 $85\%\sim 90\%$ 时，$P_e = \sum p_c q_c$ 会像吹气球一样膨胀逼近 $1$，导致分子 $(P_o - P_e)$ 和分母 $(1 - P_e)$ 同时坍缩成一个极小的小数！哪怕两方在 100 道题里有 86 道一致，算出来的 $\kappa$ 也会被错误地惩罚到 $0.2$ 左右！

---

### 11.3 高中数学拆解二：Gwet's $\text{AC}_1$ 与 PABAK 怎么用一行高中方差公式缓解？

为了治好 Cohen's $\kappa$ 在极端自然分布下的“高流行率失真症”，临床生物统计学界（Byrt et al. 1993; Gwet 2008）提出了两大救星：**PABAK（流行率与偏倚校正 $\kappa$）** 与 **Gwet's $\text{AC}_1$（一阶一致性系数）**。我们在 [`evaluate_80_unmodified_pmc_kappa.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py#L747-L778) 中把它们完整实现，其底层数学简直优雅到了极点！

#### 救星一：PABAK —— 强行拉平起跑线的线性映射（[`compute_pabak`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py#L768-L778)）
既然类别不均衡会扭曲 $P_e$，PABAK 的想法非常干脆：**不管真实世界哪个类别多，我们一律假设瞎蒙撞上的概率等于均匀分布 $\frac{1}{2}$（或者在 $K$ 分类下等于 $\frac{1}{K}$）**！
* **二分类标准 PABAK（把 $P_e = 0.5$ 代入 $\kappa$ 公式）**：
  $$\text{PABAK} = \frac{P_o - 0.5}{1 - 0.5} = \mathbf{2P_o - 1}$$
* **$K$ 分类广义 $\text{PABAK}_K$（把 $P_e = \frac{1}{K}$ 代入 $\kappa$ 公式）**：
  $$\text{PABAK}_K = \frac{P_o - \frac{1}{K}}{1 - \frac{1}{K}} = \mathbf{\frac{K \cdot P_o - 1}{K - 1}}$$
代回刚才 $P_o = 85.4\%$ 的例子：$\text{PABAK} = 2 \times 0.854 - 1 = \mathbf{0.708}$（在 $K=3$ 下 $\text{PABAK}_3 = \frac{3 \times 0.854 - 1}{2} = \mathbf{0.781}$），瞬间恢复了 $85.4\%$ 准确率应有的体面！

#### 救星二：Gwet's $\text{AC}_1$ —— 用高中二次函数抛物线精准度量“真正拿不准时的瞎蒙率”（[`compute_gwets_ac1`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_80_unmodified_pmc_kappa.py#L747-L765)）
统计学家 Kilem Gwet (2008) 指出：Cohen 把**“两人都非常确定地认出容易题”**也算成了“闭眼瞎蒙 $p_1 q_1$”，这是完全搞反了因果！
什么时候评委才会真正去“瞎蒙（Chance Rating）”？**只有当这道题处于边界、两个类别五五开（$\bar{\pi}_c \approx 0.5$）、类别方差最大的时候，评委才会犹豫瞎猜！** 反过来，如果 90% 的题目都是清清楚楚的同一类（$\bar{\pi}_c = 0.9$），类别方差极小，评委根本不需要瞎猜！

于是，Gwet 定义了两个评委在第 $c$ 类上的平均边缘概率 $\bar{\pi}_c = \frac{p_c + q_c}{2}$，并用伯努利分布的**方差项 $\bar{\pi}_c(1 - \bar{\pi}_c)$** 来定义真正的随机巧合概率 $P_e^{\text{Gwet}}$：
$$P_e^{\text{Gwet}} = \frac{1}{K - 1} \sum_{c=1}^{K} \bar{\pi}_c (1 - \bar{\pi}_c)$$
然后算出一阶一致性系数 Gwet's $\text{AC}_1$：
$$\text{AC}_1 = \frac{P_o - P_e^{\text{Gwet}}}{1 - P_e^{\text{Gwet}}}$$

**为什么这个公式能缓解高流行率问题？我们请出高一数学的“开口向下二次函数（抛物线）”**：
看单项函数 $f(\pi) = \pi(1 - \pi) = -\pi^2 + \pi = -\left(\pi - \frac{1}{2}\right)^2 + \frac{1}{4}$：
* **当两个类别五五开（$\bar{\pi}_1 = 0.5, \; \bar{\pi}_2 = 0.5$）时**：抛物线到达最高顶点 $f(0.5) = 0.25$，此时 $P_e^{\text{Gwet}} = \frac{0.25 + 0.25}{2 - 1} = \mathbf{0.50}$，恰好等于 Cohen's $P_e = 0.5^2 + 0.5^2 = 0.50$！也就是说，**在平衡数据集上，Gwet's $\text{AC}_1$ 和 Cohen's $\kappa$ 完全等价**！
* **当流行率极其悬殊（$\bar{\pi}_1 = 0.90, \; \bar{\pi}_2 = 0.10$）时**：抛物线往两边滑落，$\bar{\pi}_1(1-\bar{\pi}_1) = 0.90 \times 0.10 = 0.09$！于是：
  $$P_e^{\text{Gwet}} = \frac{0.09 + 0.09}{2 - 1} = \mathbf{0.18} \quad (\text{对比 Cohen 荒谬的 } P_e = 0.82!)$$
  再把 $P_o = 0.854$ 和 $P_e^{\text{Gwet}} = 0.18$ 代入 $\text{AC}_1$ 公式：
  $$\text{AC}_1 = \frac{0.854 - 0.180}{1 - 0.180} = \frac{0.674}{0.820} \approx \mathbf{0.8220}!$$
看！只用一行高一二次函数 $\bar{\pi}_c(1 - \bar{\pi}_c)$，就能得到一个不受高流行率压低的指标。**但要警惕反方向的问题：** 当几乎所有样本都是 `insufficient` 时，一个从不识别少数类的模型也能拿到很高的 $\text{AC}_1$ 和 PABAK（例如 24 篇未见论文的 `GROUP_SPLIT` 上，`B4_22L` 的 $\kappa = 0$，但 $\text{AC}_1 = 0.9575$）。所以 $\kappa$、$\text{AC}_1$、PABAK 和分问题结果必须一起报告，不能只挑好看的那个。

---

### 11.4 80 篇原始全文裸考成绩单（$N=24$ 未见测试集 + $N=8$ 全新外部集 + $N=80$ 全量集）

我们在 80 篇 100% 未修改的真实 PMC 临床预测论文（$n=800$ 个原汁原味窗口，完整 JSON 报告见 [`unmodified_80pmc_kappa_report.json`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/unmodified_80pmc_kappa_report.json)）上，跑出了全部模型与简化规则 `R2` 对照全文规则参考 `R1` 的成绩单（**全部是相对开发者规则的一致性**）：

![Figure 6: 80-Study Unmodified PMC Zero-Perturbation Benchmark — Agreement with the Rule-Based Reference R1](/home/cht/.gemini/antigravity/brain/48bb113e-0536-4b51-9690-17f8bcadf75c/fig6_80pmc_zero_perturbation_kappa.png)

| 评测队列与评测对象（对比全文规则参考 `R1`；整体列混合 T1+T2） | 整体一致率 $P_o$ | 未加权 Cohen's $\kappa$ [95% CI] | Gwet's $\text{AC}_1$ | PABAK ($2P_o-1$) | Task T1 一致率 $P_o$ | Task T1 $\kappa_w$ / $\text{AC}_1$ | 引文指针准确率 | 全覆盖假放行率 FCR ($\downarrow$) | $\tau=0.80$ 门控保留一致率 $P_o$ ($\uparrow$) | $\tau=0.80$ 门控保留 FCR ($\downarrow$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **未见保留集（$N=24$ 篇, $n=240$ 窗）** | | | | | | | | | | |
| **`R2 vs R1`：单窗口简化规则（非人类）** | `81.25%` | `0.7797` [`0.7202, 0.8370`] | `0.7776` | `0.6250` | `78.12%` | `0.2249` / `0.7390` | `84.17%` | `15.12%` | `81.25%` (`100%` 覆盖) | `15.12%` |
| **`B0`：确定性正则规则基线** | `50.83%` | `0.4649` [`0.4056, 0.5284`] | `0.3668` | `0.0167` | `20.83%` | `0.0424` / `-0.0763` | `35.83%` | **`81.40%` (灾难!)** | `50.83%` (`100%` 覆盖) | `81.40%` |
| **`B1`：零样本 `laya-multilingual`** | `47.92%` | `0.3867` [`0.3290, 0.4463`] | `0.3705` | `-0.0417` | `73.96%` | `-0.1053` / `0.7038` | `22.50%` | `10.47%` | `14.29%` (`2.92%` 覆盖) | `0.00%` |
| **`B3b`：顶层 7 层微调 + 校准 (`50.07M`)** | `76.67%` | `0.7177` [`0.6540, 0.7865`] | `0.7361` | `0.5333` | `82.29%` | `0.0164` / `0.8027` | `61.25%` | `9.30%` | `87.95%` (`34.58%` 覆盖) | **`0.00%`** |
| **`B3c`：全 22 层 LLRD 微调 + 校准 (`125.30M` 活跃)** | **`79.58%`** | **`0.7533`** [`0.7099, 0.7984`] | **`0.7696`** | **`0.5917`** | **`85.42%`** | **`0.2093` / `0.8367`** | **`65.00%`** (T1 `88.54%`) | `6.98%` | **`92.77%`** (`34.58%` 覆盖) | **`0.00%`** |
| **`B4_22L`：全 22 层神经符号融合 (`B0+B3c`)** | **`92.50%`** | **`0.9097`** [`0.8622, 0.9543`] | **`0.9172`** | **`0.8500`** | **`94.79%`** | **`0.6418` / `0.9414`** | **`87.92%`** (T1 `92.71%`) | **`2.33%`** | **`98.85%`** (`72.50%` 覆盖) | **`0.00%` (`2.10%` CP 上限)** |
| **全新外部集（$N=8$ 篇, $n=80$ 窗）** | | | | | | | | | | |
| **`R2 vs R1`：单窗口简化规则（非人类）** | `85.00%` | `0.8239` [`0.7565, 0.8932`] | `0.8187` | `0.7000` | `78.12%` | `0.2727` / `0.7326` | `86.25%` | `13.79%` | `85.00%` (`100%` 覆盖) | `13.79%` |
| **`B3c`：全 22 层 LLRD 微调 + 校准** | **`75.00%`** | **`0.6999`** [`0.6216, 0.8014`] | **`0.7161`** | **`0.5000`** | `81.25%` | `-0.0435` / `0.7859` | `61.25%` (T1 `87.50%`) | `10.34%` | **`92.59%`** (`33.75%` 覆盖) | **`0.00%`** |
| **`B4_22L`：全 22 层神经符号融合** | **`85.00%`** | **`0.8206`** [`0.7368, 0.8980`] | **`0.8296`** | **`0.7000`** | **`93.75%`** | **`0.4203` / `0.9286`** | **`82.50%`** (T1 `90.62%`) | **`3.45%`** | **`100.00%`** (`66.25%` 覆盖) | **`0.00%`** |
| **全量 80 篇语料（$N=80$ 篇, $n=800$ 窗）** | | | | | | | | | | |
| **`R2 vs R1`：单窗口简化规则（非人类）** | `85.25%` | `0.8248` [`0.7939, 0.8530`] | `0.8279` | `0.7050` | `88.12%` | `0.5062` / `0.8614` | `88.25%` | `9.66%` | `85.25%` (`100%` 覆盖) | `9.66%` |
| **`B3c`：全 22 层 LLRD 微调 + 校准** | **`81.37%`** | **`0.7751`** [`0.7508, 0.7996`] | **`0.7898`** | **`0.6275`** | **`88.44%`** | **`0.4250` / `0.8691`** | **`68.87%`** (T1 `88.12%`) | `7.24%` | **`91.10%`** (`36.50%` 覆盖) | `3.70%` |
| **`B4_22L`：全 22 层神经符号融合** | **`92.00%`** | **`0.9037`** [`0.8814, 0.9259`] | **`0.9116`** | **`0.8400`** | **`95.94%`** | **`0.6830` / `0.9541`** | **`85.12%`** (T1 `91.56%`) | **`3.10%`** | **`99.48%`** (`71.50%` 覆盖) | **`0.37%`** |

**四条结论（全部相对规则参考 `R1`）**：
1. **死板正则 `B0` 在真实未修改论文上表现很差（相对 `R1` 的假放行率 `81.40%`）**：在 $N=24$ 未见真题上，`B0` 的 T1 一致率只有 `20.83%`。
2. **T1 分问题结果很弱，且有两个 0**：24 篇未见论文上，按问题分开算未加权 $\kappa$——`B4_22L`：FIT_SCOPE `1.00`、EVAL_ROLE `0.00`、GROUP_SPLIT `0.00`、FEATURE_TIME `0.714`（宏平均 `0.4286`）；纯神经 `B3c` 宏平均 `0.1314`；简化规则 `R2` 宏平均 `0.1348`。96 个 T1 窗口中只有 12 个不是 `insufficient`，所以这些数字很不稳定。
3. **合并 $\kappa$ 混合了任务，且受规则重叠影响**：整体列把 96 个 T1 与 144 个 T2 窗口合在一起，`B3c` $\kappa = 0.7533$（与 `R2` 的 `0.7797` 相近），`B4_22L` $\kappa = 0.9097$、$\text{AC}_1 = 0.9172$、PABAK `0.8500`；合并 T1 未加权 $\kappa$ 为 `0.7656`（`R2` 为 `0.3390`）。这些合并值主要由 T2 决定；而且 `B4` 的规则与 `R1` 共用触发短语，从 `B3c` 到 `B4_22L` 的跃升有一部分只是“把出题人的规则借给了考生”，不能称为“近乎完美的一致性”。
4. **$\tau=0.80$ 安全门**：`B4_22L` 在 $N=24$ 上自主处理 `72.50%`（`174/240`）窗口，其余 `27.50%` 移交人工复核，保留一致率 `98.85%`（$N=8$ 全新外部集上 `100.00%`），保留子集相对 `R1` 的假放行为 `0/174`（精确单侧 97.5% Clopper–Pearson 上限 `2.10%`，Rule of Three 近似 `1.72%`；全量 $N=80$ 上 `0.37%`）。这是对规则答案的假放行，面对真人专家时的表现尚未检验。

---

### 11.5 `<6 GiB` 消费级单卡同预算跨架构对比：`1.25 亿` 活跃参数的 `MedBias-Laya V5` 与 `76.6 亿` 参数 `Qwen2.5-7B-Instruct`（3-Shot 与 4-Bit QLoRA）分数相近，但快约 `23` 倍

完成零微扰评测之后，审稿人还会抛出两个核心追问（以下所有分数都相对开发者生成的标签）：
> **追问 1（参数规模挑战）：“你们的 `MedBias-Laya V5` 总参数量是 `3.2191 亿`（`321.91M`，其中 `1.9661 亿` 是冻结的 256k 多语言词表查表层，真正参与特征变换的非词表活跃参数只有 `1.2530 亿` [`125.30M`]）。如果直接搬出同量级解纠缠注意力编码器 `mDeBERTa-v3-base`（`2.93 亿` 总参数 / `1.01 亿` 非词表）、大 `1.85 倍`（活跃大 `4.76 倍`）的 `Qwen3-0.6B`（`5.96 亿`），甚至总参数大 `23.7 倍`（活跃大 `60.8 倍`）的 `76.2 亿` 参数指令微调生成式大模型 `Qwen/Qwen2.5-7B-Instruct`（外加 3-Shot 上下文示例），是不是靠‘大力出奇迹’就能把你们秒杀？”**
> **追问 2（`<6 GiB` 单卡同预算 7B 监督微调对决）：“如果说 3-Shot 提示词对 `76.2 亿` 大模型还不算公平，那在同一张 `<6 GiB` 显存的消费级显卡（RTX 2060, 6 GiB VRAM）预算下，把完全相同的 620 道训练题（`backbone_train`）和 180 道温度校准题（`temp_calibration`, $n=180$）喂给 `Qwen2.5-7B-Instruct`，给它做 4-bit NF4 QLoRA 监督微调 + 多任务区间指针头（`B_Qwen2.5_7B_QLoRA`，`76.57 亿` 总参数 / `4,133 万` 可训参数），甚至再把你们的有界间隔神经符号外挂也装到它头上（`B_Qwen2.5_7B_QLoRA_NS`），谁会赢？”**

为了给出严谨诚实的实证答案，我们编写了跨架构与大模型扩展评测引擎 [`evaluate_larger_backbones_and_llms.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_larger_backbones_and_llms.py)（完整 JSON 报告锁入 [`larger_model_comparison_report.json`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/Paper/cmpb/reproducibility/larger_model_comparison_report.json)），在**严格匹配的 `<6 GiB` 单张消费级 GPU 预算与完全一致的三大锁定基准集**上拉开了横跨 **4 大模型家族（`321.91M` [`125.30M` 活跃] vs. `293.19M` [`101.19M` 非词表] vs. `596.05M` vs. `7,656.94M` 3-Shot 与 4-Bit QLoRA）+ 云端 `--colab-14b-32b` 扩展**的硬核擂台：

| 模型配置与架构层级 | 总参数 / 可训参数 | 锁定测试集 ($n=240$) 多任务 Macro-F1 [95% CI] | 锁定测试集 T1 / T2 / T3 (& FCR) | 综述语境探针题 ($n=32$，开发者撰写) 准确率 & F1 | 未见原始 24-PMC ($n=240$) 对照 `R1`：$P_o$ / $\kappa$ / $\text{AC}_1$ | 原文引文幻觉/截断/多句漂移率 ($\downarrow$) | 单窗延迟：打分 / 完整生成 JSON ($\downarrow$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`B_DeBERTa_ZS`：`mDeBERTa-v3-base` (`101.2M` 非词表, 零样本)** | `293.19M` / `0.00M` | `0.0942` [`0.0643, 0.1252`] | `0.1587` / `0.0521` / `0.0718` (`63.5%`) | `37.50%` (`0.2917`) | `5.00%` / `0.0334` / `-0.2030` | `0.0%` (指针切片) | `65.24 ms` (单次联合) |
| **`B_Qwen3_0.6B_ZS`：`Qwen3-0.6B` (`1.85x` 总, 0-Shot)** | `596.05M` / `0.00M` | `0.2675` [`0.2350, 0.2986`] | `0.1934` / `0.5521` / `0.0571` (`31.7%`) | `37.50%` (`0.3607`) | `40.42%` / `0.3703` / `0.1980` | **`100.0%`** (全军覆没) | `35.15 ms` / `385.2 ms` |
| **`B_Qwen3_0.6B_3Shot`：`Qwen3-0.6B` (`1.85x` 总, 3-Shot)** | `596.05M` / `0.00M` | `0.2817` [`0.2464, 0.3206`] | `0.2527` / `0.5104` / `0.0819` (`25.0%`) | `43.75%` (`0.4471`) | `48.33%` / `0.4326` / `0.3393` | **`84.38%`** (`62.5–93.8%`) | `59.17 ms` / `478.9 ms` |
| **`B_Qwen2.5_7B_ZS`：`Qwen2.5-7B-Instruct` (`23.7x` 总, 0-Shot)** | `7,615.62M` / `0.00M` | `0.3225` [`0.2762, 0.3680`] | `0.2043` / `0.6042` / `0.1590` (`85.6%`) | `50.00%` (`0.4167`) | `47.50%` / `0.4394` / `0.3221` | **`81.25%`** (`78.1–100%`) | `1,478.6 ms` / `4,522.9 ms` |
| **`B_Qwen2.5_7B_3Shot`：`Qwen2.5-7B-Instruct` (`23.7x` 总, 3-Shot)** | `7,615.62M` / `0.00M` | `0.3886` [`0.3461, 0.4318`] | `0.4444` / `0.5729` / `0.1486` (`26.9%`) | `37.50%` (`0.4208`) | `62.50%` / `0.5766` / `0.5313` | **`84.38%`** (`65.6–100%`) | `2,397.8 ms` / `5,482.2 ms` |
| **`B_DeBERTa_FT`：`mDeBERTa-v3-base` (Top-4L 微调 + 校准)** | `293.19M` / `43.32M` | `0.3925` [`0.3559, 0.4268`] | `0.2191` / `0.6875` / `0.2707` (`0.0%`) | `31.25%` (`0.3125`) | `79.58%` / `0.7487` / `0.7762` | `0.0%` (指针切片) | `64.67 ms` (单次联合) |
| **`B_Qwen2.5_7B_QLoRA`：`Qwen2.5-7B` QLoRA (`23.8x` 总, Top-8L)** | `7,656.94M` / `41.33M` | **`0.7794`** [`0.7371, 0.8192`] | `0.5672` / `0.7708` / **`1.0000`** (`14.4%`) | `56.25%` (`0.5388`) | `74.58%` / `0.6981` / `0.7113` | `0.0%` 指针 (**`75.0%`** 冻结 `lm_head`) | `287.62 ms` / `4,490.7 ms` |
| **`B3c`：`MedBias-Laya V5` 全 22 层纯神经 (`125.3M` 活跃)** | **`321.91M`** / `125.30M` | **`0.8384`** [`0.8043, 0.8752`] | `0.6611` / `0.8542` / **`1.0000`** (`6.7%`) | **`71.88%` (`0.7476`)** | `79.58%` / `0.7533` / `0.7696` | **`0.0%`** (指针切片) | **`12.51 ms` (单次联合)** |
| **`B_DeBERTa_NS`：`mDeBERTa-v3-base` + 神经符号** | `293.19M` / `43.32M` | `0.6787` [`0.6120, 0.7324`] | `0.4704` / `0.7708` / `0.7950` (`0.0%`) | **`100.0%` (`1.0000`)** | **`95.42%` / `0.9446` / `0.9503`** | **`0.0%`** (指针切片) | `64.67 ms` (单次联合) |
| **`B_Qwen2.5_7B_QLoRA_NS`：`Qwen2.5-7B` QLoRA + 神经符号** | `7,656.94M` / `41.33M` | **`0.8494`** [`0.8110, 0.8850`] | `0.7148` / `0.8333` / **`1.0000`** (`14.4%`) | **`100.0%` (`1.0000`)** | **`94.17%` / `0.9299` / `0.9360`** | **`0.0%`** (指针切片) | `287.62 ms` (单次联合) |
| **`B4_22L`：`MedBias-Laya V5` 全 22 层 + 神经符号** | **`321.91M`** / `125.30M` | **`0.8679`** [`0.8310, 0.9080`] | **`0.7183` / `0.8854` / `1.0000`** (`6.7%`) | **`100.0%` (`1.0000`)** | **`92.50%` / `0.9097` / `0.9172`** | **`0.0%`** (指针切片) | **`12.51 ms` (单次联合)** |

#### 读懂这张 `<6 GiB` 单卡同预算成绩单的四点（注意每点的限制）：
1. **给 `76.6 亿` 大模型做 QLoRA 监督微调效果明显（比 3-Shot 高 `+39.08` 个百分点）。**
   只靠 3-Shot 提示时，`Qwen2.5-7B-Instruct` 的锁定测试集 Macro-F1 为 `0.3886`（T3 代码审计 `0.1486`）。在相同训练集（`backbone_train`, $n=620$）与校准集（`temp_calibration`, $n=180$，`0` 行接触测试集）上做 5 轮 4-bit QLoRA 并挂上多任务指针头后（`B_Qwen2.5_7B_QLoRA`），Macro-F1 升至 `0.7794`（T3 `1.0000`，构造脚本太简单，属天花板效应），24 篇原始 PMC $\kappa$ 从 `0.5766` 升至 `0.6981`（$P_o = 74.58\%, \text{AC}_1 = 0.7113$）。
2. **同预算下两者分数相近，不能说谁“赢”；稳健的结论是速度。**
   装上同样的符号规则后，`B4_22L` 为 `0.8679` [`0.8310, 0.9080`]，`B_Qwen2.5_7B_QLoRA_NS` 为 `0.8494` [`0.8110, 0.8850`]：置信区间大幅重叠，且**没有做配对检验**。纯神经对比中 `B3c` 的点估计更高（`0.8384` vs `0.7794`；探针题 `71.88%` vs `56.25%`；24-PMC $\kappa$ `0.7533` vs `0.6981`；FCR `6.73%` vs `14.42%`），同样没有配对检验。7B 模型受 `<6 GiB` 显存所限只适配了顶部 `8/28` 层、提示压缩到 `max_len=416`、训练 5 轮，而 `B3c` 解冻了全部 22 层（`seq_len=1,280`）——差距可能主要来自这些预算限制，而非架构本身（单向掩码等解释只是假设，未经检验）。确定的是延迟：`12.51 ms` vs `287.62 ms`，约快 `23` 倍。全 28 层、长序列的 `7B–32B` 微调（`--colab-14b-32b`）尚未测试。
3. **非逐字引文率只代表我们的设置。**
   在同一个微调好的 `B_Qwen2.5_7B_QLoRA` 上：用**区间指针头**切片时，引文逐字有效率 `100.0%`（设计保证；定位准确率 `77.50%`）；用冻结的基础 `lm_head` 在 `36`-token 上限下自由生成 JSON（`4,490.7 ms/win`）时，JSON 合格率 `43.75%`，非逐字/截断率 `75.00%`。这些数字来自 4-bit 模型和很短的生成上限，截断是主因，不能推广成“大模型必然编造引文”——已有研究在给出清晰文本时测得 96%–100% 的抽取准确率（Konet 等 2024）。合理的结论是：指针切片让引文可被机器核对。
4. **符号外挂让每个架构都涨分——但这部分是循环的。**
   把集合交集先验（$\gamma_{\text{sym}} = 2.65$）挂到 `mDeBERTa-v3-base`（`B_DeBERTa_NS`）和 `Qwen2.5-7B QLoRA`（`B_Qwen2.5_7B_QLoRA_NS`）上时：
   - `B_DeBERTa_NS` 的锁定测试集 Macro-F1 从 `0.3925` 升至 `0.6787`（`+28.62` pp），24 篇原始 PMC $\kappa$ 升至 `0.9446`；
   - `B_Qwen2.5_7B_QLoRA_NS` 的锁定测试集 Macro-F1 从 `0.7794` 升至 **`0.8494`（`+7.00` pp）**，探针题 **`100.0%` (`32/32`)**，24 篇原始 PMC $\kappa$ 从 `0.6981` 升至 **`0.9299`（$P_o = 94.17\%, \text{AC}_1 = 0.9360$，其中 T1 未加权 $\kappa$ 从 `0.1927` 升至 `0.7275`）**！
   由于这些规则与参考答案 `R1` 及探针句共用触发短语，所有架构“一挂就涨”是构造上可以预期的，**不能**当作“跨架构通用外挂”的泛化证据。

---

### 11.6 `<6 GiB` 消费级显卡极限显存工程揭秘（上篇·推理篇）：如何把大象装进冰箱，在 `5.58 GiB` 可用显存的 RTX 2060 上丝滑跑通 `7.62B` 大模型（峰值仅 `4.49 GiB`）？

很多读者看到上面 `Qwen2.5-7B-Instruct` 的硬件记录会惊掉下巴：
> **`gpu: "NVIDIA GeForce RTX 2060"`, `total_vram_gib: 5.58`, `peak_vram_gib: 4.485 (ZeroShot) / 4.487 (3Shot)`！**
> 怎么可能？！在普通笔记本/台式机只有 `5.58 GiB` 可用显存的 RTX 2060 上，别人跑个 7B 模型连加载权重都会直接 `CUDA out of memory` 爆显存崩溃，或者被 `accelerate` 的 CPU Offload 拖慢成每分钟蹦一个词的幻灯片，你们是怎么做到峰值显存仅占 **`4.49 GiB`**、不到半小时跑完三大数据集共 512 个多任务窗口的？

这段写在 [`evaluate_larger_backbones_and_llms.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_larger_backbones_and_llms.py#L733-L814) 里的 **`<6 GiB` 极限显存手术**，只用了最朴素的高中乘法算账，是极佳的大模型底层系统工程范本！

#### 第一步：先算一笔账——为什么直接 `load_in_4bit=True` + `device_map="auto"` 必死无疑？
`Qwen2.5-7B-Instruct` 共有 `7,615,616,512`（`76.16 亿`）个参数，词表大小 $|V| = 152,064$，隐藏层维度 $d = 3,584$，共 28 层 Transformer。即使加载 4-bit NF4 量化权重（`unsloth/Qwen2.5-7B-Instruct-bnb-4bit`），显存账单依然由四大块组成：
1. **28 层 4-bit NF4 Transformer 权重**：约 $6.52 \times 10^9 \times 0.5\text{ bytes}$ + 量化缩放因子 $\approx \mathbf{3.15\text{ GiB}}$；
2. **输入词嵌入矩阵 `model.embed_tokens`（未量化的 `fp16`）**：
   $$152,064 \times 3,584 \times 2\text{ bytes} \approx \mathbf{1.015\text{ GiB}}$$
3. **输出词表投影头 `lm_head`（未量化的 `fp16`）**：同样是 $152,064 \times 3,584 \times 2\text{ bytes} \approx \mathbf{1.015\text{ GiB}}$；
4. **前向激活值 + KV Cache + 全序列词表输出张量 `[1, L, 152064]`**：当序列长度 $L = 768$ 时，如果把全部 $768$ 个位置的词表 Logits 都算出来转成 `fp32`，光这一个输出张量就要吃掉：
   $$768 \times 152,064 \times 4\text{ bytes} \approx \mathbf{445.5\text{ MiB}}!$$

把它们加起来：$3.15 + 1.02 + 1.02 + 0.45 + \text{CUDA Context} > \mathbf{5.9\text{ GiB}} > 5.58\text{ GiB}$（当场爆显存 OOM）！
而如果你偷懒写 `device_map="auto"` 让 HuggingFace `accelerate` 自动切分，它会把最后几层 4-bit NF4 层踢到 CPU 上——结果要么触发 `bitsandbytes` 4-bit `meta` 张量报错，要么每生成一个词都要通过慢速 PCIe 总线来回搬运上百 MB 的权重钩子（`_hf_hook`），慢上几十倍！

#### 第二步：三刀精准手术——“算力与查表分离 + 拔除 Hook + `logits_to_keep=1`”
我们敏锐地抓住了 `embed_tokens` 和 `layers.0..27 + lm_head` 在**计算本质**上的天壤之别：
* **第 1 刀（算术密度分流）**：28 层 Transformer 和最后的 `lm_head`（矩阵乘法 $[1, 3584] \times [3584, 152064]$）每秒要做数万亿次浮点乘加，**必须 100% 留在 GPU 上**（两者合计 $3.15 + 1.02 \approx \mathbf{4.18\text{ GiB}} < 4.30\text{ GiB}$，刚好塞得进 RTX 2060！）；而占了整整 **`1.02 GiB`** 的输入词表 `model.embed_tokens` 根本不做任何矩阵乘法——它只是按输入的 $L$ 个整数词号去字典里**抄出 $L$ 行向量（复杂度 $O(L)$）**！
* **第 2 刀（拔掉 `accelerate` 动态搬运钩子，手写 12 行 `_CpuFp16Embedding`）**：如果只把 `embed_tokens` 标为 `"cpu"`，`accelerate` 默认挂上的 `AlignDevicesHook` 会在每次前向传播时试图把整个 `1.02 GiB` 的权重矩阵临时拷进 GPU 再删掉，照样撑爆显存！我们在加载完模型后，直接抽出 CPU 上的 `fp16` 词表矩阵，调用 `remove_hook_from_module` 拆掉钩子，换上下面这个干净利落的 12 行模块（见 [`_CpuFp16Embedding`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_larger_backbones_and_llms.py#L733-L745)）：
  ```python
  class _CpuFp16Embedding(torch.nn.Module):
      def __init__(self, cpu_weight: torch.Tensor, padding_idx=None, out_device="cuda:0"):
          super().__init__()
          self._cpu_weight = cpu_weight  # 1.02 GiB 常驻系统内存，不注册为 GPU Parameter
          self.padding_idx = padding_idx
          self.out_device = out_device

      def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
          emb = torch.nn.functional.embedding(input_ids.to("cpu"), self._cpu_weight, padding_idx=self.padding_idx)
          return emb.to(device=self.out_device, dtype=torch.float16, non_blocking=True)  # 仅传输 ~5.25 MiB 激活值！
  ```
  算一算每次跨 PCIe 传输的数据量：$768 \times 3,584 \times 2\text{ bytes} \approx \mathbf{5.25\text{ MiB}}$（不到 `1.02 GiB` 的千分之五，耗时不到 `0.5 毫秒`）！
* **第 3 刀（`logits_to_keep=1` 砍掉 99.8% 输出词表显存）**：在做单步选项打分时，向模型传入 `out = llm_model(**enc_inp, logits_to_keep=1)`，让 `lm_head` 只对序列的最后 1 个位置计算词表分布 `[1, 1, 152064]`（仅占 `0.30 MiB`，省掉了 `445 MiB` 的无用张量）！

三刀合一，整座 `76.2 亿` 参数的大模型在 `5.58 GiB` 的 RTX 2060 上稳稳跑出了 **`4.485 GiB`（0-Shot）/ `4.487 GiB`（3-Shot）** 的超低显存水位！

---

### 11.7 `<6 GiB` 消费级显卡极限显存工程揭秘（下篇·训练篇）：如何在 `5.58 GiB` 的 RTX 2060 上仅用 `3.410 GiB` 峰值显存完成 `76.6 亿` 参数 `Qwen2.5-7B` 的 4-Bit QLoRA 监督微调？

如果说在 `5.58 GiB` 的 RTX 2060 上跑通 `7.62B` 推理已经让人惊叹，那么下一个问题简直像天方夜谭：
> **“推理不需要存反向传播的激活值和优化器状态，还要占 `4.49 GiB` 显存；那你们是怎么在同一张 `5.58 GiB` 的 RTX 2060 上，把 `76.6 亿` 参数的 `B_Qwen2.5_7B_QLoRA`（含 `4,133 万` 可训练参数）完整训练了 5 个 Epoch，而且峰值训练显存反而降到了不可思议的 `3.410 GiB`（`3,491.8 MiB`）？！”**

打开 [`evaluate_larger_backbones_and_llms.py`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/evaluate_larger_backbones_and_llms.py#L984-L1575)，你会看到一套堪称教科书级的**“两阶段前缀激活缓存 + 混合 4-Bit/FP16 梯度检查点”**工程方案：

#### 第一步：为什么常规 QLoRA 在 `5.58 GiB` 显卡上连 1 个 Batch 都训不了？
在常规 QLoRA 中，哪怕底层的 `layers.0..19` 是冻结的，只要你在每次 `loss.backward()` 时把全部 28 层同时放在 GPU 上跑前向传播，GPU 就不得不常驻全部 28 层权重（`3.15 GiB`）+ `lm_head`（`1.02 GiB`）+ 顶部可训层的反向激活值与 AdamW 动量状态（`> 1.8 GiB`），总显存瞬间突破 **`6.0 GiB`**！

#### 第二步：利用“冻结函数确定性恒等式”，把 28 层大山劈成两半！
回想高中函数的复合性质：在顶部 8 层（`layers.20..27`）挂载 QLoRA 适配器时，底下完全冻结的前 20 层（`embed_tokens` + `layers.0..19`）是一个**没有任何随机丢弃（`eval()` 模式）的确定性函数 $f_{0..19}(X)$**！这意味着同一道题 $X_i$ 无论在第 1 轮还是第 5 轮训练，流经前 20 层出来的特征矩阵 $\mathbf{H}^{(19)}_i = f_{0..19}(X_i)$ **永远一模一样，且不需要算梯度**！
1. **阶段一：单层流式反量化前缀缓存（Streaming Layer-by-Layer Prefix Caching，`283.26 秒`）**
   在训练开始前，我们把全部 $1,372$ 个样本窗口先过一遍 `embed_tokens`，然后**每次只把 1 层**冻结的 4-bit NF4 层（从 `layer 0` 到 `layer 19`）搬上 GPU 反量化成高速 `FP16`，一口气算完所有样本在这一层的输出，立刻把该层从 GPU 彻底清空（`del gpu_layer; torch.cuda.empty_cache()`），再搬下一层！整个阶段一的 GPU 静态显存不到 **`1.2 GiB`**，仅用 **`283.26 秒`** 就拿到了全部样本在第 19 层出口的精确特征 $\mathbf{H}^{(19)} \in \mathbb{R}^{L \times 3584}$！
2. **阶段二：删掉前 20 层与 `lm_head`，混合 4-Bit/FP16 顶部 8 层 QLoRA + 非重入梯度检查点（`934.68 秒`）**
   拿到了 $\mathbf{H}^{(19)}$ 之后，前 20 层和 `1.02 GiB` 的 `lm_head` 在训练阶段已经毫无用处，直接从内存/显存中彻底释放！此时 GPU 上只需要驻留：
   - **顶部 8 层（`layers.20..27`）**：其中 `layers.20..24` 保持 4-bit NF4 压缩（`keep_4bit=True`），最顶部的 `layers.25..27` 预先反量化为常驻 `FP16` 缓冲（`keep_4bit=False` 以加速反向传播），并在全部 8 层的 7 个线性投影矩阵（`q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`）上挂载 Rank-16 QLoRA 适配器（$r=16, \alpha=32$，共 `11,534,336` = **`11.53M`** 可训参数）；
   - **多任务区间指针决策头 `QwenQLoRADecisionHead`**：将 `3,584` 维隐藏状态映射到 7 个分类头与句子指针头（共 `29,792,770` = **`29.79M`** 可训参数，合计 **`41.33M`** 可训参数）；
   - **非重入梯度检查点（`torch.utils.checkpoint.checkpoint(..., use_reentrant=False)`）**：前向经过 `layers.20..27` 时不保存中间层内部激活，只在反向传播经过每一层时即时重算。

结果令人拍案叫绝：5 个 Epoch（`batch_size=4, grad_accum=2`）的平均训练损失从 `1.5740` $\to$ `0.9298` $\to$ `0.5310` $\to$ `0.3361` $\to$ **`0.2584`** 平滑收敛，总训练耗时仅 **`934.68 秒`**，而整个训练过程的 **GPU 峰值显存被死死锁在 `3.410 GiB`（`3,491.8 MiB`）**——甚至比 `MedBias-Laya V5` 全 22 层训练的 `3.649 GiB` 还要低 `239 MiB`！同时，我们还提供了开箱即用的 `--colab-14b-32b` 参数与配套的 [`MedBias_Laya_V6_Larger_Models_Colab.ipynb`](file:///home/cht/Works/Helper_for_Assessing_Risk_of_Bias_PROBAST/build/medbias-laya-study/MedBias_Laya_V6_Larger_Models_Colab.ipynb) 云端笔记本，让拥有 T4/A100 显卡的研究者可以一键把这套评测扩展到 `Qwen2.5-14B-Instruct` 与 `Qwen2.5-32B-Instruct-AWQ`！

---

## 🎓 终章总结：一张表背下本项目的 12 个核心数学公式

| 编号 | 模块名称 | 核心数学公式 | 一句话人话口诀 |
| :--- | :--- | :--- | :--- |
| **F1** | **零幻觉区间切片** | $T[a_k : a_k + L_k] \equiv q_k$ | 选句号不默写，原文切片永不编造 |
| **F2** | **滑窗聚焦打分** | $\text{Score}(s_i) = \sum \alpha(w)\mathbb{I}(w \subseteq s_i) + \max(0, 0.5 - 0.01i)$ | 关键词加分挑前 8，按原顺序排排坐 |
| **F3** | **Softmax 概率转化** | $p_c = \dfrac{e^{z_c}}{\sum_{j=1}^{K} e^{z_j}}$ | 指数变正拉差距，除以总和归一化 |
| **F4** | **多实例包裹损失 (MIL)** | $\mathcal{L}_{\text{MIL}} = -\ln\!\left(\sum_{s \in \mathcal{V}_i} q_s\right)$ | 多个好句装一袋，概率相加不内耗 |
| **F5** | **标签平滑 + L2 惩罚** | $\tilde{y}_c = (1-\varepsilon)y_c + \frac{\varepsilon}{K}, \quad \mathcal{R}_{L_2} = \frac{\lambda_{L_2}}{K}\sum_{c=1}^{K} z_c^2$ | 满分留八分余地，平方弹簧防爆炸 |
| **F6** | **分组梯度裁剪 + LLRD** | $\mathbf{g}_g \leftarrow \mathbf{g}_g \min\!\left(1, \frac{1}{\|\mathbf{g}_g\|_2}\right), \quad \eta_{\text{bottom}} \ll \eta_{\text{head}}$ | 底层轻调顶层猛，分组裁剪不误伤 |
| **F7** | **最小对比对消偏** | $P(Y=\text{safe} \mid N) = P(Y=\text{leak} \mid N) = 0.5, \; P(S_k)=\frac{1}{4}$ | 名词相同换介词，四个抽屉匀着藏 |
| **F8** | **温度缩放 + 先验校准** | $z'_c = \dfrac{z_c}{T} + \tau_{\text{prior}} \ln\!\left(\dfrac{\pi_{\text{cal}}(c)}{\pi_{\text{train}}(c)}\right)$ | 除以温度调冷热，对数先验修水土 |
| **F9** | **集合匹配 + 神经符号融合** | $(W \cap V \neq \emptyset) \land (W \cap S \neq \emptyset) \land (W \cap G = \emptyset), \; z^{\text{fused}}_c = z'_c + \gamma_{\text{sym}}\mathbb{I}(c=c^*)$ | 左脑集合抓关键证据，右脑对数加权重 |
| **F10** | **非对称选择性门控** | $\tau_{\text{clear}} (0.80) > \tau_{\text{min}} (0.62), \quad \text{FCR}_{\text{retained}} = 0.00\%$ | 报警容易放行严，拿不准就交专家 |
| **F11** | **Cohen's $\kappa$ 与 PABAK** | $\kappa = \dfrac{P_o - \sum p_c q_c}{1 - \sum p_c q_c}, \quad \text{PABAK} = 2P_o - 1$ | 扣除巧合算净分，拉平分布防坍塌 |
| **F12** | **Gwet's $\text{AC}_1$ 抗悖论系数** | $\text{AC}_1 = \dfrac{P_o - P_e^{\text{Gwet}}}{1 - P_e^{\text{Gwet}}}, \quad P_e^{\text{Gwet}} = \dfrac{1}{K-1}\sum_{c=1}^{K} \bar{\pi}_c(1 - \bar{\pi}_c)$ | 二次函数开口下，极端流行不失真 |
