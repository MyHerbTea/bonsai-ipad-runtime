# Build128 Q8 Metal B8 性能 Quick

Build128 延续同一台 M5 iPad、同一份 PTQ1_0 模型与 16K/B8/Q8_0 配置，只比较现有 Metal 路径与新增 Metal B8 路径：

- A：flags 64，CPU SDOT 保持开启。
- B：flags 320，CPU 仍只收到 flags 64；额外的 256 只选择 PTQ1_0 Metal B8。

PTQ1_0 是模型权重量化；Q8_0 是 K/V 缓存量化。本候选不调整模型、上下文、Batch/UBatch、GPU Layers、线程、mmap、Flash Attention 或生产默认。

## Quick 范围

首轮 Quick 使用同一份固定 128-token 输入、32-token 输出上限和四请求 A-B-B-A 顺序。单请求上限 60 秒，测量全程上限 240 秒。128 个 token 足以产生 16 个 B8 行组，可先判断候选是否值得扩大测量；只有本轮明确胜出后才考虑 512-token 后续确认。本轮不重复 600 秒的长输入 Full。每次只在实际分配 KV 张量为 Q8_0、候选 dispatch 计数有效且无 fallback 时采纳样本。

运行 `RUN_Q8_METAL_B8_QUICK.cmd`，按提示确认冷启动和 API 地址。工具保存原始输入/输出、模型与源码身份、实际 KV 类型、路由计数、预填充/解码、内存、温度和恢复结果。至少 3% 的预填充收益需超过观测漂移，且正确性、解码、内存、温度与恢复检查都满足，才记为 `QUICK_PASS`。Quick 不证明满 16K 输入可用或长期稳定。

双击 RUN_Q8_ACKNOWLEDGE.cmd 后，按提示依次输入 Build126 失败目录和独立更正 JSON 文件路径；工具自动发现 API。

Build126 的人工中止隔离仍须先由 `RUN_Q8_ACKNOWLEDGE.cmd` 通过完整 ZIP、报告、4 条 Q8 原始样本、更正记录和当前 Build128/M5 状态核验后解除。恢复步骤只保存审计快照并移除那一个已核验的 Q8 标记，不发送推理请求，也不触碰原失败证据。ACKNOWLEDGED 不是性能通过。

任何超时或用户中止都保留原始结果和隔离标记；不重放结果不确定的请求，不自动切换 Q4_0。生产默认不变；不据此宣称 Full、Certified Stable 或发布完成。
