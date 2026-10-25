# Bonsai 文档索引与权威性

Build123 / flag17：[B8批次内解包复用计划](superpowers/plans/2026-10-24-flag17-unpack-reuse.md)。单一实验候选，基线与候选均关闭原子计数和分段采样；一致性、收益待验证，不代表晋级。

Build122：[低率采样与计数开关对照](build122/plan.md)。仅服务于三次512/1真机请求；尚无测量结论。

Build121：[限时CPU prefill计时范围](build121/plan.md)。仅计时，不改优化逻辑；CPU占比和设备结果待验证。

Build120 最小恢复仅服务于 flag16 真机决策：[当前范围](build120/minimal-execution.md)、[执行记录](build120/execution-log.md)。旧快照导出方案搁置；设备测量待执行，不代表候选通过。

Build119 受控恢复：[计划](superpowers/plans/2026-10-23-build119-controlled-recovery.md)、[实施记录](build119/execution-log.md)、[Build118 中断派生说明](build119/build118-interruption-interpretation.md)。Apple CI 与新 IPA 真机比较待执行。

Build118 实验候选：[设计](superpowers/specs/2026-10-23-build118-prefill-design.md)、[执行计划](superpowers/plans/2026-10-23-build118-prefill-plan.md)。同IPA的CPU lookup/NEON候选尚待集中真机对比，不代表收益或发布通过。

Build117 本地实施记录：[执行日志](build117/execution-log.md)、[源码映射](build117/source-map.md)。该阶段尚需 Apple 编译及真机验收，不能作为发行或性能通过证据。

状态：ACTIVE。治理快照：2026-10-14（UTC+08）。现有 GitHub 文档仍是项目资料；本页只导航、分类和解决冲突。

新会话顺序：[AGENTS.md](../AGENTS.md) → 本页 → [CURRENT_STATE.md](optimization/CURRENT_STATE.md) → [DECISION_LOG.md](optimization/DECISION_LOG.md)。先核对工作区与 Git，再选任务；文档快照不是实时状态。

Build124 一键闭环：[当前执行计划](superpowers/plans/2026-10-25-build124-oneclick.md)。固定512/128六请求SDOT ABBA；新IPA真机性能待执行，保留生产默认。

## 项目目标与权威顺序

目标：在 iPad Pro M 系列运行本地 Bonsai 27B 文本／图文推理及 OpenAI 兼容 LAN API，按源码、构建产物、设备、性能四层证据逐步提高可靠性。32K 配置能力不等于实际满输入、稳定性或性能认证。

工作区以 AGENTS.md 为最高项目规则；[工作区政策](PROJECT_WORKSPACE_POLICY.md)解释操作边界。当前事实以 CURRENT_STATE 的完整 SHA 和证据为准；决策必须追溯原始资料。新记录只替代相同身份和验证范围的旧结论。历史文件中的“当前”“唯一计划”“默认”“PASS”都限于其当时版本，不能覆盖上述入口。

## 分类与权威性清单

分类：ACTIVE 当前生效；REFERENCE 按注明范围查阅；HISTORICAL 历史证据；DRAFT 前提或审阅未完成；SUPERSEDED 已被后续方案取代。分类不删除证据，也不表示软件能力通过认证。

[机器可读清单](document-authority.json)按顺序匹配，每份 Markdown 必须归入一个类别；以下覆盖当前文档目录及根文件，具体例外优先。

| 文件或范围（相对仓库根） | 分类 | 使用边界 |
|---|---|---|
| AGENTS.md、README.md、本 INDEX | ACTIVE | 规则与导航 |
| AI_HANDOFF.md | HISTORICAL | 已完成的原提交交接，独立审查 PASS_WITH_FINDINGS；不作为当前任务 |
| docs/PROJECT_WORKSPACE_POLICY.md | ACTIVE | 现行规则段；事故和旧审计段仍是历史 |
| docs/optimization/CURRENT_STATE.md、DECISION_LOG.md | ACTIVE | 分层事实、决策与重启门槛 |
| docs/optimization/DOCUMENT_AUDIT.md | REFERENCE | 本次审计范围、缺口和方法 |
| PRODUCTIZATION_PROTOCOL.md | REFERENCE | RC1.11 起的历史协议与门禁原则；不是当前核心字节冻结断言 |
| README_CN.md、OPENAI_API_QUICKSTART_RC1.20.md | REFERENCE | 历史产品／API 指南；当前行为需同 SHA 校验 |
| CHANGELOG.md、TEST_RESULT.md | REFERENCE | 追加记录；旧 Build109 内容不证明当前 main |
| Vendor/README.md、THIRD_PARTY_MLX_VISION_NOTICE.md | REFERENCE | 依赖构建／来源信息；不是发行许可认证 |
| device_tests/README.md | REFERENCE | 区分 Build106 入口和旧 Build89 runner；不是设备 PASS |
| docs/development/Bonsai_RC1.26_Build106_Optimization_Plan.md | SUPERSEDED | v1 原始研究输入；不再是唯一生效计划 |
| docs/development/2026-10-13-bonsai-optimization-plan.md | DRAFT | v2 候选路线；缺原 Spec 和完整迁移证据，不能直接照单执行 |
| docs/optimization/release/THIRD_PARTY_AUDIT.md | DRAFT | T16 候选审计；其中资源和流程不能当成当前 main |
| docs/optimization/release/EVIDENCE_MATRIX.csv | DRAFT | R01–R18 候选矩阵；缺失文件范围见审计清单 |
| docs/release/*.md | HISTORICAL | 仓库迁移／规划交付快照，含旧源仓库身份 |
| docs/history/*.md | HISTORICAL | 设计纠错、实验决策及原始状态保留 |
| docs/optimization/backburner-integration/*.md | HISTORICAL | RC1.26 各 build 的设计与局部设备结果，不能继承到后代 |
| archives/rc-history/**、archives/Bonsai_iPad_Project_Research_20261011/** | HISTORICAL | 原研究、SHA、失败证据与历史 EVIDENCE_MATRIX 保持原位 |
| tools/tests/test_release_manifest.py 等候选测试 | REFERENCE（非文档） | 文件存在不代表依赖完整或测试 PASS；见 CURRENT_STATE |

没有第二份 ACTIVE 优化实施计划。下一步以 CURRENT_STATE 的允许任务及证据前提为准；恢复 v2 Spec 后再审阅其任务与当前源码差异。

## 证据与维护入口

- [审计及缺失引用范围](optimization/DOCUMENT_AUDIT.md)、[候选文件范围清单](optimization/candidate-references.json)
- [历史研究 EVIDENCE_MATRIX](../archives/Bonsai_iPad_Project_Research_20261011/EVIDENCE_MATRIX.md)、[候选 R01–R18 矩阵](optimization/release/EVIDENCE_MATRIX.csv)
- [CHANGELOG](../CHANGELOG.md)、[TEST_RESULT](../TEST_RESULT.md)、[ChatGPT 交叉审查交接](../AI_HANDOFF.md)
- [当前 iOS workflow](../.github/workflows/build-ios.yml)、[Build106 操作入口](../device_tests/README.md)

更新规则：身份或证据变化时更新 CURRENT_STATE，并保留旧观察来源；决策变化追加 DECISION_LOG，注明范围和替代关系；新增／替代文档更新分类。提交前在官方目录运行：

```powershell
python tools/documentation_consistency.py
python -m unittest discover -s tools/tests -p test_documentation_consistency.py -v
git diff --check
```

校验只证明文档分类、相对文件链接、候选引用范围、main／CI／baseline 快照 SHA 和现行工作区规则一致，以及已完成交接保持 HISTORICAL；不要求开发分支 HEAD 等于 main，不检查远端页面存活、构建、推理或设备性能。

## PTQ1 单 IPA 自动竞赛候选

- [Build114 实现、证据边界与一键流程](optimization/PTQ1_ONECLICK_BUILD114.md)

- [Build115 启动恢复、Build112 系统崩溃证据与验证边界](optimization/PTQ1_BUILD115_STARTUP_RECOVERY.md)

- [Build116 真机入场条件与 iPad GPU 名称修复](optimization/PTQ1_BUILD116_DEVICE_ADMISSION.md)

- [Build124 SDOT implementation and pending Apple validation](build124/STATUS.md)
