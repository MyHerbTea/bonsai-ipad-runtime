# 当前状态 — 2026-10-14

状态：ACTIVE。审计入口：[INDEX](../INDEX.md)。本页是带身份的观察快照；每个新会话必须重新执行 AGENTS.md 的 Git 核对，不能用旧 CI 或历史设备结果认证新提交。

## Remote main

- 仓库：`https://github.com/MyHerbTea/bonsai-ipad-runtime.git`。
- 审计时远端 main 完整 SHA：`dc169d6759e84e6b0f66c2c8ad87e6f073bd78c6`，由 `git ls-remote origin refs/heads/main`核对。
- 本地 main 与 origin/main 同 SHA；初始 working tree clean；本地分支审计只有 main，没有未提交或未推送的候选。
- `project.yml`为 RC1.26 Build106。源码有本地文本／图文 API、M5 Governor、单序列上下文和现有 Vision 路径。源码存在与 CI 构建不证明每个能力已通过当前 SHA 的真机认证。
- 工程规则：[AGENTS](../../AGENTS.md)、[工作区政策](../PROJECT_WORKSPACE_POLICY.md)。该治理快照当时禁止改变核心、默认参数、模型、KV、Vision；当前工程授权见下方 Build110 节。

## Build110 performance candidate - 2026-10-15

- User explicitly paused documentation governance and authorized 32K Prefill engineering. Active branch: `codex/32k-prefill-b16`, based on committed governance correction `40f8a4d52a10825e6675f8d592c3637d849b7d87`; exact candidate source is Git HEAD and the generated CI TestKitIdentity.json. Original `35aa64ff6d94d8855882cd3f1fe5a5d0ceb549a2` remains in history.
- Actual local implementation reuses Build94/102 B16 launch and Build106 Governor. B8/8, 32768 allocated context, sequence=1 and Text KV reuse OFF are the controlled baseline. Qualification/pending/confirmed and sticky SAFE4 remain required; no request-time batch switching or B24/B32 default promotion.
- Unified runner: [b16_testkit.py](../../tools/b16_testkit.py), [Windows entry](../../tools/RUN_B16_TESTKIT.cmd). The CI artifact includes portable Python, source identity, unsigned IPA/hash and automated report. Source/build/configuration and asset identities must match before measurements can pass.
- Device/performance status: **WAITING_DEVICE / NOT_RUN**. Controlled inputs do not certify a full 32K input. Prefill improvement >=15%, sustained Decode ratio >=95%, ABA drift <=10% and regressions are gates, not claimed results. SAFE4 or ambiguous/missing proof yields INCOMPLETE.
- Current task permits candidate engineering, push to its independent branch and GitHub CI only. No main merge or automatic promotion. Inspect current Actions for exact HEAD; old main CI success below is separate. Local commands/results are recorded in [TEST_RESULT](../../TEST_RESULT.md).

## Prior documentation candidate snapshot

- 本次文档治理使用官方目录中的 `codex/docs-governance`，基于上面的完整 SHA。原治理提交为 `35aa64ff6d94d8855882cd3f1fe5a5d0ceb549a2`；后续修正提交以 Git HEAD/log 为准，main 的上述观察快照保持独立。
- 本次只新增／整理文档、文档校验与其 CI 步骤；未推送、未合并回 main。后续分支状态以 Git 为准。
- 旧记录提到 `codex/bonsai-rc126-optimization` Build109；该分支不在本次本地分支清单中。不能声称已审计它的 HEAD、工作树或未推送提交。
- 当前仓库保留了一部分候选脚本，但 `tools/certification/`、`BonsaiLab/ReleaseManifest.swift`、runtime evidence、BVCACHE2 fingerprint、benchmark 及候选 evidence 目录等没有完整迁移。[候选引用清单](candidate-references.json)逐项标明 PRESENT / NOT_AVAILABLE，verification 均 NOT_VERIFIED。
- 旧 CURRENT_STATE 的 T01–T14/T16 原文及摘要保存在 [2026-10-13 原状态](../history/CURRENT_STATE_20261013.md)。它是历史候选记录，不能覆盖当前事实。CHANGELOG、TEST_RESULT、T16 矩阵中的历史 PASS 不可移植给当前 main。
- v1 已 SUPERSEDED；v2 为 DRAFT（原 Spec 缺失），没有另一份 ACTIVE 实施计划。

## CI

- 当前 main：GitHub API 查询 run `38579679479`，head SHA `dc169d6759e84e6b0f66c2c8ad87e6f073bd78c6`，completed / success，更新于 2026-10-14 22:29:29（UTC+08）。
- [原始 run](https://github.com/MyHerbTea/bonsai-ipad-runtime/actions/runs/38579679479)；[本次元数据快照](evidence/main-ci-20261014.json)记录 API 来源、SHA、artifact 与查询范围。
- Artifact `11903470229`，Build106 M5 Governor，API 当次 expired=false；wrapper digest `sha256:0c2234cda4e5fda55059e3c9c73bfe931889c236c08dd1c1321ef97b003cad5b`。到期时间 2026-10-28 22:29:23（UTC+08），届时必须重新查可用性。
- 本次只核对 CI/API 元数据；未下载新产物、未核对 IPA 内嵌身份／签名。wrapper digest 不是 IPA digest。
- 本次文档候选的本地校验见 [TEST_RESULT](../../TEST_RESULT.md)；远端 CI 尚未执行，不继承 main 的 success。
- 旧源仓库 `bonsai-ipad-prob` Build106 source `1abfa8598629e25b69e14350a6559176ffc4a926`、run `38147351064`及旧 artifact 是另一条身份链。缺少本地 evidence 索引时不能声称本次独立核验过。

## 设备认证

- 当前 main 和文档候选：`NOT_VERIFIED / WAITING_DEVICE`。本次无安装、签名、M5 smoke 或全套设备认证。
- 历史可靠检查点：[Build75](backburner-integration/RC1.26_BUILD75_STABLE_CHECKPOINT.md)，源码 `c09b2e09706dd0c0391b7a15727da57e0f17d425`，M5 12GB、context 2048、32/32；该文档记录设备 ZIP 名称与 SHA256。仅对当时设备／配置／测试范围成立，未重放原 ZIP。
- [研究矩阵](../../archives/Bonsai_iPad_Project_Research_20261011/EVIDENCE_MATRIX.md)区分历史 D/C/S。Build104 启动失败、Build105/106 候选不能被描述为 32K 稳定冻结。
- Build106 runner 是可用操作入口，不是已执行的认证；HTTP runner 不替代签名安装、终止进程后的人工重启。

## 性能认证

- 当前 SHA：`NOT_RUN`。没有本次同身份、同模型／Vision hash、实际 tokens、热／内存状态、启动模式的 ABA 或持续使用证据。
- 不能把配置的 32768 context 当成实际 32K 满输入验证，不能把编译成功或单次历史收益当成默认档位推广。
- 历史局部性能及失败经验见 [DECISION_LOG](DECISION_LOG.md)；当前源码事实是 KV reuse OFF、n_seq_max=1、BVCACHE1。候选记录中 BVCACHE2、certified envelopes 与共享 benchmark 不是当前 main 能力。

## Next allowed actions

1. Finish and push the Build110 candidate to `codex/32k-prefill-b16`; verify the exact-source macOS/Xcode CI and combined artifact before asking for one consolidated M5 run.
2. Sign/install the unsigned candidate through the existing device installation workflow, select the same model/Vision assets and 32768 context, then double-click RUN_B16_TESTKIT.cmd. Enter the key once; follow full-app-restart prompts. TestKit returns B8 when all arms complete and emits PASS/FAIL/INCOMPLETE with measured scope.
3. Use real same-identity ABA evidence to decide whether to promote B16. If gates fail, retain evidence and locate the next native Prefill hotspot. No claim of speedup, 32K full-input certification or default promotion before evidence.
4. Documentation governance is paused. Missing historical Build109 resources remain unavailable; no reconstruction or unrelated Runtime test repair is authorized by this engineering task.
