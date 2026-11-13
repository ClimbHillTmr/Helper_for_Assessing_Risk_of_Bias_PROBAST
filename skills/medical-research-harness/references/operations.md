# 从研究问题到实际操作

当用户要求推进研究时，按下面的顺序留下可运行的产物。先读取目标项目的协议、数据生成路径和既有命令；从用户目标补齐设计决策，不能只返回通用检查表。

## 只有公开文献时

使用 [literature.md](literature.md) 的独立文献入口，不要求不存在的研究清单或实验审批。全文身份、许可和外发范围必须与实际输入绑定，引用校验通过不等于结论正确；文献分析结果不能作为下列 executed 审计。

## 第一次接手研究

1. 在目标项目确认数据发布身份、入组与分析单位、结局和实际可用时间、切分及已有实验。把“已确定、缺证据、需要决策”分别写进工作记录。
2. 按 `workflow.md` 形成具体的处理顺序、主分析和敏感性任务；用 `assets/protocol.md` 固定研究问题。引用已有批准，不静默替换旧协议。
3. 在已授权的数据准备范围内生成行元数据和固定折清单，再用 `assets/example_study.json` 的结构写入目标项目 `study.json`。没有数据时先完成协议草案；任务编译需要实际清单来冻结身份。示例是软件合成案例，其研究问题、指标、命令和批准记录都不能用于真实研究。
4. 每个任务的 command 必须指向目标项目的实际入口；缺少适配器时，在已授权范围内实现它并做聚合检查。未获得数据访问/实验授权时可以完成设计与代码，明确指出阻塞执行的具体条件。
5. 调用下列命令并读取产物。出现退出码 1/2 时先处理指出的问题；不能只改报告的 PASS 字段。

脚本绝对路径为 `<skill>/scripts/study.py`，下文用 `study.py` 简写。所有 `--out` 均须不存在；不会覆盖旧运行证据。所有命令都不执行训练或清洗。

## 自动串联现有检查

已有研究优先使用 [automation.md](automation.md) 的 `workflow.py --plan ... --phase preflight|results --out ...`。它复用下述函数，明确记录未执行/阻塞项，生成 workflow.json 和后续动作；不启动训练、不修改批准或旧计划。需要排查单项时再使用下述原子命令。证据包阶段、研究身份及协议必须匹配，既有阶段角色要求不变。

## 1. plan：生成可交给现有 runner 的任务

```bash
python3 <skill>/scripts/study.py plan /study/study.json --out /study/plan-v1
```

`study.json` 包含 `study_id`、`protocol`、`manifests`、`task_template`、`experiments`、`audit`。`manifests` 指向已有的 rows、folds 文件；相对路径相对 study.json。`task_template` 使用 ResearchLab 的任务规格字段；每项 experiment 明确 id、purpose、model、seed、parameters 和 command（argv 数组）。不得把主终点、入组或切分变化藏进参数对照。真实任务需由 agent 检查命令语义与协议一致。

输出 `plan.json` 和每项实验的 task JSON。协议、配置、行清单和折清单身份进入任务指纹，批准字段初始为 DRAFT。后续每次读取计划，均从原配置重建预期计划并核对完整实验集合；不能删去一个任务来隐去 NOT_RUN。批准的协议锁必须包含协议及原 rows/folds 三份文件的路径与哈希。添加真实的已有科学批准后，原有 runner 可校验并运行这些任务；生成命令本身不会授予批准。已经批准且无需改变的现有任务直接沿用，避免重新登记重复实验。

固定清单按字节哈希识别，重排/改写文件也会改变身份。需要变更队列或切分时走已批准的修订流程，创建新版本并保留旧计划和汇总；不要为了检查通过而重跑已完成的有效实验。

当前审计路径明确限定为：患者互斥的预测研究、固定外层切分、完整的内部折成员表、所有实验共享协议切分。重复患者未来预测、带间隔排除的时间交叉验证等需要专用适配和审查，不要通过改成患者互斥来改变原研究问题。

## 2. audit：检查计划的分区与实际拟合证据

在目标项目用既有数据栈导出三个私有 CSV。这里是审计接口，不要求改变原始数据格式；也不把 CSV 内容放入聊天、skill 或共享记忆。

| 文件 | 精确字段 | 由什么产生 |
|---|---|---|
| rows.csv | row_id, patient_id, split, index_time, feature_max_time, label_start_time, label_end_time | 已批准队列、标签算法及最终特征可用性清单；每条分析记录一行 |
| folds.csv | fold_id, row_id, role | 固定的内部折定义；role 为 train / validation |
| fits.csv | experiment_id, operation, fold_id, row_id | 计划阶段来自允许拟合的成员表；运行后来自每个实际 fit 调用的记录 |

时间必须包含时区，支持 ISO 8601。`feature_max_time` 是该记录全部最终输入实际可用时点的最大值，不能拿采集时间代替发布/可用时间。必须另行核对字段覆盖完整性、病例数量及导出器和真实代码的对应关系。

`audit.split_order` 从 train 开始，至少两组，每组非空。`patient_disjoint` 本版必须 true。`chronological=true` 要求前一组所有索引和标签窗结束都严格早于后一组最早索引；边界允许相接的协议不适用这个严格策略。`label_start=after_index` 要求窗起点晚于索引；`at_index` 要求等于索引。结束必须晚于起点。这些是显式配置规则，不能替代研究者定义诊断/预后目标。

每个 fold 都要覆盖全部外层 train 记录；除保留名 `final` 外，必须有训练和验证成员。`final` 用于在全部允许的开发记录上最终拟合。`expected_fits` 逐项列明 experiment_id、operation、fold_id，覆盖所有实验和全部拟合操作，例如填补、缩放、筛选、重采样、调参/模型及校准；漏掉整个声明操作会被拒绝。每条日志只能引用该折 train 成员，外层保留集不能进入开发折。

执行前检查计划的拟合成员：

```bash
python3 <skill>/scripts/study.py audit /study/plan-v1/plan.json \
  --mode planned --rows /study/rows.csv --folds /study/folds.csv \
  --fits /study/planned-fits.csv --out /study/planned-audit.json
```

输出违例计数和对应修复动作：患者重叠、内部折患者重叠、未来特征、标签时间、跨时期标签窗口、未声明分区、不完整折成员、缺少拟合操作、拟合越界，以及相对已冻结行/折清单的身份变化。计划成员检查只能核验执行方案。

实际运行中，每次 fit 调用记录真实输入 row_id。在运行目录输出实际拟合日志，按单个实验和 run_id 再审计：

```bash
python3 <skill>/scripts/study.py audit /study/plan-v1/plan.json \
  --mode executed --experiment-id baseline --run-id ACTUAL-RUN-ID \
  --rows /study/rows.csv --folds /study/folds.csv \
  --fits /run/actual-fits.csv --out /run/audit.json
```

运行后 fits.csv 仅含该实验的真实记录；审计仍核对对应实验全部声明操作。汇总核验时从其引用的清单重新计算 executed 审计，不能通过修改 PASS 字段或更新哈希跳过违例检查；重算仍不认证日志确实来自实际 fit。计划清单不能替代 actual fit 日志，结果汇总会拒绝 mode=planned 的替代物。

## 3. preflight：接入现有审批与协议锁

```bash
python3 <skill>/scripts/study.py preflight /study/plan-v1/plan.json \
  --audit /study/planned-audit.json --lab /absolute/path/to/lab.py \
  --out /study/preflight.json
```

先核对计划审计与当前输入哈希，以及相对已冻结行/折的身份，并重新计算审计以核对完整报告。本地拒绝非 APPROVED 或缺少批准者/证据字段的任务，检查锁后再调用已有 `lab.py validate-task`。未批准的 DRAFT、协议锁缺少协议/行/折身份、清单变更、审计失败都会阻止检查通过。批准与锁必须来自实际科学决定；不能复制演示里的模拟批准。`lab.py` 路径由调用者指定，需使用受信任的既有 runner。

通过后，在既有批准范围内由 ResearchLab `run` 管理运行、登记、资源和输出。这里的 preflight 不启动实验，也不能认证批准者身份或替代运行时监督。每次实际拟合后仍需 executed 审计；无需为首次执行预先伪造运行日志。

本包不分发 ResearchLab。兼容校验器的调用接口是 `python <lab.py> validate-task <task.json>`；验证通过返回 0，未获授权、任务不完整或锁无效必须返回非零。它应核对真实的批准记录、任务字段、目标项目和锁中每个文件的哈希。`example_study.json` 包含任务字段示例，禁止直接采用其中的模拟批准。没有兼容工具时可独立使用 plan/audit/summarize，但必须明确未执行外部审批校验。脚本只接受用户明确指定的受信任校验器路径，不下载或搜索运行器。

## 4. summarize：把运行登记与实际结果对账

本版直接读取 ResearchLab 的 `run-directory/start.json`、`finish.json`，不另建登记系统。读取其 task、protocol、git_commit、git_status、run_id、status 和 exit_code。git_status 必须是存在的字符串，空串才表示记录为干净；脏代码需要额外的 64 位小写十六进制 code_snapshot_sha256。每个终态必须有整数 exit_code 和 reason（允许 null），成功必须为零，失败/中断/无效必须非零。失败重试各有独立目录。共享 registry 只汇总任务 ID 属于该计划或明确标记同一 study_id 的运行。

成功运行另提供 `audit.json`（上述 executed 审计）与 `metrics.json`。后者是聚合指标，精确字段：

```json
{
  "run_id": "ACTUAL-RUN-ID",
  "task_design_sha256": "从 plan.json 对应 task 条目取得的 design_sha256",
  "name": "协议的 primary_metric.name",
  "estimate": 0.72,
  "lower": 0.61,
  "upper": 0.80,
  "n": 100,
  "ci_method": "实际采用的区间方法、重采样单位与参数"
}
```

以上数字仅示意。指标和区间必须由目标项目按批准方法计算；本命令不计算预测性能。n 为该估计的分析分母；事件数、删失和次指标保留在目标项目报告及正式结果表中。本版检查主指标身份、有限数值、区间顺序及正整数分母，不判断区间方法的统计适用性。

```bash
python3 <skill>/scripts/study.py summarize /study/plan-v1/plan.json \
  --runs /study/registry/runs --out /study/summary-v1
```

输出 `summary.json` 和 `summary.md`。每次尝试独立占行并保留退出码和私有 finish 记录定位；不复制可能含敏感数据的错误原文。失败/中断无成功指标，缺 finish 显式为 RUNNING（表示未获得终态记录，不证明进程还活着），计划中尚无尝试的任务为 NOT_RUN。错误 run_id、任务漂移、缺少/过期/错绑的 executed 审计、折清单替换、代码状态缺失、终态证据不完整、缺少指标和协议锁不匹配会形成问题并返回非零。报告会保留失败实验；科学结论仍由逐题偏倚评估和复核决定。

退出码：0=该命令的检查通过，1=产物包含明确未解决问题，2=输入无效、身份变化或输出冲突。所有状态都不表示临床有效或获批。被提供的 registry 是否涵盖实际全部尝试，仍须与原登记源核对。

## 可重复的操作演示

```bash
python3 <skill>/scripts/test_study.py --out /tmp/medical-harness-demo
```

默认生成完整合成材料、计划、已知缺陷审计和模拟运行汇总，运行 24 项核心检查，明确跳过外部校验器集成。只有显式增加 `--lab /absolute/path/to/lab.py` 时才运行额外 3 项 validate-task 集成检查，绝不调用 run。所有模拟批准和指标仅在隔离演示目录中；传入不存在的 --lab 路径会报错，不会被当成已通过或静默跳过。
