# M0：默认验证与Hermes集成分层

状态：本轮针对已发现的默认测试安装依赖问题完成修复及复验；不是全部操作系统、Python版本或远程CI验收。未启动训练、未提交、未改生产适配器。

## 修改

- test_hermes_decision_adapter.py：默认单元/契约测试使用隔离合成源码标记，模拟CLI传输，不依赖维护者Hermes安装；保持真实命令构造检查。
- 真实bootstrap集成由 HERMES_ADAPTER_INTEGRATION=1 显式开启。未开启明确skip，开启后缺失或不兼容安装明确失败。
- POSIX进程组与Linux安装集成记录平台限制，不将跳过报告为通过。
- CI的默认adapter检查明确设置 HERMES_ADAPTER_ROOT=/nonexistent、HERMES_ADAPTER_INTEGRATION=0；decision-agent.md 同步操作说明。

## 父代理实际复验

1. 缺安装路径，默认adapter检查：13项被发现，12项通过、1项集成skip，退出码0。
2. 本机真实安装，显式集成开启：13项通过，退出码0；只验证工具定义与执行拒绝，不调用远程模型。
3. 缺安装路径，显式集成开启：12项单元通过，1项集成ERROR（tool_isolation_unavailable），退出码1，符合预期的负例。
4. HERMES_ADAPTER_ROOT=/nonexistent、集成关闭的unittest discover：52项被发现，51项通过、1项显式skip。
5. test_check_bundle.py：PASS；test_study.py：24项通过；git diff --check：退出码0。

实现子代理另报告执行独立回归探测76项通过；本轮父代理未重复其该次运行，不将自报混作父代理执行记录。前一轮父代理已有76项回归通过记录。

## 限制与后续

本轮模拟了不存在的安装root，但未在全新容器/Windows/macOS验证；GitHub Actions未远程执行。Linux Hermes可选适配器仍依赖内部API，安装升级后需重新显式集成。开源发布前补环境矩阵和文档同步。

计算资源见 docs/compute-resource-assessment.md：本机RTX2060 6GiB，Colab MCP已连接测试但未取得云运行时资源。模型暂为候选，不据M0测试直接允许训练。

## 教学要点

单元测试证明局部行为，契约测试证明输入输出与失败规则，集成测试证明真实依赖能协作，科学评价才检验语义判断是否可靠。跳过一个未配置集成是信息，不是成功；显式要求集成后缺依赖必须失败。异常断言需验证具体错误和经过的路径，避免因无关前置失败而假通过。
