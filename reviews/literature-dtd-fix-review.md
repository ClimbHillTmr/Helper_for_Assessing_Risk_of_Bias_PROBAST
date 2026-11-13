# DTD解析修复：限定范围PASS

2026-10-20。独立只读复核 `deleg_24e2b7a8`，运行时记录模型 `devin/swe-2`；父代理再次执行边界测试，9项全部通过。此结论只关闭已发现的内部DTD许可属性注入及相关解析绕过，不认证完整产品安全或医学语义。

## 实现与证据

`skills/medical-research-harness/scripts/literature.py` 的parse_jats先进行原有ENTITY字节检查，再由标准库Expat的StartDoctypeDeclHandler拒绝has_internal_subset。参数实体解析设为NEVER，外部内容回调跳过读取。guard通过后才调用ElementTree。ContractError不被解析异常捕获分支吞掉。

独立复核报告9项边界测试通过，并额外验证：UTF-16内部子集/ENTITY、单引号SYSTEM标识中的`>`、PUBLIC标识中的`>`均拒绝；外部DTD加正文未定义实体报invalid_xml；普通无DOCTYPE文档可解析。父代理本轮重跑 `python3 tests/test_literature_boundaries.py`，9项OK；`git diff --check`通过。此前父代理已实际运行两篇公开输入dry-run，见 `build/literature-dry-expat-fixed/finish.json`，completion_verified true。

## 状态与限制

前次“扫描全raw即修复”被后续绕过推翻的记录保留；当前PASS针对Expat版本，不追授旧版本。原真实模型运行保持其旧源码身份，两输入均无内部子集，不覆盖其报告。

全文产品仍为PARTIAL，未完成附件发现/许可核查/解析、中断恢复、原始响应字节留存及完整P1/P2契约。不作科学接受、不宣称OS沙箱或全面安全。
