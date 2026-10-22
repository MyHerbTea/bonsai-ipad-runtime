# Build114：PTQ1 同进程竞赛候选

对象仅为 M5 iPad Pro / 12GB，官方 `Ternary-Bonsai-2-27B-PTQ1_0.gguf`。
源码基线为 `32c479fb62f63f1172df2f912239135bf2250ebb`，Prism 固定在 `adfffbe41b2cabcd51fff326ab045662265062bb`；开发分支 `codex/ptq1-oneclick-tournament`。不合并 main，不发布 Stable。

## 实际审计及实现

- 上游 PTQ1 mat-vec 已在寄存器中解码三值字节并做点积；Hadamard 属于相邻图算子。本轮没有把已有融合冒充新实现，也没有改动 Hadamard 数学。
- 新原生候选实例化独立的五行 mat-vec pipeline，复用同一组激活系数，替代候选路径中四行一组的分派；补齐五行尾块的越界读取保护。收益取决于实际寄存器压力和设备测量。
- TensorOps 沿用已实现的 PTQ1 kernel；修复进程首次注册禁用 Tensor 后同进程无法命中的问题。不可变生产 registry 保持原样，另行捕获硬件/源码能力，使用 benchmark 专属宏和原子策略掩码选择路径。真实门禁包括 PTQ1/F32、M5、K%128、M%16、N>=128、维度及 stride。
- LOW_OVERHEAD 复用预填充与逐 token decode 的 `llama_batch` 存储，减少现有循环中的反复分配释放；记录真实分配和复用次数。
- SAFE_BASELINE 强制关闭以上候选策略；要求模型启动于生产 Tensor-disabled registry，避免混入旧实验启动臂。
- BEST_COMBINATION 仅由已实测具有独立收益且满足数值、内存和解码约束的组件构造，再独立通过完整门槛。

## 生命周期与证据

只保留一个 PTQ1 模型实例。候选切换先等待 GPU，再释放旧 context/KV，设置独立原生策略，重建 context，并读取真实 n_ctx/n_batch/n_ubatch/序列数与创建时 K/V 类型。失败配置隔离并尝试回滚；取消标志与状态锁不依赖被同步推理占用的 actor。普通 API 与 UI/vision 操作在 benchmark 持有租约时被拒绝。

原生 ABI 记录真实 command buffer 提交、完成与错误，区别于 dispatch 入队。每次请求另有首个命中算子的 K/M/N、权重/激活/输出步长和 pipeline 名称。Metal pipeline 缓存属于模型后端的共享资源，保留以避免重复编译；context 临时资源在切换时释放。初始基线峰值约束覆盖保留缓存导致的内存增长。

记录 50ms 采样 footprint 峰值、系统进程生命期 resident 峰值、Metal 分配、最小可用内存和热状态。采样峰值不等于未采样的绝对瞬时峰值。上下文重建阶段也单独采样。

官方资产清单在 `tools/ptq1_official_model.json`：revision `b072e1d3b35a0a630cece372c2127528e0994386`，文件 5,946,648,928 字节，SHA256 `53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3`。App 和工具均要求完整模型 SHA256，工具同时核验同包 IPA、源码、构建号及交付文件校验和。

## 一键竞赛

入口只有 `RUN_BONSAI_PTQ1_ONECLICK_BENCHMARK.cmd`。复用旧 Quick TestKit 的地址规范化和 ZIP 校验组件，附带固定哈希的官方便携 Python。

流程：16K/B16/Q4/FA/seq1 预热与实际约512输入 token 筛选；最多两个候选与基线进行约2048输入 token、每臂至少3个有效样本的交错比较；合格组件组合独立复验；固定实现进行8K/16K/32K、B8/B16调优，B24及Q8仅在能力/内存允许时追加。128输出 token 仅用于微基准。

质量集另用1024输出预算，覆盖中文约束、整数数学、受限 Python 独立进程执行、多轮、JSON和真实长输入定位。推理采用确定性、reasoning_effort=none；本轮不据此宣称覆盖模型的全部思考能力。持续检查默认30分钟，可选60分钟，包括真实取消、上下文释放重建和长请求。模型权重未重新量化。

验收保留预填充+15%、TTFT+10%、解码不低于95%、新增观察峰值<=1GiB与>=512MiB实际余量、严格确定性输出哈希、有限 logits、质量与完整率及持续稳定性。没有全部合格候选保留生产安全基线；缺失证据为 INCOMPLETE。成功结束后恢复原始生产配置并核对真实参数。

断流/超时不重放推理；保存检查点并隔离不确定配置。App 已被系统终止时 HTTP 无法启动它，需要用户只重新打开一次，再运行同一入口。若基线本身已被隔离，停止而非反复触发同一故障。

## 构建与验证边界

`.github/workflows/build-ptq1-tournament.yml` 在 macOS 执行 Swift 状态机/故障恢复行为测试、Python HTTP断流/脱敏/门槛/打包测试、Prism真实 C++控制逻辑与 codec 测试、原生 XCFramework 和 Release app 编译、二进制 ABI 核验、单 ZIP 打包与校验。

交付为一个 Actions artifact，内有一份 unsigned IPA、一键入口、便携 Python、身份清单与 CI 日志。仓库没有用户签名证书，IPA 需要用用户现有侧载方式签名安装一次。

截至源代码编写时，没有连接 M5 真机。设备上的 Metal 源码编译、实际路由完成、数值、性能、任务质量和持续稳定性必须以一键工具生成的真实报告为准。CI 成功只证明构建和所运行的自动化测试。

二进制核验分别要求原生框架的 dlsym 目标为全局导出，以及 App 直接链接的桥接函数存在于已定义代码符号表；后者经链接器本地化属于正常行为，不等于接口缺失。
