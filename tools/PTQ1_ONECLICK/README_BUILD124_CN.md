# Build124 M5 SDOT 一键集中测试

1. 将本包解压到一个新文件夹，保留完整目录及 python 子目录。
2. 用现有签名方式安装本包中唯一的 Build124 IPA（unsigned IPA 需要先签名）。保持模型数据，启动当前 PTQ1_0 模型，开启局域网 API；iPad 保持前台。
3. Windows 双击 RUN_PREFILL_COMPARE.cmd，只输入 API 地址和必要的 Key；无需安装 Python、编辑配置或逐个调用 API。

工具核验 IPA/工具哈希、app 完整源码 SHA、M5/模型 SHA、实际原生配置和保护标记。旧 Build124 同编号但不同SHA会被拒绝，不能混用旧IPA。
固定同模型、16K、Batch/UBatch 8/8、KV Q4_0，tokenizer校准精确512输入，128输出预算。A原始CPU、B SDOT(flag64)，均counting off及sampling period0。
总计六次推理：A预热、B预热、A1→B1→B2→A2。预热不计分，不增加轮数，不自动重试或晋级。若模型提前EOS，作为不完整报告，避免不同输出量可比性错误。

结果在 RESULTS/prefill-时间/：COMPARISON.md（中文决策）、report.json、samples.csv、report.html、完整合成请求、统一results.zip及校验和。提交results.zip即可，无需拼日志。Key不写入报告；checkpoint含本地会话恢复状态，不纳入ZIP。
中断、错误、源身份不一致、候选未证实或计时缺证据均不会报告PASS；退出码2表示未完成或恢复未确认。存在未知请求时不得直接重跑，先保留证据检查App状态；不自动清除隔离标记。

工具结束会恢复进入实验前的实际运行配置。恢复失败明确报告；此时先停止其他推理并重启App检查。
判断使用相对Prefill改善与组内波动：<3%或不超过波动停止扩展，>=5%且CPU节点明显改善/无回退保留候选并建议一次简短确认，3%–5%或缺证据不确定。单轮ABBA不是最终认证。
CPU节点时间包含屏障等待，不等于可消除耗时；GPU时间为全请求command-buffer之和、可能重叠，包含decode，缺失显示unavailable，不能与CPU计时相加或当作prefill独占GPU耗时。
SDOT证据来自实际配置/原生能力、非零PTQ1 CPU节点和同SHA已检验强制分支，并非硬件指令追踪。生产路径不启用本候选。

新IPA真机性能：待执行。CI、数值parity和汇编检查均不证明性能提升。
