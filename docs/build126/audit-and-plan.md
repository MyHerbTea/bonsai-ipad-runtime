# Build126 固定 Q8_0 审计与实施计划

审计基线：官方目录 D:\\codexSpace\\bonsai-ipad-runtime，分支 codex/build125-sdot-pair，干净 HEAD 5f304385e394e23f52e6ed6b4c1610829db75bdf。会话 iPad27B 副本 aa7404f 是 Build123，不作为来源。2026-10-26 只读审计完成后才开始本候选修改。

## 真实调用链与当前行为

- BonsaiLab/ProductionView.swift:927 AppStorage BonsaiRC1235APIContextProfile 默认4096；982白名单512/768/1024/2048/3072/4096/6144/8192/16384/32768/65536，非法持久化值回4096。1570 Picker运行时禁用；preservedRuntimeMatchesAPISelection:1006用ActiveAPIContext和ActiveAPIRuntimeProfile决定复用。UI选择不是已分配值。
- startAPIServer:3840捕获选择 -> apiRuntime.context:3944 -> applyBuild82LongContextPolicy -> engine.loadModel:4023 -> runtime.validated -> llama_context_default_params.n_ctx:713 -> llama_init_from_model:824。实际n_ctx/n_batch/n_ubatch由llama_n_*读取，现有B16 evidence的context字段仍取传入值。
- reconfigureAPIRuntimePreservingModel:3630（本节行号为Build125基线）停listener后选择参数 -> reconfigureTextContextKeepingModel:905 -> makeContext:3272 -> llama_init_from_model:3341。创建失败尝试previousRuntime一次，抛原错误。涉及GPU档位变化时走模型卸载/重载。活动推理由actor与benchmark lease串行管理；UI运行时禁用设置。Vision headroom/cleanup也可经makeContext重建，必须保留独立KV配置。
- loadModel:749和makeContext:3295明确按context阈值选择：<=4096 F16、4097..16383 Q8_0、>=16384 Q4_0，并强制量化V启用Flash Attention。这就是16K Q4原因，不是运行时测量后降级。benchmarkKV仅在makeContext覆盖；初次加载没有覆盖。bench restore清空覆盖再按旧context重算。
- RuntimeConfig:LabTypes.swift:10只含context没有KV策略；Equatable因此也无法识别KV变化。BonsaiBuild79KVCacheType在初次加载前写持久化，不证明当前context，重建后可能过时。
- B16RuntimeEvidence.created:59标注successful_native_creation_parameters；Engine:843/3356记录传入type_k/v，不是读取KV tensor。benchmark actual是candidate.json。现有链只能证明请求参数及成功创建，缺少独立tensor读回。
- 固定Prism上游adfffbe41b2cabcd51fff326ab045662265062bb：src/llama-context.cpp传params.type_k/v到model.create_memory；默认F16；量化V需要Flash，头维度不满足量化块尺寸时返回NULL；异常返回NULL。src/llama-kv-cache.cpp:262/263用该类型建tensor，未发现按context切Q4。Build83分层分配、84..89和115调度器malloc/mmap/compact恢复不改变KV dtype；保留。不能把NULL直接断言为OOM。
- 主模型general.file_type=143/PTQ1_0、SHA53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3，与KV Q8_0完全不同；CPU乘法临时Q8激活也不是KV。
- 当前Build125 Quick为B8/8,Q4_0,GPU56,线程6,mmap,flags64单行保留；双行128未晋级。既有Quick仅放行Q4；Full初始B16/Q4，均不适合直接验证Q8。旧失败marker不清理。
- .github/workflows/build-ptq1-tournament.yml是Build125实际路径：Windows真实CMD测试 -> macOS15固定Prism+原补丁链 -> Swift/Python/native检查 -> XCFramework -> 同SHA注入 -> xcodegen -> unsigned Release IPA + dSYM -> package_ptq1_oneclick.py带便携Python/manifest。build-ios.yml和build112工作流是旧独立入口，不取代当前。本机Windows没有xcrun/Swift；Apple编译必须走现有CI。
- tools/PTQ1_ONECLICK现有Client/Tournament保存请求级配置、模型SHA、source/process/context身份、50ms采样footprint/Metal/available、GPU完成和同请求profile。HTTP无法冷启动或重启被系统终止的iPad App，签名证书也不在仓库；一键工具须明确人工安装/进程重启边界，不伪造冷启动。
- 原始Build125设备结果在iPad27B/Build125-Delivery，Quick COMPLETE不是Full稳定认证。原文件只读保留。

## 最小方案与取舍

采用独立RuntimeConfig KV策略：legacy保持原生产行为，另提供固定Q8_0（内部明确F16/Q4供旧测试使用）。UI新增一个兼容/固定Q8选择，默认legacy，原context默认4096不变。选择只在创建/明确重建时快照；固定Q8不会因context变化降Q4。旧context恢复可为Q4，但必须返回原失败并记录恢复的实际类型，候选判失败。

不采用全局改Q8默认（未认证），不采用仅bench临时覆盖（不能修复真实产品生命周期）。native仅添加只读逐KV tensor类型查询和失败原因捕获，不改分配、内核、参数或调度器恢复。未知/混合类型不得冒充Q8证据。增加受限q8_baseline模式：仅16K、B8、Q8、flags64；32K须新证据和决策，当前不放行。

## 实施与验证清单

- [ ] 先写失败测试：策略边界、产品配置、tensor核验、Q4伪通过、清理/重启门槛、原始结果完整性。
- [ ] RuntimeConfig/UI/Engine两创建点及回退；native逐tensor只读核验，原生失败诊断。
- [ ] 受限Q8 baseline lease/marker，复用现有鉴权/Client/采样/请求工具；独立Quick/Full工具与不可覆盖结果目录。
- [ ] 同源码Windows/macOS专项及既有回归、CI构建；候选IPA+独立便携测试包+SHA/源码身份。
- [ ] 16K真机Quick：初始冷启动证据单独确认、Q8创建、固定输入连续prefill/decode、真实/v1/chat/completions、请求结束/恢复、人工重启后再次推理。任何Q4/身份变化/不确定请求不重放。
- [ ] Full：Quick前提+更长固定请求/持续运行+接近容量输入和重启。Quick PASS不得写成Full或稳定认证。设备/签名/端点未具备则BLOCKED。
- [ ] 原始JSON/CSV/配置/请求/hash/trace保留；决策PASS/FAIL/BLOCKED按范围输出。16K通过后才讨论32K，不改生产默认/Certified Stable。

审查重点：回退后Q4不能覆盖Q8失败；旧隔离marker不清；证据来自allocated tensor；活动请求不变更；GPU/线程与基线一致；能力边界与配置容量区别。用户已明确授权审计后最小实现及CI候选，本计划按该授权在本会话执行，不合并main。


## 独立审查修正（实施后）

独立只读审查发现并修正：C桥接声明移入extern C；Q8验证异常在恢复前保留隔离标记；合成请求保留原始text、SSE事件并重算输出SHA；仅q8_baseline的capacity阶段使用14400秒客户端/服务端一致上限，其余模式维持1800秒watchdog。容量阶段仍可取消，不改变任何推理性能参数。Full持续512/128循环单独至少30分钟，不把长容量请求时间充作持续循环。重启前后要求同固定输入输出/logit一致。

本地原生/Swift编译依赖Apple CI；Windows专项与实际CMD可本机验证。文档检查本地165项失败均来自既有忽略的deliveries导出目录，新增文档已分类；不删除这些历史文件。推送被自动审批要求明确远端授权，未绕过；CI/IPA/M5均尚未运行。
