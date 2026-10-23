# Build120 API Cancellation Recovery Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, with one fresh whole-change review. The user accepted direct Build120 implementation; do not ask for another execution-method approval.

**Goal:** explicitly audit recovery of the operator-cancelled Quick interruption and export old/new nonfatal audit snapshots without inference.

**Architecture:** retain the exclusive acknowledgement operation; add a separately validated operator cancellation evidence summary. Save and independently read the audit before exact compare-and-clear of the Quick marker. Add a Foundation-only snapshot HTTP handler reused by CrashDiagnostics behind the existing server authorization guard.

**Tech Stack:** Swift/Foundation, existing Python unittest/portable testkit, GitHub macOS CI and unsigned iOS IPA packaging.

**Spec:** `docs/superpowers/specs/2026-10-23-build120-recovery-design.md` (user accepted option B of the original review on 2026-10-23).

## Global Constraints

- Work in `D:/codexSpace/iPad27B/bonsai-ipad-runtime`; no new worktree. Base aeed5ef8556b28273e4389534ed2581e504fa7d9.
- No device POST/inference, benchmark replay, performance promotion, CPU math changes, or old evidence/package edits.
- Keep B16 quarantine; reject missing/contradictory evidence and preserve Quick marker on save/read/compare failure.
- Historical origin source/process are distinct from the current accepting source/process after an IPA upgrade.
- Explicit reason `operator_confirmed_api_cancel`; provenance `operator_supplied_files_not_server_receipt`.

## Review Focus

- JSON booleans/numbers and malformed nested dictionaries must not satisfy cancellation proof accidentally (T1/T2 negative tests).
- An old marker restored across IPA installation must bind to historical files, not be mistaken for a new cancellation (T1/T2 identity tests).
- Audit privacy cleanup/depth limits must preserve all fields used in readback comparison (T1 real store tests).
- HTTP method/path/prefix confusion must not make audit snapshots deletable or bypass existing authentication (T1 router tests and integration check).
- Lost POST response/readback failure must retain local attempt evidence and must not trigger an automatic second acknowledgement (T2 fault tests).

### Task 1: Swift recovery and snapshot export

**Files:** BenchmarkInterruptionRecovery.swift, new DiagnosticSnapshotAPI.swift, CrashDiagnostics.swift, DiagnosticStore.swift, BonsaiEngine.swift, LocalOpenAIServer.swift; tools/build120_recovery_tests.swift, tools/build120_snapshot_tests.swift; retain Build119 regressions.

**Interfaces:** `acknowledge(..., saveAudit: (String,[String:Any]) throws -> String, readAudit: (String) throws -> [String:Any]?) throws -> String`; evidence shape shared with T2. `DiagnosticSnapshotAPI.handle(store:method:path:) -> (Int,String,Data)` is called inside CrashDiagnostics's serial queue.

- [ ] Write Swift tests for API cancellation acceptance and rejection, real store readback failure/mismatch, marker race, B16 preservation, exact JSON/Markdown GET and method/ID/path rejection.
- [ ] Run new tests against base on macOS CI to observe expected missing behavior (Windows lacks Swift); no native build after failure.
- [ ] Implement bounded evidence validation, server runtime checks, audit save/read/compare/clear, dedicated read-only snapshot routing, Markdown audit section.
- [ ] Run Swift tests on Apple CI alongside existing Build119/session/diagnostic tests; all must pass before packaging.

### Task 2: Evidence-bound explicit client and fault tests

**Files:** tools/PTQ1_ONECLICK/acknowledge_quick_interruption.py, new tools/PTQ1_ONECLICK/cancellation_evidence.py, tools/tests/test_build120_recovery.py, tools/PTQ1_ONECLICK/PREFILL_COMPARE.md.

**Interfaces:** `build_cancel_evidence(directory, marker) -> dict` validates before/cancel/after/report and returns compact summary with hashes. `acknowledge(client, identity, reason, output, evidence_directory=None) -> dict` persists pending attempt before exactly one POST; exports new audit and verifies current source/process, marker removal and B16 preservation. Original manual reason remains available.

- [ ] Write/run Python tests RED for real original evidence validation, contradiction/missing fields, cross-version current/origin distinction, exclusive output creation, lost POST response, failed export, and no inference/retry.
- [ ] Implement summary construction, allowlisted server-compatible fields, staged local evidence, explicit CLI reason/evidence requirements, JSON export/readback verification.
- [ ] Run affected client/recovery/compare/packaging tests GREEN; document recovery-only invocation and installation prerequisite.

### Task 3: Identity, review, CI and deliverable

**Files:** project.yml, .github/workflows/build-ptq1-tournament.yml, delivery identity test, docs/build120/execution-log.md, docs/INDEX.md, docs/document-authority.json.

- [ ] Set Build120 identity consistently; use `codex/build120-api-cancel-recovery` in this same checkout and add new Swift/Python tests to existing CI.
- [ ] Run affected local tests, codec parity and diff checks. Record actual scope; do not claim historical full-suite pass.
- [ ] Obtain one fresh whole-change review, fix material findings with regression tests, then commit and push candidate branch only (no main merge).
- [ ] Wait for exact-source CI, inspect test/build and artifact identity, download new artifacts, verify IPA/source/manifest/hash and UUID/symbol linkage, package in new Build120 delivery paths.
- [ ] Deliver new package and installation/recovery instructions. Device confirmation and all performance measurements remain NOT_RUN pending installation.
