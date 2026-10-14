# Bonsai RC1.26 优化方案与计划 v2（2026-10-13）

状态：HISTORICAL 规划交付快照。独立 checkout 是当时位置；当前规则见 [INDEX](../INDEX.md)。下文 source/CI 属于旧源仓库，不能认证当前 main。

本地原plan、research文档包与Build106当前源码/Actions已对照，完整交付位于独立checkout中。原plan和research包保留为历史输入；后续执行以本v2链接的方案与计划为准。

- 完整优化方案（NOT_AVAILABLE）：原路径 `lab-v1-rc1-26-build106-m5-governor/docs/superpowers/specs/2026-10-13-bonsai-optimization-design.md`：目标、架构、完整认证矩阵、6类优化方向、推广与回滚门槛。
- [实施计划（DRAFT）](../development/2026-10-13-bonsai-optimization-plan.md)：7个里程碑、16项任务、18项需求映射、文件/接口/验证步骤、角色与排期。
- 原状态 JSON（NOT_AVAILABLE）：`lab-v1-rc1-26-build106-m5-governor/docs/optimization/CURRENT_STATE_20261013.json`；现存 [CURRENT_STATE](../optimization/CURRENT_STATE.md)仅记录当前身份与分层验证状态；原 JSON 所规划的研究包 hash 尚未恢复。
- 交付核对记录（NOT_AVAILABLE）：原路径 `lab-v1-rc1-26-build106-m5-governor/docs/optimization/PLANNING_AUDIT_20261013.md`。

当前source=1abfa8598629e25b69e14350a6559176ffc4a926，[CI run 38147351064](https://github.com/MyHerbTea/bonsai-ipad-prob/actions/runs/38147351064)已success。M5完整设备认证仍NOT_VERIFIED；本次只交付方案/计划，未改产品代码或执行性能实验。

顺序：封存现有产物 → 身份/native观测/一键runner → SAFE4与B8完整32K认证 → B16/B24单变量实验 → 内存与Governor → KV/Vision/native热点 → 冻结与维护治理。

立即下一项：T01封存Artifact11704414799并核对IPA/runner身份，不再重复“修复当前CI失败”。该artifact当前到期2026-10-25 22:37:37（UTC+08），其GitHub digest是wrapper摘要，不是IPA自身摘要。

