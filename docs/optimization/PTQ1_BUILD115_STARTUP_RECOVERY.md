# Build115：调度器分配失败恢复候选

用户提供的 Build112 系统崩溃（2026-10-22 20:20:46 UTC+08）是 `SIGABRT`。通过原始 Actions 产物核对框架 UUID，并解码 ARM64 调用地址，确认 `ggml_init +420` 对应前一条 `ggml_abort` 调用，断言为 `ctx->mem_buffer != NULL`。证据见 [二进制核对记录](evidence/build112-scheduler-abort-20261022.json)。这不是 Jetsam 记录，不能用虚拟地址空间总量推算实际 RAM 峰值。

Build114 的两次 Swift 原生日志停在 `llama_init_from_model()` 调用附近，时间约 21:43；其中 B8/16K 的 `native_trace_enabled=false`。它没有异常类型，尚不能证明和上述 Build112 系统崩溃同因。Build114 沿用了被确认存在缺陷的原生调度器分配路径。

旧路径在首次 metadata malloc 失败时，仅当 `BONSAI_BUILD84_TRACE_PATH` 存在才启用紧凑预算和匿名 mmap 恢复。16K/B8 通常不设置此日志变量，因此可把 NULL 外部池传入 `ggml_init()`，再次分配失败后触发断言。

修复只去掉分配失败恢复对日志变量的依赖，并把全部恢复失败时的释放/返回 NULL 移到平台条件外。原始 malloc 成功路径、紧凑容量公式、模型权重、KV 类型、上下文/Batch 默认值及候选 kernel 均保持原有行为。已有 llama 调度器 NULL 检查将失败转为异常，由 App 报告初始化失败；它不保证任意内存压力下都能成功加载。

验证使用真实 patched `ggml-backend.cpp` 的分配代码块，注入初始 malloc 失败、两次 malloc 失败、malloc/mmap 全部失败，分别开启/关闭日志，共 8 种组合。验证返回指针、对齐、mmap 所有权、释放和 NULL 失败退出。合成小缓冲故障测试不代表 M5 真机性能或内存容量。

交付仍由同一 workflow 构建单 IPA + Windows 便携测试包，身份升为 Build115；CMD 保持 CRLF 修复。真机状态 **NOT_RUN**，需要同包安装后的 API 启动与完整竞赛报告才能判断启动恢复和性能。

## 本地验证记录

- 新回归先在未修复的 patched Prism 上失败，指出恢复路径依赖 trace；应用 Build115 补丁后同一回归通过。
- 一键工具 10 项、真实 Windows CMD 入口 4 项通过；原生候选 5 项中 4 项通过，C++ 编译执行在 Windows 因缺少编译器跳过，由 macOS CI 执行。调度器 2 项中源码回归通过、故障注入编译同样交给 CI。
- Python 编译检查、仓库及 patched Prism 的 `git diff --check` 通过。
- 按 AGENTS 执行完整文档检查：失败项均来自本机被 Git 忽略的 `deliveries/` 缓存（165 项）；受控源码与新增文档检查无剩余问题。原文档单元测试为 7 通过、3 项受该缓存影响失败。未修改校验器或删除缓存来隐藏结果。
