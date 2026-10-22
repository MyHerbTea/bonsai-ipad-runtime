# Build117 本地实施与验证说明

本阶段代码基于 Build116 提交 `4dce38a80ddfbfe186c3af052cb4932012367a70`。本地 Windows 验证不证明 Swift/Objective-C++ 已编译、Metal 已执行或 iPadOS 27 已适配验收；本轮按用户要求先完成本地代码与可运行检查，不推送、不触发 Actions。

## 测量和报告

每个候选独立 A1→B1→B2→A2；每个正式样本前两次256生成 token上限预热。快筛512输入/128输出；确认2048输入/128输出，需5个有效轮，最多10次尝试。输入 token 按真实 tokenizer 校准，不改变模型或生产默认参数。

吞吐正收益为 `(B-A)/A`，耗时正收益为 `(A-B)/A`；先在轮内取两对平均，再跨轮统计。各指标基线漂移 `(A2-A1)/A1` 绝对值>5%为告警、>10%为不稳定；告警轮不能计入5个有效轮。可用 `--drift-warning-pct` / `--drift-unstable-pct` 配置。

Decode目标提升≥3%，prefill下降至多10%；Prefill目标改善≥5%，decode下降至多10%；Balanced 保持prefill≥15%、两种TTFT≥10%、decode下降至多5%。稳定确认还需主要配对收益95% Student-t区间下界>0。均值±样本标准差与置信区间分别输出。

等级与晋级分开：2–5%为MINOR，5–15%为MODERATE，≥15%为SIGNIFICANT；小收益须经重复稳定验证。+4.3%是MINOR。快筛未晋级为SHORT_SCREEN_NO_BENEFIT；充分重复后无收益为CONFIRMED_NO_BENEFIT；证据不足保持INCOMPLETE。历史三对样本算法仅供兼容读取，Build117实际测量不使用它晋级。

候选数字掩码仍为0/1/2/4；2规范名PTQ1_MV_R5，4规范名PTQ1_BATCH_REUSE；旧名称输入别名保留，组合候选仍需独立验证。所有质量、输出哈希、logits、实际配置、模型/IPA身份、内存余量和不确定请求不重放机制继续保留。

## 诊断与 profiling

认证沿用现有API设置。开启API Key鉴权时，以下请求使用相同的Bearer Key；报告默认本地保存，不上传。

```text
GET /debug/profiling
POST /debug/snapshot
GET /debug/crashes?limit=20&offset=0
GET /debug/crashes/{id}
GET /debug/crashes/{id}/markdown
DELETE /debug/crashes/{id}
DELETE /debug/crashes
```

JSON为数据源；Markdown按摘要、设备、应用、内存、栈、时间线、错误、性能和假设分节派生。文件分别位于Documents/CrashReports和Documents/Diagnostics；恢复检查点位于Application Support/Build117Diagnostics。报告/快照各最多50份，总计默认100MiB。

正常运行串行持久化，普通事件最多每2秒写检查点，关键错误强制保存；最近breadcrumbs100条、timeline200条。解码进度按16 token采样，不保存token正文。最近状态可能早于实际崩溃，报告明确标注采样范围。磁盘写入失败会降级，不能保证断电时保存。

致命路径只写24字节固定原始记录（signal、PC、fault address），使用预打开fd；下次启动合并此前状态。最小捕获器没有完整线程栈、Swift error捕获或系统Jetsam分类。完整线程栈需要匹配UUID的系统崩溃日志和dSYM；App/llama dSYM经UUID验证后作为独立符号ZIP保留，UUID身份文件随测试包分发；报告保留App/llama加载地址和UUID，不伪造符号。用户强制退出、SIGKILL、OOM、断电可能只留下previous_session_unclean，不能据此认定崩溃或根因。

`ai_analysis`不调用外部AI，只提供证据查证步骤；缺少依据时假设数组为空，confidence为insufficient_evidence。分析顺序：摘要→时间线→内存趋势→breadcrumbs→匹配UUID的栈→近期错误→验证假设。

profiling记录CPU准备/llama_decode/结果采样边界；真实dispatch统计R4/R5/FWHT/总数、M=1/M>1矩阵操作。GPU时间是command buffer GPUStartTime/GPUEndTime之和，允许重叠，不等于端到端时长。CPU提交调用耗时另列；gpu_wait_ms没有独立边界，返回null。嵌套阶段不能相加当作总时间。

原生计数是进程共享的context计数，采用请求差量；只有benchmark独占运行时才宣称归属于单次请求，普通推理只保证CPU侧分解，原生计数返回不可用原因。观测开销和并发/取消行为仍需Apple环境量测。

健康采样每10秒，低内存<500MiB、同模型/配置decode速度<基线70%、serious/critical热状态告警，状态变化或60秒冷却后记录。GPU碎片率/利用率不可得，保持null。不会自动释放推理中的模型/KV、限制token或修改参数。活跃推理超过120秒无可观测进展时记录INFERENCE_NO_PROGRESS_SUSPECTED；这可能是长kernel，不能据此断言死锁。现有benchmark watchdog继续提供超时取消保护。

## 常亮与界面

设置键benchmark_keep_screen_on默认关闭，仅在开关打开且API运行或benchmark会话有效时保持常亮；由主线程单一协调器处理。UI已增加状态提示和手动快照；主界面/API状态和开发页数字输入按紧凑宽度/辅助字体使用纵向布局，颜色沿用系统语义颜色，最低系统版本保持17.0。

布局依据Apple [Layout指南](https://developer.apple.com/design/human-interface-guidelines/layout)和[Dynamic Type说明](https://developer.apple.com/videos/play/wwdc2024/10074/)。这些通用布局修改不能替代iPadOS27全屏、旋转、窄窗口、Stage Manager和辅助功能实测。

## 可重复的本地检查

在仓库根目录运行；不连接iPad的测试使用标明synthetic的样本，不能用作性能结论。

```powershell
python -m unittest discover -s tools/PTQ1_ONECLICK -p "test_*.py"
python -m unittest discover -s tools/tests -p test_abba_measurement.py
python -m unittest discover -s tools/tests -p test_drift_detection.py
python -m unittest discover -s tools/tests -p test_measurement_thresholds.py
python -m unittest discover -s tools/tests -p test_windows_launcher.py
python -m unittest discover -s tools/tests -p test_documentation_consistency.py
```

原生补丁必须按现有workflow顺序应用到固定Prism，然后应用rc126_build117_patch_profiling.py。设置BONSAI_PRISM_TEST_DIR后运行test_build117_native_profile.py。该测试的C++行为项需要编译器；Windows本机缺少该编译器时会明确skip。

## 后续Apple环境验证

已配置`.github/workflows/build-ptq1-tournament.yml`面向Build117；它加入Swift存储/策略测试、原生独立子进程信号测试、profiling原子计数测试与符号检查。本轮不触发此workflow。

尚须完成：Xcode完整编译及dSYM匹配、真实受控崩溃重启、诊断API认证/并发/磁盘异常运行测试、常亮和全窗口截图、profiling开销量测、5轮ABBA、质量及至少30分钟持续检查。只有这些通过后，package_ptq1_oneclick.py才可从真实Build117 App生成带身份和校验和的IPA一键包。

不提供改名的旧IPA，也不将synthetic包装测试产生的字节作为可安装App。完整状态见执行日志与工作区任务文档。

恢复报告写盘失败时，恢复门禁阻止所有新检查点覆盖旧会话；应释放存储后重启恢复。此时本次启动可能没有安装信号捕获，报告会显示初始化/写盘失败。备用信号栈只安装在诊断初始化线程，其他线程栈溢出捕获不作保证。
