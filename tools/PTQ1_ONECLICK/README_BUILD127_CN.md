# Build127 固定 Q8 + PTQ1 Metal B8 Quick TestKit

本候选只比较同一台 M5 iPad、同一份 PTQ1_0 模型与 16K/B8/Q8_0 KV Cache 下的两条 Metal 小批量路径：

- A：现有 PTQ1_0 路径，flags 64（CPU SDOT 保持开启）
- B：新增 PTQ1_0 Metal B8 路径，flags 320（CPU 仍只收到 flags 64；额外的 256 仅控制 M5 Metal 路由）

PTQ1_0 是模型权重量化；Q8_0 是 K/V 缓存量化。此候选不修改模型、KV 类型、上下文长度、Batch/UBatch、GPU Layers、线程、mmap、Flash Attention 或生产默认。

## 运行范围

1. 使用本 TestKit 对应 Build127 IPA 与官方模型 SHA。模型、源码 SHA 或构建号不一致时工具会拒绝运行。
2. App 完全冷启动，选 16K + 固定 Q8_0，启动本地 API。
3. 双击 RUN_Q8_METAL_B8_QUICK.cmd，输入 API 地址（如果自动发现失败），按提示键入 COLD。
4. 工具执行四请求 A-B-B-A 短筛选：每次约 128 prompt tokens、32 output tokens，总时限 10 分钟；之后核验恢复与普通 API。

结果位于唯一 RESULTS/Build127-Q8-Metal-B8-* 目录，含输入/原始输出、请求配置、实际 KV 张量读回、每请求候选 route/pipeline/dispatch/fallback 计数、性能/内存/热状态、恢复快照、manifest 与自校验 ZIP。只在实际 Q8_0、候选 dispatch 可见、fallback 为零、输入/输出一致且候选收益超过观测漂移至少 3 个百分点时，状态才为 QUICK_PASS。

QUICK_PASS 只是短筛选，不是 Full、长期稳定或 Certified Stable。NO_SAFE_WIN 表示本次没有足够安全的收益；不自动转测 32K，也不改变默认。任何 FAIL/中断都保留原始证据与隔离标记；不要删除证据、清除 App 数据或重放不确定请求。