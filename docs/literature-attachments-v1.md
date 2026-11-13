# 补充材料发现审计 v1

状态：**已发现指针，未获得附件，未验证附件许可，未调用模型**。这是来源链路的工程审计，不是对附件内容的评价。

## 实际运行

- 脚本：`scripts/discover_literature_attachments.py`；正文入口的 `literature.py` 现在也会在选定 article 的 `back`/正文结构中保存 `supplement_pointers`。
- 产物：`build/literature-attachment-discovery-v2/report.json`、`report.md`，以及两份 OAI 元数据快照；正文入口新 dry-run 为 `build/literature-dry-pointers-v1/`。
- 运行使用 `--allow-public-egress --probe-assets`，只请求 PMC OAI 元数据和候选附件 URL 的 HTTP headers；没有保存附件正文。
- `asset_bodies_downloaded=false`，`models_called=false`。候选响应的 `text/html` 或 `404` 不被当作附件成功获取。

## 发现结果

| 来源 | 元数据中的指针 | 文章许可元数据 | 候选URL探测 | 当前裁定 |
|---|---|---|---|---|
| PMC12874331 | `mmc1.docx` | 未从 OAI `article-meta` 发现 CC URL | 两个候选均返回 HTML，未验证为 docx | 需来源/许可核查 |
| PMC12231630 | `ActaO-96-44248-s1.pdf` | `https://creativecommons.org/licenses/by/4.0/` | 一个 404，一个返回 HTML，未验证为 PDF | 需来源/许可核查 |

“文章是 CC BY”不自动推出附件可按同样范围处理。即使候选 URL 返回二进制，也还需要核对附件实际许可、来源条款、允许的模型处理范围和文件哈希；这些条件本次均未满足。

## 工程含义

1. 第二篇正文明确指向补充表 I–IV，但本轮只能证明存在附件指针，不能把指针当作表格内容，也不能据此反向改写首轮的 `INSUFFICIENT`。
2. 第一篇附件没有在本次 OAI 元数据中出现可用 CC URL；不能因为文章页面有开放访问就推断 `mmc1.docx` 可外发。
3. 当前自动化已从“附件缺失”细化为“指针已发现、候选 URL 未验证、权限未决”。后续获取必须是新运行，保留本次 OAI 哈希和失败探测。
4. 附件正文一旦获取，先做文件类型、大小、哈希、恶意内容/宏风险和许可记录，再决定是否允许模型读取；本审计器不执行这些后续动作。

## 可复现检查

```text
PYTHONPATH=scripts python3 scripts/test_discover_literature_attachments.py
python3 scripts/discover_literature_attachments.py \
  --manifest build/literature-public-demo-v2/manifest.json \
  --out build/literature-attachment-discovery-v2 \
  --allow-public-egress --probe-assets
```

测试结果：3 tests，全部通过；实际运行处理 2 个来源，未下载附件正文。
