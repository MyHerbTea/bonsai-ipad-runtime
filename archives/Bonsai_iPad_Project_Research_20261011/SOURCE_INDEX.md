# 源码和一手证据导航（可直接点击）

> 所有路径均从 GitHub API 递归树确认；“分支”是为了可读性，关键版本请以 SHA 固定。并非逐行静态审计全部文件。

仓库：https://github.com/MyHerbTea/bonsai-ipad-prob  
Build105 固定 SHA：`4c25b0abd79d316754b0e612ab7c5fa53cabffd6`  
Build106 核心分析固定 SHA：`37291498aed19cc357f8a53ec8115d7b9be482e3`  

## 必读的入口文件

| 模块 | Build105 固定源码链接 |
|---|---|
| XcodeGen 配置 | [project.yml](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/project.yml) |
| macOS GitHub Actions | [build-ios.yml](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/.github/workflows/build-ios.yml) |
| 产品 UI 与 API 管理 | [ProductionView.swift](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/BonsaiLab/ProductionView.swift) |
| 原生 Engine | [BonsaiEngine.swift](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/BonsaiLab/BonsaiEngine.swift) |
| OpenAI LAN 服务器 | [LocalOpenAIServer.swift](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/BonsaiLab/LocalOpenAIServer.swift) |
| MLX Vision | [BonsaiMLXVisionSidecar.swift](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/BonsaiLab/BonsaiMLXVisionSidecar.swift) |
| Native cache/injection | [StagedVisionBridge.mm](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/BonsaiLab/StagedVisionBridge.mm) |
| OpenAI 图文归一化 | [OpenAIMultimodal.swift](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/BonsaiLab/OpenAIMultimodal.swift) |
| 多图拼接 | [OpenAIMultiImageComposer.swift](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/BonsaiLab/OpenAIMultiImageComposer.swift) |
| Batch 状态机 | [Build94BatchExperiment.swift](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/BonsaiLab/Build94BatchExperiment.swift) |
| Build104 → 105 恢复 | [Build105StartupRecovery.swift](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/BonsaiLab/Build105StartupRecovery.swift) |
| 运行指标 | [RuntimeOptimization.swift](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/BonsaiLab/RuntimeOptimization.swift) |
| 认证状态 | [CertificationRunRecorder.swift](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/BonsaiLab/CertificationRunRecorder.swift) |
| Build106 独立 Governor | [M5RuntimeGovernor.swift](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/37291498aed19cc357f8a53ec8115d7b9be482e3/BonsaiLab/M5RuntimeGovernor.swift) |

## 历史及设备事实

- 历史总方针：[PRODUCTIZATION_PROTOCOL.md](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/PRODUCTIZATION_PROTOCOL.md)
- Multi-image 实测：[Build57](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/RC1.25.0_BUILD57_DEVICE_EVIDENCE.md)、[Build60](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/RC1.25.1_BUILD60_DEVICE_EVIDENCE.md)
- Build64 冻结：[manifest](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/docs/backburner-integration/BASELINE_MANIFEST.json)
- 真实 Decode 吞吐：[Build55](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/RC1.24.0_BUILD55_DEVICE_EVIDENCE.md)、[Build56](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/RC1.24.1_BUILD56_DEVICE_EVIDENCE.md)
- Build75 Stable：[文档](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/docs/backburner-integration/RC1.26_BUILD75_STABLE_CHECKPOINT.md)、[CI 37449639193](https://github.com/MyHerbTea/bonsai-ipad-prob/actions/runs/37449639193)
- Build79 长 Context：[文档](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/docs/backburner-integration/RC1.26_BUILD79_STORAGE_MEMORY_LONG_CONTEXT.md)
- Build89 内存问题：[文档](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/docs/backburner-integration/RC1.26_BUILD89_COMPACT_SCHEDULER_METADATA.md)
- Build94 内核边界纠错：[文档](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/docs/BUILD94_AI_AB_RECONCILED_DECISION.md)
- Build102 B16/B24/B32：[文档](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/docs/backburner-integration/RC1.26_BUILD102_32K_BATCH24_32_SWEEP.md)
- Build103 output cap：[文档](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/docs/backburner-integration/RC1.26_BUILD103_INTEGRATED_OUTPUT_STAGE.md)
- Build104 事故前设计：[文档](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/docs/backburner-integration/RC1.26_BUILD104_INTEGRATED_32K_PERFORMANCE.md)
- Build105 回退：[文档](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/4c25b0abd79d316754b0e612ab7c5fa53cabffd6/docs/backburner-integration/RC1.26_BUILD105_STARTUP_RECOVERY.md)、[CI 38070840581](https://github.com/MyHerbTea/bonsai-ipad-prob/actions/runs/38070840581)
- Build106 发展：[文档](https://github.com/MyHerbTea/bonsai-ipad-prob/blob/37291498aed19cc357f8a53ec8115d7b9be482e3/docs/backburner-integration/RC1.26_BUILD106_M5_GOVERNOR.md)、[初始失败 38142193090](https://github.com/MyHerbTea/bonsai-ipad-prob/actions/runs/38142193090)

## CI 关联失败示例

`38142193090` 的 Build93 Contract 在入口处仍要求 `CURRENT_PROJECT_VERSION: "105"`，但 `project.yml` 更新至 106，造成 AssertionError。这是一个已核对的源身份门禁错误，不等于 Build106 GPU 推理结果。

## 非默认原则

**任何报告引用性能时，必须同时记录 Context、actual Batch/uBatch、真正 input/completion tokens、启动状态、热状态、来源 SHA、实测设备、是否 full response、是否存在 KV reuse。** 单写“27B 有 xx tok/s”不足以构成工程证据。
