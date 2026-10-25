# 当前 Build124 一键SDOT实验

直接双击 RUN_PREFILL_COMPARE.cmd。当前默认64、512/128、A/B各一次预热及ABBA，六次推理。完整步骤见 [中文说明](README_BUILD124_CN.md)。下方Build120/119命令仅保留历史，不是本轮入口。

# Build120：先恢复，再只测 flag16

当前主线只运行 flag16 的一轮独立 Quick ABBA，不使用下方历史三个候选的默认命令。512输入、128正式输出，每槽两次预热，共12次推理；45分钟预算，异常/身份变化/恢复失败立即停止，不自动重试或加轮。

Build119主动API取消造成的Quick隔离，需要安装本包配对Build120后显式确认。保留原App数据，不卸载，不冒用manual_forced_exit。先确认API、模型与源身份，再执行：

```powershell
.\python\python.exe -X utf8 .\acknowledge_quick_interruption.py --url http://192.168.1.92:8080 --reason operator_confirmed_api_cancel --cancel-evidence D:\codexSpace\iPad27B\docs\build119\device\20261023T080803Z --output D:\codexSpace\iPad27B\docs\build120\device\NEW_RUN\api-cancel-ack.json
```

工具核对原before/cancel/after/report及完整隔离标记，绑定当前接收确认的源/进程。历史取消与当前IPA身份分别记录。服务端先保存并从DiagnosticStore读回审计，再仅解除匹配Quick标记，B16保留。该读回是服务端内部验证，未提供独立HTTP快照导出。请求丢失或读回失败保留attempt/response文件，不自动重发确认。

解除确认通过后，使用新的输出目录：

```powershell
.\python\python.exe -X utf8 .\prefill_compare.py --url http://192.168.1.92:8080 --rounds 1 --prompt-tokens 512 --candidates 16 --output D:\codexSpace\iPad27B\docs\build120\device\NEW_RUN\flag16
```

NEW_RUN必须是本次新目录，不拼接Build119的旧配对，不自动晋级配置。以下Build119说明保留为历史使用参考。

## Build119 集中优化对比（历史）

同一IPA包含原始CPU算法、CPU查表解码（8）、ARM NEON解码/整数点积（16）及已有输入batch缓存复用（4）。生产默认不变。8/16不能同时开启；本入口只比较独立候选，不启用TensorOps或R5，不调整GPU层数/线程/模型精度。

先安装本包配对的Build119 unsigned IPA（使用已有签名方式），启动API并保持前台。进入完整测试包目录，集中运行：

```powershell
.\RUN_PREFILL_COMPARE.cmd --url http://192.168.1.92:8080
```

默认在16K/B8/Q4做512输入/128输出、每候选一轮A1/B1/B2/A2；每slot先两次512输入、最多256输出的预热。三个候选一起测试，实际耗时取决于设备，远超过一次普通请求。每轮输出长度、哈希/logits、GPU完成、实际配置、CPU候选命中、温度及内存均需符合契约。无实际CPU命中不是收益证据。

结果统一保存在新建的RESULTS/prefill-时间目录；COMPARISON.md横向展示Prefill、首内容、Decode变化，report.json提供原始数据、CPU计数和漂移。正数改善、负数退步。一个有效轮仅是Quick探索，不能晋级；有希望的候选可用 `--rounds 5 --candidates 8`（或16/4）确认，长输入单独用 `--prompt-tokens 2048`。这些仍不等于完整Full质量/持续回归。

旧B16隔离标记保持不变。Quick请求未完成、执行异常或校验抛错时，其标记也会阻止再测，不能删除或反复触发；即使生产上下文恢复成功仍保留故障标记。只有已确定结束但统计漂移导致无效的轮次，不按未知故障隔离。断流/超时不重放，停止本轮并保留检查点；恢复失败保留租约/不提供普通推理。客户端失联后watchdog恢复也保留Quick标记。使用新的输出目录，避免混合版本/阶段结果。

正式入口RUN_BONSAI_PTQ1_ONECLICK_BENCHMARK仍使用B16，受旧隔离保护，不应用来替代本轮B8实验。没有自动默认配置更改，也没有预先宣称性能提升。

## Build119 人工中断恢复与进度

长预填充现在每15秒输出实际PREFILL/DECODE token进度，不将心跳计入首内容延迟。人工强退后需先显式审计确认（仅在操作者已确认时使用）：

```powershell
.\python\python.exe -X utf8 .\acknowledge_quick_interruption.py --url http://192.168.1.92:8080 --reason manual_forced_exit --output manual-interruption-ack.json
```

此操作验证当前源码/进程/完整Quick标记，先保存本地非致命审计快照，再仅清除该Quick标记；旧B16不动，且不运行推理。不能用来确认自动崩溃或未知根因。进程已重启时原始测试不能报RESTORED，原始失败报告不改写。随后使用新的输出目录重新进行测试。
