# 公开全文输入与许可核查 v1

核查对象为已有来源快照，不是重新下载或患者数据。执行目录 `build/literature-public-input-v1/`，清单 `manifest.json`；全部输入来自既有 `build/m1-source-snapshots/`。若要重建，应通过来源记录的合法 PMC E-Utilities 链接获取，并重新核对身份和许可。不得把本地路径存在当下载可复现。

| 身份 | DOI | 原始 XML SHA-256 | 本次正文段落数 |
|---|---|---|---:|
| PMC12874331 | 10.1016/j.apjon.2026.100853 | 300b8d22f9f32154d0a151c0d049a2328abef50f48fe021be51768d4c9aa6fc4 | 53 |
| PMC12231630 | 10.2340/17453674.2025.44248 | 5c5b18ebdbd5abbe23cf7d7b9381421b210773be764c9bbf55ba12bf55e18254 | 38 |

以上计数来自 XML body 内 p 元素，仅表示原始抽取数量，不代表研究信息或完整解析覆盖。两个快照根节点均需要按实际 XML 结构识别 article；第一篇发现根为 `pmc-articleset`，不能假设根总是 article。

两篇 JATS permissions/license 均明确链接 https://creativecommons.org/licenses/by/4.0/，正文分别声明 CC BY 和 CC BY 4.0。题名、作者、原始链接及归属见 [pilot材料](m1/pilot-v1/materials.json)。原文文本依 CC BY 4.0 使用，不由仓库 MIT 许可重新授权；模型收到的仅是选定公开正文段落，不含患者记录、图片、表格逐行数据或第三方附件。

本轮正文分析遵循用户“开始行动”对公开案例实施的授权；实际模型调用需显式开关并记录 provider/model。后续附件指针审计见 [附件审计](literature-attachments-v1.md)：已发现 `mmc1.docx` 与 `ActaO-96-44248-s1.pdf` 指针，但候选URL未验证为附件正文，且附件许可未独立核实。正文许可不自动扩展至附件；遇到附件指针应标记缺失材料，不凭作者在正文中的一句总结补成已核实。

工程基线：`build/literature-baseline-20261020-150626/results.json`，六组检查均真实返回0：check_bundle、study、workflow、decision_agent、Hermes adapter默认离线测试、review_probes。另显式运行 Hermes 安装 API 集成，13项通过，无供应商调用；该安装兼容检查不证明模型可调用。真实供应商连通性和文献分析另存运行记录。
