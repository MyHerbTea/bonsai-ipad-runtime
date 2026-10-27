# API 思考模式配置实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Build129 增加 App 默认思考模式设置和 OpenAI API `reasoning_effort` 支持声明，同时保持默认直接回答和 Q8/B8 性能基准不变。

**Architecture:** `ProductionView` 持久化一个默认关闭的 API 思考模式开关；`LocalOpenAIServer` 每次请求读取该默认值，未指定参数时关闭映射到 `none`、开启映射到 `medium`，显式请求值优先。健康状态和模型发现信息从同一策略公布能力；现有引擎 prompt 分支继续负责生成模式。

**Tech Stack:** SwiftUI、Swift、Python source-contract tests、现有 GitHub Actions iOS workflow。

**Spec:** [API 思考模式配置设计](../specs/2026-10-27-api-reasoning-effort-design.md)

## Global Constraints

- 思考模式默认关闭，默认 API reasoning effort 为 `none`。
- App 开启时仅改变省略 `reasoning_effort` 的 API 请求默认值为 `medium`。
- 显式 API 值优先，并仅接受 `none`、`minimal`、`low`、`medium`、`high`、`xhigh`。
- 设置即时生效，不重建模型或推理上下文。
- Q8_0、PTQ1_0、Metal B8、上下文和其他运行参数保持不变；性能基准显式使用 `reasoning_effort=none`。
- Build129 的构建身份、项目版本、workflow 和构建产物命名必须一致；Build128 历史分支和证据保持不变。

## Review Focus

- 默认关闭时省略参数仍执行直接回答：测试 UI 默认值、服务默认解析和 `/health`。
- 开启设置后省略参数使用 `medium`：测试默认值读回及模型发现。
- 显式 `none` 在开关开启时仍优先：测试请求覆盖规则。
- 错误字符串或非字符串类型不能静默退回默认：测试请求校验失败路径。
- 健康检查和 `/v1/models` 的能力与默认强度一致：测试两个发现入口都公布 reasoning 支持。

---

### Task 1: API 思考模式契约测试

**Files:**
- Modify: `tools/rc1252_api_usability_contract_tests.py`
- Test: `tools/rc1252_api_usability_contract_tests.py`
- Test: `tools/build129_reasoning_effort_policy_tests.swift`
- Test: `tools/build129_reasoning_effort_policy_tests.swift`

**Interfaces:**
- Consumes: 当前 `LocalOpenAIServer.parseChatPayload` 与模型发现契约。
- Produces: 对 App 默认开关、默认值、请求覆盖和 reasoning 能力声明的失败优先回归检查。

- [x] **Step 1: 修改契约断言**
  - 取代“reasoning 不支持”断言，要求 `supported_parameters` 包含 `reasoning_effort`，health/model capabilities 均为 true。
  - 要求 App 设置键默认关闭，API 设置说明文案能说明 `medium` 默认和请求覆盖。
  - 要求 API parser 使用 App 默认值，但显式 `reasoning_effort` 覆盖默认值并保留六值校验。
  - 要求复制 API 配置与诊断能力字段不再写死为 Reasoning OFF。
  - 要求内部性能基准仍显式传 `none`。

- [x] **Step 2: 运行契约并确认失败**
  - Run: `python tools/rc1252_api_usability_contract_tests.py`
  - Expected: FAIL，失败点只涉及尚未实现的 reasoning 配置/发现行为。

### Task 2: 实现 App 默认设置与 API 覆盖

**Files:**
- Modify: `BonsaiLab/ProductionView.swift`
- Modify: `BonsaiLab/LocalOpenAIServer.swift`
- Add: `BonsaiLab/APIReasoningModePolicy.swift`
- Add: `BonsaiLab/APIReasoningModePolicy.swift`

**Interfaces:**
- Consumes: Task 1 固定的 setting key `BonsaiLocalAPIThinkingModeEnabled` 和现有 reasoning effort parser。
- Produces: 持久化 UI 默认开关；API 未指定值时返回 `none` 或 `medium`；请求指定值优先；health/model metadata 一致声明支持。

- [x] **Step 1: 增加 App 设置**
  - 在局域网 OpenAI API 设置区添加 `@AppStorage("BonsaiLocalAPIThinkingModeEnabled")` 开关，默认 false。
  - 开启映射到 `medium`；说明客户端显式参数覆盖，设置对运行中的 API 即时生效。
  - 更新 API 能力摘要、复制配置和诊断输出，避免继续宣称 reasoning 不支持。

- [x] **Step 2: 接通 API 默认值与显式覆盖**
  - 将设置开关映射为服务当前默认值，按请求读取，不缓存到模型上下文。
  - 把默认值传入 `parseChatPayload`；缺参使用默认，显式字符串使用请求值。
  - 若参数存在但类型错误，返回 `unsupported_reasoning_effort`，不得当作缺参静默使用默认。
  - `/health` 与 `/v1/models` 公布 reasoning 支持及当前默认；保留现有六值合法列表和引擎调用。
  - 在已有受鉴权、无提示词请求 trace 中记录解析后的 `reasoning_effort`，让真机 TestKit 能按 request ID 核实实际采用值。

- [x] **Step 3: 重跑专项契约**
  - Run: `python tools/rc1252_api_usability_contract_tests.py`
  - Expected: PASS。

### Task 3: Build129 身份、文档与 CI 构建

**Files:**
- Modify: `project.yml`
- Modify: `.github/workflows/build-ptq1-tournament.yml`
- Modify: `docs/INDEX.md`
- Modify: `docs/document-authority.json`
- Modify: `tools/documentation_consistency.py`
- Test: `tools/tests/test_documentation_consistency.py`
- Add: `tools/package_build129_reasoning.py`
- Add: `tools/BUILD129_REASONING_TESTKIT/*`
- Test: `tools/tests/test_build129_reasoning_package.py`
- Add: `tools/package_build129_reasoning.py`
- Add: `tools/BUILD129_REASONING_TESTKIT/*`
- Test: `tools/tests/test_build129_reasoning_package.py`

**Interfaces:**
- Consumes: Task 2 的 API 设置与元数据。
- Produces: 与 Build128 分离的 Build129 源分支和 CI IPA/TestKit 构建身份。

- [x] **Step 1: 建立 Build129 候选分支和构建身份**
  - 从当前 Build128 性能分支建立 `codex/build129-reasoning-mode`。
  - 将项目版本、workflow push trigger、`BUILD_NUMBER`、CI 注入的 source SHA/build identity 和 artifact 名称统一为 129；由 `/debug/build` 的动态 build number/source SHA 核验设备身份，不覆盖历史静态标签。
  - 独立打包 Build129 思考模式 TestKit；不复用 Build128 Q8/B8 性能运行器。
  - 保留旧 Build128 分支和原 workflow 历史。

- [x] **Step 2: 更新文档导航与分类**
  - 将新设计和实施计划标记为 DRAFT，并在 `docs/INDEX.md` 增加链接；不改写 Build128 测量结论。

- [x] **Step 3: 执行本地验证**
  - Run: `python tools/rc1252_api_usability_contract_tests.py`
  - Run: `python tools/documentation_consistency.py`
  - Run: `python -m unittest discover -s tools/tests -p test_documentation_consistency.py -v`
  - Run: `git diff --check`
  - Expected: 可运行的源码、包装、文档检查 PASS；Swift 编译与 IPA/TestKit 由 macOS CI 验证。

- [ ] **Step 4: 提交并推送 Build129 分支触发 CI**
  - 仅推送 `codex/build129-reasoning-mode`；不合并 main、不改生产默认。
  - CI 必须明确验证 Build129 IPA 与 TestKit 身份；设备真机效果仍单独标为待测。
