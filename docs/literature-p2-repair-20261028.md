# Literature P2：内部修复与离线续跑验收

状态：**离线准备与续跑已真实验证；没有新模型分析结果。** 本次没有网络请求、模型调用或附件下载。冻结的 `build/literature-live-v1/` 全部文件哈希保持不变。

## 修复内容

| 问题 | 修复 | 验证 |
|---|---|---|
| paragraph ID 有空洞，扩窗误用 ID 数字作 order | 以实际保留段落的 `order` 查邻居 | p0001/p0003/p0004 合成回归 |
| 父 p 的 itertext 包含嵌入图表文字 | 保留引用底本 text/sha256；增加等长空格遮蔽的 evidence_text/evidence_sha256；检索与扩窗只读证据视图 | FIGURE_ONLY 不进入证据；After. 的字符偏移不变；跨遮蔽引文拒绝 |
| 部分复制失败后留下未登记文件 | 在复制前记入本次创建清单，失败先清理再清空报告 | 第二文件篡改，第一文件不残留 |
| 空 artifacts 假成功 | writer 拒绝空 INDEXED/ANALYZED 清单；旧恢复器与 v2 恢复检查器拒绝缺少必需文件 | 空清单回归 |
| 恢复只有复制，没有后续执行 | 新 `literature_offline.py` 实际复用完成来源、恢复部分索引并继续待完成步骤 | 真 SIGTERM/SIGINT/SIGKILL，中断三来源任务后复用 s1、继续 s2/s3 |
| 只绑定 manifest | v2 绑定 manifest/config/问题库/核心及宿主源码/Python 版本，并再次核源文件字节 | 身份变更、文件篡改均 BLOCKED |

## 运行与证据

根目录：`build/literature-p2-repair-20261028-131432/`。

- 修改前源码：`preserved/`。
- 冻结运行的修改前全文件哈希：`frozen-before.json`。
- 最终通过的验收：`acceptance-r2/validation.json`、`validation.md`、`completion.json`。
- 各测试原始 stdout/stderr：`acceptance-r2/test-*.stdout.log`、`test-*.stderr.log`。
- 真实中断与续跑：`acceptance-r2/SIGTERM/`、`SIGINT/`、`SIGKILL/`，保留被中断目录和新 resumed 目录。
- 缺文件、篡改、空清单、身份冲突、未登记产物：`acceptance-r2/fault-input-*/` 与 `fault-output-*/`。
- 两篇本地公开快照的新准备运行：`acceptance-r2/public-demo/`。
- 公开快照的全复用验证：`acceptance-r2/public-resumed/`；它没有待执行来源，所以不拿它单独证明断点续跑。
- 公开运行的父一致性检查：`acceptance-r2/public-parent-verification.json`。

验收脚本：`python3 scripts/validate_literature_p2.py --out NEW_TIMESTAMPED_DIR`。只读既有公开 JATS 和合成数据。现有完整测试中的 adapter 路径是合成 Python 响应器，不连接供应商。

`acceptance-r2/validation.json` 有22个检查组，包括12个测试入口、review_probes、3种实际中断、5种持久化故障和冻结目录核对。`review_probes` 自身的检查数量以其原始输出为准，不能与22个检查组相加成独立统计证据。

公开快照结果：

| 来源 | 保留段落 | section_path 不同取值数 | 无 section 段落 | 附件指针 |
|---|---:|---:|---:|---:|
| PMC12874331 | 37 | 21 | 0 | 1 |
| PMC12231630 | 28 | 19 | 2 | 1 |

保留段落的旧 id/text/sha256 通过冻结索引回归；新 evidence_text 单独登记哈希。21/19是 section_path 不同取值数（包含空路径时也计一组），不是题目数量或证据条数。

## 真实续跑语义

```text
s1 已完成准备 → 复用 index 与 source 结果
s2 已写索引，在检索前暂停 → 恢复索引，继续检索并生成 source 结果
s3 未开始 → 读取并验证源 XML，完成索引与检索
```

被中断目录不被修改。SIGTERM/SIGINT 记录实际信号和阶段；SIGKILL 不可捕获，只在新运行中记录 unclean_exit_unknown 及最后已提交阶段。不能伪称知道强制终止的具体原因。

恢复失败输出新的 BLOCKED report/completion，不静默重算。已有目标目录拒绝写入。v1 检查点无完整身份，不自动迁移；`--restore-only` 标注 artifact_copy_only、continuation_completed=false。

新 CLI：

```text
python3 skills/medical-research-harness/scripts/literature_offline.py --manifest MANIFEST --config CONFIG --out NEW_DIR
python3 scripts/resume_literature_run.py --run OLD_OUTPUT_DIR --manifest MANIFEST --config CONFIG --out NEW_DIR
```

## 失败记录与限定

第一次汇总 `acceptance-r1/` 最后失败于验收器把所有子目录 completion.json 也排除出实际文件集合。该失败目录保留；修正为只排除根 completion 后，在 `acceptance-r2/` 全部重跑通过。不得引用 r1 为最终验收。

本次源码收尾复核由当前 agent 只读完成，没有派发新的模型 reviewer，以遵守“不调用模型”。工程测试和当前 agent 复核不等于不同模型独立评审或科学接受。CI 文件已经登记新测试，本地执行通过不代表远程 GitHub CI 已运行。

以下仍不在本次通过范围：模型请求中断后的恢复、章节参与检索排序的效果评价、附件来源映射与许可核实、附件下载及解析、正式 PROBAST 评价、医学判断准确率。`COMPLETED` 只表示离线准备完成；`state=DRY_RUN`、请求数0、scientific_acceptance=false。无检索证据的问题仍可 INSUFFICIENT，不声称模型已分析。

## 下一执行约束

先消费最终 completion/validation；不要复用旧 v1 检查点启动模型。后续仅在另行允许的范围查询附件权威元数据，保留链接、许可覆盖和获取状态；不把正文 CC BY 自动扩展到附件。当前交付没有开始该外部查询。
