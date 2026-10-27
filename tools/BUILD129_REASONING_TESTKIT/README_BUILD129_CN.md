# Build129 思考模式功能测试包

此包仅验证 App 默认开关、API 能力发现、`reasoning_effort` 请求覆盖和 Build/SHA 身份。它不是性能测试，也不代表 M5 稳定性认证。

## 测试步骤

1. 安装同一候选包中的 `BonsaiLab-Build129-Reasoning-unsigned.ipa`，按你现有的签名与安装方式安装。
2. 在 M5 iPad 上启动 API。测试电脑需能访问 iPad 的局域网地址；默认地址为 `http://192.168.1.92:8080`。
3. 双击 `RUN_BUILD129_REASONING_API_SMOKE.cmd`。按提示先关闭 App 中的思考模式开关，再开启；API 无需重启。
4. 若 API 要求 Key，运行器会安全提示输入；Key 只保存在当前进程内，不写入报告。
5. 报告、原始 JSON 响应和 SHA-256 清单写入 `RESULTS`。成功状态为 `PASS_FUNCTIONAL_SMOKE`。

运行器会核对 `/health`、`/v1/models` 和 `/debug/build`，然后各发送两个极短请求：默认值及显式覆盖。每个完成请求都用唯一请求 ID 从受鉴权的 `/debug/request-trace` 读回服务实际解析的 `reasoning_effort`。预期关闭时默认值为 `none`，开启时为 `medium`；显式请求值应覆盖 App 默认。诊断只记录强度与请求状态，不记录提示词或 API Key。

若设备无法连通、身份不符、能力元数据不符或请求失败，报告保留为 FAIL/BLOCKED，不会自动重试切换策略或更改 App 设置。请求限为 4 个输出 token，单个推理请求最多等待 90 秒；此检查不测量速度、模型质量、长时内存或长期稳定性。
