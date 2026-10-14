# Bonsai RC1.26 Optimization Implementation Plan

状态：DRAFT。当前官方工作区以 [AGENTS](../../AGENTS.md)为准：D:/codexSpace/bonsai-ipad-runtime。以下旧 checkout、候选文件／接口与任务为当时规划；缺原 Spec 与完整候选迁移证据，不是当前可直接执行的唯一计划。参见 [审计](../optimization/DOCUMENT_AUDIT.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. 本次仅交付方案和计划；后续执行前由用户审阅并选择执行方式。

**Goal:** 在 M5 12GB 上建立覆盖文本、图文、32K实际长输入、恢复和持续性能的可靠候选，再分离验证 Batch、内存、KV、Vision 和原生热点优化。

**Architecture:** 保留 Prism 27B Engine actor、MLX Vision Sidecar/BVCACHE1、Network.framework API 和 Build94 launch状态机。补齐三层manifest、真实context证据、共享认证runner与绑定运行指纹的certified envelope，所有行为优化单变量、默认OFF、可回滚。

**Tech Stack:** Swift 5.0、SwiftUI、Objective-C++/C++17、固定Prism/Metal、MLX Swift 0.31.3、Python 3.8+ stdlib、Windows PowerShell、GitHub Actions macOS。

**Spec（NOT_AVAILABLE / NOT_VERIFIED）:** 原引用 `../specs/2026-10-13-bonsai-optimization-design.md`未迁入；不能以此计划替代缺失设计审阅。

## Global Constraints

以下值与Spec一致，所有任务隐含继承，不得将实验成功当产品冻结：

- 设备iPad Pro M5 12GB；初始OS对照iPadOS 27.0.1；模型Ternary-Bonsai-2-27B-PTQ1_0.gguf，API ID=bonsai-2-27b-local。
- Prism=adfffbe41b2cabcd51fff326ab045662265062bb；MLX Swift=0.31.3；iOS deployment=17.0；Swift=5.0；C++17。
- 32K基线context=32768、n_seq_max=1、Q4_0 K/V、FA ON、GPU layers=99、KQV/Op ON、mmap；实际Metal Tensor/线程配置归档。
- SAFE4=4/4；BALANCED8=8/8；B16/B24/B32=16/16、24/24、32/32为资格/显式选择约束实验。
- profile变化要求完整进程重启；禁止mid-request更改已分配context参数；sticky SAFE4和Build105迁移保留。
- KV复用默认OFF；外部Vision prefix reuse OFF；最多3图contact sheet，MLX Sidecar/Hard Graph-Cut/BVCACHE1/native injection保留。
- 单候选只改一个行为变量；Engine/API/Vision/Governor行为分开提交和设备验收。
- Windows+GitHub Actions+iPad，无本地Mac前置；HTTP无法签名/安装/重启终止App，使用人工checkpoint。
- CI PASS不等于Device PASS；用户凭据、私有图片、原prompt/completion不入报告或公开仓库；模型/vision weights不入IPA。
- 原始v1计划/research/历史失败证据保留；规划基线1abfa8598629e25b69e14350a6559176ffc4a926。

## Review Focus

1. 旧IPA沿用Build106号、未知source/hash或签名改变digest：重负载前拒绝错误/不可核实身份；由T02/T05负例验证。
2. advertised=32K但native参数/asset指纹过时：停止认证，两个context创建路径均需要成功创建证据；由T04/T08验证。
3. 强制退出、网络断开、pending与真实崩溃混淆：保存原因/phase，不能伪报Jetsam或自动反复试险；由T06/T11验证。
4. SSE仅role/usage/一次缓冲内容，多图相同fixture：不能获得真实流或grounding PASS；由T06/T07验证。
5. 长prompt、视觉logical/physical边界、资产变化或失效KV：native decode前admission、cache隔离、错误后存活；由T08/T13/T14验证。

## 0. 执行规则、角色与文件组织

当前工作目录：D:/codexSpace/iPad27B/lab-v1-rc1-26-build106-m5-governor。根工作区原有删除/未跟踪内容保留。新的实现从固定基线建立codex/前缀独立候选；不向历史frozen分支回写。开始时重新查询remote HEAD、Actions/artifact、现存device results，若改变则保留本快照并新增状态，不静默覆盖研究历史。

T01为立即可执行的证据封存；当前CI已成功，禁止以“修CI”名义重复旧断言修补。之后的代码候选用新的可识别Build/source组合；当前Build106号不得作为不同SHA的同一认证身份。Build号在执行时检查远端占用后确定，manifest由project.yml读取唯一值，而不是在多处各自改数字。

角色：开发者/agent负责代码、合约、CI和报告；GitHub macOS负责iOS/native编译；设备操作者负责签名安装、选择资产、前台API、人工重启和系统诊断采集。无实时设备时，任务停在BUILD_READY/WAITING_DEVICE，保留全部真机门禁。

新增文件均为计划接口，不代表已实现：

| 文件/目录 | 单一职责 |
|---|---|
| tools/release_manifest.py | 生成/验证release与artifact manifests；patch顺序摘要 |
| BonsaiLab/ReleaseManifest.swift | 加载内嵌身份、与Bundle/CI注入身份一致 |
| BonsaiLab/RuntimeContextEvidence.swift | 成功native context创建参数与generation ID |
| BonsaiLab/RuntimeEvidenceRecorder.swift | bounded phase/measurement事件 |
| BonsaiLab/CertifiedRuntimeEnvelope.swift | 按环境指纹绑定全套设备认证资格 |
| tools/certification/{identity,verdicts,sse,fixtures,redaction,report,run_suite,benchmark}.py | 共享runner组件，stdlib |
| tools/tests/test_*.py；tools/*_tests.swift | 可执行负例/纯策略合约 |
| docs/optimization/{evidence,benchmarks,release}/ | 结构化状态、报告索引和冻结范围 |

所有具体测试文件在对应任务创建。现有Build106 GUI/runner保留为smoke入口，并在共享runner完成后成为薄包装。不要同时重写全部历史脚本。新公共接口在任务Interfaces块锁定；后续若改名，同步消费者和Spec。

每项独立提交前更新CHANGELOG.md、TEST_RESULT.md：源SHA/rollback SHA、范围、命令/结果、设备状态、benchmark结果或NOT_APPLICABLE/NOT_RUN及原因。没有benchmark的性能任务不能完成；没有设备结果的稳定性任务不能完成。保留raw trace引用和隐私过滤记录。提交仅包含该任务文件，不能git add整份用户工作区。

## 1. 里程碑、依赖与排期

| 里程碑 | 任务 | 前置 | 出口 | 估算工程量 |
|---|---|---|---|---|
| M0现状封存 | T01 | 当前基线 | 产物/研究身份可复核 | 0.5–1人日 |
| M1可信平台 | T02–T05 | M0 | 身份/native测量/runner门禁CI候选 | 4–7人日 |
| M2全套32K认证 | T06–T09 | M1 | SAFE4/B8完整证据或明确缺口 | 4–8人日+设备等待 |
| M3 Batch实验 | T10 | M2 | B16/B24限定收益和拒绝/推广结论 | 2–4人日+长输入时间 |
| M4 Governor/内存 | T11–T12 | M2；自动高档需M3 | 有指纹的启动资格和可归因内存改进 | 3–6人日 |
| M5专项优化 | T13–T15 | M2；分别依赖测量/内存 | 各独立候选或NO_SAFE_WIN | 6–12人日 |
| M6冻结治理 | T16 | 已采纳候选重过M2 | 32K RC、完整证据、回滚与维护索引 | 1–2人日 |

共约20.5–40人日规划区间，不是交付承诺；单人顺序执行，设备/签名/长输入耗时额外计。首个目标是M0–M2；M3–M5不能为了按期而降低M2范围。M5研究可以NO_SAFE_WIN关闭，M6不以未被采纳的实验成功为前提。每个已采纳候选必须重新过相关功能与完整发布门禁。

关键路径：T01→T02/T03→T04→T05→T06/T07/T08→T09→T10→T11/T12→T16。只有明确共享接口固定后才可并行；当前计划不自行派出子agent。

## 2. 分任务实施清单

### T01：封存当前真实候选与输入（R01；M0）

**Files:** 创建docs/optimization/evidence/build106-artifact-index.json、INPUTS.sha256、CURRENT_STATE.md；二进制归档到本地artifacts/build106-1abfa859/并gitignore，不提交模型或IPA。

**Interfaces:** 消费当前snapshot；产出artifact index{source_sha,ci_run,artifact_id,wrapper_digest,unsigned_ipa_digest,runner_digest,scope,status}。

- [ ] 重查分支HEAD与run38147351064、job114493396250、artifact11704414799；状态改变则记录新观察。
- [ ] 获取完整artifact，校验wrapper范围；解包核对BUILD_INFO、IPA .sha256、runner ZIP成员与CRC。读取IPA内Info.plist/native framework/内置source身份，缺项标NOT_VERIFIED。
- [ ] 将六份research文件hash、v1 plan hash和ZIP hash记入INPUTS.sha256；保持原文件。
- [ ] 归档CI日志中有效compiler/SDK/Xcode、Prism与patch步骤；区别“workflow步骤成功”和“已独立检查binary”。
- [ ] 设备可用时签名安装当前IPA并跑原smoke，记录真实profile和结果；smoke不会标full-certified。无法设备操作则明确WAITING_DEVICE。
- [ ] 记录artifact当前到期为2026-10-25 22:37:37（UTC+08）；优先本地封存，不能依赖过期后的下载。

**Verify:** Windows Get-FileHash与包内digest一致；IPA plist build=106、CI/source=1abfa859…；index中每种digest标清对象。此任务不改运行参数。

### T02：补齐统一Release/Artifact/Device身份（R02；M1）

**Files:** 创建tools/release_manifest.py、BonsaiLab/ReleaseManifest.swift、tools/tests/test_release_manifest.py、tools/certification/identity.py；修改project.yml资源、build-ios.yml、BonsaiCertificationBuildIdentity.swift生成逻辑、LocalOpenAIServer.debugBuildObject和ProductionView身份展示。

**Interfaces:** build_release_manifest(project: Path, source_sha: str, ci_run: str, prism_sha: str, ordered_patches: list)->dict；verify_identity(expected: dict, observed: dict)->list[str]返回差异；Swift ReleaseManifest.load(bundle: Bundle)->ReleaseManifest，sourceGitSHA:String、workflowRunID:String、prismSHA:String、patchDigest:String。设备资产hash由T04/T05提供，CI不伪造。

- [ ] test_release_manifest.py覆盖：错source/build/Prism/patch顺序、unknown-local-build、相同build不同SHA、unsigned/signed digest混淆；正确输入无diff，错误输入必须拒绝。
- [ ] 运行python -m unittest discover -s tools/tests -p test_release_manifest.py；首次RED原因须为新增功能缺失，不能外部网络失败。
- [ ] 生成嵌入release_manifest.json，复用CI现有source/run注入；打包之后生成外部artifact_manifest.json，避免IPA自hash循环。
- [ ] UI/API/report读取同一身份；保留baseline_commit历史字段，不作current身份。
- [ ] device manifest增model/vision SHA、实际OS/entitlements、签名来源。streaming hash不在每次请求热路径；文件身份改变后重新计算。
- [ ] 重跑单测与完整iOS workflow；从生成IPA解包读取manifest与App/API身份核对。
- [ ] 提交本任务+changelog/test result，rollback=父提交；标Device NOT_VERIFIED直到真机。

### T03：Current Release Contract与历史门禁治理（R03；M1）

**Files:** 创建tools/current_release_contract_tests.py、tools/tests/test_current_release_contract.py、docs/optimization/CONTRACT_COVERAGE.md；修改build-ios.yml和当前identity相关旧gate，保留各历史行为测试。

**Interfaces:** validate_current_release(project: dict, manifest: dict, packaging: dict)->list[str]；消费T02 manifest；coverage记录old assertion→new assertion→negative fixture→CI step。

- [ ] 制作RED负例：project/API/artifact/runner build或SHA冲突、缺native符号、删除fallback/injection gate、缺checksum、错patch顺序必须失败。
- [ ] 区分历史快照精确身份测试与跨版本行为不变量；逐条映射，不用版本>=X通配冒充语义。
- [ ] 将当前身份输入统一到manifest；旧本build契约改为正确语义，已修的Build93/89/90问题不重复臆造。
- [ ] 运行python tools/current_release_contract_tests.py及python -m unittest discover -s tools/tests -p test_current_release_contract.py；完整workflow含所有等价旧行为/Swift策略/native symbol gates。
- [ ] 保存覆盖映射与CI结果，再独立提交。未映射断言不可删除。

### T04：真实Context/资产/phase/内存证据（R04；M1）

**Files:** 创建RuntimeContextEvidence.swift、RuntimeEvidenceRecorder.swift、tools/runtime_evidence_tests.swift、tools/tests/test_runtime_evidence.py；修改BonsaiEngine.swift两个context创建点、RuntimeOptimization.swift、LocalOpenAIServer诊断；复用SystemProbeBridge，不先加行为优化。

**Interfaces:** RuntimeContextEvidence: Codable, Sendable，字段contextID:String、context:Int、batch:Int、ubatch:Int、sequenceMax:Int、kvK:String、kvV:String、sourceSHA:String、modelSHA256:String?、observationSource:String；RuntimeEvidenceRecorder.record(requestID:String,phase:String,values:[String:Double])和snapshot()->[RuntimeEvidenceEvent]。RuntimeEvidenceEvent: Codable, Sendable定义requestID:String、phase:String、monotonicSeconds:Double、values:[String:Double]；phase限定queue/load/vision_encode/admission/prefill/first_content/decode/cleanup/failed；最多256事件/请求，额外计数droppedEvents:Int，不保存文本。

- [ ] Swift测试：成功创建才READY；失败不留下旧context；loadModel/recreate记录相同规则；shape=4/8/16/24/32正确；未知native值不填宣传常量。
- [ ] Python结果schema测试：requested/advertised/native区分；序列=2、错context ID、漏prompt count不可通过。
- [ ] 两路径创建成功后记录实际传入C参数；pinned getter存在则交叉验证并标来源。不得假设不存在的getterAPI。
- [ ] 复用BonsaiReadSystemProbe、RuntimeTelemetrySnapshot.capture；按阶段+有限周期采样，记录sampled peak/频率。phase时钟统一monotonic，native wall不称GPU time。
- [ ] 资产streaming SHA与cache失效放后台准备阶段；未知hash禁止完整认证；避免加载前多份权重驻留。
- [ ] 编译Swift纯策略测试（swiftc RuntimeContextEvidence.swift RuntimeEvidenceRecorder.swift tools/runtime_evidence_tests.swift）并跑生成二进制；Python schema测试；完整iOS CI。
- [ ] 真机对比observer OFF/ON相同短负载，新增开销>5%则降低采样/关闭逐事件开销后复测；无证据不称零开销。
- [ ] 保存measurements.json/trace和字段来源，独立提交。

### T05：一键Checkpoint Runner、隐私与报告（R05；M1）

**Files:** 创建tools/certification/{__init__,verdicts,redaction,report,run_suite}.py、tools/tests/test_certification_verdicts.py、test_report_redaction.py、test_runner_resume.py；修改RUN_BUILD106_GUI.ps1及现runner为兼容包装，不删原smoke。

**Interfaces:** CaseResult{case_id,state,request_id,evidence,metrics}；aggregate(required_ids:set,results:list)->str；redact_report(value:object)->object；run_suite(argv:list[str])->int。exit0=PASS、1=FAIL、3=INCOMPLETE、130=user stop；session manifest包含required case版本与artifact identity。

- [ ] RED：缺必需case、SKIP、模型早停/缺usage、wrong SHA、仅HTTP200都不能overall PASS；unexpected exception写结构化安全错误。
- [ ] RED隐私：Key sentinel、Bearer、data URL、私有prompt/completion、异常response excerpt、嵌套snapshot不能出ZIP。
- [ ] 实现统一suite入口：--suite smoke/full/benchmark、--base-url、--expected-manifest、--resume；Key由getpass/GUI受控输入读入内存，不入CLI参数/持久文件。
- [ ] GUI调用一次，支持WAIT_FOR_INSTALL/WAIT_FOR_RESTART；resume必须重校source和新的contextID，不能复用旧app状态。没有额外手改JSON前置。
- [ ] ZIP输出FINAL_REPORT.md、metrics.json、device_manifest.json、case_results.json、logs/trace/snapshot；仅allowlist脱敏成员，archive_index列每成员hash。
- [ ] 非恢复性身份/Native安全错误阻止重负载；同context超时/退出后终止该安全相关链。独立HTTP格式负例只有存活证实后才继续。
- [ ] 运行python -m unittest discover -s tools/tests -p 'test_report_redaction.py'、test_certification_verdicts.py、test_runner_resume.py；python tools/certification/run_suite.py --dry-run。
- [ ] GUI/报告打包CI验证成员，生成例子ZIP仅使用合成fixture，再提交。

### T06：文本、输出、SSE、错误与恢复生命周期（R06/R07/R08；M2）

**Files:** 创建tools/certification/sse.py、tools/tests/test_sse_cases.py、test_text_output_cases.py、test_lifecycle_cases.py；在run_suite中注册相关cases。只在设备失败有根因证据时另开最小API/Engine修复候选。

**Interfaces:** parse_sse(lines:Iterable[bytes], timestamps:Iterable[float])->SSEEvidence，含content_delta_count、first_event_ms、first_content_ms、usage、finish_reason、done；文本case返回CaseResult；restart checkpoint消费T04 contextID。

- [ ] RED：role-only/usage-only、一非空chunk、无DONE、破UTF-8、usage丢失、断连不应PASS；分块中文必须还原。
- [ ] 长输出三别名和omitted分别用能生成>256的fixture；真实completion>256才PASS，早停INCONCLUSIVE。保留当前min到remaining与strict拒绝语义。
- [ ] 多轮使用上次实际assistant历史和随机公共marker，做确定性检索；别名或max请求被接受不等于budget认证。
- [ ] 加Bearer/X-API-Key、非法Key、未知模型、404/CORS、非法payload、stream cancel，再做next-request存活探针。
- [ ] SAFE4/B8各10次fresh启动/5次API Stop-Resume；记录pending/正常quit/异常终止区别；无故障证据不注入“Jetsam”标签。
- [ ] 验证模型/vision切换、取消、background→foreground；前台服务能恢复，listener取消被await，lease已排空。
- [ ] Python单测与CI后运行python tools/certification/run_suite.py --suite full --expected-manifest <本地artifact_manifest路径>；GUI同一入口。每次人工restart前后验证actual shape/contextID。
- [ ] 收齐case/native证据后独立提交；失败修复一次一类，不夹带batch/vision优化。

### T07：Vision语义与错误恢复基线（R09；M2）

**Files:** 创建tools/certification/fixtures.py、公共fixture索引、tools/tests/test_vision_cases.py；复用OpenAIMultiImageComposer及MLX/Bridge，不先变渲染策略。

**Interfaces:** make_vision_fixture(kind:str,index:int)->bytes；fixture manifest{sha256,label,expected_order,ocr_text}; score_fixture(fixture_id:str,response:str)->dict，只存评分/hash，不存私有response。

- [ ] 生成3张互不相同的颜色/编号/方位合成PNG，单/双/三图不同组合；response须满足fixture标注的grounding/排序断言。
- [ ] 建公共OCR样例：大/小字体、长宽比、旋转；固定normalized exact/字符准确率定义和对照评分。
- [ ] 文→图→文、图→图追问5循环；确认Vision prefix reuse=OFF、model常驻、cleanup阶段收敛。
- [ ] 损坏data URL、4图、远程URL/非法类型按既有契约拒绝；失败后下一次正常text与vision都成功。
- [ ] Pythonfixture/评分负例必须拒绝“图像正常”泛化空洞响应；iOS CI；真机full suite中的vision必需cases通过。
- [ ] 保存fixture hashes、logical/physical admission、MLX/native stages与sampled memory，提交基线测试任务。

### T08：真实长输入、配置梯度与Admission边界（R10；M2）

**Files:** 创建tools/certification/context_cases.py、tools/tests/test_context_cases.py；添加BonsaiEngine/现debug诊断中的只读tokenize/admission证据（必要时），复用当前request ID关联。

**Interfaces:** build_context_fixture(target_prompt_tokens:int,seed:int)->Fixture；fixture counts以服务端真实tokenizer/模板结果校准。classify_admission(observed:dict,requested_output:int)->CaseResult；文本reserve=1，与当前公式一致；Vision单独logical/physical验证。

- [ ] RED：字符数冒充tokens、只看context_window、旧contextID、输入加输出越界、没有真实prompt count不得PASS。
- [ ] 2048/8192/16384/32768配置分别native attestation；只变context，profile按该配置已有政策独立记录，不假定非32K也是B8。
- [ ] 32K下actual prompt目标256/1024/4096/8192/16384（校准误差<=5%，保存精确值），开始/中间/末尾sentinel检索，short output=64；各档通过后继续。
- [ ] 接近合法上限按actual total template tokens+output+1<=32768构造；再造越界用例，在decode前拒绝/按该路径既有clamp处理。不能用32768输入再加输出。
- [ ] Vision logical span与physical KV cells分别near-boundary/over-boundary；别用文本context字符长度替代。
- [ ] pilot估rate后设置deadline，保留live phase、completed token/batch进度；没有进度证据的timeout=INCONCLUSIVE，不自动replay。
- [ ] Python校准/admission单测、iOS CI；真机long-input trace完整。8K/16K/边界先各一次，按风险与方差再追加。
- [ ] 报告actual tested input上限、耗时/检索质量和未完成档位；完整32K项缺失则M2 INCOMPLETE，不降格目标。

### T09：冻结SAFE4/B8完整基线与Benchmark标准（R11；M2）

**Files:** 创建tools/certification/benchmark.py、tools/tests/test_benchmark_verdicts.py、docs/optimization/benchmarks/baseline.json、release/BASELINE_CANDIDATE.json。

**Interfaces:** compare_paired_runs(baseline:list,candidate:list,policy:dict)->BenchmarkVerdict；raw_run字段source/asset/config/contextID/requestID/actual tokens/sampling/thermal/memory/cold-warm/cache state全部必需。

- [ ] 固定公开prompts、seed=1234、temperature=0与相同其余sampling；record exact actual counts/input hashes；不能比较命中KV与fresh。
- [ ] 至少短/中/长输入和32/384输出两档；M2长档按已实际认证envelope选择，并明确未满载范围。
- [ ] SAFE4/B8分别20连续文本+5图文循环、60min混合前台；报告median、range、TTFT/native prefill/decode、sampled峰值与thermal，样本少时不虚构p95置信度。
- [ ] RED统计fixtures：missing identity/actual counts、基线ABA漂移>10%、重复cached prompt、失败请求被排除，都不得给PROMOTE结论。
- [ ] 核对T06–T08所有必需case；签名lineage、资产hash/entitlements/native trace缺失为INCOMPLETE。
- [ ] 形成第一份本轮Device-certified baseline，明确observed failures/total attempts与范围；不外推crash probability。
- [ ] Pythonbenchmark单测、CI、真机baseline JSON+ZIP索引；只有完整证据后提交认证文档。

### T10：B16/B24单变量收益实验（R12；M3）

**Files:** benchmark.py增batch_aba；复用Build94BatchExperiment/M5RuntimeGovernor；创建tools/tests/test_batch_benchmark.py和benchmarks/batch-aba.json。

**Interfaces:** profile由原POST /debug/build102/next-launch或兼容Build94接口计划下次启动；消费T09baseline/envelope；结果为REJECT/INCONCLUSIVE/EXPERIMENT_PASS，不直接Stable。

- [ ] RED：profile label与actual batch/uBatch不一致、pending没完成、seq2/KV hit、thermal不匹配、缺返回基线，不得有效对照。
- [ ] B8→B16→B8至少3组，短中负载通过后补2K与认证长档、Vision/持续用例。
- [ ] B16满足资格后B16→B24→B16至少3组；每切换full process restart，至少一次>=200actual prompt-token成功清pending。
- [ ] 固定context32768/Q4/seq1/GPU99/offload/Prism/model/sampling、output budget；不同时改kernel/env/vision。
- [ ] 推广建议门槛：median Prefill或TTFT>=15%改善、decode不劣化>5%、baseline漂移<=10%、无必需语义/稳定性回归、内存在envelope内；否则REJECT或INCONCLUSIVE。
- [ ] B32只在另行明确higher-risk选择和原资格齐全后独立试验；不自动搜索32/64，不是此任务默认完成条件。
- [ ] 保存ABA原始结构化结果、完整回归与rollback，本任务不改变默认值；修改默认须T11+T16门禁。

### T11：认证指纹、失败状态与启动Governor（R13；M4）

**Files:** 创建CertifiedRuntimeEnvelope.swift、tools/certified_envelope_tests.swift；修改M5RuntimeGovernor/Build94BatchExperiment（仅状态政策）、ProductionView启动接入；扩展诊断；不变Engine/Vision行为。

**Interfaces:** RuntimeFingerprint: Codable, Hashable字段sourceSHA/prismSHA/patchSHA/modelSHA/visionSHA/osVersion/kvType/profile/startupMode均String，context:Int；CertifiedRuntimeEnvelope含fingerprint、status:String、maxObservedStartupFootprintDeltaMiB:Double、requiredStartupAvailableMiB:Double、reportSHA:String、caseSetVersion:String；CertifiedRuntimeEnvelope.matches(_ fingerprint:RuntimeFingerprint)->Bool；M5RuntimeGovernor.decide(arm: Build94BatchExperiment.Arm, context:Int, assessment:MemoryGovernorAssessment, certified:[CertifiedRuntimeEnvelope])->M5RuntimeDecision。保留旧decide入口兼容包装，禁止直接bypass原scheduleNext资格。

- [ ] RED Swift：旧bool资格不等于full certified；source/模型/OS/vision改变失效；sticky先于任何preference；serious/critical不升档；未认证B24拒绝；非32K沿用原policy。
- [ ] 区分TRIAL_COMPLETED/FULL_CERTIFIED、manual quit/interrupted/native failure；unknown退出保守SAFE4但不标确定crash。
- [ ] 根据T09/T10同cold/warm启动类别的测量建立envelope：requiredStartupAvailableMiB=max(512, maxObservedStartupFootprintDeltaMiB+max(512,0.10*maxObservedStartupFootprintDeltaMiB))；availableBytes转换MiB后比较，现有assessment critical或serious/critical热态仍拒绝自动升档。数值/公式入manifest，说明为初始工程政策；缺数据禁止自动升档。
- [ ] 只在next-launch/context-creation选择；进程内contextId/batch不变；人工recovery ack后才解除sticky，不自动重试。
- [ ] Foundation Swift策略测试编译执行、原Build93/94/102/105/106全部回归、iOS CI；真机各状态/重启cases。
- [ ] 更改行为为独立候选、完整回归后提交，默认仍B8/SAFE4直到Release gate批准已认证高档。

### T12：32K startup/metadata/footprint改进（R14；M4）

**Files:** 根据T04峰值来源只选择一个文件/释放点：BonsaiEngine或MLX生命周期，或新的单独tools/patch_prism_memory_candidate.py；不得同候选同时改三路。创建tools/tests/test_memory_candidate.py，若native则增patch fixture测试。

**Interfaces:** 现RuntimeEvidenceRecorder事件与固定native patch链；候选manifest含changed_variable、baseline_sha、rollback_sha、before/after allocation证据。

- [ ] 先用load/context-init/prefill/vision/cleanup分段证据确认主峰；Q4/mmap/Build89已存在，不能再命名“首次启用”。
- [ ] RED针对实际故障：临时对象未释放/重复buffer，或scheduler容量在后续图不足；选择对应最小负例。
- [ ] 单候选改一个释放/复制/分配策略。scheduler若被选，依据hash capacity/copy slots/headers保持容量下界，保留malloc+mmap失败保护。
- [ ] 当前配置相同A/B，sampled peak下降>=5%或经证据确认的分配失败消失；每次保留quality/性能比较。
- [ ] 测Q4/retrieval、long-context、text/vision图形变化、内存失败恢复和完整M2；native patch另跑pinned XCFramework+symbol CI。
- [ ] 无收益/回归则NO_SAFE_WIN回父SHA；成功候选封存native diff/framework摘要，提交后重新设备认证。

### T13：单序列KV reuse可行性与隔离（R15；M5）

**Files:** 独立候选BonsaiEngine.swift、必要的单序列Bridge方法；tools/tests/test_kv_reuse_evidence.py、tools/kv_reuse_contract_tests.py；benchmarks/kv-reuse.json。

**Interfaces:** 先读取pinned hybrid/recurrent state API，未来TextKVReuseEvidence记录fingerprint、prefixTokens、reusedTokens、restoreResult、tailTrimResult。启用布尔独立默认OFF，不引入seq2。

- [x] 检查pinned recurrent state与历史设备证据；Build76 partial-tail删除返回false且未解决，停止当前方案推广并归档NO_SAFE_WIN。Vision whole-sequence snapshot/restore不等于单序列tail-trim证明。
- [x] RED：future evidence contracts拒绝prompt/template/model/sampling指纹不匹配、Vision边界、cancel/failure、无actual reused_tokens、未通过restore/tail-trim或seq2。
- [ ] 单序列fresh-vs-reuse同输入输出对照未执行；按未解决tail-trim退出条件停止，维持reuse OFF。
- [ ] 质量、内存、Prefill收益及完整M2未取得；因此没有EXPERIMENT_PASS或推广。
- [x] Build105保持text KV reuse OFF、n_seq_max=1；没有引入seq2。任何snapshot redesign需另立研究。
- [x] NO_SAFE_WIN证据/合同已归档，待本阶段独立提交。

### T14：Vision cache/embedding/多图质量优化（R16；M5）

**Files:** 独立选择BonsaiMLXVisionSidecar或OpenAIMultiImageComposer或StagedVisionBridge之一行为改变；创建tools/tests/test_vision_cache_identity.py和benchmark fixture score表；不要同候选同时改layout/cache/分辨率。

**Interfaces:** VisionCacheFingerprint{imageSHA,modelSHA,visionSHA,preprocess,grid,dimension,formatVersion}；沿用encodeForInjection/cleanupAfterRequestSuccess/Failure，明确success/failure/asset-switch失效。

- [x] RED：覆盖内容hash、字段差异、同路径同尺寸替换后的新代际、stale generation拒绝，以及所有原生缓存入口携带fingerprint。
- [x] 只选择缓存身份和payload格式这一项行为改变；MLX与native共享BVCACHE2，Hard Graph-Cut与prefix isolation保留。
- [ ] 测1/2/3 distinct图、公共OCR小字/旋转/长宽比、排序/follow-up；admission logical/physical近边界和错误恢复。
- [ ] 至少5图文循环验证MLX active/cache/peak/footprint收敛；公共quality评分不低于基线，速度/内存收益按T10/T12对应门槛。
- [x] 没有增加cache limit、独立多图embedding或切图；后两项仍需单独架构计划。
- [ ] macOS CI、M2设备benchmark或NO_SAFE_WIN归档，之后独立提交。

T14 implementation checkpoint: local implementation is integrated; macOS Swift/Xcode CI and M5 quality, cache-hit, memory, and lifecycle evidence remain pending. No performance promotion is claimed.

### T15：原生PTQ1/GDN/Decode热点（R17；M5）

**Files:** 独立tools/patch_prism_route_observer.py、可选后续tools/patch_prism_kernel_candidate.py、tools/tests/test_prism_route_observer.py；CI保持固定upstream与Build83–89顺序，在其后增独立候选patch。

**Interfaces:** native route counters按(op,weightType,shapeRange,branch)聚合，bounded容量；snapshot不包含tensor内容。kernel candidate由观测结果选一个route，不能先猜算法。

- [x] RED合同：只接受聚合形状桶和bounded snapshot，拒绝逐op日志、重复patch、先决patch缺失及分支锚点漂移；本地5项合同通过。
- [ ] Observer已接入 `/debug/execution` 并加入Build83–89之后的独立patch；仍待pinned XCFramework CI、M5真实route采样与observer开销测量，之后才能冻结baseline。
- [ ] 单独评估PTQ1_0 dispatch/GDN/tensor-layout/FA其中一个；GPU timing不具备则UNKNOWN；不同时升级Prism或改batch/KV。
- [ ] pinned patched XCFramework、native symbols、patch diff-check与SHA链CI；同模型同真实tokens/sampling/device ABA、质量和M2回归。
- [ ] sustained decode额外比较20请求/60min、burst/paced/idle，记录thermal不自动强制cooldown。
- [ ] 实测门槛>=15%目标阶段收益、decode回归<=5%、无质量/安全回归；否则NO_SAFE_WIN；独立提交与回滚。

### T16：冻结32K RC、发布审计与维护归档（R18；M6）

**Files:** 创建docs/optimization/release/RELEASE_BASELINE.json、RELEASE_README.md、EVIDENCE_MATRIX.csv、KNOWN_LIMITS.md、EXPERIMENT_INDEX.md；更新CHANGELOG.md/TEST_RESULT.md/当前开发导航，补第三方LICENSE/NOTICE核查结果（由维护者确认具体授权，不虚构许可）。

**Audit checkpoint (2026-10-13, implementation 6a47e7b; audit 426e521):** 在 `docs/optimization/release/` 建立标为 `INCOMPLETE` 的 R01–R18 草稿矩阵、限制、实验索引和 third-party source inventory；新增 `gate_class` 明确区分 mandatory gate、optional experiment 和当前设计的 `NO_SAFE_WIN`。矩阵由独立4项测试和CI检查。分支无tracked `Package.resolved`；CI现会生成并上传lock、把哈希/pins绑定到artifact manifest；Swift Numerics已在project.yml显式固定1.1.1，解析版本不符会被合同拒绝。当前SHA macOS执行仍待完成；Vision attribution 仍需维护者核实。尚未生成 `RELEASE_BASELINE.json`；这些草稿不表示最终门禁通过。

**Interfaces:** ReleaseGateReport{requirements,case_evidence,source_sha,ci_run,artifact_digests,device_runs,verified_profiles,actual_prompt_envelope,rollback_sha,status}；只从前述不可变证据生成，不读取漂移分支作为冻结身份。

- [ ] 对全部R01–R18做requirement-by-requirement审计，区分mandatory product gate与未采纳实验；未采纳候选NO_SAFE_WIN允许结案，mandatory缺证据不得Stable。
- [ ] 每个采纳候选最终同source完整CI+M2全矩阵、持续/长输入、资产hash、签名lineage/有效entitlement、privacy ZIP检查通过。
- [ ] 清楚声明32K容量、已测actual prompt/输出/图文范围、无法认证部分；缺full32K计划项则继续active，不称完整32K稳定。
- [ ] rollback优先本轮相同范围已认证节点；历史64/75回退注明context2048。105/106绿色CI不能伪称设备稳定回退。
- [ ] baseline/active/archive索引保留失败证据；仅在必要变更区域提取policy/diagnostic小模块，旧接口回归。
- [ ] 归档权重/第三方分发许可核查和实际签名entitlements；模型不入IPA，Key/私有内容不入公开发布。
- [ ] 生成FINAL_REPORT、metrics、trace/snapshot ZIP checksum和安装/Windows测试指南；完整gate通过才标DEVICE_CERTIFIED_RC。
- [ ] 完成独立提交和冻结记录；推送、PR、发布按后续实际用户授权执行。

## 3. 证据状态与失败处理

| 状态 | 意义 | 允许下一步 |
|---|---|---|
| PLAN_READY | 设计/任务完整可审阅 | 选择执行方式，开始T01 |
| BUILD_READY | exact-source CI/产物通过 | 签名安装/设备检查 |
| WAITING_DEVICE | 缺实时设备/人工安装 | 保留门禁，完成不依赖设备的工作 |
| EXPERIMENT_PASS | 限定负载有效且有收益 | 补完整范围，不能自动改默认 |
| INCOMPLETE/INCONCLUSIVE | 缺case、计数、身份或不确定结果 | 补特定证据，不伪PASS |
| NO_SAFE_WIN | 无收益或安全不可证明 | 回滚并归档，保留32K目标 |
| DEVICE_CERTIFIED_RC | final SHA所有mandatory gates通过 | 才能提议冻结/发布 |

任何异常退出、native allocation/decode错误、seq!=1、实际profile不符、严重热/内存压力：停止当前候选重负载，保存最后完成phase/trace/checkpoint，下一启动SAFE4按已有保护；不得无证据断言Jetsam。网络timeout先读同request进度/handle，不自动重复发长请求。证据确认任务终止后才人工重启；Key和图片永不作为定位日志输出。

## 4. Spec覆盖和计划审查

| Requirement | 主任务 | 验收证据位置 |
|---|---|---|
| R01 | T01 | evidence/index+INPUTS.sha256 |
| R02 | T02/T05 | 3 manifests+identity负例 |
| R03 | T03 | CONTRACT_COVERAGE+full CI |
| R04 | T04 | runtime evidence+observer device结果 |
| R05 | T05 | checkpoint/required cases/ZIP privacy |
| R06 | T06/T09 | fresh startup/Stop-Resume/native trace |
| R07 | T06 | actual >256四路径+语义 |
| R08 | T06 | strict SSE/negative/lifecycle |
| R09 | T07 | distinct fixtures/OCR/follow-up/cleanup |
| R10 | T08 | actual token ladder/边界/positions |
| R11 | T09 | paired benchmark/20+5/60min |
| R12 | T10 | ABA/15%/5%/10%/full回归 |
| R13 | T11 | fingerprint失效/sticky/next-launch |
| R14 | T12 | measured peak+单变量+全矩阵 |
| R15 | T13 | hybrid/单序列/tail-trim或NO_SAFE_WIN |
| R16 | T14 | cache identity/quality/memory |
| R17 | T15 | actual route/kernel候选/持续 |
| R18 | T16 | final release gate/回滚/归档 |

计划初版自审：18项均已映射；Review Focus五类均有负例/设备case；mandatory设备证据不能由静态测试替代；次数/收益阈值为工程门槛建议。该计划现处执行阶段，不能再用“初版所有复选框未勾选”描述当前状态。

执行状态以 `docs/optimization/CURRENT_STATE.md`、`docs/optimization/release/EVIDENCE_MATRIX.csv` 和 `TEST_RESULT.md` 为准：T01–T13已有实现/处置记录；T14本地已实现但Swift/Xcode与M5门禁待验证；T15 observer实现待pinned XCFramework CI和M5测量；T16审计仍为INCOMPLETE。后续先取得当前SHA构建/签名/设备证据，再对mandatory gate逐项复核；未获授权前不推送或发布。

