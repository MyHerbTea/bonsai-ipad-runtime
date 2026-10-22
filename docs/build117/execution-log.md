# Build117 execution ledger

2026-10-23 Asia/Shanghai — T00: repository cloned into user-requested workspace, base 4dce38a, clean codex/build117-diagnostics branch. Existing runner tests 10/10 PASS. See source-map.md.

Ruling: Current explicit user workspace instruction overrides AGENTS.md's different directory. Use this checkout; no hidden worktree. Cost if wrong: relocating checkout; no shared branch has been changed.

Pre-flight shared interfaces:

| Producer → consumer | Interface/ruling |
|---|---|
| T01 → T02/T03 | Stable mask and optimization_target; schema version 2; aliases accepted, canonical output |
| T02 → T03 | ABBA round_id/slot + raw samples; comparisons refuse unpaired historical data |
| T04 → T06 | Completed profiling snapshot, request ID and observed native counters; missing data null |
| T05 → T06/T07 | Serial diagnostic storage; controlled IDs, atomic complete reports and bounded journal |
| T06 → T07 | Recovery reports distinguish signal evidence from unknown unclean session |
| T08 → T09 | Single idle timer coordinator, shared API/benchmark state |
| T03/T04/T07/T09 → T10/T11 | Device evidence required; local tests never authorize performance/IPA completion |

Ruling: Existing tests require the old three-pair comparison. Retain it as explicitly legacy compatibility, but all new production tournament decisions must use ABBA and five valid rounds. Cost if wrong: historical callers remain on stricter old gates; never use legacy results for Build117 promotion.

T00 DONE for source discovery/baseline; Apple build, signing and device environment PENDING_DEVICE.

2026-10-23 — User selected “先完成本地代码与全部可运行验证”. No push, GitHub Actions dispatch, IPA creation or device performance claim is authorized by this local-only handoff.

T01–T03: Implemented canonical candidate names/aliases and targets, ABBA collector, two warmups per slot, thermal precheck, configurable drift, five valid rounds/ten attempts, paired Student-t statistics, target gates, independent benefit grades and report coverage. Initial ABBA tests failed for absent collector/analyzer; final ABBA/drift/threshold tests pass. Existing output quality and fault quarantine tests pass. An isolated `-I -S --check-code` child initially failed on the new sibling import; moved measurement import under the existing child-worker guard and verified the restricted-code test passes.

T04: Added opt-in native atomic profile counters, real R4/R5/FWHT/total dispatch sites, matrix operation shape counts and Metal command-buffer GPU timestamps. Replay of the entire pinned Build83–117 patch chain passes; CPU-side times are monotonic and overlapping scopes are labelled. Snapshot publication occurs only after benchmark GPU drain/terminal counter confirmation. Ordinary inference never claims exclusive native counters. C++/Metal compilation and instrumentation overhead remain pending.

T05–T07: Added bounded Codable data, serial atomic journal/report storage, JSON-derived Markdown, retention, signal-safe fixed-size raw record, restart recovery, UUID metadata, authenticated diagnostic routes, snapshots, resource warnings and suspected no-progress observation. Added portable Swift storage/privacy/recovery/policy tests and a standalone native macOS crash subprocess test. They are configured in CI but cannot run on this Windows host; these tasks remain PENDING_DEVICE rather than DONE.

T08–T09: Added persisted common-screen toggle, main-thread singleton coordination, effective-state indication, manual snapshot feedback, adaptive compact/accessibility layouts and updated scene-phase callbacks. Existing deployment target remains iOS17. Apple SDK build, screen lock and iPadOS27 layout screenshots remain pending.

T10 local verification:

- `evidence/targeted-final.json`: 47 tests, 43 PASS, 4 explicitly skipped for missing C++/Apple compiler. Includes runner, ABBA, drift, thresholds, symbols, delivery identity, actual CMD, documentation and pinned native source contracts.
- `evidence/final-full-suite.txt`: 117 tests, 105 PASS, 4 FAIL, 1 import ERROR, 7 skips. All failures are baseline issues: three B16 source-contract tests; current-release source contract reports the same 44 issues on original and modified trees; release_manifest test imports missing `tools.certification`. Baseline reproduction: `baseline-source-failures.txt`, `baseline-release-contract.json`. Different absolute workspace strings were normalized before comparing the latter.
- `evidence/portable-python-help.txt`: actual bundled Python3.12 plus source runner/CMD succeeds in a Chinese/space path. `windows-launcher.txt`: four real CMD behavior tests pass.
- `evidence/native-patch-chain-final.txt`: fresh pinned source patch replay succeeds. `codec.txt`: reference codec arithmetic passes; GPU parity explicitly NOT_VERIFIED.
- `baseline-delivery-verification.txt`: historical Build116 full delivery manifest and paired IPA SHA256 pass; historical files unchanged.
- Python source compilation and `git diff --check` pass. Apple/Swift/Metal/device tests have not run.

Ruling: Keep unrelated pre-existing B16/current-release failures and missing certification module outside this phase's fixes after reproducing them on the base. Cost if wrong: broad suite remains red and is explicitly not a release gate PASS; remediation needs its own scope. No runtime safety gate was weakened.

Ruling: Reuse the repository's C bridge style (`BonsaiProfileCounter/Reset/Enable`) and Swift ProcessInfo thermal reading instead of introducing the pseudocode's Objective-C class getters. Public diagnostic JSON carries the requested metrics. Cost if wrong: an external consumer written against the illustrative class methods must use the actual exported interface.

2026-10-23 — Independent final review (separate reviewer, read-only) found two Important issues:

1. Failed recovery could overwrite an unrecovered checkpoint. Fixed with DiagnosticSessionJournal's recovery gate; a regression case asserts failed recovery cannot alter original journal bytes. This Swift regression is written but NOT_RUN on Windows. If recovery fails, current signal capture may remain unavailable; old evidence is preserved and failure remains observable.
2. UUID/dSYM artifacts were not retained. Added build117_symbols.py, strict UUID+architecture comparison, explicit app dSYM generation, native/app symbol ZIP + SHA256 upload and UUID identity copied into the kit. UUID rejection and synthetic packaging tests failed before the fix and pass after it. Actual Apple symbol generation remains NOT_RUN.

Final: Ruling: Reviewer classified export-time re-redaction as Minor; elevated it because the plan explicitly requires privacy on export. DiagnosticStore.read now redacts again, so both JSON and Markdown exports remove sensitive legacy keys. Added a Swift regression seeded with a private legacy field; NOT_RUN locally. Cost if wrong: over-redaction may remove an otherwise useful diagnostic label; it cannot expose extra content.

Final: minor (deferred): Alternate signal stack is installed only on the initialization thread; other threads' stack-overflow capture is not guaranteed. Documented in README; validation needs real thread-specific crashes and remains Apple work.

T11: Build117 project/CI/package identities now agree. Packaging and retained-symbol checks are synthetic offline tests only. No real Build117 IPA or dSYM has been generated. A source-review archive is provided separately and must not be used as an installable package. Parent workspace task table and repository mirror retain all Apple/device requirements as pending.

Verification note: one intermediate documentation test run raced another suite's temporary FINAL_REPORT.md directory; a sequential final targeted run passes. Do not run repository-wide documentation enumeration concurrently with tests creating temporary report directories.
