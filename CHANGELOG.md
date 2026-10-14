# Changelog

范围说明：以下旧 T01–T16 / Build109 记录是历史候选记录。当前仓库缺部分对应实现与证据，历史 PASS 不证明当前 main。以 [CURRENT_STATE](docs/optimization/CURRENT_STATE.md) 和 [候选引用清单](docs/optimization/candidate-references.json)为准。


## 2026-10-14 — Minimal documentation governance

- Added the AGENTS → INDEX → CURRENT_STATE authority chain, five status classes, evidence-based decision log and ChatGPT AI_HANDOFF.
- Corrected active workspace rules to D:\codexSpace\bonsai-ipad-runtime; retained old incidents, plans and failure evidence with explicit historical/candidate scope.
- Separated remote main, local documentation candidate, CI, device and performance identity. Inventoried 60 candidate references, 49 currently unavailable; no candidate verification is inferred from path presence.
- Preserved the original CURRENT_STATE checkout bytes in docs/history, with raw and normalized Git-blob digests; fixed seven original broken navigation links or marked their unavailable evidence explicitly.
- Added stdlib documentation checks, negative tests and one isolated step in the existing iOS workflow. No inference source, runtime defaults, model/KV/Vision settings changed.


## T01 — Build106 evidence archival

- Archived and verified the Build106 CI wrapper, unsigned IPA, and runner ZIP locally; added evidence index and input hash manifest.
- Recorded missing embedded workflow-run ID and pending real-device/signing evidence explicitly.

## T02 — Release identity manifest (Build109 candidate)

- Added a generated release manifest shared by the app header, diagnostics API and certification identity, with explicit unverified local fallback.
- Updated CI to inject source/run/Prism/ordered-patch identities, compute the actual native diff digest, compare the app Bundle build, and publish an external artifact manifest binding the unsigned IPA and runner digests.
- Pending remote macOS/Xcode workflow; no device certification claimed.

## T03 — Current release contract and historical gate migration

- Added exact manifest/package identity and negative-fixture contracts for conflicting API/artifact/runner identities, patch order, checksums, native symbols, Vision fallback and live injection gates.
- Migrated stale current-build and IPA path pins in historical contracts to the manifest-driven Build109 identity and retained their behavior gates.
- Added contract-to-CI coverage mapping. Local verification passed; GitHub CI remains pending.

## T04 — Runtime context and phase evidence (Build109 candidate)

- Added success-gated context evidence for initial load and context recreation, including native sequence count, actual C parameter shape, source SHA, and asynchronously streamed model SHA256.
- Added a bounded numeric-only monotonic phase recorder and exposed context/evidence snapshots through `/debug/build`; request phases include queue, admission, Vision encode, prefill, first content, decode, cleanup and failure when observed.
- Added Swift policy and Python schema/source tests plus CI execution. Device overhead comparison and Xcode compilation remain pending.

## T05 — Shared checkpoint certification runner

- Added a shared smoke/full/benchmark CLI with structured PASS/FAIL/INCOMPLETE verdicts, bounded report members, recursive privacy redaction, and an archive index whose SHA256 values are verified against every ZIP member.
- Checkpoints bind source SHA, external artifact identity and digest, case-suite version, and completed case evidence. Resume rejects stale source/artifact/case versions and requires a newly created native context. The Windows GUI can choose a checkpoint after the operator restarts the app.
- Converted the Build106 runner path into a compatibility wrapper; the original smoke remains available through `--legacy-smoke`. The Actions packaging gate checks all runner modules and rejects unsafe ZIP paths.
- Full suite remains INCOMPLETE until T06–T09 register and execute its required cases. Remote macOS CI and real-device validation have not run; device status is WAITING_DEVICE.

## T06 — Text, SSE, error, and restart lifecycle cases

- Added strict SSE parsing with content delta counts, first event/content timing, usage, finish reason, UTF-8/JSON error counts, and `[DONE]` validation. Role-only, usage-only, single-content-chunk, missing-usage, broken-UTF-8, and disconnected streams cannot PASS.
- Registered full-suite cases for three output-budget aliases plus omitted budget, actual-token-count gating above 256, two-turn marker recall using returned assistant history, Bearer/X-API-Key and negative auth, unknown model/route, CORS preflight, invalid JSON, stream cancellation, and liveness probes. Related inference chains stop when a request is uncertain or fails.
- Added restart checkpoint classification: the first run records WAIT_FOR_RESTART; a later run can certify only the same source/artifact/case version with a different native context ID. No device run was available, so SAFE4/B8 repeated fresh-start and Stop/Resume matrices and foreground/vision-switch lifecycle evidence remain pending.
- Local source and unit gates pass. Full M2 remains INCOMPLETE until T07/T08 cases and real-device evidence are collected; remote macOS CI has not run.

## T07 — Synthetic Vision semantics and recovery baseline

- Added deterministic public PNG fixtures for three distinct color/number/position cards and large, small, wide, and rotated OCR samples. Reports retain fixture IDs and hashes, normalized exact OCR, character accuracy, grounding/order scores, response hashes, and numeric request phase evidence; raw prompts, responses, and image data stay out of reports.
- Full suite now includes 1/2/3-image grounding, four OCR profiles, invalid data URL/four-image/remote URL/invalid MIME rejection with liveness, text→vision→text (5 cycles/15 requests), and image→image (5 cycles/10 requests) conversation follow-ups. Vision PASS requires the actual prefix reuse setting OFF and request-correlated admission, vision encode, prefill, decode, and cleanup phases. Follow-up requests must preserve a stable native context ID.
- Local implementation and contracts pass. GitHub macOS/iOS workflow, packaged runner execution, and M5 full suite have not run; MLX/native cleanup convergence and physical residency evidence remain device-gated and are not claimed.


## T08 — Long-input, native context, and admission boundaries

- Added deterministic synthetic context prompts with start/middle/end markers, SHA256-only prompt identity, real tokenizer calibration, five-level long-input requests, native context attestations, and verified text near/over-boundary cases. A report cannot substitute character count for token count or reuse a stale context ID.
- Added request-correlated text and Vision admission telemetry. Vision boundary requests record M-RoPE logical positions and physical KV cells independently; long requests poll governor native batch/token progress and mark uncertain timeouts INCOMPLETE without automatic retry.
- Full suite requires both text and Vision boundary rejection before post-error recovery cases. Local Python/contract gates pass; M5 long-input traces and macOS package CI remain pending.


## T09 — Paired benchmark standard

- Added fixed public short/medium/long workloads with seed 1234, temperature 0, 32/384 output tiers, exact prompt hashes, and mandatory engine-reported actual token counts.
- Added A1/B/A2 pairing and verdicts that require consistent source/assets/config/sampling/thermal/cache state, signed lineage, entitlements and native trace, all T06–T08 cases, and the T08-certified long-input envelope. Reports use median/range, record total attempts and observed failures, block cached-hit/fresh pairs, and return INCONCLUSIVE for >10% ABA drift.
- Added privacy-filtered baseline ZIP export with an exact member hash index. SAFE4/B8 baseline and candidate records are empty `WAITING_DEVICE` templates; no M5 performance result is claimed.


## T10 — B16/B24 single-variable experiment gates

- Added batch ABA evaluation for B8→B16→B8 and B16→B24→B16. The verdict verifies actual governor label/batch/ubatch, pending completion after at least 200 prompt tokens, distinct full-process restarts, seq1/Q4/GPU99/Metal fixed settings, unchanged kernel/environment/Vision/sampling, thermal/cache evidence, and the T09 identity/memory envelope.
- An experiment passes only with at least three matched groups, 15% median prefill or TTFT improvement, decode regression no worse than 5%, ABA drift no more than 10%, semantic/stability PASS, and memory within envelope. Output is `EXPERIMENT_PASS`; it does not alter defaults. B24 requires a prior passing B16 trial.
- Added a `WAITING_DEVICE` ABA template. No M5 experiment ran and no profile was promoted.


## T11 — Certified startup envelopes (2026-10-13)

- Added exact source/Prism/native patch/model/Vision/OS/KV/profile/startup/context fingerprints and a bundle registry for `FULL_CERTIFIED` startup envelopes. Missing hashes or registry data fail closed; the checked-in registry is empty.
- The 32K context-creation Governor now verifies prior arm qualifications, matching baseline/candidate envelopes, startup available-memory budget, and nominal/fair thermal state. Sticky SAFE4 retains priority; downgraded candidates clear pending state, and uncertain interrupted attempts are recorded as `INTERRUPTED_UNKNOWN` rather than a crash. Runtime context shape still changes only at next context creation.
- Added Foundation Swift policy tests and CI wiring, plus Python source/resource/manifest contracts. Local Python suite passes; Swift compilation, macOS CI and M5 state/restart evidence remain pending. Defaults remain B8/SAFE4.


## T12 — 32K memory candidate evidence gate (2026-10-13)

- Inspected the frozen Build106 evidence and confirmed it has no M5 phase-attributed load/context-init/prefill/Vision/cleanup peak samples, allocation-failure trace, or verified model/Vision asset hashes. No speculative runtime allocation change was made; Q4_0, mmap and Build89 scheduler metadata remain identified as existing mechanisms.
- Added a paired memory-candidate evaluator requiring identical runtime configuration, all five phase peaks, sampled peak, quality PASS and performance regression no greater than 5%. It returns INCOMPLETE without device evidence, NO_SAFE_WIN below 5% measured peak reduction unless a confirmed allocation failure is eliminated, and FAIL if the candidate still fails allocation.
- The archived candidate record is `INCOMPLETE_DEVICE_EVIDENCE`; T12 cannot advance to a runtime candidate until an M5 trace identifies the dominant peak.


## T13 — Single-sequence text KV reuse exit (2026-10-13)

- Pinned-source and historical M5 evidence review found the Build76 partial-tail `llama_memory_seq_rm` call returned false on device and correctly fell back to full prefill. Current Build104 checkpoint reuse is gated on `n_seq_max >= 2`; Build105 quarantines the preference and production remains `n_seq_max = 1` with text KV reuse OFF.
- Archived T13 as `NO_SAFE_WIN` for the current single-sequence design. Whole-sequence on-device state snapshot/restore used by the Vision bridge does not establish arbitrary text tail-trim or single-sequence restore correctness; no seq2 or runtime behavior was enabled.
- Added a fail-closed evidence evaluator and contracts for fresh-reference fingerprint equality, actual reused tokens, tail-trim/restore success, Vision/cancel/failure invalidation, one sequence, and T10 performance/safety gates.


## T15 — Prism Metal route observer

- Source `a216e45`; rollback anchor `d6bf30d`. Added Build107 bounded aggregate route counters and `/debug/execution` snapshot for selected `GGML_OP_MUL_MAT` paths. No kernel math or batch/KV defaults changed.
- Local verification: 124 unit tests, 60 historical source contracts, Build91 execution contract, pinned Prism source patch-application check, Python compile, workflow YAML parse, and diff checks passed.
- GitHub XCFramework/macOS CI, native symbol and Swift link checks, M5 route/overhead measurements, and M2 regression remain NOT RUN. Observer verdict is UNKNOWN and no candidate was chosen.


## T16 — requirement audit checkpoint (draft only)

- Began the R01–R18 audit at implementation checkpoint `a216e45` with `docs/optimization/release/EVIDENCE_MATRIX.csv`, `RELEASE_README.md`, `KNOWN_LIMITS.md`, and `EXPERIMENT_INDEX.md`. Every matrix evidence path exists and unverified gates are explicitly listed. Added a pinned-source license inventory for MLX Swift/C++/C API, vendored fmt/JSON, historical Swift Numerics, Prism and the Qwen3 sidecar lineage; added 3 R01–R18 matrix contracts and explicit CI/upload integration; the build106 log resolves swift-numerics 1.1.1, while this branch has no tracked Package.resolved. Maintainer attribution/distribution confirmation remains open.
- This is not a release baseline. No mandatory device gate, signed artifact/entitlement audit, third-party license review, or final release decision is marked complete. `d6bf30d` is only the pre-T15 observer rollback checkpoint; the final release rollback remains unselected.

## T16 — post-audit verification refresh (2026-10-13)

- Re-ran the current local Python verification after the audit matrix was added: 127 unit tests and all 60 historical source contract scripts passed. The Windows contract invocation used `PYTHONUTF8=1`, matching the existing test instructions. This refresh does not change the release audit status.

## T16 — SwiftPM resolution evidence pipeline

- The generated Xcode project's `Package.resolved` is now required and uploaded by CI; `artifact_manifest.json` binds its file hash and normalized package versions/revisions. The pipeline does not claim a current resolution until the workflow runs.

## T16 — Swift Numerics exact resolution

- `project.yml` directly pins and links `apple/swift-numerics` 1.1.1; release source and artifact contracts reject a missing/mismatched product or resolved version.

## T16 — Release gate classification audit checkpoint

- Added an explicit `gate_class` for all R01–R18 rows, separating mandatory integrity/runtime/product gates from optional profile, memory and route experiments and the current T13 `NO_SAFE_WIN` disposition. Updated plan execution notes; the audit remains `INCOMPLETE`.

## T14 — Vision cache identity (local implementation checkpoint)

- Replaced filename/size-oriented cache keys with a generation-scoped SHA256 fingerprint over image, model and Vision assets, preprocessing, grid policy, projection dimension and format version.
- Upgraded native and MLX projected embedding cache packets to BVCACHE2 with an embedded fingerprint; every native cache read validates the expected fingerprint, and old-format data becomes a miss.
- Added async hashing cancellation, Swift fixtures, Python source contracts and a macOS CI step. Cache/layout/resolution behavior and image math were not changed.
