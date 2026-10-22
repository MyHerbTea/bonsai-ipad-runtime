Bonsai Build114 PTQ1 一键真机竞赛

1. 完整解压整个交付 ZIP，保留 IPA、TestKitIdentity.json、DELIVERY_SHA256.json 和 python 文件夹。
2. 用现有侧载工具签名并安装同包 unsigned.ipa 一次（本仓库没有用户签名证书）。
3. iPad 导入官方 Ternary-Bonsai-2-27B-PTQ1_0.gguf，加载模型并开启本地 API 一次。
4. 电脑与 iPad 在同一局域网，保持 App 前台；双击 RUN_BONSAI_PTQ1_ONECLICK_BENCHMARK.cmd 一次。
5. 自动发现不唯一时仅输入一次地址；开启认证时仅输入一次 API Key。随后所有候选/参数均自动切换。

默认持续运行检查30分钟，之前还有筛选、对照、质量及调优，整体耗时取决于真机。
需要60分钟检查时可在CMD后附加 --duration-minutes 60。
不要为每种候选重开 App/API 或更换 IPA。结束后自动恢复启动时的生产上下文。
浏览器会打开中文 HTML，RESULTS/current 下同时有 JSON、CSV、结果ZIP及校验和。

若系统终止 App 或网络中断，脚本会保存检查点、隔离不确定请求配置并尝试取消/恢复。
进程已终止时 HTTP 无法启动 App：只需重新打开 App 并开启 API，然后运行同一入口；不会重放不确定推理。
没有全门槛合格候选即保留安全基线。INCOMPLETE 表示缺少证据，不能作为性能成功。
代码生成任务只接受受限 Python 子集，在独立进程执行有超时的测试，原始提示/答案与密钥不写入报告。
完整模型 SHA256、IPA/源码/工具身份、真实 GPU 提交/完成、实际 KV/批次均会核验。
CI 编译成功不代表 M5 性能或长期稳定性已验证。
