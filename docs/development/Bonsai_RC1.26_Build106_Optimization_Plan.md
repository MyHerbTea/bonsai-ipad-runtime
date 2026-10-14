# Bonsai iPad RC1.26 Build106 后续优化推进计划

状态：SUPERSEDED。v1 为原始研究输入；后续 [v2 计划](2026-10-13-bonsai-optimization-plan.md)仍为 DRAFT。当前不存在第二份 ACTIVE 实施计划，执行前读取 [INDEX](../INDEX.md) 与 CURRENT_STATE。

版本：Optimization Plan v1.0
基线：RC1.26 Build106
原目标（已被后续方案替代）：作为 Codex 持续开发、自动化测试、版本推进的工作计划输入

---

# 0. 当前项目判断

Build106 不应该继续采用“不断增加性能参数”的路线，而应该进入：

> 稳定基线建立 → 自动化验证 → 单变量性能优化 → 真机认证 → 冻结发布

当前核心矛盾不是模型无法运行，而是：

1. 32K Context 已经接近 M5 12GB 内存边界。
2. 性能优化（B16/B24/B32、KV reuse、多序列）与稳定性存在冲突。
3. 实验参数过多导致无法判断真实收益来源。
4. CI、源码版本、IPA、真机状态必须建立统一身份链。

Build105 已完成安全恢复方向：
- 单序列 KV；
- B24 默认关闭；
- SAFE4 回退；
- 保留 Build103 输出能力。

因此 Build106 第一目标不是更快，而是成为可靠实验平台。

---

# Phase 0：版本身份冻结（最高优先级）

## 目标

建立唯一可追踪版本身份。

## 任务

### 0.1 建立 Release Manifest

新增：

```
release_manifest.json
```

字段：

```json
{
  "build": 106,
  "git_sha": "",
  "prism_sha": "",
  "model_sha256": "",
  "vision_sha256": "",
  "context": 32768,
  "batch": 8,
  "ubatch": 8,
  "n_seq_max": 1,
  "governor_profile": "BALANCED8"
}
```

所有 API debug、测试报告、IPA 打包均读取该文件。

## 验收

PASS：
- App 显示 SHA
- API debug 返回 SHA
- Windows 测试报告包含 SHA
- IPA 与源码一致

---

# Phase 1：Build106 CI 收敛

## 目标

让 Build106 成为可构建候选。

## 当前问题

历史 Build contract 仍绑定旧版本。

## 任务

禁止：
- 删除测试
- 修改测试为永远 PASS
- 跳过 workflow

正确方案：

将：

```
BuildXX contract test
```

升级为：

```
Current Release Contract
```

检查：

- 当前 Build
- 当前 SHA
- 当前 runtime contract
- 当前 artifact

## 验收

GitHub Actions：

```
Build
Contract
IPA
Artifact
Checksum

全部 PASS
```

---

# Phase 2：Build106 真机安全认证

## 原则

一次只改变一个变量。

禁止同时改变：

- Context
- Batch
- KV
- Governor
- Vision

---

## 测试矩阵

### A. 启动测试

配置：

```
Context=32768
n_seq_max=1
SAFE4
```

验证：

- API READY
- 无闪退
- 重启恢复
- trace 完整

---

### B. 文本 API

测试：

- 简单问答
- 中文 UTF-8
- 多轮
- SSE
- output >256

记录：

- TTFT
- prefill
- decode tok/s
- completion tokens

---

### C. Vision

测试：

- 单图
- 双图
- 三图
- 图后追问
- 错误图片恢复

---

# Phase 3：性能优化路线

## 原则

稳定版本：SAFE4/BALANCED8

实验版本：B16/B24/B32

不能直接替换默认。

---

# 优化方向 1：Batch Governor

## 当前策略

```
SAFE4
BALANCED8
PERFORMANCE16
TURBO24
LEGACY32
```

## 优化目标

建立自动选择：

输入：

- Context
- RAM
- 历史失败记录
- 温度状态

输出：

- batch profile

但必须：

启动阶段决定。

禁止运行中切 batch。

---

# 优化方向 2：32K Context 内存优化

目标：

不是扩大 Context，而是降低：

- KV footprint
- scheduler metadata
- startup peak memory

实验顺序：

1. Q4 KV
2. mmap 优化
3. scheduler metadata
4. Metal tensor layout
5. KV reuse

每一步必须独立 benchmark。

---

# 优化方向 3：KV Reuse

当前状态：

关闭。

原因：

Build104 双序列 KV 曾导致启动风险。

重新开启条件：

必须证明：

- n_seq_max=1 无影响
- 单轮/多轮一致
- 图文不会污染 KV
- crash rate 不增加

否则保持关闭。

---

# 优化方向 4：Vision Pipeline

当前路线：

MLX Vision Sidecar
+
BVCACHE1
+
Native injection

继续优化：

1. cache 生命周期
2. embedding 内存释放
3. 多图拼接质量
4. OCR benchmark

不要重新引入 mtmd 全驻留方案。

---

# Phase 4：自动化测试体系升级

最终目标：

一个命令完成：

```
Install
↓
Connect API
↓
Health
↓
Text
↓
Vision
↓
Long Context
↓
Performance
↓
Report ZIP
```

输出：

```
FINAL_REPORT.md
metrics.json
logs/
trace/
snapshot/
```

---

# Phase 5：性能 Benchmark 标准化

所有性能测试必须固定：

## Hardware

```
iPad Pro M5
12GB RAM
iPadOS 27.0.1
```

## Model

```
Ternary-Bonsai-2-27B-PTQ1_0
```

## Metrics

必须记录：

|指标|意义|
|-|-|
|TTFT|首 token体验|
|Prefill|长输入速度|
|Decode tok/s|持续输出|
|Peak RAM|稳定性|
|Crash rate|可靠性|

---

# Codex 工作规则

每次任务必须遵守：

## 开始前

读取：

```
PROJECT_RESEARCH_AND_HANDOFF.md
EVIDENCE_MATRIX.md
本计划
```

确认：

- 当前 branch
- 当前 SHA
- 当前测试状态

---

## 修改原则

一次只解决一个问题。

禁止：

- 同时改 Engine + API + Vision + Governor
- 没有 benchmark 的性能优化
- 没有真机测试的稳定性声明

---

## 提交要求

每次提交必须包含：

```
CHANGELOG.md
TEST_RESULT.md
rollback SHA
benchmark result
```

---

# 最终路线图

```
Build106 CI PASS
        |
        v
Build106 SAFE4 真机认证
        |
        v
Build106 BALANCED8 认证
        |
        v
B16/B24 单变量性能实验
        |
        v
32K Stable Release Candidate
        |
        v
Bonsai 27B iPad Production Engine
```

---

# 当前下一步唯一任务

不要继续调性能。

下一轮 Codex 应执行：

1. 修复 Build106 CI contract。
2. 生成 Build106 完整测试 IPA。
3. 在 M5 真机执行 SAFE4/BALANCED8 验证。
4. 收集完整报告。
5. 再决定是否恢复 B16/B24 性能实验。

这是当前风险最低、收益最高的推进路径。
