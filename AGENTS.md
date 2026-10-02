# Medical Research Harness

本仓库的产品是 `skills/medical-research-harness/`。先读其 `SKILL.md`；设计与迁移依据见 `system_design.md`。技能支持医疗研究指导、偏倚评估和证据汇总，实验代码与患者数据属于目标研究仓库。

读取目标研究仓库规则、活动协议及最新决定。若所在环境已配置 ResearchLab，读取该环境的 README 和共享模板。复用已批准协议、审批和运行登记；不要假设维护者的文件路径在其他机器存在。

不能静默改变研究人群、结局、时间锚点、特征时点、切分、主指标或停止条件。协议变更必须记录并获得科学批准。正式接受结果前进行新的只读复核；文档检查通过不能替代科学批准。

不把患者行、逐行预测、嵌入或凭据放进技能、共享记忆或提示。输出聚合证据与定位。保留失败、中断、阴性和探索性结果。

最小验证：`python3 skills/medical-research-harness/scripts/test_check_bundle.py` 及 `python3 skills/medical-research-harness/scripts/test_study.py`。后者使用隔离的合成清单与模拟运行记录，不执行科研实验。

完整公开回归：`python3 tests/review_probes.py --out build/review-probes`（输出目录须不存在）。外部运行器只可通过显式 `--lab` 参数指定；默认检查不得读取维护者环境。

修改技能时同步其工作流、模板和检查器的阶段角色。保持 Python 标准库实现；不要加入训练、临床服务或自动清洗模块。

实际操作读 `skills/medical-research-harness/references/operations.md`：计划拟合成员只用于执行前检查，正式结果需要绑定具体运行的 executed 拟合审计。不能把“现有文件通过”报告为“数据检查通过”。
