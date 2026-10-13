# 新开发者快速接手：Bonsai iPad 27B

> 这是《PROJECT_RESEARCH_AND_HANDOFF.md》的实际操作入口。本页面不能取代完整报告，尤其不能抹掉版本及真机认证范围。2026-10-11 快照。

## 第一天的任务不是改代码

**先分清四种“最新”**：GitHub 默认 `main` 是旧 RC1.23.1；`frozen-v1-rc1-25-3-build64-device-certified` 是 2048 Context 的正式历史设备基线；Build75 是独立 2048 Context 冷启动/性能检查点；Build105 为成功 CI 的较新 32K 安全启动修复候选；Build106 仍在快速推进，未报告冻结设备认证。

### 克隆及定位

```powershell
git clone https://github.com/MyHerbTea/bonsai-ipad-prob.git
cd bonsai-ipad-prob
git fetch --all --prune
git branch -r
git log -1 --format="%H %ad %s" origin/lab-v1-rc1-26-build105-startup-recovery
# 下面分支正在变化，仅查看，不要未经验证直接部署
git log -1 --format="%H %ad %s" origin/lab-v1-rc1-26-build106-m5-governor
```

**不能**在 `main` 上直接开始“接续 RC1.26 的最新开发”。先建立独立 worktree，并明确新分支由哪个固定、可解释 SHA 衍生。不要往冻结分支回写代码。

### 按此顺序读代码

1. `project.yml`、`.github/workflows/build-ios.yml`：什么才是真实 Build Identity 与真实 Prism 二进制。
2. `PRODUCTIZATION_PROTOCOL.md`、`README_CN.md`、`docs/backburner-integration/BASELINE_MANIFEST.json`：目标、冻结范围、后退路线。
3. `BonsaiLab/ProductionView.swift` 的 `startAPIServer` 和 `applyBuild82LongContextPolicy`：具体配置如何进入推理 Context。
4. `BonsaiLab/BonsaiEngine.swift` 的 `loadModel` / `makeContext` / `generateText` / `generateCachedVision`：本地 27B 推理和 KV 边界。
5. `BonsaiLab/LocalOpenAIServer.swift` 的 `process`：OpenAI JSON/SSE/模型发现/鉴权。
6. `BonsaiLab/BonsaiMLXVisionSidecar.swift`、`StagedVisionBridge.mm`、`OpenAIMultiImageComposer.swift`：视觉和缓存。
7. `Build94BatchExperiment.swift`、`Build105StartupRecovery.swift`、`M5RuntimeGovernor.swift`：B4/B8/B16/B24/B32 的下次启动选择和恢复保护。
8. `tools/rc126_build105_full_stage_certification.py`、`tools/RUN_BUILD105_GUI.ps1`：不用额外手工参数配置的统一真机测试。

### 第一个任务建议

修复 Build106 CI 的 **跨版本遗留身份断言**，但不要通过删测试、通配旧版号、跳过失败步骤来获得绿色。源码门禁正确后仍需 M5 真机认证。

在改动之前：检查当前 Build106 `git rev-parse HEAD`、对应最近 Actions run、其真正失败步骤、Build105 已成功产物 SHA。**本报告用固定快照，最新开发 HEAD 可能已经改变。**

### 真机与 Windows 自动化的正确关系

- iPad 已安装签名后的 unsigned IPA；选中外部 GGUF / 可选 Vision Tower；保持 App 在前台并启动本机 LAN API。
- Windows 双击相应 Build 的 `tools/RUN_BUILD*_FULL_STAGE.cmd`；窗口输入 LAN host 和 API Key；Python 3.8+ stdlib，避免繁琐配置。
- 测试 ZIP 要核对 Build、真实 Batch/Context、文本、SSE、multi-turn、output >256、1–3 image、图后文本，以及出错后的存活。
- Windows 没办法通过普通 HTTP 自动重启 iPad 已被系统杀死的 App；对中断必须记录 FAIL/INCONCLUSIVE 和原生 trace。

### 五个不能做的动作

1. 只看到 `CURRENT_PROJECT_VERSION=106` 就称“Build106 已通过”。
2. 把 `/health.context_window=32768` 当作真实 32768-token 输入性能认证。
3. 强行把 `n_seq_max=2` 或实验 KV checkpoint 打开以追求速度。
4. 把多图 contact sheet 说成 3 路独立图像 token 输入。
5. 将 Key、用户图片、用户私有 Prompt/response 打包到结果 ZIP 或公开 GitHub。

## 当前交接判定

**接手可以开始，发布不应冒进。** 有可信的历史设备基线与可构建候选，但 32K 全功能/真机稳定还需要统一证据。第一里程碑是可信身份 + 单次全阶段回归 + 安全回滚，之后再谈性能收益。
