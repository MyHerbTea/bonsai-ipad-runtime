# API 思考模式配置设计

## 意图

在下一版 Bonsai iPad Runtime 中，让用户可在 App 的“局域网 OpenAI API”设置中配置默认思考模式，并让 OpenAI 兼容客户端通过 `reasoning_effort` 请求参数覆盖默认值。保持现有直接回答行为为默认值，避免影响现有 Q8/B8 性能基线。

## 实施前源码审计快照

- `LocalOpenAIServer.parseChatPayload` 已接受 `none`、`minimal`、`low`、`medium`、`high`、`xhigh`，但请求省略时固定使用 `none`。
- `BonsaiEngine.makeSimpleChatPrompt` 对 `none` 使用已闭合的空 `<think>` 区块；其他值使用开放的 assistant 前缀。
- API 的 `/health` 和 `/v1/models` 当前宣称 reasoning 不支持，模型元数据也未公布 `reasoning_effort`。
- App 目前没有文本聊天的思考模式默认设置；普通视觉演示仍固定使用 `none`。

## 方案

考虑了两种实现：

1. **只开放 API 参数**：修改最少，但用户无法在 App 设置默认值。
2. **App 默认开关 + API 请求覆盖（推荐）**：App 提供一个默认关闭的开关，开启映射到 `medium`；省略参数的 API 请求使用 App 默认值，显式传入的 `reasoning_effort` 优先。这样同时满足 App 配置和客户端控制。

按用户已选择的第二种方案实施。

## 行为与范围

- 在“局域网 OpenAI API”设置中增加持久化“思考模式”开关；默认关闭。
- 关闭时 API 默认 reasoning effort 为 `none`；开启时为 `medium`。设置即时生效，不重建模型或推理上下文。
- API 显式的 `reasoning_effort` 覆盖 App 默认值，并继续校验现有六种合法取值。
- `/health` 返回当前有效的 `default_reasoning_effort`；`/v1/models` 公布 `reasoning_effort`，并将 reasoning 能力标记为支持。
- 现有引擎 prompt 分支和 effort 指令保持不变；不新增独立 reasoning 输出字段，也不改写回答流。
- 视觉调试演示与其他内部基准保持 `none`。
- Q8_0 KV Cache、PTQ1_0 权重、Metal B8、上下文、生产默认和性能参数均不在本次修改范围。

## 验证

- 专项测试覆盖默认关闭、持久化开关、显式参数覆盖、非法值拒绝，以及 `/health` 与 `/v1/models` 能力声明一致；真机 TestKit 通过受鉴权请求 trace 核对每次请求实际解析的强度。
- iOS CI 构建验证源码和打包。
- 安装后用短文本请求分别验证默认 `none`、开关开启后的 `medium`、以及请求级覆盖。
- Q8/B8 性能比较始终显式设置 `reasoning_effort=none`，本功能不构成性能认证或生产默认变更。
