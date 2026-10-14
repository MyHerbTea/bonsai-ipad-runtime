# 文档治理审计 — 2026-10-14

状态：REFERENCE。基线 `dc169d6759e84e6b0f66c2c8ad87e6f073bd78c6`；官方目录 `D:\codexSpace\bonsai-ipad-runtime`。治理前 140 份 Markdown，7 个失效相对文件链接；本地只有 main，HEAD=origin/main=远端 main，working tree clean。未发现本地待保全工作；未检查旧目录、其他 checkout 或其工作树，不对它们作不存在断言。

## 方法与范围

逐项读取 AGENTS、README/README_CN、PRODUCTIZATION_PROTOCOL、PROJECT_WORKSPACE_POLICY、CURRENT_STATE、两份开发计划、规划交付摘要、仓库迁移基线、CHANGELOG、TEST_RESULT、两个 EVIDENCE_MATRIX；扫描全部 Markdown 的相对文件链接、分类覆盖与文件清单。历史资料按原路径分类，重点核对 Build75、76、94、105、106 与 RC1.23.5 的失败／决策原文。没有声称重新执行 140 份文档中的全部历史测试、逐行审计全部历史源码、重放原设备 ZIP 或验证所有远端链接。

## 已处理冲突

- AGENTS 补齐未闭合的 powershell fence，修正隐藏 worktree 路径中的空格，并只新增 INDEX 入口。
- 政策现行路径改为官方目录；旧事故和审计路径保留并限定为历史；旧“推荐纠正计划”不再是生效任务。
- PRODUCTIZATION_PROTOCOL、README_CN 限定历史范围，不以 RC1.11 字节冻结或早期 Lab 行为覆盖 Build106。
- v1 标 SUPERSEDED；v2 标 DRAFT，缺失 Spec 作为未恢复引用而非伪造文件。规划摘要中已有实施计划／状态链接指向现存文档，其他缺失文件保留原路径文字并注明不可用。
- 原 CURRENT_STATE 的 checkout 字节另存历史快照，Git blob 内容按 CRLF/LF 归一后完全一致（两种摘要见 evidence）；新状态分别说明 main、本地候选、CI、设备、性能。历史 T01–T16、CHANGELOG/TEST_RESULT 的 PASS 均不转给 main。
- T16 CSV 与第三方审计为 DRAFT；其 Build107 patch、release resources／manifest／certified envelope 等候选描述不代表当前 Build106。未修改历史矩阵和许可通知内容。

## 未恢复引用与候选范围

[candidate-references.json](candidate-references.json)收集旧 CURRENT_STATE 的关键缺失文件、v2 Spec／交付核对、T16 CSV 的逐项 implementation_evidence。每项均标 scope、当前 PRESENT / NOT_AVAILABLE、verification=NOT_VERIFIED。PRESENT 只证明路径存在，不证明候选功能、测试、部署或身份成立；NOT_AVAILABLE 不自动等于文件被删除、候选从未存在，或能从任意旧分支恢复。

缺失引用不是一条 ACTIVE 导航链接；历史原文留存，不通过新增空壳文件或替换 SHA 制造证据。待恢复的原始路径包括：
- `docs/specs/2026-10-13-bonsai-optimization-design.md`（迁移后计划所引用）
- `lab-v1-rc1-26-build106-m5-governor/docs/superpowers/specs/2026-10-13-bonsai-optimization-design.md`
- `lab-v1-rc1-26-build106-m5-governor/docs/optimization/CURRENT_STATE_20261013.json`
- `lab-v1-rc1-26-build106-m5-governor/docs/optimization/PLANNING_AUDIT_20261013.md`
- `docs/optimization/evidence/INPUTS.sha256`、`docs/optimization/evidence/build106-artifact-index.json`

当前仓库 main 的 CI 元数据已查询并存 [证据快照](evidence/main-ci-20261014.json)。旧 `bonsai-ipad-prob` 链接是历史源仓库来源，不批量改指向新仓库，避免伪造 SHA／artifact 身份。远端 URL 可用性不是本地文档校验的 PASS 范围。

## 校验及执行边界

复用 Python stdlib unittest 与已有 build-ios.yml；新增文档门禁只检查 Markdown 分类覆盖、相对文件链接、候选引用 availability/scope/verification 一致性和核心导航。校验不代替候选 release contracts，不调用设备，不修改推理核心或默认配置。

已知迁移缺口：现存 `test_release_manifest.py`依赖未迁入的 `tools.certification.identity`；current release contract 读取未迁入的 ReleaseManifest.swift。它们应由独立迁移任务修复，而不是让本次文档门禁伪报整个 tools/tests PASS。准确命令／结果见 [TEST_RESULT](../../TEST_RESULT.md)，交叉审查见 [AI_HANDOFF](../../AI_HANDOFF.md)。
