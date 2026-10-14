# Test and Verification Results

范围说明：以下旧 T01–T16 / Build109 记录是历史候选记录。当前仓库缺部分对应实现与证据，历史 PASS 不证明当前 main。以 [CURRENT_STATE](docs/optimization/CURRENT_STATE.md) 和 [候选引用清单](docs/optimization/candidate-references.json)为准。


## 2026-10-15 - Build110 B16 candidate local verification

Base: `40f8a4d52a10825e6675f8d592c3637d849b7d87`, branch `codex/32k-prefill-b16`. This records host/source checks, not iPad certification.

- `python -m unittest discover -s tools/tests -p test_b16_*.py -q`: exit 0, **47 tests PASS** in 59.878s on the final local source. Includes actual loopback orchestration (63 inference requests, 18 Prefill benchmark samples), restart/resume/no-replay, identity/configuration, privacy ZIP/hash, memory sampling, sustained Decode, SSE and packaging negatives. Mock performance is not a device result.
- `python tools/b16_testkit.py --dry-run`: exit 0; registration succeeds while verdict remains INCOMPLETE, device_certified=false and full_32k_input_certified=false.
- All 53 Python source-contract scripts selected from the existing workflow's `python3 tools/*contract_tests.py` commands: exit 0, 53 PASS, using PYTHONUTF8=1. Old behavioral/native/API/Vision assertions retained; current package version pins follow project.yml.
- Workflow YAML: 67 steps; all 64 run blocks checked by Git Bash `bash -n`, exit 0. Windows GUI PowerShell AST and Python 3.8 AST checked separately: PASS; portable Python digest/extraction fixtures included in the 47-test suite.
- `python tools/documentation_consistency.py` and `python -m unittest discover -s tools/tests -p test_documentation_consistency.py -q`: PASS, 10 tests, exit 0. Run document scan after temporary loopback fixture cleanup; simultaneous scans can see unclassified temporary reports.
- `git diff --check`: exit 0. Protected diff against base is empty for Vendor/Prism, BonsaiMLXVisionSidecar, StagedVisionBridge, M5RuntimeGovernor, RuntimeOptimization and BonsaiUltraSmoke. project.yml changes only CURRENT_PROJECT_VERSION 106 -> 110. BonsaiEngine changes attach/invalidate creation evidence and report actual build; native parameter assignments and default Runtime configuration are retained.
- Red/green failures exercised missing runner/evidence, invalid identity/context, stale observations, unsafe resume, missing sustained Decode, injected degradation/drift and SSE timing. Windows local checkpoint-sharing and mock socket concurrency failures were corrected and the full suite rerun sequentially. Only local filesystem checkpoint replacement can retry; uncertain HTTP requests cannot replay.
- Independent read-only review found and resolved context invalidation/qualification, failed Vision hash readiness, first-event timing and repeat asset-hash issues. Swift tests cover source-gated pending/sticky policy, real creation identity, absent/stale identity, asset coexistence/mutation and bookmarks.
- Local Swift/iOS compilation NOT_RUN (Windows has no swiftc/Xcode); exact-source GitHub macOS CI is required. User M5/32K performance **NOT_RUN / WAITING_DEVICE**. Candidate gates are >=15% median Prefill improvement, >=95% sustained Decode, <=10% ABA drift and no registered regression/memory failure; no default promotion.
- Unrelated historical Build109 infrastructure gaps remain as recorded below; this is not a blanket tools/tests PASS. No missing Build109 framework reconstruction or old Runtime test repair.

## 2026-10-15 — PASS_WITH_FINDINGS follow-up

Correction base: `35aa64ff6d94d8855882cd3f1fe5a5d0ceb549a2`. Original commit was conditionally accepted by the user's ChatGPT review; that conclusion does not certify this correction, devices or performance.

- `python tools/documentation_consistency.py`: exit 0, PASS; includes main/CI/candidate SHA, ACTIVE workspace and completed-handoff checks.
- `python -m unittest discover -s tools/tests -p test_documentation_consistency.py -v`: exit 0, 10 tests PASS. Negative subcases independently change each SHA source, shorten/remove main SHA, regress each active directory declaration, and revive handoff authority/body. Historical paths and differing development HEAD are accepted.
- TDD: 8 injected-conflict subcases failed before implementation; all 10 tests passed after correction. Tests call actual validate() through read overrides without editing real evidence.
- `git diff --check`: exit 0. Python 3.8 syntax: PASS.
- Protected comparison against correction base: exit 0, empty diff for BonsaiLab (Engine/Vision/Governor/Runtime defaults), BonsaiUltraSmoke, project.yml, Vendor, .github, archives, historical backburner/release evidence and Build83-89 Prism patch scripts.
- CI metadata and candidate-baseline files unchanged; no development-HEAD/main equality requirement. Old candidate Runtime tests were not repaired or rerun.
- Candidate remote CI / M5 / performance NOT_RUN. No push, main merge, new iPad build or profile promotion.

## 2026-10-14 — Documentation governance verification

Scope: documentation candidate based on `dc169d6759e84e6b0f66c2c8ad87e6f073bd78c6`. Commands ran in the official workspace; new remote CI, Swift/iOS build, device and benchmarks NOT_RUN.

| Check | Result and exact scope |
|---|---|
| `python tools/documentation_consistency.py` | PASS: local Markdown classification, relative file links, navigation and candidate-reference scope only |
| `python -m unittest discover -s tools/tests -p test_documentation_consistency.py -v` | 6 tests PASS; broken-link, missing/false-PASS candidate, missing-scope, invalid authority status and missing-navigation negative fixtures included |
| Authority inventory | 145 Markdown: ACTIVE 7, REFERENCE 9, HISTORICAL 126, DRAFT 2, SUPERSEDED 1; T16 CSV separately DRAFT |
| Candidate references | 60 paths: PRESENT 11, NOT_AVAILABLE 49; all NOT_VERIFIED |
| Workflow YAML parse | PASS: existing build job parses with 65 steps including the isolated document gate |
| `git diff --check` | PASS |
| Protected-source comparison against base | PASS: BonsaiLab, BonsaiUltraSmoke, project.yml, Vendor, archives, historical backburner evidence and T16 release files unchanged |
| Historical CURRENT_STATE preservation | PASS: original checkout bytes copied; text identical to base Git blob after CRLF/LF normalization. Raw SHA256 `949fb6e6b58b3fd3542c3fe5484b4824ec78ecd796cd4a39eaf65a1ebad49dc5`; Git blob SHA256 `7b2a3f2518a5039745500f5789009c1b245c74638a7d2dc7a277724d643d3d87` |
| Baseline main CI metadata | run 38579679479 completed/success for exact base SHA; API metadata only, no new IPA extraction, signing or device validation |
| New documentation commit CI / M5 / performance | NOT_RUN / WAITING_DEVICE / NOT_RUN |

TDD observation: the new document tests initially failed with ModuleNotFoundError for the unimplemented checker, then passed after implementation. Internal read-only review found no blocking factual/scope issue; both wording and negative-fixture suggestions were addressed. This is separate from the requested external ChatGPT cross-review.

Known pre-existing candidate infrastructure gaps (not a complete tools test PASS):
- `python -m unittest discover -s tools/tests -p test_current_release_contract.py -v`: 10 tests, 9 PASS, 1 FAIL. Source-contract check reports 45 missing candidate wiring/resources/identity gates.
- `python -m unittest discover -s tools/tests -p test_release_manifest.py -v`: import ERROR: missing `tools.certification.identity`.
- These candidate tests were retained. This task does not fill missing Runtime files, bypass tests or revise historical PASS statements into current PASS.


## T01 — Build106 evidence archival

- `python` ZIP CRC checks: outer artifact, IPA, and runner ZIP all passed (`testzip() == None`).
- Unsigned IPA SHA256 matched the companion `.sha256`: `cc4943452345780c91009856ceff9c50d2e185802456aae07249ca2d3efe7291`.
- GitHub wrapper SHA256 matched locally: `db01dac3b5a11d325cf87dd96bd2693d9dd59866110e4a1c4a3b1e478b6a97aa`.
- IPA `CFBundleIdentifier=local.bonsai.lab.v1`, `CFBundleVersion=106`; source SHA and Prism SHA occur in executable; workflow run ID does not.
- All six research-file SHA256 values match the preserved source checksum list. The research ZIP and v1 plan hashes are recorded in `docs/optimization/evidence/INPUTS.sha256`.
- Device install/smoke: NOT RUN; unsigned IPA, no attached iPad integration in this execution environment. Device certification remains `WAITING_DEVICE`.

## T02/T03 — Build109 source verification (2026-10-13)

- `python tools/current_release_contract_tests.py`: PASS.
- `python -m unittest discover -s tools\tests -p test_release_manifest.py`: 8 tests PASS.
- `python -m unittest discover -s tools\tests -p test_current_release_contract.py`: 9 tests PASS.
- All 59 `tools/*contract_tests.py` source contracts: PASS.
- `python tools/rc126_build106_full_stage_certification.py --dry-run`: PASS.
- `python -m compileall -q tools`: PASS; `git diff --check`: PASS.
- Workflow YAML parses as 65 steps. Remote macOS/Xcode build and artifact inspection: NOT RUN; device certification: WAITING_DEVICE.

## T04 — Runtime evidence (2026-10-13)

- `python -m unittest discover -s tools\tests -p test_runtime_evidence.py`: 8 tests PASS, including wrong context ID, sequence=2, absent prompt count, unknown model hash, both native context paths, and debug evidence exposure.
- Existing release-manifest tests: 8 PASS; current-release contract tests: 9 PASS; all 59 historical source contracts: PASS.
- `python -m compileall -q tools`: PASS; workflow YAML parses as 66 steps and includes the Swift evidence test gate.
- Pure Swift test source added; local execution NOT RUN because `swiftc` is unavailable on this Windows host. GitHub macOS compile and M5 observer OFF/ON overhead comparison are pending. Device certification remains `WAITING_DEVICE`.

## T05 — Shared certification runner (2026-10-13)

- `python -m unittest discover -s tools/tests`: 46 tests PASS, including verdict, privacy, report ZIP hashes, checkpoint source/artifact/case-version/new-context checks, and compatibility entrypoint.
- All 59 `tools/*contract_tests.py` scripts PASS with `PYTHONUTF8=1` (legacy source contracts rely on UTF-8 default decoding on the macOS CI host).
- `python -m compileall -q tools`, shared runner dry-run, direct script and module runner dry-runs, compatibility wrapper dry-run, retained legacy smoke dry-run, PowerShell GUI syntax parse, workflow YAML parse (67 steps), and `git diff --check`: PASS.
- Remote packaging/CI ZIP execution: NOT RUN yet. macOS Swift/iOS build: NOT RUN. M5 device cases: NOT RUN; full suite intentionally remains INCOMPLETE pending T06–T09 and device access.

## T06 — Text/SSE/error/restart contracts (2026-10-13)

- `python -m unittest discover -s tools/tests`: 57 tests PASS, including the new SSE (4), text output (3), lifecycle (3), runner resume and report contracts.
- All 59 historical `tools/*contract_tests.py` scripts: PASS with `PYTHONUTF8=1`.
- Python compileall, module and direct runner dry-runs, retained Build106 smoke dry-run, PowerShell GUI parser, workflow YAML parse (68 steps), and `git diff --check`: PASS.
- No iPad was available. SAFE4/B8 10× fresh starts, 5× Stop/Resume, native lease cleanup, app background/foreground, and vision-switch recovery: NOT RUN. Vision semantic cases and calibrated 32K input remain T07/T08. No API/Engine behavior change was made.
- GitHub macOS/iOS workflow and packaged Windows GUI execution: NOT RUN; T06 remains locally implemented but externally unverified.

## T07 — Synthetic Vision and recovery contracts (2026-10-13)

- `python -m unittest discover -s tools/tests`: 66 tests PASS, including deterministic fixture hashes/PNG CRC, OCR normalization and character accuracy, grounding/order negative cases, actual prefix reuse diagnostic presence, five-cycle aggregate rules, and full-suite registration of invalid-input and follow-up cases.
- All 59 historical `tools/*contract_tests.py`: PASS with `PYTHONUTF8=1`; `python -m compileall -q tools`, shared and compatibility runner dry-runs, workflow YAML parse (69 steps), and `git diff --check`: PASS.
- Full runner cases are implemented but were not executed against the app. GitHub macOS/iOS build/package CI and real M5 Vision/OCR, 15+10 follow-up requests, model residency, sampled-memory convergence, and native cleanup validation: NOT RUN. These gates remain INCOMPLETE / WAITING_DEVICE.


## T08 — Long-input and context admission contracts (2026-10-13)

- `python -m unittest discover -s tools/tests`: 82 tests PASS, including real-token evidence requirements, native context identity, 5% calibration, text and Vision logical/physical admission, clamped output, over-boundary rejection, deterministic sentinels, and complete-ladder resume behavior.
- All 59 historical `tools/*contract_tests.py` scripts: PASS with `PYTHONUTF8=1`; `python -m tools.certification.run_suite --dry-run`, Python compile checks, and `git diff --check`: PASS.
- Full suite runner now has 2048/8192/16384/32768 context attestations, calibrated 256/1024/4096/8192/16384 input levels, text and Vision near/over boundaries, governor progress samples, and post-rejection text/Vision recovery gates. No device request was executed here. iOS/macOS CI, Swift compilation on macOS, actual M5 8K/16K/near-32K traces, output retrieval quality, and physical/logical Vision boundary behavior remain NOT RUN; full M2 status is INCOMPLETE / WAITING_DEVICE.


## T09 — Paired benchmark and baseline contracts (2026-10-13)

- `python -m unittest tools.tests.test_benchmark_verdicts`: 13 tests PASS, covering fixed workload hashes/sampling/output tiers, short/medium/long requirements, SAFE4/B8 shape, missing identities/counts/signature/native traces, absent T06–T08 evidence, >10% ABA drift, cached prompt mismatch, failed attempts, memory/latency regression, median/range output, and baseline ZIP member hashes/privacy.
- Baseline templates parse as JSON and intentionally contain no measurements; SAFE4 is 4/4, B8 is 8/8, and both require 20 text runs, 5 vision cycles and 60 minutes mixed foreground.
- Device matrix, complete T06–T08 run evidence, signed artifact/entitlements lineage, and baseline ZIP from a real iPad M5: NOT RUN. T09 is locally implemented, while benchmark baseline certification remains INCOMPLETE / WAITING_DEVICE.


## T10 — Batch ABA verdict contracts (2026-10-13)

- `python -m unittest tools.tests.test_batch_benchmark`: 9 tests PASS for three-group B8/B16/B8 qualification and negative profile shape, pending, actual-token count, seq2/KV reuse, thermal mismatch, missing return baseline, decode regression, memory envelope, B24 prerequisite, workload coverage, and non-batch config changes.
- The experiment artifact `docs/optimization/benchmarks/batch-aba.json` is an empty `WAITING_DEVICE` design record. No next-launch arm was scheduled, no default was changed, and no M5 run was made. Build94/M5 runtime governor source remains unchanged by T10.


## T11 — Certified runtime envelope and startup Governor (2026-10-13)

- `python -m unittest discover -s tools/tests -v`: 110 tests PASS, including six certified-envelope contracts and all existing tests.
- Swift Foundation policy tests and Build106 compatibility policy tests are wired into `.github/workflows/build-ios.yml`; local Swift execution is NOT RUN because `swiftc`/Xcode are unavailable on this Windows host. GitHub macOS CI has not run for this branch.
- All 59 historical Python source contracts PASS; Python compileall, shared runner dry-run, workflow YAML parse (72 steps), and `git diff --check` PASS.
- No M5 device was available. Fresh-start memory envelopes, candidate trial classifications across real process exits, and M5 restart cases remain NOT RUN / WAITING_DEVICE. The shipped envelope registry is empty, so no high profile is certified or eligible; default behavior remains B8/SAFE4.


## T12 — 32K memory candidate evidence gate (2026-10-13)

- `python -m unittest tools.tests.test_memory_candidate -v`: 4 tests PASS for missing phase evidence, paired config, 5% peak threshold, quality/performance gates and confirmed allocation-failure elimination.
- Frozen Build106 evidence review: no M5 phase-attributed peak trace or allocation-failure trace is available; model/Vision hashes are unverified. The candidate record therefore remains `INCOMPLETE_DEVICE_EVIDENCE`; no runtime memory policy was changed and no `NO_SAFE_WIN` measurement claim is made.
- The new evaluator and test are wired into the macOS workflow and artifact upload. Swift/device certification is not applicable to this evidence-only checkpoint; collecting M5 measurements remains the next T12 prerequisite.


## T13 — Single-sequence KV reuse evidence (2026-10-13)

- `python tools/kv_reuse_contract_tests.py`: PASS; confirms `textKVReuseEnabled = false`, `n_seq_max = 1`, Build105 recovery quarantine and the archived `NO_SAFE_WIN` result.
- `python -m unittest tools.tests.test_kv_reuse_evidence -v`: 5 tests PASS for the no-promotion archive, actual reused-token requirements, reference identity mismatch, Vision/cancel/failure invalidation, tail-trim/restore and T10 gates.
- Evidence basis: the historical Build76 M5 report records tail removal returning false; current Build104 path requires seq2 and Build105 keeps it quarantined. No new M5 A/B run was possible. This is a deliberate `NO_SAFE_WIN` for the current design, not proof that every future single-sequence checkpoint design is impossible.


## T15 — Prism Metal route observer (2026-10-13; implementation checkpoint)

- Added Build107 bounded aggregate counters for selected `GGML_OP_MUL_MAT` encoder paths (FWHT, Q1_0 popcount, `mul_mv_ext`, `mul_mm`, fallback `mul_mv`) and exposed cumulative snapshots through `/debug/execution`. Snapshot records are capped at 128; omitted/invalid observations are surfaced as overflow. The observer collects no tensor contents and does not claim GPU completion or GPU timing.
- `python -m unittest tools.tests.test_prism_route_observer -v`: 5 tests PASS, including the cross-layer C ABI/diagnostic endpoint/CI patch-order contract. `python -m unittest discover -s tools/tests -v`: 124 tests PASS. All 60 historical `tools/*contract_tests.py` scripts PASS with `PYTHONUTF8=1`.
- Python compile checks, Build91 forensics endpoint contract, workflow YAML parsing, and `git diff --check`: PASS. The patch was applied in memory to the complete pinned `ggml-metal-ops.cpp` blob (`c41bae469ac5330ef52dd4b57541e51cd3fcb989`): all five route anchors matched exactly, one function signature remained, and the resulting source contained five route markers. This verifies patch application only; it is not a native compile.
- GitHub macOS/iOS XCFramework build, exported-symbol check, Swift app link, M2 regression, actual M5 route counts, and instrumentation overhead measurement: NOT RUN. `prism-route-observer.json` remains `UNKNOWN` / `WAITING_DEVICE`; no kernel candidate or optimization claim is selected.


## T16 — requirement audit draft (2026-10-13; not a release gate)

- Drafted all 18 R01–R18 rows in `docs/optimization/release/EVIDENCE_MATRIX.csv`; checked that every referenced implementation evidence path exists. Added the draft release status, known limits, and T10–T15 experiment index.
- `python -m unittest tools.tests.test_release_evidence_matrix -v`: 3 tests PASS for all 18 unique rows, required fields, existing evidence paths, and the non-release draft gate. Matrix/path validation, workflow YAML parse, and `git diff --check`: PASS. Third-party source inventory was checked against pinned upstream license files and the archived Build106 package log; it found a historical `swift-numerics` 1.1.1 resolution, no tracked current `Package.resolved`, and a Qwen3 sidecar attribution requiring maintainer review. No legal/distribution conclusion is claimed. The draft deliberately records `INCOMPLETE`; no `RELEASE_BASELINE.json` or release approval was produced because M2 device evidence, current-SHA macOS CI, T14 review/implementation, T15 device data, signed entitlements, and license review remain incomplete.

## T16 — post-audit verification refresh (2026-10-13)

- `python -m unittest discover -s tools/tests -v`: 127 tests PASS.
- All 60 `tools/*contract_tests.py` scripts: PASS with `PYTHONUTF8=1`.
- Diagnostic: invoking `rc1231_source_contract_tests.py` without UTF-8 mode on Windows Python 3.11.4 (preferred encoding `cp936`, `utf8_mode=0`) reproduces a `UnicodeDecodeError` in legacy `Path.read_text()` calls. With `PYTHONUTF8=1`, that script and all 60 contracts pass. Existing T05 instructions already document this environment requirement; no product-source change was needed.
- The refreshed GitHub source ref still resolves to `1abfa8598629e25b69e14350a6559176ffc4a926`; it remains an ancestor of the optimization branch. macOS CI and M5 device gates remain NOT RUN; T16 remains INCOMPLETE.

## T16 — Per-artifact SwiftPM resolution evidence (2026-10-13)

- TDD RED: the new artifact-manifest test failed because `build_artifact_manifest` did not yet accept a resolved lock; after implementation, `tools.tests.test_release_manifest` has 10 tests PASS, including exact lock hash/pins and fail-closed missing version/revision cases.
- `tools.tests.test_current_release_contract`: 9 tests PASS; `tools/current_release_contract_tests.py`: PASS. Workflow now resolves SwiftPM after project generation, builds with automatic re-resolution disabled, uploads the generated `Package.resolved`, and binds its SHA256 plus package versions/revisions into `artifact_manifest.json`.
- Full Python suite: 137 tests PASS; all 60 historical contracts PASS with `PYTHONUTF8=1`; Python `compileall`, 77-step workflow YAML parse, 4 release matrix tests and `git diff --check`: PASS. No current-SHA macOS run exists, so the lock contents remain unobserved and unclaimed.

## T14 — Vision cache identity checkpoint (2026-10-13)

- `python -m unittest tools.tests.test_vision_cache_identity -v`: 7 tests PASS, covering fingerprint fields/version, content hashing/stale generations, cache v2 fingerprint validation, native/MLX identity policy, bridge call-site propagation, and staged scope/order.
- `python -m unittest discover -s tools/tests -q`: 137 tests PASS. All 60 historical `tools/*contract_tests.py` scripts PASS with `PYTHONUTF8=1`; Python `compileall`, 77-step workflow YAML parse, 4 release evidence matrix tests and `git diff --check`: PASS.
- Local host has no `swiftc` or `xcrun`; Swift fixture, macOS/Xcode CI, M5 device quality/cache-hit/memory/lifecycle measurements: NOT RUN. T14 remains incomplete for release/performance evidence; no speed or memory improvement is claimed.

## T16 — Swift Numerics 1.1.1 exact pin (2026-10-13)

- TDD RED: the new source and artifact contracts failed because `project.yml` did not declare Swift Numerics and the artifact validator accepted a `1.1.2` pin.
- `project.yml` now directly pins and links the `Numerics` product at 1.1.1. The source contract enforces the exact package/product declaration; artifact manifest generation rejects any resolved Swift Numerics version other than 1.1.1.
- `tools.tests.test_current_release_contract` (10 tests), `tools.tests.test_release_manifest` (10 tests), `tools/current_release_contract_tests.py`, and the full Python suite (138 tests): PASS. The current-SHA resolved lock and Xcode project generation still require macOS CI; no current artifact resolution is claimed.
