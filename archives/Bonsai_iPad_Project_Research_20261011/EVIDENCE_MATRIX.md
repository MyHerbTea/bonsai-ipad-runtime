# Bonsai 版本证据矩阵（截至 2026-10-11）

> D=有设备认证/证据；C=编译/CI；S=仅有源码候选；H=假设。每一项只在注明的功能与 Context 范围成立。

| 版本 | 基线 SHA / 分支 | Context / 主要内容 | 证据 | 可推广状态 | 未证实的部分 |
|---|---|---|---|---|---|
| RC1.23.4 B46 | `4c0a4533...` | 512，多模态/基础复用 | D/冻结历史 | 历史回退根 | 后续 API 变更、32K |
| RC1.24.0 B55 | `a62748d7...` | 512，连续 Decode 观测 | D/诊断 | 速度基准 | DVFS 根因 |
| RC1.24.1 B56 | `c38c5c7d...`（frozen 分支） | 512，Safe/Flash/KQV/Full A/B | D/诊断 | Full 优于其他 tested profiles | 32K 性能 |
| RC1.25.0 B57 | `46063eed...`（frozen 分支） | 512，1–3 图 contact sheet | D/冻结 | 有界多图 | 独立 3 路图 token |
| RC1.25.1 B60 | `5fc6e1cf...` | 512，UTF-8 / logical+KV admission | D/冻结 | 多图错误契约 | 长 Context |
| RC1.25.3 B64 | `0d84e106daa10590ddbd1b7a3b6b3212114db6f7` | 2048，图后文本、native prefill 隔离 | D/冻结、Manifest | RC1.26 历史基线 | 32K 与最新 API output 改动 |
| RC1.26 B75 | `c09b2e09706dd0c0391b7a15727da57e0f17d425` | 2048，Cold Start、Batch 32 | D/稳定检查点 | 该配置可回退 | 32K |
| RC1.26 B79 | Build79 dev branch | 6144/8192/16384、量化 KV | D/设备文档 | 相应长 Context 档位已通过指定测试 | 统一长时/视觉认证 |
| RC1.26 B89 | `4245e997...` | 32768，GGML compact scheduler metadata | C/S+故障修复 | 诊断/实验入口 | 32K 全回归、满输入 |
| RC1.26 B100 | `4e40956e...` | 32768，B8/B16 | D/局部性能 | 具体用例 Prefill 改善 | 其他请求和持续使用 |
| RC1.26 B102 | `33e08b53...` | 32768，B16/B24/B32 资格门槛 | S/D（后续局部证据） | 限定实验 | 未独立固化完整 ABA ZIP |
| RC1.26 B103 | `0362ccb88...` 修复分支 | 32768，输出预算 >256、综合 runner | C+报告称部分 D | 证明隐藏 256 问题被处理的指定路径 | 全套 32K 稳定冻结 |
| RC1.26 B104 | `a55f318e...` | 32768，B24 auto、dual seq KV | C、真实启动失败 | **不可作为稳定基线** | 双序列是根因尚未证明 |
| **RC1.26 B105** | **`4c25b0abd79d316754b0e612ab7c5fa53cabffd6`** | 32768，single seq safe startup 恢复 | **C：65 step PASS** | 可签名供真机认证的候选 | M5 全套实际认证 |
| **RC1.26 B106** | 核心审查固定 `37291498aed1...`；活跃分支持续变化 | 32768，M5 Governor | **S：截至本报告最新查询仍在 CI 调整** | 不可推广 Stable | 构建、真机启动、长时性能 |

## 使用时的硬性规则

**不要将上表“D”的历史设备结果继承给所有后代源码**。要认证后代，必须做重跑，并证明部署的是同一个 CI artifact、来源 SHA 和模型配置。所有失败应保留 Native Trace，返回最后真正确认的安全 Build 和 Context。
