# Build126 16K + 固定 Q8_0 候选（尚未真机验证）

先用已有侧载工具签名安装同包IPA。导入原官方PTQ1_0模型；在API设置选择16K与“固定 Q8_0”，完全退出后重开，启动API。其他设置维持原样，不启用B16/NAX/Tensor候选。

双击 RUN_Q8_BASELINE.cmd。自动发现地址不唯一时输入一次地址，需要认证时输入一次Key。确认冷启动后自动核验模型/源码/分配tensor、B8/8、GPU56、线程6/mmap，连续四次512/128固定输入、profile/峰值资源、清理和两次普通API。随后只需按提示完全退出并重开App/API，工具核验不同进程，再完成相同请求。工具不会通过HTTP启动被终止的App，也不回放中断请求。

Quick PASS仅为短筛选，分配16K不证明满容量。Quick通过后再双击RUN_Q8_FULL.cmd，额外包含8192/16000实际prompt tokens和至少30分钟容量/连续请求阶段。长输入可能耗时数小时；Full仅证明此范围，不能等同无限长期稳定。32K未开放，不自动扩容。

两种工具各自创建唯一RESULTS目录；完整原始合成请求/结果、配置/模型SHA、源码SHA、同请求profile、资源、前后/失败快照、CSV、manifest与自校验results.zip保留。checkpoint仅本地含会话token，不进ZIP；API Key仅内存使用。不删除旧失败或隔离记录。任何Q4/未知实际类型都失败，恢复旧Q4不会判Q8通过。

生产默认4096/兼容策略保持原样；PTQ1_0是模型权重量化，Q8_0是KV；未改Metal、Batch/UBatch、GPU层、线程、Governor或认证。候选未晋级，尚无Certified Stable声明。读取报告中PASS/FAIL/BLOCKED和具体范围；CI成功不代替M5。

### Quick 中断后的恢复

如果 Quick 被强制退出或 API 在请求中断开，Build126 会保留 `q8_prior_interrupted` 隔离标记，并拒绝重放。不要删除标记、清除 App 数据或覆盖 FAIL 包。先完整保存原 `results.zip`、`OPERATOR_CORRECTION.json` 与诊断文件；更新安装带有恢复端点的候选后，双击 `RUN_Q8_ACKNOWLEDGE.cmd`，选择原 FAIL 目录并核对 M5、源码、模型、实际 Q8 与标记完全匹配。只有在审阅历史结果后，输入 `ACKNOWLEDGE PRESERVED FAILED Q8` 才会让 App 将标记与三个证据 SHA256 写入可读回的诊断快照，再移除运行隔离。该步骤不做推理、不改变当前上下文，也不删除原失败证据。ACKNOWLEDGED 不是测试 PASS；之后必须重新冷启动并新建唯一的 Quick 结果目录。