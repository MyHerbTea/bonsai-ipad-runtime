# Accepted Build120 design

User accepted option B and direct Build120 implementation on 2026-10-23. The historical review below remains a record of the investigation; its pending/NOT_RUN labels describe that point in time. Current implementation progress is in docs/build120/execution-log.md.

# Build119 恢复核查与后续方案（待选择）

2026-10-23，沿用 `D:/codexSpace/iPad27B/bonsai-ipad-runtime`。
本文件是调查结果及方案建议，不代表已实施、已批准 Build120 或已解除隔离。

## 本次实际操作与现状

- 仓库分支 `codex/build119-controlled-recovery`，HEAD `aeed5ef8556b28273e4389534ed2581e504fa7d9`，源码工作树干净。没有新建 worktree，没有改已交付包。
- 仅发送三个成功到达设备的 GET：`/debug/benchmark/status`、`/debug/benchmark/capabilities`、旧审计 `/debug/crashes/SNAPSHOT_1C25E002-8E17-4D68-8669-53BBB7F44D45`。分别返回 200、200、400；原始响应位于本目录。
- 初次 PowerShell 请求使用了错误的 `/v1/benchmark/` 路径，且在本机代理 `127.0.0.1:9` 即失败，没有到达设备。两份 `*-error.json` 保留该失败；随后改用源码确认的 `/debug/benchmark/` 和直接 LAN 连接。
- 设备仍为 Build119 和上述 source SHA，process `8DFFF28F-D8E2-488A-9A8F-48E10D588686`，与暂停前后完全相同。
- status/capabilities 均为 active=false、running=false、ordinary_requests=0，thermal=0。native context 仍是 `0AF680B7-2863-4771-94E9-AAC7E2A5DE9A`，16K/B8/ubatch8、Q4_0 K/V、56 GPU 层、mmap、sequence=1，text KV reuse=false。
- Quick interruption `2615C0E0-C2A2-406A-9A23-8B5A6BAD56E6` 与历史 B16 标记均与暂停后证据一致。没有发送 POST、推理、取消、恢复或确认命令。

## 根因与当前可行边界

1. `BenchmarkInterruptionRecovery.acknowledge` 把 reason 严格限定为 `manual_forced_exit`；现有 CLI 同样只有这一选项。本次主动 API 取消不符合该事实，不能调用它。
2. `QuickClient` 在 run APIError 后设置 preserve_interrupted，finally 中 restore(preserve_interrupted=true)。Engine 恢复原生产 context 后有意保留 Quick 标记；runtime 已恢复与实验隔离仍保留是两个独立事实。
3. `BenchmarkSessionControl.cancel` 只设置内存布尔值；`endSession` 会清除该值。Build119 没有持久化可供新进程独立核验的取消收据。当前 cancelled=false 不能否认此前 cancel，也不能单独证明此前 cancel。
4. `benchmarkStart` 会拒绝已有 Quick 标记。空闲时 `benchmarkRestore` 因 benchmarkOriginal=nil 直接返回，不能据此正规解除标记。构造新会话或使用其他 debug 路径清标记不属于合法恢复策略。
5. `DiagnosticStore.validID/read` 支持 SNAPSHOT_；`CrashDiagnostics.api` 的 HTTP ID guard 额外只允许 CRASH_。本次真实 GET 复现 HTTP400 invalid_report_id。App UI 现有按钮只保存新快照并显示 ID，没有现成的快照导出功能。

因此，目前 Build119 应继续保留隔离。现有事实不能通过伪造 manual_forced_exit、清 UserDefaults、卸载重装或重复旧确认来修复。

## 两个可选方向

### A：保留 Build119，只结束调查

设备可保持当前生产配置与实验隔离，旧证据原样保留，不做候选补测。无需新 IPA，但无法通过现有 HTTP 读回旧快照，Quick 实验仍被阻止。

### B：最小 Build120，显式 API 取消审计恢复 + 快照只读导出（建议）

保留现有 Swift、Python 与 IPA 交付方式，仅修改恢复和诊断路径；CPU 数学、候选实现、生产默认配置保持现状。

恢复设计建议：

- 新增与 manual_forced_exit 分开的显式原因 `operator_confirmed_api_cancel`。其含义是操作员根据保留证据确认此次 API 取消，不宣称 App 自己持有历史取消收据，不宣称已排除所有原生故障。
- 专用工具读取本次原始 before/cancel/after/report，核对同一源、同一历史进程，before/cancel 的 session/request 一致、cancelled=true、after 同进程且生产配置恢复、report restoration=RESTORED，以及 after 与当前的完整 Quick marker 相同。保留文件 SHA256、原 session/request、源版本、原进程、原配置与结果摘要。
- 这些文件是操作员提供的证据，不是经过签名的服务器证明。审计明确记载这一来源；不得把任意客户端 reason 字符串变成自动清除许可。新原因必须携带完整、结构有效且互相一致的证据摘要，缺失或矛盾则拒绝。
- 服务端继续取得排他 lease，确认 benchmark 未活动、普通推理未活动、生产 runtime 已加载且配置符合恢复要求，绑定当前 source/process 与完整 expected_interruption。历史源/进程与当前接收确认的源/进程分别记录，升级后不能假设它们相同。
- 先持久保存非致命审计，再经真实 DiagnosticStore 读回并核对关键字段；删除前再次比较完整 marker。保存失败、读回失败或 marker 改变都保留隔离并拒绝确认。只移除匹配的 Quick 标记；历史 B16 不动。
- 显式确认不发起推理，不自动重试，不恢复 runner，不复用旧 checkpoint。未来取消自动恢复或通用故障恢复框架不纳入本次范围。

快照导出建议：

- 新增受现有认证保护的 `GET /debug/snapshots/<SNAPSHOT_ID>` 与 `/markdown`，复用 ID 校验和存储路径限制。
- 快照路由仅支持读取，不把 CRASH_ 的现有批量删除行为扩展到审计。现有 crashes API 语义保持现状。
- Markdown 增加 operator_acknowledgement，JSON 仍是审计来源。
- 新版读取旧 ID，不能重新确认旧手工强退来制造替代审计。若旧文件实际已不存在，应如实记为不可读，不能补造保存成功证明。

## 验收条件（尚未执行）

1. 错误 reason、错误当前 source/process、无 interruption_id、旧 marker、矛盾取消证据、活动推理/会话均拒绝；隔离保留。
2. 审计存储失败、读回不符、删除前 marker 变化均保留隔离；真实存读通过后只清目标 Quick marker，历史 B16 完整相同。
3. API GET 可读真实 SNAPSHOT_ JSON/Markdown；非法 ID、路径穿越、CRASH_ 混入快照路由、缺失 ID 与未授权请求按明确状态拒绝；快照 DELETE 不支持。
4. 工具拒绝覆盖证据文件；导出读回失败不得打印“独立核验通过”；确认和导出都不触发 benchmark/run。
5. 先运行受影响 Python 测试及 Apple Swift 真实存储/管理器测试，再核对新源 CI、IPA、符号、TestKit 身份和哈希。Windows 上不能把未执行的 Apple 测试当通过。
6. 新 IPA 安装后重新核对当前 source/process、资产和生产配置，先读回旧审计，再显式执行新原因确认，独立读回新审计并比较标记。若安装后标记消失，应视为证据异常，不以此宣称合法恢复成功。

## 补测决策边界

- 23 个完成请求均 valid=true；其中 16 个 warmup、7 个正式 screen。flag4 完整 ABBA 但漂移超限，有效轮0；其 benefit_level=NO_BENEFIT 不能作为有效收益结论。
- flag8 的 A1/B1/B2 观察到退步，A2 正式请求由用户取消；没有完整配对。flag16 没有样本。本轮总体 INCOMPLETE、restoration=RESTORED。
- 不能仅补一个跨时段或跨 IPA 的 A2，把它拼成旧 ABBA。旧原始报告不改，新结果始终进入新目录。
- 建议在恢复功能验收完成后另行选定短测范围：优先考虑尚未测的 flag16 独立一轮 Quick ABBA；是否重测 flag4/8 由目标与时间预算决定。本建议不是补测授权，本次不发起测试。
- 即使新 IPA 不改 CPU 数学，跨 Build 的观测也分别报告；不得自动晋级候选或改变默认 batch。

## 原始取消证据 SHA256

目录 `D:/codexSpace/iPad27B/docs/build119/device/20261023T080803Z/`：

| 文件 | SHA256 |
|---|---|
| operator-stop-before.json | 62776da5cc82620f0efc5bb0d3bfe7775d8dbbc940c61556f02f13b8f33532a0 |
| operator-stop-cancel.json | 7fd937cee0a3ae01a81e47934f31b84ff68362def180298d83c4562083c216c2 |
| operator-stop-after.json | c4c95b688d6a4765cf5f100de5225f9f1ae7566ed52349624afdc651d337c345 |
| comparison/report.json | 0216eae69151898471e74f1542a2eebf915f83a1489959d06407de0c05523be4 |

状态：调查完成；源码修改、Build120、隔离解除与补测均未执行。
