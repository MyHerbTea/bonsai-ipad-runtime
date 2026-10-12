# Current State — 2026-10-13

- Frozen source: `1abfa8598629e25b69e14350a6559176ffc4a926` on `lab-v1-rc1-26-build106-m5-governor`.
- Actions run/job: `38147351064` / `114493396250`; all 64 reported job steps completed successfully.
- Artifact `11704414799` is now downloaded locally and CRC-checked. GitHub wrapper SHA256 equals the locally downloaded ZIP SHA256.
- Unsigned IPA digest matches its companion `.sha256`; IPA bundle id is `local.bonsai.lab.v1`, bundle version `106`; runner ZIP CRC is valid.
- Executable contains exact source SHA and pinned Prism SHA. Run ID was not found in executable; it appears in `BUILD_INFO.txt`.
- CI environment: macOS 15.7.9 arm64, Xcode 16.4 build 16F6, iPhoneOS SDK 18.5, Swift language mode 5, iOS deployment target 17.0, MLX Swift 0.31.3. Prism base `adfffbe41b2cabcd51fff326ab045662265062bb`; ordered source patches Build83–89 were built, with logged PASS confirmations for 83/84/85/86/88/89 and Build87 marker checks.
- Device/signing state: `WAITING_DEVICE`; unsigned IPA only. No M5 install/smoke or full device certification is claimed.
- Artifact expiry: `2026-10-25 22:37:37 +08:00`; local wrapper archived at `artifacts/build106-1abfa859/`.
- Research source hashes and the v1 plan/ZIP hashes: see [INPUTS.sha256](evidence/INPUTS.sha256). Binary digests and verification detail: see [build106-artifact-index.json](evidence/build106-artifact-index.json).

## Build109 optimization candidate (local development)

- Branch: `codex/bonsai-rc126-optimization`, created from the frozen Build106 source SHA above. Project build number is 109; remote Build107 and Build108 names were occupied when checked.
- T01–T04 are committed locally. T02/T03 source contracts pass; T04 Swift/macOS compilation and M5 observer overhead still require remote CI/device evidence.
- New local fallback manifest is intentionally unverified. CI must inject the source SHA, Actions run ID and actual native diff digest before producing a certifiable artifact.
- GitHub macOS workflow has not run for this branch yet; Xcode build and IPA extraction are pending. Device/signing/full certification remain `WAITING_DEVICE`.

- T04 runtime evidence is implemented locally: native context data is published only after successful creation; source SHA is embedded, model SHA256 is streamed on a utility task, and request evidence records numeric monotonic phases with per-request and global bounds. Swift compilation and observer overhead still require the remote macOS runner and M5 device.

- T05 shared certification runner is implemented locally: report ZIP privacy and member hashes, artifact-bound checkpoint resume, Windows GUI resume selection, and a compatibility wrapper retaining the historical Build106 smoke. Local tests pass; remote package CI and device validation remain pending. Full suite status is INCOMPLETE until T06–T09 add its required cases.

- T06 text/SSE/error lifecycle cases are implemented locally. The parser rejects role-only, usage-only, one-delta, missing-DONE/usage, and malformed UTF-8 streams; full suite now records output-budget, multi-turn, HTTP error/liveness, cancellation, and manual restart evidence. SAFE4/B8 repeated restart matrices and native lifecycle checks remain `NOT RUN`; T07–T09 remain required before full suite can PASS.

## T07 — Vision semantics and recovery baseline

- Implemented locally on `codex/bonsai-rc126-optimization`: deterministic public fixture library/index, semantic grounding/OCR scoring, response redaction, request-bound numeric phase events, and read-only `/debug/build` exposure of the configured Vision prefix reuse value. The full runner refuses Vision PASS if the setting is not observably OFF.
- Registered synthetic Vision, OCR, invalid-input/liveness, five-cycle text→vision→text, and five-cycle image→image cases. Conversation history is retained in memory between requests; the full loop checks that observed native context IDs stay constant and that each Vision request emits cleanup evidence.
- 66 local unit tests and 59 historical contracts pass. No macOS CI or M5 run has occurred. The current runtime evidence does not measure a post-cleanup residual-memory threshold or independently prove MLX model residency; those device evidence claims remain pending.


## T08 — Long input and admission boundaries

- Local branch implements deterministic, hash-identified text fixtures calibrated against the engine tokenizer; native context attestations; sequential 256/1024/4096/8192/16384 prompt cases; and text plus Vision near/over-boundary cases. Vision evidence keeps M-RoPE logical positions separate from physical prompt KV cells.
- Long request polling retains request-correlated governor batch/token progress. Timeouts with uncertain request state remain INCOMPLETE and are not replayed. Post-context-error recovery runs only after both text and Vision over-boundary cases pass.
- Local Python checks pass. macOS package CI, Swift compilation, iPad installation, and all M5 context/quality traces have not run. Full M2 certification remains `INCOMPLETE` / `WAITING_DEVICE`.


## T09 — SAFE4/B8 paired benchmark baseline

- Added `tools/certification/benchmark.py` with fixed hashed public prompts, native actual-token requirements, A1/B/A2 pairing, identity/cache/thermal/configuration validation, SAFE4/B8 sample gates, median/range summaries, attempts/failures counts, >10% ABA inconclusive verdict, and latency/memory regression limits.
- Added empty baseline/candidate JSON templates and an indexed, prompt-redacted baseline ZIP exporter. SAFE4 is 4/4 and B8 is 8/8. The templates remain `WAITING_DEVICE`; no benchmark measurements have been recorded.
- Local T09 tests pass. Full 20-text/5-vision/60-minute matrices, signed lineage, T06–T08 device evidence and M5 ZIP remain pending. Full M2 remains `INCOMPLETE` / `WAITING_DEVICE`.


## T10 — Guarded batch experiments

- `benchmark.py` can evaluate single-variable B8→B16→B8 and, only after B16 qualifies, B16→B24→B16 evidence. It checks three paired groups, per-process restarts, pending-clear proof, exact active shape, T09 fingerprint, thermal and memory envelope, and the 15%/5%/10% decision gates. A successful verdict is `EXPERIMENT_PASS`, never a default promotion.
- The experiment record has no device runs. B8/B16/B24 selection, candidate restart behavior, performance and memory remain NOT RUN; current defaults are unchanged.


## T11 — Certified startup envelope implementation

- The 32K context-creation policy now binds source, Prism, native patch, model, Vision, OS, KV type, profile, startup mode and context to a `FULL_CERTIFIED` report envelope. It checks the documented available-memory formula and blocks constrained/critical memory or serious/critical thermal state. Fingerprint or measurement omissions fail closed. The checked-in registry has no device envelopes.
- B16/B24/B32 retain the original eligibility/consent flags and additionally require full matching envelope evidence; B16/B24 also require certified lower-profile envelopes. Sticky SAFE4 is checked before arm preferences. Candidate downgrade clears pending state; unknown prior process exit is recorded as `INTERRUPTED_UNKNOWN`, not labeled a crash.
- New Swift executable tests are included in macOS CI, but neither that workflow nor a local Swift compiler has run. Device startup-memory measurements and real restart/state classifications remain `WAITING_DEVICE`; no profile promotion is claimed.


## T12 — Memory optimization candidate status

- T12's mandatory evidence review found no device trace with phase-level memory samples across load, context initialization, prefill, Vision and cleanup, and no confirmed allocation failure to target. Model/Vision hashes are also absent from the frozen Build106 evidence. Q4_0 KV, mmap and Build89 compact scheduler metadata are already present and are not being presented as new changes.
- No BonsaiEngine, MLX lifecycle or Prism allocator/scheduler runtime code was changed. `docs/optimization/benchmarks/memory-candidate.json` records `INCOMPLETE_DEVICE_EVIDENCE` with baseline/rollback SHA and missing evidence. A fail-closed evaluator and four negative/positive contract cases are wired into macOS CI.
- T12 remains incomplete until M5 stage-attributed data identifies one dominant peak and supports a controlled A/B. This record does not claim `NO_SAFE_WIN` because no candidate was measured.


## T13 — Text KV reuse disposition

- T13 is archived as `NO_SAFE_WIN` for the present single-sequence implementation. Build76's historical M5 run observed partial-tail removal failure (`llama_memory_seq_rm` returned false); Build104's exact-prefix checkpoint path depends on two sequences; Build105 disables its persisted preference and current context creation remains `n_seq_max = 1`. Text KV reuse remains OFF.
- The pinned Vision bridge proves a whole-sequence on-device snapshot/restore mechanism exists, but it does not prove arbitrary recurrent tail trim or the planned single-sequence text checkpoint lifecycle. No seq2 workaround or runtime change was introduced.
- Added `tools/certification/kv_reuse_evidence.py` and tests that reject fingerprint mismatch, missing actual reused tokens, Vision boundaries, cancellation/failure, unproven restore/tail trim, and performance or quality gates. A future independent design needs fresh M5 evidence and complete M2 before promotion.

## T16 — SwiftPM resolution evidence pipeline (CI pending)

- `project.yml` now declares and links `apple/swift-numerics` exactly at `1.1.1`; the current release contract checks both the package version and its `Numerics` product dependency, and artifact generation rejects any other resolved version. The CI workflow resolves after XcodeGen, uploads `Package.resolved`, disables automatic re-resolution during the iOS build, and records the full lock SHA256 and normalized pins/revisions in the artifact manifest.
- The chosen Numerics version is source-pinned, but no current-SHA lock artifact exists until macOS CI runs; other transitive pins remain per-artifact evidence rather than a committed lock.

## T14 — Vision cache identity implementation checkpoint

- Added generation-scoped streaming SHA256 identity for image, primary model and Vision assets, with a versioned complete fingerprint. Native and MLX projected embeddings now use the shared `BVCACHE2` payload and validate the expected identity on reads.
- Added Swift runtime fixtures, including three distinct image identities, Python source contracts and a macOS CI step; targeted local T14 contracts pass 7/7. The Windows host does not have Swift/Xcode, so compilation remains unverified until macOS CI.
- M5 distinct-image quality, repeated lifecycle cleanup, cache-hit latency and sampled-memory gates remain NOT RUN. No runtime default, image math, resolution, cache limit or multi-image embedding behavior changed; no performance promotion is claimed.
