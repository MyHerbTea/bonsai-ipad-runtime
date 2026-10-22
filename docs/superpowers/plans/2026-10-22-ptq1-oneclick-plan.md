# PTQ1 One-click Tournament Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. User explicitly authorized audit then immediate implementation and Actions build.

**Goal:** One IPA and one Windows entry run real PTQ1 candidate screening, runtime reconstruction, tuning, quality/stability gates, restore and Chinese reports.
**Architecture:** Keep the production path isolated. A benchmark-only engine session serializes native context teardown/configure/rebuild with a single resident model. A native per-session strategy selector avoids mutating the process-latched device registry. Authenticated endpoints expose capabilities, switching, generation/tokenization, cancellation and restore. Reuse Quick TestKit HTTP/report components where compatible.
**Tech Stack:** Swift actors, C++/Objective-C++/Metal Prism patches, Python stdlib, Windows CMD/PowerShell, GitHub macOS Actions.
**Spec:** 2026-10-22-ptq1-oneclick-spec.md

## Global Constraints
- Only M5 iPad Pro 12GB and official PTQ1_0 GGUF; no PQ2/MLX migration or main merge.
- Official workspace D:/codexSpace/bonsai-ipad-runtime; independent codex/ptq1-oneclick-tournament branch based on 32c479fb62f63f1172df2f912239135bf2250ebb. Existing untracked pycache preserved.
- One resident model; await GPU completion before freeing context or changing candidate. Never mutate immutable registry flags to simulate switch.
- Initial working point 16384/16/16/Q4_0/FA/seq1; actual settings and execution counters required.
- +15% prefill, +10% TTFT, decode >=95%, peak delta <=1GiB plus real headroom, quality/stability required. Missing evidence never PASS.
- Safe defaults restored; uncertain timed-out inference is cancelled/polled, never blindly replayed. Actual crash cannot be recovered by HTTP while app is terminated; persist checkpoint and require one user relaunch if OS kills app.

## Review Focus
- Concurrent ordinary inference vs candidate switch: exclusive benchmark lease and rejection.
- Missing Metal capability, compile failure and silent fallback: unsupported/blocked evidence, never winner.
- Interrupted request or client disconnect: cancellation token outside inference actor, bounded status and no replay.
- Failed context allocation: free partial resources, blacklist setting, restore known safe context.
- Missing samples/thermal drift/early EOS: no invalid paired comparison or fabricated complete answers.

## Tasks
- [ ] T1 Native strategy ABI, actual fused PTQ1 optimization, low-overhead candidate only with code evidence, command-buffer completion/error counters; meaningful codec/patch tests and native CI.
- [ ] T2 BenchmarkCandidateRegistry and engine session lifecycle; isolated context creation, singleton model, cancellation and restore; Swift executable policy tests and compile.
- [ ] T3 Authenticated benchmark API connected to actual engine, exclusive lease, metadata and actual configuration; test lifecycle and admission boundaries.
- [ ] T4 One-click Python tournament and GUI/CMD; short screening, repeated paired 2K, combinations, adaptive parameter tuning, quality/stability, checkpoint/redaction/report ZIP; behavior tests with explicit synthetic test fixtures only.
- [ ] T5 One workflow builds native framework and Release IPA, runs tests, bundles portable Python + one entry + identity + reports in one artifact; push branch, wait CI, inspect artifact and download.
- [ ] T6 Independent code review, fix substantive findings, rerun affected tests and final CI. Device evidence remains NOT_RUN until real iPad execution.

## Interface contract
- Native bridge: BonsaiBenchmarkConfigure(int32_t flags) where -1 restores production, 0 baseline, bits 1 TensorOps / 2 fused / 4 low-overhead; returns 1 success, 0 unavailable/unsafe. BonsaiBenchmarkCapabilities() flags; BonsaiBenchmarkCounter(index) monotonic uint64 counters. No real counter fabricated for unsupported candidates.
- HTTP /debug/benchmark/*: capabilities GET; start/configure/run/tokenize/cancel/restore POST; status GET. Session ID required for mutation; ordinary chat rejected during lease. JSON schema version 1 with actual runtime config and per-request counters.
- Candidate IDs SAFE_BASELINE, PTQ1_TENSOROPS, PTQ1_FUSED_KERNEL, PTQ1_LOW_OVERHEAD, PTQ1_BEST_COMBINATION; combinations only from qualified component flags.
- Runner never promotes production defaults; reports best daily/long config recommendations after gates, always restores original production configuration.

## Decisions
User's attached spec and direct implementation authorization supersede skill approval handoffs. Repository single-workspace rule supersedes worktree preference. Subagent-driven-development is used for independent native implementation and reviews; root owns integration. No parallel implementation subagents on shared files.
