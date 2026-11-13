# 文献入口（literature.py）

标准库实现的公开 JATS 全文入口。只回答四个工程问题（FIT_SCOPE / EVAL_ROLE / GROUP_SPLIT / FEATURE_TIME），输出工程风险建议；不做正式 PROBAST 评级、不做临床判断、不授权任何研究执行。

## 输入

- `--manifest`: `{format_version:1, sources:[{id, doi, title, license_url, rights_basis, path, sha256}]}`，`path` 相对 manifest 所在目录。`sha256` 为 64 位裸 hex（无 `sha256:` 前缀）；`rights_basis` 为非空自由文本来源说明，不是枚举。`license_url` 必须是精确的 `http(s)://creativecommons.org/licenses/by/4.0`（允许尾随斜杠，大小写不敏感）。每个源必须：sha256 匹配、JATS XML 含 `<article>`（支持 `pmc-articleset` 等包装根，只取第一个 article）、`<article-meta>` 内 `article-id pub-id-type="doi"` 与 manifest DOI 一致、`<article-meta>` 内许可为 CC BY 4.0 且 URL 与 manifest `license_url` 精确一致。逐源核验，不处理任意路径或患者文件。
- `--config`: `{format_version:1, max_requests, timeout_seconds, models:{analysis:{provider,model,command:[...]}, reviewer:{...}}}`。`max_requests` 为每篇请求预算（上限 30）。命令为可信 argv，`shell=False`，复用 `decision_agent.bounded_adapter`。
- `--out`: 新目录，不覆盖输入或既有运行。

## 运行模式

- 默认 dry-run：解析、索引、检索全部真实执行；模型标记 `NOT_REQUESTED`，状态 `DRY_RUN`。
- 真实调用需 `--execute-models --allow-public-egress` 两个显式开关，并在报告中留痕许可来源与范围。这不是安全沙箱：适配器凭据与远端路由归运营者。

## XML 安全与身份绑定

- 全字节拒绝任何 `<!ENTITY`；DOCTYPE 只允许无内部 subset 的外部声明（外部实体永不解析）；带内部 subset（`[...]`）拒绝。
- DOI、license 只从第一个 `<article>` 的 `<article-meta>` 提取——参考文献 `<ref>` 或第二个 article 的标识不参与核验。
- license 识别途径：`<license>` 自身 `xlink:href`、后代 `ext-link` href、license 元素文本中的字面 URL（覆盖 `ali:license_ref`、`license-p` 散文）。只接受精确 CC BY 4.0 URL，不识别近似域名/路径前缀。
- 只索引该 article `<body>` 内 `<p>`；`table-wrap`、`fig`、公式、补充材料和 ref-list 中的段落不作为正文证据输出。为了不破坏既有段落身份，旧的唯一段落序号仍用于正文段落，排除的唯一段落占用序号但不出现在新索引中；因此新索引允许 `p0007` 等编号出现空洞。保留段落的 `id`、文本和 SHA-256 不变，`section_path` 是附加定位字段；无标题 section 使用 `null`，无 section 使用空数组。
- section path 只从正文 `<sec>/<title>` 构造，不把 figure/table caption 猜成章节。
- 引用底本 `text`/`sha256` 保留旧规范化坐标；`evidence_text` 用等长空格遮蔽嵌入图表、公式、附件与参考文献文字，另存 `evidence_sha256`。检索、扩窗和模型输入只使用此视图。空格不改变后续字符位置，不把删除后的两段拼成连续引文。扩窗使用保留段落的连续 `order`，不从有空洞的 ID 推导邻居。

## 流程

1. 解析 manifest/config（严格 JSON，拒绝重复键/非有限数）。
2. 逐源校验身份/许可/哈希；文件缺失、字段错误、哈希不匹配 → 该源 BLOCKED，仍写 report+completion，不 traceback。
3. 每问题关键词检索 top-K 段落为证据；无证据直接 `INSUFFICIENT`，不请求模型。
4. analysis 调用 → 严格校验（精确字段、question_id/model 回环、引文逐字存在于证据并记录偏移 start/length、非 insufficient 必须有引文、not_applicable 必须有证据支撑）。
5. 独立盲复核：reviewer 只看问题与相同原文段落，不看初稿。finding 或 applicability 不一致 → `UNRESOLVED`，不投票。模型异常（不可哈希 id、畸形类型）被捕获并留痕于 attempt。
6. `same_model_independent_context` 仅按 provider+model 判定——argv 不同不代表不同模型。
7. insufficient 语义：analysis 返回 insufficient 且扩窗后仍 insufficient，或双方一致 insufficient → `INSUFFICIENT`/`UNRESOLVED`；reviewer 失败/未请求 → `UNRESOLVED`，绝不用空复核把 insufficient 覆盖成 ASSESSED。
8. 至多一次扩窗补证：analysis 返回 `insufficient` 时，追加 top 命中段落的相邻段落重试一次；不重复同一输入。

## 输出

`index.<source_id>.json`（稳定段落索引与哈希，另含 `section_path` 与 `supplement_pointers`）、`report.json`、`report.md`（人可读：每问题状态、finding、summary、逐字引文及其在证据内的偏移）、`attempts/<source_id>/`（每次模型调用的实际request/原始response字节及SHA-256）、`run_state.json`（逐源检查点；状态 `CREATED` / `INDEXED` / `ANALYZED` / `BLOCKED` / `COMPLETED`）和 `completion.json`（原子写，含全部产物文件哈希与退出码）。`scripts/resume_literature_run.py` 只从同一 manifest SHA-256 下恢复仍能通过哈希校验的已完成 source artifacts；缺文件、哈希变化、manifest变化或非法状态保持 BLOCKED，不重置为空，不调用模型或网络。报告外层状态仍为 `DRY_RUN` / `AWAITING_SCIENTIFIC_REVIEW` / `PARTIAL` / `BLOCKED`；`scientific_acceptance` 与 `execution_authorized` 恒为 false。每个 attempt 记录 `evidence_ids`、请求/响应哈希、原始字节相对路径及解析后的引文偏移对象。

## 公开案例重建

仓库宿主通过 `terminal` 运行 `python3 scripts/prepare_literature_demo.py --snapshots build/m1-source-snapshots --out build/public-demo-new`，随后 `python3 scripts/run_literature_demo.py --manifest build/public-demo-new/manifest.json --config build/public-demo-new/config.json --out build/literature-run-new`。真实调用另加 `--execute-models --allow-public-egress`。模型路由和解释器在运行前显式配置；后台运行使用解释器绝对路径，不依赖 shell 的 python3。准备脚本只从已有来源登记与快照重建，不自动下载；快照缺失时按来源合法获取并重新核对许可。

当前默认只解析单篇 article（允许单篇 pmc-articleset 包装），拒绝多 article 输入，source id 仅允许文件名安全字符。纯空白证据/引文与空白摘要拒绝。

## 离线续跑 v2（优先于上面的旧恢复描述）

`run_literature_demo.py` 默认调用 `literature_offline.py`。独立 skill 也可直接运行：

```text
python3 <skill>/scripts/literature_offline.py --manifest manifest.json --config config.json --out NEW_DIR
python3 <skill>/scripts/literature_offline.py --manifest manifest.json --config config.json --out NEW_DIR --resume-from OLD_OUTPUT_DIR
```

仓库包装命令为 `python3 scripts/resume_literature_run.py --run OLD_OUTPUT_DIR --manifest ... --config ... --out NEW_DIR`。这些入口不接受模型执行/外发开关。旧 `--restore-only` 仅复制产物，明确标注 `continuation_completed=false`；不能称完整续跑。

- v2 身份绑定 manifest、config、问题库、依赖源码与 Python 版本。旧 v1 检查点无这些身份，拒绝自动升级为 v2；只可显式复制或新建离线运行。
- 每来源区分 `CREATED`、`INDEXED` 以及 `preparation_complete`：已完成的来源复用 index 和 source 报告；仅有 index 的来源继续检索；未开始来源正常执行。离线永不升级为 `ANALYZED`。
- 恢复前验证全部来源字节、检查点来源集合、必需文件集合、哈希、已有 completion。任一缺失、篡改或歧义均输出新的 BLOCKED report/completion，且不静默重算。目标目录已存在则拒绝写入。
- SIGTERM/SIGINT 捕获真实原因与阶段；SIGKILL 无法捕获，后续记录 `unclean_exit_unknown` 及最后已提交阶段。未提交的额外来源产物属于歧义，阻塞而不猜测。
- 完成仅表示离线解析/检索准备完成：`state=DRY_RUN`、`run_state=COMPLETED`、请求数0；无证据的问题仍可为 INSUFFICIENT。模型续跑与附件获取均不在本契约内。

## 多层证据、研究设计抽取与章节排序（literature_design.py）

在不改变 `literature.py` 既有正文段落 ID（`source_id/pXXXX`）与 v1/v2 检查点契约的前提下，`literature_design.py` 提供 Action Plan v2 的扩展能力：

```text
python3 <skill>/scripts/literature_design.py \
  --manifest manifest.json --config config.json --out NEW_DIR \
  [--include-tables] [--compare-run OLD_REPORT_JSON]
```

- **有类型证据层（`layers.<source_id>.json`）**：将 `body_paragraph`、`table`（`<table-wrap>`，编号 `tXXXX`）、`figure_caption`（`<fig>`，编号 `fXXXX`）和已核验本地补充材料 `supplement_paragraph`（`supp/<supp_id>/pXXXX`，支持标准库安全解析 `.docx` / `.txt` / `.md`）分开存储。未获取或未核实 CC BY 4.0 许可的附件保持 `POINTER_DISCOVERED_UNACQUIRED` / `RIGHTS_UNVERIFIED`，绝不伪造或混入证据层。
- **11 项结构化研究设计抽取（`design.<source_id>.json`）**：抽取 `study_purpose`、`target_population`、`unit_of_analysis`、`prediction_target`、`prediction_time_anchor`、`feature_availability_time`、`split_strategy`、`preprocessing_scope`、`tuning_strategy`、`evaluation_metrics`、`validation_type`，每项非 `unknown` 值绑定逐字引文与字符偏移。
- **章节感知检索**：结合关键词命中与章节权重（优先 `Methods` / `Participants` / `Model Development`，降权 `Introduction` / `Discussion`），并支持 `--compare-run` 逐题归因新旧报告差异。

## 限制

- `public_egress.executed` 表示至少已尝试一次适配器调用，保守记录可能外发；不认证实际网络送达，后续来源失败不清除该标记。
- 引文校验只验证逐字位置，不验证语义正确性。
- 返回的 model 标识是适配器自报，不是权重认证。
- 许可核对确认申报的 CC BY 4.0 条款，不是法律审计。
- 未请求不等于已分析；格式或引文错误不能伪装成功。
- 不报告医疗准确率、ECE 或同等质量降本。
