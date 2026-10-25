Build125当前入口：双击 RUN_PREFILL_COMPARE.cmd，详见 README_BUILD125_CN.md。A原始/B单行/C双行；各一次预热+ABCCBA共9请求，主要比较C/B。以下旧说明为历史。

Build124 当前任务：双击 RUN_PREFILL_COMPARE.cmd，输入API地址及必要Key。
先阅读 README_BUILD124_CN.md。固定六请求SDOT ABBA，自动生成统一results.zip；无须手工配置。
以下旧Full竞赛说明为历史参考，不是本轮测试入口。

Build118 集中Prefill对比
入口：RUN_PREFILL_COMPARE.cmd --url http://<iPad-IP>:8080
详细步骤及限制见 PREFILL_COMPARE.md。下方正式Full流程仍使用B16及旧隔离，不可与B8 Quick混用。

Bonsai Build117 PTQ1 一键真机竞赛

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

Build117 新增：逐候选 ABBA（每样本两次256 token预热）；漂移>5%警告、>10%不稳定；按候选目标评价并经5轮确认。
PTQ1_MV_R5 主要看decode；收益等级与晋级分开。mean±std不是置信区间。
App新增测试常亮设置、GET /debug/profiling、GET /debug/crashes、POST /debug/snapshot；沿用原API鉴权。
崩溃的完整JSON/Markdown通常在下次启动后生成；系统强杀可能只有未正常结束标记，不能推断根因。
匹配dSYM通过独立 Bonsai-Build117-Symbols 构建产物保留；UUID身份文件随CI_EVIDENCE分发。
详见 BUILD117_GUIDE.txt；真机验收完成前，不把候选构建当成已证实性能收益。
