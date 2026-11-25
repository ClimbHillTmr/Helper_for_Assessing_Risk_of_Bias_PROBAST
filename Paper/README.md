# 参考文献与许可边界

公开版本用文献引用及官方链接替代原先存放的第三方 PDF。本项目的 MIT 许可证适用于本项目代码与原创说明，不为第三方论文或官方量表重新授权。下载、使用与再分发这些材料时，应遵守各原始来源的条款。

- Wolff RF et al. **PROBAST: A Tool to Assess the Risk of Bias and Applicability of Prediction Model Studies.** Ann Intern Med. 2019. [DOI: 10.7326/M18-1376](https://doi.org/10.7326/M18-1376)。
- Moons KGM et al. **PROBAST+AI: an updated quality, risk of bias, and applicability assessment tool for prediction models using regression or artificial intelligence methods.** BMJ. 2025;388:e082505. [原文](https://www.bmj.com/content/388/bmj-2024-082505)。
- [PROBAST 官方工具与版本入口](https://www.probast.org/)。
- [TRIPOD 官方报告指南与材料](https://www.tripod-statement.org/)。
- 原 `TRIPOD checklist.pdf` 标注的文章标识：[DOI: 10.1136/bmj-2022-071058](https://doi.org/10.1136/bmj-2022-071058)。不能据旧文件名认定它是当前版本。
- 陈香萍、章仲恒，**PROBAST：诊断或预后预测模型研究偏倚风险的评估工具**。中国循证医学杂志，2020。[DOI: 10.7507/1672-2531.201910087](https://doi.org/10.7507/1672-2531.201910087)。

旧的研究专用填写表不属于公开示例。当前版本及独立 skill 包不包含这些 PDF；历史提交保留其原有内容，本次发布不重写 Git 历史。

## 短篇伴生软件论文（JOSS）

本仓库的方法学开源工具包短篇伴生软件说明（Software Paper）及投稿就绪检查工具位于 [`Paper/joss/`](joss/)：

- [`Paper/joss/paper.md`](joss/paper.md)：符合 *Journal of Open Source Software* (JOSS) 格式的纯软件工程底座说明稿（`750–1750` 词，含 `Summary`、`Statement of Need`、`State of the Field`、`Software Design`、`Research Impact Statement`、`AI Usage Disclosure`、`Acknowledgements` 与 `References`）。
- [`Paper/joss/paper.bib`](joss/paper.bib)：配套 BibTeX 参考文献库（7 条文献均含 DOI；脚本仅检查 DOI 语法，零未发表预印占位条目）。
- [`Paper/joss/check_joss_ready.py`](joss/check_joss_ready.py)：纯 Python 3.10+ 标准库编写的 JOSS 投稿前一键自检与作者元数据原子回填脚本（校验 YAML 头、正文词数 `[750, 1750]`、章节结构、PNG 配图像素尺寸、BibTeX DOI 完整性、仓库治理文件及 ISO 7064 Mod 11-2 ORCID 校验位）。
- [`Paper/joss/SUBMISSION_CHECKLIST.md`](joss/SUBMISSION_CHECKLIST.md)：分阶段补充计划、验收条件、研究证据与作者待确认事项；开发历史和编辑资格不能由 CI 绿标替代。
- [`Paper/joss/paper_preview.pdf`](joss/paper_preview.pdf)：基于 Pandoc + XeLaTeX 生成的本地排版与参考文献渲染预览 PDF。
