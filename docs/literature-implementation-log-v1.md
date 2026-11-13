# 文献入口实施记录

阶段：P0 已执行；首轮两篇公开全文真实运行已结束并读取，状态 PARTIAL。23次模型请求均有效，8项问题中2项ASSESSED、6项INSUFFICIENT，没有适配器错误。产物完整性不代表科学接受，P1/P2完整计划尚未全部交付，见下方验收缺口。运行采用未提交工作树，HEAD `008fee57d3bcc0b1fd413ca39a6097e5b23026de`，精确源码身份见 `build/literature-live-v1/identity.json`。

## 已执行

- 默认五脚本与独立 review_probes 六组检查全部 exit 0，输出 `build/literature-baseline-20261020-150626/`。
- 两篇公开 JATS DOI、原始哈希与 CC BY 4.0 权限逐篇核对，见 [来源核查](public-case-rights-v1.md)。附件未获取。
- 明确开启 Hermes 本地安装 API 集成：13项通过；不涉及供应商调用。
- 最初后台调用使用短 `python3`，两候选均约0.33秒即失败；固定到已验证环境的解释器绝对路径后，后台新适配器调用成功。未记录短解释器解析结果，故根因仅定位为后台启动环境/解释器选择差异，不断言提供商故障。`codex/gpt-6-astra` 本轮仍未核验可用。
- 当前已实际调用 `magpie/codex/gpt-6.1-sol`，新文献适配器合成请求返回有效结构和逐字引文；输出 `build/literature-adapter-live-20261020-151356/response.json`。独立复核若沿用同模型，必须记录独立上下文，不能称双模型。
- 适配器26项离线测试通过；搬至正确skill/scripts目录后修正相对导入。增加中文摘要要求与非排他性/时点构念约束。
- `scripts/prepare_literature_demo.py` 已实际执行，生成 `build/literature-public-demo-v2/`，未调用模型。

## 更新：真实运行已启动

修复后 `build/literature-dry-parent-v3` 两篇成功索引并完成哈希核验，零模型请求。九组默认与新增检查实际通过，输出 `build/literature-regression-20261020-152319/`。新适配器28项测试、父审边界5项通过。后台 `build/literature-live-v1` 已启动 Sol 分析与 Astra 盲复核，运行代码及输入/配置哈希在 identity.json；本节不预告结果。

人工检查检索输出发现当前关键词top-5会混入结果和讨论段；SECTION信息尚未参与排序，且无完整附件抓取。首版适合暴露流程问题，不可把未检索到解释成整篇没报告。后续若改检索，必须新运行、保留首版输出，不能用结果倒调已有案例的最后结论。

## 独立复核修复记录

最终独立审查复现两个缺陷：超8KB内部DTD属性注入可绕过许可检查；前源有模型请求、后源BLOCKED时外发标记漏报。父代理新增两回归先跑得2 FAIL，随后修复扫描全raw与按累计request_count记录外发尝试，7项边界测试通过；标准文献测试和真实输入dry-run再次通过。修前源码保留 `build/preserved_literature_before_review_fix/`，修后dry-run `build/literature-dry-review-fixed/`。首轮live-v1启动在修复前，按其identity解释，不能宣称已使用新修复。实际两个CC BY快照无内部DTD，具体影响待运行结束核对，不能泛化为无需修复。外发标志表示适配器调用已尝试，并非对网络包实际送达的认证。

## 真实运行完成与验收边界

前文“启动/尚未核验”是当时状态，现由本节更新：Sol分析与Astra盲复核均已真实完成。`build/literature-live-v1/finish.json`记录PARTIAL、exit 1、completion_verified true。父代理重新核验全部产物哈希、91段文本哈希和79条attempt层引用偏移；23请求全valid、零错误，2项ASSESSED、6项INSUFFICIENT。详见[首轮结果与未完范围](literature-live-result-v1.md)。独立真实报告语义复核已分派，尚未返回。未宣布完整P1/P2或科学接受。

首轮原始响应字节没有保存，`raw_response`实为解析且加偏移的对象，因此不能重算response_sha256；此限制已经登记，不能倒造首轮原始字节。后续需补响应留存、章节索引、附件链与恢复，继续使用新目录。

## DTD修复的后续纠正

2026-10-20：`deleg_456f7f17`确认前次“扫描全raw”仍可被DOCTYPE引号内的`>`绕过；因此前节关于DTD已修复的说法由本节纠正。父代理新增UTF-8/UTF-16具体注入用例，先复现两种编码均未抛错；随后改用标准库Expat的StartDoctypeDeclHandler，在has_internal_subset为真时立即拒绝，不再用正则解释DTD语法。参数实体解析关闭，外部引用不读取。9项边界测试与文献核心测试通过，两真实输入重新dry-run至 `build/literature-dry-expat-fixed/`，completion_verified true。新增独立窄审已分派，尚未返回；通过测试不提前宣称全面安全。

原首轮真实模型报告保持不变。本轮两输入无内部子集，故这个修复不改变输入文本或模型证据；不为验证纯解析修复重复付费调用模型。外发标记前次修复获独立确认，但只表示调用尝试。

## DTD独立窄审完成

`deleg_24e2b7a8`已返回限定范围PASS；父代理再次运行9项边界测试全部通过。见[复核记录](../reviews/literature-dtd-fix-review.md)。这只关闭DTD修复范围，不替代语义复核或全文产品验收。

## 原始调用字节留存已补齐

新运行会在 `attempts/<source_id>/` 保存实际request/response字节，记录路径和SHA-256，并将文件纳入completion。两篇dry-run `build/literature-dry-raw-retention-v1/` 与父一致性核验通过；合成真实执行路径也验证了字节哈希。旧`literature-live-v1`没有这些文件，严格核验器拒绝旧运行是预期结果，不能回填。

## 真实报告语义复核完成

`deleg_1868c139`已返回，父代理核对后形成[语义审查与裁定](../reviews/literature-live-v1-semantic-review.md)。保留第一篇GROUP_SPLIT证据口径争议，EVAL_ROLE仍为组合推断的风险建议；不改冻结输出。纠正审查中的60条引用、扩窗未触发、预算未登记、模型标识未注明等陈述：最终角色引用57条（全部偏移有效）、attempt引用79条、相邻扩窗7次、配置预算30/篇且实际11/12次。6项不足不全是附件缺失，也不能保证附件能解答。DTD修复已另行PASS，两个审查范围不互相替代。

## DTD独立窄审完成

`deleg_24e2b7a8`已返回限定范围PASS，未发现该修复范围内剩余绕过；父代理再次重跑9项边界测试全部通过。见[DTD复核记录](../reviews/literature-dtd-fix-review.md)。上文“窄审待返回”作为历史状态保留，由本节关闭。全文产品仍PARTIAL，语义审查与产品未完范围不受此PASS替代。

## 首轮父审发现并修复中

1. FIT_SCOPE 被错误解释为研究任务是否符合产品范围，必须恢复为训练折拟合边界。EVAL_ROLE明确评估集是否用于模型/阈值/校准选择。
2. DOI/许可扫描全XML，可能错绑其他article或参考元数据；改为单article的article-meta。
3. 核心擅自改变hash/rights字段，与冻结契约不一致。
4. 无证据/两模型均信息不足可能被误记为完整分析。
5. Markdown只有状态，无可阅读的证据摘要。

上述缺陷在全文真实分析前发现，尚不存在需要作废的真实论文分析结论。保留既有合成运行，不把合成PASS当产品验收。后续必须新目录运行并独立审查最终代码。

## 补充材料发现审计

新增 `scripts/discover_literature_attachments.py` 与3项离线测试。对 `build/literature-public-demo-v2/manifest.json` 实际运行 `--allow-public-egress --probe-assets`：从 PMC OAI 元数据发现 `PMC12874331/mmc1.docx` 和 `PMC12231630/ActaO-96-44248-s1.pdf` 两个指针；候选 URL 未验证为附件内容（HTML/404），许可未独立核实。没有下载附件正文，也没有调用模型。报告与两份OAI快照在 `build/literature-attachment-discovery-v2/`，说明见 [附件审计](literature-attachments-v1.md)。

正文入口随后增加了本地 `supplement_pointers` 提取和 `index.*.json` 输出；实际新 dry-run `build/literature-dry-pointers-v1/` 的两来源均为 `declared_pointers:1; resolved:0; rights_verified:0`，completion_verified=true。

## P2：章节索引与恢复契约

新增 `literature_recovery.py`、`resume_literature_run.py` 及恢复测试。每个新 run 在解析 manifest 后写入 `run_state.json`，记录逐源 `CREATED`/`INDEXED`/`ANALYZED`/`BLOCKED` 状态、manifest SHA-256 和已验证 artifact 哈希；完成时为 `COMPLETED`。恢复器只在 manifest 哈希一致、源状态可恢复且 artifact 文件哈希一致时复制到新目录，任何篡改、缺失、非法状态或目标冲突都保留 `BLOCKED`，不调用模型或网络。

章节索引已加入 `section_path`：标题来自正文 `<sec>/<title>`，无标题为 `null`，无 section 为 `[]`；table/figure/公式/补充材料/ref-list 中的 p 不作为正文证据。为保护旧引用，排除的唯一段落占用旧 ordinal，故新索引允许编号空洞；保留正文段落的文本、SHA-256 和 paragraph ID 不变。两篇真实快照回归通过：保留段落身份与文本哈希一致，分别索引37/28段，章节路径21/19组。

实际最终 dry-run：`build/literature-p2-sections-recovery-20261025-153637/`；恢复验证：`build/literature-p2-recovered-20261025-153637/`；父一致性核验通过，未调用模型。

## 2026-10-28纠正与修复（优先于上节完成描述）

前版仅实现产物复制，不足以称完整断点续跑；图表独立段落被排除，但嵌入父 p 的图表文字仍会进入证据；有空洞 ID 还破坏了扩窗。已按实际复现修复，并建立离线 v2 身份绑定续跑，实际 SIGTERM/SIGINT/SIGKILL 与合成故障验收通过。最终22个检查组、原始日志、两篇新准备运行和旧目录全文件不变核验见 [本轮交付](literature-p2-repair-20261028.md)。修复前源码及第一次验收器失败目录均保留。本轮没有新模型结果，模型续跑、附件来源映射均未执行。
