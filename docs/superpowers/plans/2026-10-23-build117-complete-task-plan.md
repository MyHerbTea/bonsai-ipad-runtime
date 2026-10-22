# Build 117 完整阶段任务与执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成可靠的性能测量、原生 profiling、候选命名、测试常亮、iPadOS 27 界面适配和可追因的本地崩溃诊断，交付可核验的 Build 117 与 Windows 一键测试包。

**Architecture:** Python 负责测量编排和报告；Swift 负责应用状态、诊断存储与 UI；Objective-C++/原生 Metal 层提供真实执行计数与计时。通过版本化 JSON、稳定候选 ID 和关联 ID 联结各层；致命异常仅采集安全的最小信息，完整报告在下次启动组装。

**Tech Stack:** Python、Windows CMD、Swift/SwiftUI、Objective-C++、现有 llama/ggml/Metal 后端、Xcode、iPad 真机。沿用项目现有依赖和测试框架。

**Spec:** [原始需求全文](2026-10-23-build117-original-requirements.txt)。该文件是需求来源，其中示例数据、推测和伪代码不等于已验证能力；执行口径以本文明确的规则为准。

创建时间：2026-10-23，Asia/Shanghai。本地实施已启动；状态与证据见下表。用户已选择本轮先完成本地代码与可运行验证，Apple构建及真机验收另行进行。

## 全局约束

- 不改变模型精度、推理参数或核心算法；保留原有质量、安全、身份与配置核验，调整性能评价不能绕过这些核验。
- 基于确认的源码版本开发 Build 117；保留 Build 114–116 包及结果，不覆盖历史证据。
- 候选原始值 0/1/2/4 不变，旧名称、旧 API 和历史报告可读；1 保留原有能力/占位语义，不能随重命名误删。
- 默认本地存储，不自动上传；可选上传和独立设置页、常亮 API 不是本阶段完成的必要条件。
- 不默认记录提示词、回答正文、API Key、Authorization、用户绝对路径；关联 ID 使用不携带身份的随机值。
- 不把不可采集数据写成 0，不伪造堆栈、设备名称、GPU 时间、利用率、碎片率或根因。缺失字段为 null，并提供 availability/reason/source。
- 不直接照搬原文致命崩溃回调里创建 Swift 对象、JSON 编码、文件遍历或调用单例的做法。SIGKILL、OOM/Jetsam、断电不能保证执行回调。
- Windows 不能替代 Xcode 编译、签名和真机验证。无证据项保持 BLOCKED 或 PENDING_DEVICE，不能声称全阶段完成。
- 不自行提高最低系统版本、开启文件共享权限、引入第三方崩溃服务或改变生产默认配置；确有必要时记录依据和影响。

## 当前本地事实与执行入口

已发现 `Bonsai-Build116-PTQ1/ptq1_oneclick.py`、CMD 入口、README、unsigned IPA、历史 Build 包及 `Bonsai-Build116-RESULTS/current/`。本次文件搜索未发现 Swift 源码、Xcode 工程或 AGENTS.md。README 标题仍写 Build114，交付身份一致性必须核验。

原需求提到的 `BonsaiLab/` 和 `tools/PTQ1_ONECLICK/` 是源码侧预期路径，当前尚未证实。T00 必须记录真实仓库、提交、路径和构建方式，再更新下面路径映射，不能在测试包旁创建假工程来声称完成 App 改动。

建议交付目录：`Bonsai-Build117-PTQ1/`；证据目录：`docs/build117/evidence/`；执行日志：`docs/build117/execution-log.md`。执行时才创建这些目录。

## 执行协议与持久化状态

1. 首先读取本文、原始需求及实际仓库适用的 AGENTS.md；检查工作区改动，保护用户已有修改。
2. 顺序执行 T00–T11；每次开始任务和验证结束后更新任务表。可执行内容持续推进，单项阻塞不应阻止无依赖任务。
3. 状态仅使用 TODO、IN_PROGRESS、DONE、BLOCKED、PENDING_DEVICE。DONE 必须有产物路径、实际验证命令/步骤、结果和证据。
4. 中断后从首个未完成且依赖满足的任务恢复；先核对已有产物，不重复跑耗时真机任务，不重放结果不确定的推理。
5. 日志每条记录时间、任务 ID、源码 SHA、改动文件、验证结果、证据路径、阻塞原因和下一步。命令输出必须脱敏。
6. 对明确的实现选择按本文默认值执行；仅外部访问、源码/设备缺失或真实需求冲突需要询问。构建/真机不可用时完成其余工作，提交准确的阻塞清单。
7. 所有必需任务 DONE 且验收矩阵通过才可声明完成；不因收益很小或没有候选晋级而虚构胜出者。

## 任务总表

| ID | 任务 | 依赖 | 状态 | 完成证据（执行时填写） |
|---|---|---|---|---|
| T00 | 源码、环境、历史基线与文件映射 | 无 | DONE | bonsai-ipad-runtime/docs/build117/source-map.md；baseline-oneclick.txt |
| T01 | 候选命名、兼容与 JSON 契约 | T00 | PENDING_DEVICE | 候选别名/目标已实现；Python测试通过，Swift测试待Apple编译 |
| T02 | A/B/B/A、漂移和恢复 | T01 | DONE | ABBA采样与恢复代码；abba-green.txt、drift测试；真实设备交由T10 |
| T03 | 按目标评价、统计和报告 | T02 | DONE | measurement.py与目标/分级/区间报告；thresholds-final.txt |
| T04 | 原生计数和分阶段 profiling | T01 | PENDING_DEVICE | 原生补丁重放通过；profile-final.txt；Metal计时与开销待测 |
| T05 | 诊断模型、持久化和留存 | T01 | PENDING_DEVICE | Codable模型/原子存储/留存/Markdown；Swift行为测试待编译 |
| T06 | 崩溃采集、恢复和关键埋点 | T04,T05 | PENDING_DEVICE | 最小信号记录、启动恢复与埋点；独立子进程测试待Apple运行 |
| T07 | 诊断 API 与健康监控 | T06 | PENDING_DEVICE | 诊断路由与健康监控已接入；Apple端认证/并发/错误运行测试待测 |
| T08 | 屏幕常亮与状态持久化 | T00 | PENDING_DEVICE | 常亮偏好与唯一主线程协调器已接入；真机锁屏待测 |
| T09 | iPadOS 27 界面适配 | T08 | PENDING_DEVICE | 窄窗口/动态字体布局已修改；截图及SDK编译告警待测 |
| T10 | 集成、回归和真机验证 | T03,T04,T07,T09 | PENDING_DEVICE | 专项43通过/4跳过；全套117项有4个基线失败/1个基线导入错误；独立审查修正已落盘，Apple验证待测 |
| T11 | 构建、交付包和使用文档 | T10 | PENDING_DEVICE | Build117打包与CI配置已更新；合成包装测试通过；无真实IPA |

## Review Focus

1. 时间漂移、热状态、进程重启或网络断连导致样本不可比：T02 验证中断轮不能混入有效收益。
2. 阈值边界、零基线、NaN、小样本产生伪收益：T03 验证边界和不足证据状态。
3. 多请求并发导致计数和报告串线：T04/T06 验证 request/run/context 作用域及计数复位。
4. 低内存、磁盘满或损坏尾记录让诊断系统二次崩溃：T05/T06 验证限额、恢复和降级。
5. 调试 API 泄漏敏感数据或越权读写文件：T07 验证认证、ID 校验、删除边界和脱敏。

## T00：确认真实起点

**文件：** 读取 Build116 的脚本、README、TestKitIdentity.json、DELIVERY_SHA256.json、现有报告和实际源码构建配置；产出 `docs/build117/source-map.md`。

- [x] 核对实际目录、源码来源/提交、原生子模块版本、候选掩码、构建号、IPA 哈希和模型身份。
- [x] 定位 Swift 工程、原生 dispatch 点、API 路由、测试与 CI；逐项记录真实路径，无源码时标记受影响任务 BLOCKED。
- [x] 检查 Python、现有自动化测试入口、Mac/Xcode SDK、签名/unsigned 导出能力和 iPadOS 27 设备可用性；记录工具版本。
- [x] 运行既有可执行的离线自检，保存原有失败与通过项；读取历史结果以了解数据格式，不据此推断 Build117 性能。
- [x] 更新本文路径映射，明确源码侧与交付包侧脚本同步方式。

**验收：** 能从源码定位每个后续改动点，或明确列出缺失输入及受阻任务；不要求凭空获得缺失环境。

## T01：候选与公共契约

**文件：** 实际路径下的 `BenchmarkCandidateRegistry.swift`、`BenchmarkTelemetry.swift`、Python 候选映射；新增版本化报告 schema/fixture。

**接口：** `optimization_target` 使用 DECODE_FOCUSED/PREFILL_FOCUSED/BALANCED；规范名称 0=SAFE_BASELINE、2=PTQ1_MV_R5、4=PTQ1_BATCH_REUSE。旧名称 PTQ1_FUSED_KERNEL/PTQ1_LOW_OVERHEAD 作为输入别名，输出规范名称和稳定数字 ID。

- [ ] 添加兼容测试：新旧名解析到同一掩码，历史记录可解码，未知候选明确报错；1 的现有行为不变。
- [ ] 实现 displayName、description、optimizationTarget；描述 R5 的 M=1、K%128==0 限制与 batch reuse 的 CPU 分配作用，预期收益标记为假设。
- [ ] 定义 `schema_version`、UTC ISO8601 时间、单调时钟耗时、单位、run_id/request_id/context_id、采集来源和缺失原因。
- [ ] 按实际工程测试命令运行候选和契约测试，保存命令/结果。

## T02：可靠交错测量

**文件：** `ptq1_oneclick.py` 实际源码、`tools/tests/test_abba_measurement.py`、`tools/tests/test_drift_detection.py`；复用原有请求恢复/检查点逻辑。

**接口：** 每轮保存 A1/B1/B2/A2 原始样本及各自 thermal_state、warmup、配置身份。每个正式样本前 2 次短预热，256 指生成 token 上限；实际生成量另记，预热不进入统计。快速筛选正式配置为输入 512/输出 128，沿用既有确定性输入生成策略。

- [x] 写测试并确认旧实现不满足：次序严格 ABBA；4 个正式样本各自有 2 次预热；失败预热不静默进入计时。
- [x] 对每项主要指标计算 `drift_pct=100*(A2-A1)/A1`，判定用绝对值。>5% DRIFT_DETECTED；>10% UNSTABLE；恰好 5%/10% 不触发对应严格大于阈值。阈值可配置。
- [x] 保存配对原始差值 `mean(B1-A1,B2-A2)`；吞吐收益 `mean((Bi-Ai)/Ai)*100`，耗时收益 `mean((Ai-Bi)/Ai)*100`，统一正值表示改善。
- [x] 任一主要指标漂移>10% 整轮无效；5–10% 保留数据并标警，不计入确认稳定收益，建议重测。热状态 serious/critical 延后测试或标记无效，记录原因。
- [x] 基线零/非有限值、配置不同、冷启动状态不同、GPU 完成证据不足、请求中断均不得生成有效收益；检查点保存采集进度，中断轮作废且不重放不确定请求。
- [x] 晋级后 5 轮 ABBA；无效轮不计入 5 轮，默认至多尝试 10 轮，仍不足标记 INCOMPLETE。保持串行推理和原有取消/生产上下文恢复。
- [x] 沿用项目 unittest：分别执行 `python -m unittest discover -s tools/tests -p test_abba_measurement.py` 和 `python -m unittest discover -s tools/tests -p test_drift_detection.py`，保存通过证据。

## T03：评价规则、统计和报告

**文件：** Python 评价/报告逻辑、BenchmarkTelemetry、HTML/JSON/CSV 输出及对应测试。

**明确原文冲突：** 收益等级与候选晋级是两个字段，不能互相替代。原例 +4.3% 应为 MINOR；`mean ± std` 是描述统计，不是置信区间。

| 目标 | 通过条件（确认阶段还必须稳定） | 次要指标 |
|---|---|---|
| DECODE_FOCUSED | decode 吞吐提升≥3%；单 token TTFT 单独展示 | prefill ±10% 不淘汰，超出此范围标回归待核验；TTFT 不虚设原文未给出的淘汰值 |
| PREFILL_FOCUSED | prefill 耗时改善≥5% | decode 下降≤10% |
| BALANCED | prefill 改善≥15%、TTFT 改善≥10% | decode 下降≤5% |

等级按目标主要收益：≥15% SIGNIFICANT；≥5% 且<15% MODERATE；≥2% 且<5% 并经重复稳定验证为 MINOR；<2% 或不稳定为 NO_BENEFIT，另保留不稳定原因。BALANCED 的 SIGNIFICANT 还需满足 TTFT≥10% 和 decode 护栏；其余改善只能记录等级，不能绕过晋级门槛。

- [x] 测试 2/3/5/10/15% 边界、decode -5/-10%、prefill ±10%、无样本/单样本/NaN，以及 +4.3% 的正确等级。
- [x] 快筛只有“晋级/未晋级/证据不足”的暂定结论；未进入重复比较标 SHORT_SCREEN_NO_BENEFIT，充分重复且无收益才标 CONFIRMED_NO_BENEFIT；失败或无效样本标 INCOMPLETE/UNSTABLE。
- [x] 以每轮配对收益作为独立统计单位，报告均值、样本标准差、有效轮数及 95% 配对均值置信区间；采用 Student-t 区间并明确假设，不将同轮 token 当独立样本。
- [x] 本阶段“稳定”默认定义：5 个有效轮、无漂移告警、主要收益 95% 区间下界>0、次要护栏满足；小样本不满足时不得确认有效。
- [x] JSON/CSV/HTML 同时展示 A1/B1/B2/A2、漂移、原始指标、收益符号、目标、等级、晋级结果、M=1/M>1 实际计数、prefill/decode 占比及来源；profiling 明细默认不塞入标准报告。
- [x] 运行统计与报告测试，检查 JSON/CSV 可解析、HTML 转义和历史报告兼容。

## T04：真实原生 profiling

**文件：** `BonsaiEngine.swift`、`BenchmarkNativeBridge.h/.mm`、真实 Metal dispatch 源文件、API 路由和 telemetry。

**接口：** `getKernelStatistics`、`getLastGPUExecutionTime`、`getThermalState`；`GET /debug/profiling` 返回最近已完成推理的 breakdown、kernel_stats、thermal_state、request_id、采样窗口、availability。字段沿用原文 batch_prep_ms/decode_call_ms/metal_submit_ms/gpu_wait_ms/result_read_ms 和 R4/R5/FWHT/M1/M>1 计数。

- [ ] 为计数复位、差量、并发隔离、取消请求和无 GPU 时间支持写原生/接口测试。
- [ ] CPU 使用单调高精度时钟；在真实准备、调用、提交、等待、读回边界插桩。标注包含关系，不能将 decode 总耗时和其子阶段相加作为总时间。
- [ ] 在真实 dispatch 点统计 R4/R5/FWHT/其他，定义 operation 与 dispatch 的粒度；线程安全、context 创建时复位，请求报告使用起止差量。
- [ ] GPU 执行时间优先使用可用的 Metal 完成时间戳；CPU 提交至完成仅为估算且单独标 source，不能命名为真实 GPU 时间。不可取得的拆分项返回 null。
- [ ] 验证候选 R5 在合法形状命中、非合法形状走既有回退；不改 kernel 算法。确保 profiling 读取不会阻塞正在运行的推理。
- [ ] 比较 profiling 开/关的观测开销并记录；有可测干扰则默认关闭详细采样，报告采样模式。

## T05：诊断模型与本地存储

**新增文件：** `DiagnosticModels.swift`、`CrashDiagnostics.swift`；必要时把存储拆成独立文件并更新工程 target。报告 schema 与示例放 `docs/build117/diagnostics/`。

**接口：** 线程安全的 `recordBreadcrumb(action, metadata)`、`recordTimelineEvent(event, details)`、`recordError(severity,type,message)`、`captureSnapshot(reason)`。使用可 Codable 的受控 JSON 值类型，不依赖未定义的 AnyCodable。

- [ ] 定义原文所有顶层信息域：executive_summary、device_info、app_state、stack_trace、memory_state、operation_timeline、breadcrumbs、performance_snapshot、kernel_statistics、configuration、recent_errors、ai_analysis；增加 schema_version、关联 ID、字段来源/可用性。
- [ ] facts 与 hypotheses 分离；假设包含 evidence_refs/confidence/verification_steps，禁止直接宣称热状态或碎片率是崩溃根因。设备、模型、版本示例只能标为 synthetic fixture。
- [ ] 正常运行时串行低开销写入；breadcrumbs 上限100、timeline上限200，token 高频事件采样/聚合，保留最近 token 索引和错误，不能每 token 强制刷盘。
- [ ] Application Support 保留恢复日志和最小状态；最终报告按项目现有共享策略保存 `Documents/CrashReports/`，手动快照放 `Documents/Diagnostics/`。JSON 原子替换，Markdown 从同一 JSON 派生。
- [ ] 默认最近50份崩溃报告；快照也限制50份；两者总量默认100 MiB。先清理最旧已完成报告，不删正在写入/恢复的文件；磁盘不足降级并记可诊断错误。
- [ ] 测试 Codable 往返、必需字段、null 原因、循环上限、重启恢复、损坏尾记录、磁盘满、保留策略、并发和敏感字段脱敏。JSON 与 Markdown 信息保持一致。

## T06：致命采集、下次启动恢复与追踪

**文件：** 实际 App 入口/AppDelegate、CrashDiagnostics、BonsaiEngine、API 生命周期和原生错误处理点。

- [ ] T00 后确定可用的崩溃采集机制：优先复用已有经过验证的捕获器；若无，则实现安全最小原生记录与下次启动恢复。若选择依赖，记录许可证、侵入性和选择依据。
- [ ] 正常路径预持久化 session/run/request、配置、最后成功步骤、低频资源趋势；致命路径只做该机制允许的最小安全记录，不能锁竞争或在 signal handler 中运行 Swift JSON/Markdown 生成。
- [ ] 下次启动合并最小记录、预持久化上下文和系统诊断，生成最终 JSON/Markdown；保留原始地址、binary image UUID、架构、源码 SHA 和匹配 dSYM 信息，离线符号化时验证 UUID。
- [ ] 未正常结束的 session 标为 previous_session_unclean；只有系统证据支持时才分类 Jetsam/OOM，否则 unknown_termination。正常用户退出和系统终止不能仅凭标记断言为崩溃。
- [ ] 埋点覆盖模型加载/释放、API启动/停止/请求/取消、候选/配置变化、预热、ABBA轮次、prefill/decode、原生失败、内存警告和热状态变化；统一关联 ID。
- [ ] 在专用测试构建验证非致命错误、受控异常/abort、重启恢复、损坏记录、符号匹配/不匹配；OOM/Jetsam 或系统 kill 验证不回调也能保留此前证据。测试崩溃入口不进入生产 UI。
- [ ] 报告记录线程/异步任务“可观测范围”；无完整线程栈不能用占位内容伪装完成。

## T07：诊断 API 与健康监控

**文件：** API 路由、`HealthMonitor.swift`、诊断存储；沿用 API 服务现有认证机制。

| 方法/路径 | 响应与行为 |
|---|---|
| GET /debug/crashes | 元数据列表、total；有界分页，默认20，最多50 |
| GET /debug/crashes/{id} | 完整 JSON；不存在404 |
| GET /debug/crashes/{id}/markdown | UTF-8 Markdown，正确 Content-Type |
| DELETE /debug/crashes/{id} | 仅删除受控目录对应报告；结果明确 |
| DELETE /debug/crashes | 清除已完成历史，不影响正在写入的记录 |
| POST /debug/snapshot | 非致命快照，返回 snapshot_id 和受控文件标识 |

- [ ] 测试成功/空列表/404/坏 ID/越权/路径穿越/并发删除/磁盘错误；只接受安全 ID，不接受用户路径，不暴露设备绝对路径。
- [ ] 实现上表并保持与既有鉴权、局域网绑定及错误格式一致；导出之前再次脱敏，不新开无认证诊断端口。
- [ ] 每10秒健康采样，生命周期可启动/停止且不重复注册；记录内存、thermal、可观测 CPU/GPU、线程/任务摘要和性能趋势。
- [ ] available memory<500 MiB 告警；同配置有效基线存在且 recent decode<0.7*baseline 告警；serious/critical 热状态告警。按同类状态变化与冷却时间去重，基线缺失/零不比较。
- [ ] GPU 碎片率>0.5 仅在真实指标可得时告警；不可采集明确 unavailable。卡顿/疑似死锁用无进展超时信号记录为疑似，不伪称完整死锁检测。
- [ ] 自动清理仅调用已验证、并发安全的闲置资源清理路径；不能在推理中释放使用中的模型/KV，也不能为消除告警改变推理参数。无法保证时只记录并建议操作。
- [ ] 用可注入时钟/资源采样器测试阈值、退订、去重、性能基线缺失和监控自身故障隔离。

## T08：测试常亮

**文件：** 现有设置/ProductionView、API与benchmark状态源；必要时新增专一 idle timer 协调器。

**规则：** UserDefaults 键 `benchmark_keep_screen_on`，默认关闭；开关为 true 且 API运行或测试进行中时，主线程设置 `UIApplication.shared.isIdleTimerDisabled=true`。任一活动仍在时不得提前恢复；均结束/异常清理时恢复系统行为，多窗口由唯一状态源协调。

- [ ] 测试开关×API×benchmark状态组合、重启偏好、取消/失败清理与多窗口更新。
- [ ] 增加 Toggle、说明文本及当前有效常亮状态；开关持久化，UI状态反映有效条件。
- [ ] 真机验证自动锁屏行为和 UI 状态；若实现可选 POST /debug/screen-on，沿用鉴权并复用同一状态逻辑。

## T09：iPadOS 27 界面

**文件：** 所有实际 SwiftUI View、导航、设置、API和测试/诊断页面；仅在确有必要时改 Info.plist。

- [ ] 用真实 SDK 文档核对 API 可用性/弃用，不将原文“新样式”描述当成系统事实；保留项目 deployment target 和可用性保护。
- [ ] 按窗口宽度/size class 适配布局；使用 safe area/系统间距，修正硬编码截断；导航迁移仅在确有必要且兼容时实施。
- [ ] 语义颜色、深浅主题、动态字体、VoiceOver标签、键盘焦点、主线程 UI 更新；长列表避免新增同步诊断 I/O。
- [ ] 真机/模拟器截图检查：13英寸全屏、横竖屏、1/3/1/2/2/3窗口、窄浮动窗口和系统实际支持的多任务模式、Stage Manager；系统未提供的模式标 N/A 并给依据。
- [ ] 检查最小至最大辅助字体与深浅色；保存设备/OS/窗口尺寸和截图，处理本次引入的布局/弃用警告，既有警告单列。

## T10：集成与回归

- [ ] 运行现有完整离线测试及 T01–T09 新增的实质性测试；保存命令、返回码与结果摘要。
- [ ] Windows 全新解压测试包，在带空格/中文路径运行 CMD；核对 bundled Python、依赖、发现/鉴权、超时、取消、恢复、JSON/CSV/HTML/ZIP和哈希输出。
- [ ] 真实 iPad 验证候选→profiling→ABBA→报告→诊断的关联 ID、源码/IPA/模型身份和实际配置一致。
- [ ] 验证快筛后5轮比较、漂移和热状态失效、无收益保留基线、取消/网络断开后恢复原生产上下文。
- [ ] 完成至少既有默认30分钟持续检查；若原流程还包含筛选、质量和调优，不缩短为“总计30分钟”。记录温度、内存、计数和有效样本。
- [ ] 在专用测试环境完成一次受控崩溃→重启→JSON/Markdown→API导出→脱敏→符号化链路，以及非致命手动快照链路。
- [ ] 核验模型精度、固定输入质量、推理参数与既有核心算法未被修改；测试数据不能代替真机性能结果。

## T11：构建、文档和交付

- [ ] 使用 T00 确认的 Mac/Xcode/CI 构建 Build117，包含新增源文件和原生改动；保存构建日志、源码 SHA、dSYM UUID 和导出方式。
- [ ] 交付可导出的 unsigned IPA；签名安装依赖用户已有签名工具，不能将 unsigned 描述为可直接安装；证书不可用不伪造签名成功。
- [ ] 生成完整 Build117 一键包，更新 TestKitIdentity、DELIVERY_SHA256、IPA/ZIP校验和、README 标题/版本和脚本；验证身份互相匹配，禁止简单修改 Build116 包名冒充新构建。
- [ ] README 解释 ABBA、正负收益、分级与晋级区别、置信区间、漂移、常亮、profiling采样、崩溃边界、导出/清理和中断恢复。
- [ ] 提供脱敏 synthetic 崩溃样本及一份真实受控测试证据；指南教 AI 从事实/时间线/内存/错误/栈查证，再评估假设，未证实根因必须保留不确定性。
- [ ] 更新任务表、验收矩阵、执行日志和剩余限制；核对交付包 SHA256，提交最终产物清单。提交代码遵循仓库规则，不自动推送、发布或覆盖历史包。

## 最终验收矩阵

每行状态初始为 TODO；执行者填入 PASS/BLOCKED/PENDING_DEVICE/FAIL 和证据路径，不能仅打勾。

| 原始验收 | 对应任务 | 需要的证据 | 状态 |
|---|---|---|---|
| 1 ABBA与漂移 | T02 | 顺序/边界测试与真机逐样本报告 | PENDING_DEVICE |
| 2 decode目标不因允许prefill波动淘汰 | T01,T03 | ±10%测试、候选报告 | PENDING_DEVICE |
| 3 区分快筛/确认无收益 | T03 | 两种状态与不足证据测试 | PASS（离线行为） |
| 4 profiling | T04 | 真实计数/时间来源、端点JSON | PENDING_DEVICE |
| 5 常亮持久化 | T08 | 状态组合测试与真机记录 | PENDING_DEVICE |
| 6 iPadOS27布局 | T09 | 各窗口截图、构建/运行警告 | PENDING_DEVICE |
| 7 主题与动态字体 | T09 | 两种主题及字体边界截图 | PENDING_DEVICE |
| 8 JSON与Markdown崩溃报告 | T05,T06 | 受控崩溃重启恢复产物 | PENDING_DEVICE |
| 9 关键诊断上下文 | T04–T06 | schema、真实数据、缺失原因、符号匹配 | PENDING_DEVICE |
| 10 历史查询下载 | T07 | 认证/响应/导出测试 | PENDING_DEVICE |
| 11 预防性诊断 | T07 | 可控资源采样测试与真机事件 | PENDING_DEVICE |
| 12 回归与Windows一键包 | T10,T11 | 测试日志、全新解压运行、哈希 | PENDING_DEVICE |
| 13 精度参数算法不变 | T10 | 代码差异、质量与配置核验 | PENDING_DEVICE |

## 给后续 Codex 的完整执行指令

```text
请在本工作区执行 docs/superpowers/plans/2026-10-23-build117-complete-task-plan.md。
先读全文和同目录原始需求，按 T00–T11 连续实施并验证；无需每个任务重复询问是否继续。
维护任务表、验收矩阵、docs/build117/execution-log.md 和证据目录；先确认源码与工具身份，保护历史包和用户改动。
采用当前会话逐项执行方式；遵守实际仓库 AGENTS.md 和适用技能。只整理计划的前一阶段已结束，本指令授权开始实现。
规则冲突按本文明确的测量公式、目标门槛、稳定性和崩溃安全边界执行；保留事实与假设区别。
缺少源码、Mac/Xcode、证书或真机时，先完成所有无依赖且可验证的工作，准确记录阻塞项，再集中请求必要输入。
未经真实构建/测试不得把任务标为 DONE，不把测试替身、旧IPA或示例数据当成完成证据。
最后给出完成任务、验证结果、产物链接、剩余阻塞和下一步；只有所有必需项有通过证据才能宣布整个阶段完成。
```
