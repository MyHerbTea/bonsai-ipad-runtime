# Build117 本地结果

已完成本轮本地源码实现与可运行专项验证。仓库分支：`codex/build117-diagnostics`；起点：`4dce38a80ddfbfe186c3af052cb4932012367a70`。

| 内容 | 本地结果 | 后续要求 |
|---|---|---|
| ABBA、漂移、分目标评价、区间与报告 | Python行为测试通过 | 真机5有效轮 |
| 候选命名与兼容 | Python通过，Swift测试已添加 | Swift编译/运行 |
| 原生profiling | 固定Prism补丁重放及源码契约通过 | C++/Metal构建、计数/开销量测 |
| 崩溃存储、启动恢复、诊断API、健康监控 | 源码/测试已写入，独立审查问题已修正 | Apple编译、磁盘/并发/受控崩溃测试 |
| 常亮与iPad布局 | 源码已修改 | iPadOS27真机锁屏、窗口及字体截图 |
| Windows入口 | 4项CMD测试通过；真实便携Python中文/空格路径运行通过 | 与新IPA联测 |
| Build117打包及符号留存 | 身份/UUID规则与合成包装测试通过 | 真实App/dSYM构建及SHA校验 |

专项合计 **47项：43通过、4跳过**（无本地C++/Apple编译器）。全套本地单元回归 **117项：105通过、4失败、1导入错误、7跳过**。四个失败及缺失模块均已在Build116基线上确认，详情与完整命令见[执行日志](execution-log.md)和[evidence](evidence/targeted-final.json)。不能宣称全套测试通过。

没有推送、触发Actions、生成Build117 IPA或执行真机性能测试。Swift/Objective-C++的可编译性尚未由本机证实；这些验证已配置到后续Apple流程。

独立审查的两项Important问题已作源码修正：恢复失败不覆盖旧证据；App/llama符号与UUID证据持续留存。恢复门禁和导出再脱敏的Swift回归仍待运行。备用信号栈只覆盖安装线程，其他线程栈溢出捕获不保证。

继续实施时读取工作区任务表和[使用/验证说明](README.md)，完成其中所有PENDING_DEVICE项后，才可以交付真实IPA和确认阶段完成。
