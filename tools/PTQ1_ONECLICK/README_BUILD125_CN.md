# Build125 双行SDOT一键A/B/C

完整解压本包；使用现有签名方式安装唯一的unsigned IPA，加载官方PTQ1_0模型并打开API。Windows双击 RUN_PREFILL_COMPARE.cmd，仅输入API地址和必要Key。便携Python包含在包中，无需安装运行环境、编辑配置或逐个调用API。

A=原始CPU flags0；B=已验证Build124单行SDOT flags64；C=Build125双行SDOT flags128。三者同一IPA。16K、Batch/UBatch8/8、KV Q4_0、精确tokenizer确认512输入、128输出预算，counting off、sampling period0。各一次预热，正式顺序A1→B1→C1→C2→B2→A2，总计9次推理，不自动补测。不是另做Build124独立确认。

主要投入决策只比较C/B；A保留参考。相对改善<3%或未超过组内波动则建议停止CPU微内核方向；>=5%、CPU节点改善且无回退则建议保留双行；其余不确定，均交用户决定，不自动晋级或开始GPU分析。

双行只对当前列成对权重行启用，奇数尾行/不支持形状回单行。工具要求C有实际pair_chunks及pair_rows，A/B不得命中；计数来自现有prefill线程TLS按chunk汇总，不增加每dot原子计数。A/B/C关闭计数的控制检查按每逻辑行一致。单行Build124热点数学代码保留；生产-1路径不改。

结果位于RESULTS/prefill-时间/：COMPARISON.md、完整report.json、samples.csv、完整合成请求和统一results.zip。只需交results.zip，无需拼日志。无效token数、路径未命中、错请求profile、数值不一致、错误或恢复失败不会报告完成；不确定请求不重放，保留隔离标记。认证Key和checkpoint会话状态不纳入ZIP。

CPU节点区间含屏障等待，GPU时间是全请求command-buffer之和且可能重叠、含decode；不能相加或当prefill独占GPU成本，缺失显示unavailable。

Build125门禁和Release成功只证明实现可进入测试；本阶段不执行真机推理，双行真实收益待你一次测试后决定。保持生产默认，不创建Stable Release。历史Build124/120说明仅供参考。
