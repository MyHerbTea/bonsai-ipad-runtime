# Build118 Prefill Candidates Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, in this workspace. User explicitly requests implementation then concentrated testing, with no further per-task confirmation.

**Goal:** Implement two CPU PTQ1 candidates and a safe batch8 comparison in one IPA.
**Architecture:** One pinned native patch and shared scalar/NEON helper; Swift retains session ownership and both quarantines; Python reuses the existing tournament contracts.
**Tech Stack:** C11/ARM NEON, Swift, Python3.12, GitHub macOS CI.
**Spec:** ../specs/2026-10-23-build118-prefill-design.md

## Global Constraints
- No model, precision, GPU placement, thread count or production default changes.
- flags8/16 mutually exclusive; original0 and existing1/2/4 remain compatible.
- Legacy B16 quarantine remains; Quick gets a separate marker and no automatic promotion.
- No unknown-request replay; user installs the new unsigned IPA before real device comparison.
- All candidates implemented before concentrated validation, per explicit user instruction.

## Review Focus
1. Byte interleaving and signed Q8 extremes must retain integer/float parity.
2. Unsupported ARM capability or wrong native ABI must fail closed.
3. Failed start/restore must not release an unsafe lease or clear old quarantine.
4. Partially completed ABBA and missing CPU hits must not become winners.
5. Packaging must bind Build118 source/IPA/symbols and retain historical files.

## Task 1: Native CPU candidates
Files: tools/native/build118_ptq1_cpu.h, tools/rc126_build118_patch_cpu_prefill.py, tools/tests/test_build118_cpu.py.
- [x] Implement lookup and NEON branches, per-request real hit counters and atomic opt-in ABI.
- [x] Patch native strategy capability/configure to compose with existing flags and production disable.
- [x] Author exhaustive decoder/random dot/disable/mask tests for actual compiled helper.

## Task 2: Swift safe Quick sessions and bridge
Files: BenchmarkCandidateRegistry.swift, BenchmarkSessionManager.swift, BonsaiEngine.swift, BenchmarkNativeBridge.{h,mm}, tools/build118_policy_tests.swift, tools/benchmark_manager_behavior_tests.swift.
- [x] Add CPU names/validation and quick_prefill explicit initial B8.
- [x] Preserve legacy quarantine; reject matching shapes before mutation; separate Quick pending/restoration key.
- [x] Return actual CPU counter deltas and ABI availability.
- [x] Author policy and manager behavior checks, including invalid mode and failed-start lease.

## Task 3: Concentrated comparison and Build118 delivery
Files: tools/PTQ1_ONECLICK/prefill_compare.py, measurement.py, ptq1_oneclick.py, Quick CMD/README, tests, workflow, packager/symbol tool, project.yml.
- [x] Reuse sample identity/parity/ABBA and preserve both markers in client validation.
- [x] Produce a single exploratory comparison and optional5-round confirmation; stop on uncertain outcomes.
- [x] Update Build118 workflow, artifact identity and retained symbols; include both optimized paths in sameIPA.

## Task 4: Concentrated verification and build
- [x] Local consolidated 44 tests: 40 pass/4 missing compiler skips; pinned patch applied; CMD 5/5 pass; docs consistency and diff check pass. Actual Swift/C/NEON execution pending Apple CI.
- [ ] Review final diff and address defects. Commit/push branch and execute Apple CI once implementation is ready.
- [ ] Verify actual IPA identity/metadata/hash/symbol UUIDs, deliver unsignedIPA and paired runner.
- [ ] After user installs newIPA, run one concentrated Quick matrix at matching identity; record gains/regressions, no automatic promotion. Device installation is an external dependency.
