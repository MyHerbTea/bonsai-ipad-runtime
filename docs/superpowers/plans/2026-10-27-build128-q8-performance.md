# Build128 Q8 Metal B8 执行计划

1. 先写失败测试，锁定唯一 Build126 Full 人工中止来源、精确更正文本与标记 ID；验证错 SHA、错配置、缺少任一归档证据和不一致审计读回都会拒绝恢复。
2. 以最小 Swift 改动允许该来源一次归档确认，把用户更正、报告/ZIP/诊断 SHA 写入并读回，然后仅移除该 Q8 标记。
3. 将恢复验证器加入 TestKit；不改写或搬动历史失败目录。首轮 Quick 固定 128-token 输入、32-token 输出上限、单请求 60 秒、全程 240 秒，仍为 16K/B8/Q8_0、flags 64/320、A-B-B-A；只有首轮胜出才增加 512-token 确认。
4. 将 app build、workflow 和 TestKit 同步到 Build128；运行受影响的 Python/Swift 测试、原有 B8 逻辑测试、打包与哈希检查；提交独立候选分支并等待 macOS CI IPA/TestKit。
5. 安装 Build128 后只运行一次 128-token Quick。记录真实 A/B 预填充、候选 dispatch、内存、温度和恢复。若 Quick 失败或中止，保存证据并停止，不自动再测长输入或切换 Q4。

本轮不碰生产默认、PTQ1 数学、Q8 KV 实现、其他性能参数或 Metal TensorOps。CI 与 Quick 不等于 Full 或 Stable 认证。
