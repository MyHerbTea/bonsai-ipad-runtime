# Build129 同版本单变量性能实验

目标：同一 Build129 派生版本内分别测试普通文本路径的原生 GPU profiling 计数开销和 PTQ1 CPU SDOT 候选，保持同一进程、context、模型与运行参数；仅有真机可靠结果才考虑生产默认。

- 冻结：官方 PTQ1 模型 SHA、16K、Q8_0、batch/ubatch 8/8、56 GPU layers、线程 6、KV unified、Flash Attention、KQV offload；不修改认证、Metal B8、权重量化或隔离的 KV reuse。
- 计数实验：CPU 时钟计数与 Prefill 边界同步均关闭，仅切换原生 GPU profiling 计数，普通生产默认不变；记录 TTFT、端到端、输出、资源、状态与哈希。
- CPU 实验：仅显式请求候选 SDOT（能力校验通过）；相同 native context 下比较生产标量基线及 SDOT；两个 arm 均关闭实验采样和 profiling 计数，严格恢复原 sampling 和 native flags。设备或恢复失败时保持租约并终止，绝不静默回生产。
- 安全：实验互相独立且默认关闭；每次只改变一个候选。中断、状态未知、温度和内存警戒均停止不重试；性能证据必须超出实测漂移、具备输出与数值核验。
- 暂不实现 B8 TensorOps：现有 M>=16 的路径与已冻结 B8 不兼容；不解禁混合架构中已隔离的 KV checkpoint。其设计继续研究，不捏造硬件命中或收益。
- 测试：先验证参数严格拒绝、单变量隔离、恢复失败锁定、计数归零和数值一致；GitHub Actions 构建与符号验证，再进行固定提示 ABBA，保留全部原始证据。
