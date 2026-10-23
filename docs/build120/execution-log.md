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
