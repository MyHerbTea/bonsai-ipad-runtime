# Build124 一键 M5 闭环执行计划

目标：复用现有 Quick 客户端、会话及打包工具，交付同源码 IPA 与便携 Python，一次六请求实验得到可信的投入决策。
约束：生产默认不变；flag64 仅 Quick 16K/B8/Q4/counting off；不重放不确定请求；不创建 Stable Release。

- [x] 先用回归测试证明 flag64、请求关联、缺证据及决策分支问题。
- [x] 最小修复原生 A/B 关闭采样时的公共控制前缀；原始数学保持不变，ARM64 parity/汇编由 CI 执行。
- [x] benchmark 返回当前请求的完整 profile 与计数模式；客户端验证身份、实际配置、精确512 token、128预算、数值与请求关联。
- [x] prefill_compare 默认 SDOT 六请求（warm A/B、A1 B1 B2 A2），其余候选保持旧流程；失败立刻停止并恢复，统一中文报告与 ZIP。
- [x] 覆盖相对改善3/5%、基线及候选漂移、CPU节点变化、GPU不可用/重叠限制，生成源码级下一步。
- [ ] 实际 Windows CMD、专项 Python 测试、静态检查；提交推送现有候选分支触发 Release CI，下载并独立验证同 SHA 包。
- [ ] 真机 API 可用时仅检查身份，未安装新IPA时保留待执行；不冒充性能认证。

实施默认：保持 Build124 编号，以完整 source SHA 区分新旧IPA；不用新测试框架，不增加热路径计数器。SDOT路径证据为原生能力、实际 flag64、执行过PTQ1 CPU节点以及同SHA已检验的强制分支；这不是逐条指令硬件追踪。

本地专项：SDOT一键6、兼容Quick6、实际Windows启动器5、原工具10全部通过；SDOT源码/汇编解析2通过，实际Apple编译2本地skip待CI。文档治理检查失败源于历史ignored deliveries/，相关10测试中3失败，保留build/build124-oneclick-doc-*.txt，未当作PASS。
