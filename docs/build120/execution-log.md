# Build120 execution ledger

Plan: docs/superpowers/plans/2026-10-23-build120-api-cancel-recovery.md
Base: aeed5ef8556b28273e4389534ed2581e504fa7d9.
User accepted direct minimal Build120 on 2026-10-23. Use existing iPad27B checkout; no device mutation or performance rerun.

Ruling: execute inline without another planning approval — user accepted the concrete review and direct implementation; avoids repeated permission prompts.
Ruling: use Apple CI to execute Swift RED/GREEN because Windows has no Swift toolchain; Python tests run locally. Keep CI RED before native compilation to avoid unnecessary builds.
Pre-flight T1/T2: share the compact cancellation evidence JSON schema and audit dictionary; both validate the same identities, marker and production configuration. Current receiver identity is separate from historical cancellation identity.
Pre-flight T1/T3: Foundation-only snapshot handler must be included in Swift CLI tests as well as automatic Xcode source discovery.

Task 1/2: pending.
Task 3: pending.

## Latest steering: stopped for priority review

User manually interrupted implementation and requested prioritizing crash fixes, proof of effect and bottleneck identification over additional instrumentation. The original direct-execution authorization no longer implies automatic continuation of this infrastructure plan. Local tests/design/identity commit 7dbda9b exists; runtime fixes are not implemented, new Python tests are intentionally RED, and no Build120 is delivered. Push was not confirmed; GitHub Actions API returned no runs for this branch. No device mutation/inference occurred. See D:/codexSpace/iPad27B/BUILD120_REFOCUS_CHECKPOINT.md before resuming.

## 2026-10-24: authorized minimal unblock and flag16 only

User explicitly authorized the short path described in minimal-execution.md. This replaces the broad export plan: no HTTP snapshot export/Markdown changes, no generic monitoring, no CPU math changes. Only truthful API-cancel acknowledgement and a bounded flag16 decision run.

Initial device endpoint refused; user confirmed the App/API had not been opened. No inference or device mutation. Await API availability. New5 Python cancellation tests observed RED (missing workflow/evidence functions), then GREEN. Existing20 focused client/recovery/compare/identity tests pass. Original119 cancellation files validate offline and produce a3069-byte bounded proof, stored outside the source tree. Swift tests require Apple CI; do not claim local Swift RED/GREEN.

Ruling: do not push a separate intentionally failing Apple build — local Python RED establishes the workflow gap, and real Swift storage/validation tests run in the single delivery CI; minimizes build delay and runner consumption. Paused snapshot tests remain in history/source but are not selected by active CI.

Focused independent review: no Critical issues; corrected explicit-null session evidence and flush/fsync-before-POST. Promoted missing quarantine observation ambiguity to a required correctness fix: missing fields cannot substantiate marker/B16 verification. Python regression failures observed before fixes,7/7 after fixes; Swift omitted-session regression awaits Apple execution. Deferred export/Markdown/performance claims remain outside review scope. No outstanding material review finding; no second review requested.
