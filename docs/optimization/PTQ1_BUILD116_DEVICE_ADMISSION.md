# Build116：真机预检发现的入场条件修复

## Build115 真机事实

用户安装 Build115 后，API 与 benchmark 接口均返回 HTTP200。设备报告 `Apple M5 GPU`、`iPad17,1`、12,084,002,816 字节物理内存；App source 为 `404e6972d645ac6ade9880dc02b15590f8d7e8d8`，context 16384、B8/UB8、Q4_0、FA、mmap、seq1、请求 GPU layers=56。官方 PTQ1 模型完整 SHA256/大小匹配，热状态为 nominal。此次确认 API 启动成功，不构成持续稳定性或性能认证。

配套工具实际执行后得到 HTTP409，0 推理样本。服务状态明确记录 `WAIT_FOR_OFFICIAL_MODEL_HASH_AND_FULL_GPU_MMAP`，active=false/running=false，原 context 保留。诊断与原始结果留在用户的 `Bonsai-Build115-RESULTS`；没有执行推理或自动晋级配置。

## 两处根因与修复

1. benchmarkStart 错把请求 GPU 层数 >=99 当成全 GPU 证明，而已验证的 16K 生产启动策略会限制到56。规格要求使用现有稳定模型作基线、同进程保留单模型，并不要求重载模型改变放置方式。Build116 允许现有 mmap 且正数 GPU 层请求的模型，仍严格核对官方模型哈希、PTQ1 格式、参数规模、设备与安全 Tensor-disabled 启动。候选间保持同一模型放置。证据新增请求 GPU 层数、模型层数及“配置时观察”的范围，不声称已测量全部层实际驻留 GPU。
2. pinned Prism 解析 `Apple M5`，使用完整字符串精确比较，不接受真机的 `Apple M5 GPU`，因此识别为 GENERIC。能力发布要求 M5，结果为0。Build116 只移除精确的末尾 ` GPU` 再做原表精确匹配；未知型号、非 Apple 前缀或任意尾部文本仍为 GENERIC。生产 Tensor 禁用策略保持原样，候选仍需真实 pipeline/shape/完成证据。

GPU 名称归一化会使相关硬件选择正确识别 iPad M5，最终 kernel 行为仍需要真实设备验证。没有修改模型精度、KV 类型和生产 Context/Batch 默认值。Build115 调度器恢复修复继续保留。

## 验证边界

两项新回归在修复前失败。macOS CI 编译执行原始原生 parser（包含真实型号表），验证 M5/M5 GPU/M5 Pro GPU 及未知名称；Swift 行为测试确认56和99允许、0/负数/非mmap拒绝。Windows 无 C++/Swift 编译器，相关执行由 CI 完成。本机运行源码回归、打包、真实 CMD、原生已有专项与文档范围检查。

Build116 真机状态 **NOT_RUN**。需要安装同包 IPA 后先核对 capabilities 与 start，再执行完整竞赛，才能生成速度、精度和稳定性结论。
