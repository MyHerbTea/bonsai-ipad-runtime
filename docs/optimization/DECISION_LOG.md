# 技术决策日志

状态：ACTIVE；整理于 2026-10-14。这里只提炼已有原始证据，推断和未核验的旧报告明确区分；不新增 Runtime 政策。当前身份见 [CURRENT_STATE](CURRENT_STATE.md)。

| 决策 | 原始证据与失败经验 | 当前处理策略 | 重新开启条件 |
|---|---|---|---|
| D01 单一官方工作区 | [工作区政策](../PROJECT_WORKSPACE_POLICY.md)记录 T16 在另一 checkout 生成 `598a9f7b9555213519032206ed68c29acc17c24d`，发布提交为 `b93d4873832d8236fb5b48091c5214b3bfd16f49`；混淆 checkout 导致误判交付状态 | 依 [AGENTS](../../AGENTS.md)，只在 `D:\codexSpace\bonsai-ipad-runtime`开发；旧路径是历史，不清理旧工作 | 仅项目所有者明确变更工作区规则；既有外部工作需先保全与审查 |
| D02 CI、设备、性能分开 | [Build106](backburner-integration/RC1.26_BUILD106_M5_GOVERNOR.md)、[历史矩阵](../../archives/Bonsai_iPad_Project_Research_20261011/EVIDENCE_MATRIX.md)明确 build-ready 不等于认证 | 完整 SHA → CI artifact → 签名／安装身份 → 实际配置与原始报告；当前 M5 等待中 | 同 SHA、设备／资产 hash／配置一致的完整测试结果到位才改变对应状态 |
| D03 文本 KV 与双序列隔离 | [Build104/105 事故及恢复](backburner-integration/RC1.26_BUILD105_STARTUP_RECOVERY.md)：32K 启动失败，trace 不足以证明根因，seq2 是嫌疑；[Build76 设计](backburner-integration/RC1.26_BUILD76_TEXT_KV_REUSE_LAB.md)要求 trim 失败回退 | 当前源码 `textKVReuseEnabled=false`、两处 context 创建 `n_seq_max=1`；保持 Build105 quarantine。旧 T13 称 trim 返回 false／NO_SAFE_WIN，但当前仓库缺该原始设备 trace，不升级为本次独立证实 | 单序列 recurrent restore／tail-trim 能力、正确性、取消／失败／Vision 隔离、memory 与 TTFT 的新 M5 证据，完整相关回归；不得以 seq2 绕过当前安全约束 |
| D04 Batch 是受控实验 | [Build75 检查点](backburner-integration/RC1.26_BUILD75_STABLE_CHECKPOINT.md)：2048 下 32→64 prefill +8.619%，decode throughput -31.655%；[Build106](backburner-integration/RC1.26_BUILD106_M5_GOVERNOR.md)仅创建 context 时选 profile | SAFE4 恢复、BALANCED8 常规 32K，16/24/32 仍资格／显式选择实验；历史 2048 性能不推广到 32K | 实际 token／shape、同 workload／温度／内存的重复配对；process restart，单变量，完整响应与回滚；门槛须由审阅后的实验方案固定 |
| D05 不猜 Metal kernel 或风险比例 | [Build94 纠错](../history/BUILD94_AI_AB_RECONCILED_DECISION.md)基于 Prism `adfffbe41b2cabcd51fff326ab045662265062bb`：ne11 是右操作数的行维度，不能等同 seq 或全局 batch；8→9+ 是候选边界 | 源码条件不证明 M5 实际 dispatch；host-wall decode 不称 GPU 时间；无样本不写风险百分比 | 同 pinned 源码上的有界 per-op 计数、开销校验、同配置 ABA 与持续 decode 证据，再决定单独 kernel 候选 |
| D06 NO_SAFE_WIN 是有效结论 | [RC1.23.5 closure](../../archives/rc-history/RC1.23.5_NO_SAFE_WIN_CLOSURE.md)：suffix packing 已密集；256 比 512 在四对中均慢且有切换崩溃，冻结源 `4c0a453339350c0c915578a46a15d4235ab0ff99` | 保留失败数据；不把更小 context 或 batching 理论当收益，也不沿用当时 Vision 默认到当前 | 有新的可归因瓶颈证据，先处理 lifecycle 稳定性，再单变量重新测量；不能重写旧实验为成功 |
| D07 Vision 历史与候选分层 | [历史 staged 协议](../../PRODUCTIZATION_PROTOCOL.md)、当前源码 BVCACHE1；[旧 T14 状态](../history/CURRENT_STATE_20261013.md)称 BVCACHE2 identity，但对应实现未迁入 | 本次保留既有 MLX 生命周期、Hard Graph-Cut、cache 与多图行为；不冒充新 fingerprint 已部署 | 恢复完整候选源码／Spec 并审阅；同 artifact 的 1/2/3 图语义、cleanup、cache identity、内存与时延认证之后才能采纳 |
| D08 未归因内存不做“优化” | [旧 T12 状态](../history/CURRENT_STATE_20261013.md)、[候选 R14](release/EVIDENCE_MATRIX.csv)都指出缺 stage-attributed M5 trace | 当前 Q4_0、mmap 与历史 scheduler 补丁是既有机制；无测量不写新收益或 NO_SAFE_WIN | model／Vision hash、分阶段内存峰值与确证失败到位，确定一个主峰，再给单候选 A/B 与回滚 |

每次新增决策：写明原始 SHA／报告、适用范围、判定、失败与回滚、重启条件；若替代旧决策，注明旧编号，不删除历史记录。v2 计划仍 DRAFT，其实验数值不是已经批准的发布默认。

## D09：分配恢复不能依赖诊断日志开关（2026-10-22）

Build112 原始框架 UUID 与系统日志一致，确认 `ggml_init +420` 的前置 abort 为 `ctx->mem_buffer != NULL`。旧 compact/mmap 分配恢复受原生 trace 环境变量门控，16K/B8 没有同等恢复能力。Build115 仅解除该门控并保证失败返回 NULL，保留原分配成功路径和容量规则。[证据与适用边界](PTQ1_BUILD115_STARTUP_RECOVERY.md)：该系统日志不能认证 Build114 为同因；Build115 真机恢复、数值和性能均待测。
