# Skills 自动化升级复评

## 评估结论

原有产品已具备任务冻结、患者/时间/拟合成员审计和完整尝试对账。主要缺口是跨阶段编排、失败后交接、明确的完成标记，以及旧审计报告验证仍信任 PASS 字段。当前开发版 0.2.0-dev 增加本地自动检查入口，保持标准库和外部 runner 边界；未发布、未提交、未修改现有 Alpha ZIP。

## 已实现

- workflow.py：新 DRAFT 计划或复用原计划；精确阶段、研究和协议身份检查；planned 审计；显式外部 preflight；results 实际运行对账；JSON/Markdown 交接。
- 保留每个失败、未结束和未执行项，不将完整对账解释为实验成功。
- 验证审计时重新计算原始清单规则并比较报告，阻止改 PASS 或换 fits 后更新哈希绕过检查。
- preflight 本地拒绝缺批准的任务，再核协议锁并调用受信任校验器。批准身份真实性仍由外部流程核实。
- 输出须新建且位于登记目录之外；最后原子发布 completion.json，包含所有本轮产物哈希和退出码。中断的部分输出没有完成标记。
- SKILL.md 按研究类型/阶段按需加载参考资料，automation.md 记录调用、状态、恢复和 Jev 扩展边界；CI 增加自动化集成测试。

## Jev 的适用性

已阅读官方 coding-agents、agent-skill、confidence、skill_suggestion、citation_check 和 sde_cascade 页面。Jev 是结构化判断组件，可辅助候选技能选择、协议语义抽取核验、来源是否支持主张的判断。单一技能产品的固定门禁优先用确定性代码，避免用外部模型替代哈希或成员归属计算。

当前没有 Jev SDK/API 集成、真实请求或医疗领域性能证据。若引入服务，先取得合适材料的外发授权，用专家标签比较纯规则、agent 和 agent+Jev，记录错误放行/拦截、弃权、成本和延迟；问题、阈值、模型与缓存身份须可追溯。cookbook 的通用示例阈值及效果不作为本项目证据。

## 已执行验证

- `python3 skills/medical-research-harness/scripts/test_check_bundle.py`：PASS。
- `python3 skills/medical-research-harness/scripts/test_study.py`：24 项通过。
- `python3 skills/medical-research-harness/scripts/test_workflow.py`：18 tests，OK。
- `python3 tests/review_probes.py --out build/automation-final-probes`：76 项通过，84 个监测文件保持不变。输出目录为本轮验证产物，默认忽略，不随技能分发。
- `git diff --check`：退出码 0。

测试全部使用合成元数据、模拟批准和运行，无患者数据、真实模型训练或 Jev 推理。新增测试覆盖跨研究/阶段/协议证据、缺校验器、伪造审计 PASS、DRAFT 加恒零校验器、协议漂移、失败及未结束记录、登记路径重叠、输出冲突、中断完成标记及产物哈希。

两轮独立只读审查已指出并修复审计重算、DRAFT 防护和输出污染问题。修复后的最终独立只读复核通过：重新运行 18 项工作流测试，并以隔离合成探针验证符号链接/同目录/`..` 路径拒绝、审计聚合字段篡改、缺失/空白/错误类型审批和最终发布中断；未发现这四项修复的阻断问题。该结论为软件复核，不构成科学接受。完成标记采用原子替换，但未提供断电持久性保证。

## 仍有边界

- 文档门禁检查身份、哈希和角色，不验证正文科学含义，也未把所有角色自动绑定到本轮生成文件；旧 summary 的语义时效需人工/agent复核。结果对账独立重算，不据文档直接判定运行有效。
- 重新计算审计不认证日志确实来自实际 fit，也不证明导出器字段覆盖或登记根目录包含所有真实尝试。
- 报告是时点快照，completion.json 标识输出完整性，不是源输入的事务锁；运行时身份锁、资源、并发写入和真实批准仍由目标项目 runner 负责。
- 不支持无人值守训练、自动科学批准、自动正式 PROBAST 逐题结论；患者非互斥等设计仍需专用适配。

参考与具体接口见 `skills/medical-research-harness/references/automation.md`。
