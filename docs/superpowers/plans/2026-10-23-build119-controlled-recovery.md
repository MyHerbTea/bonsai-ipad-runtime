# Build119 Controlled Manual Interruption Recovery

User confirmed they manually force-quit Build118 after perceiving a freeze. The run was still in baseline warmup: recorded prompt completion after94s and output through80 tokens. All candidate measurements remain NOT_RUN. This does not prove the UI was responsive or resolve the older B16 failure.

**Goal:** make long native work observable, allow explicit audited recovery of the acknowledged manual Quick interruption, and stop reporting a restarted process as RESTORED.
**Architecture:** keep Build118 CPU math unchanged. Add bounded progress counters to the existing session lock and15s SSE progress events. Add a separate explicit acknowledge_interruption operation which acquires a lease, checks exact marker/source/process identity, saves a durable nonfatal audit snapshot, then removes only the Quick marker. Legacy B16 marker is never touched. No auto-ack, no inference replay.
**Execution:** user already requested direct implementation and concentrated validation; no new per-task approval. Continue in the selected iPad27B workspace. This document is the small design and implementation plan.

- [ ] T1: Swift progress and audited acknowledgement: BenchmarkCandidateRegistry.swift, BenchmarkSessionManager.swift, BonsaiEngine.swift, LocalOpenAIServer.swift. Test token bounds, wrong reason/source/process/marker rejection, failed snapshot leaving marker, and exclusive lease.
- [ ] T2: Python recovery command and restoration proof: acknowledge_quick_interruption.py, prefill_compare.py, ptq1_oneclick.py. Client requires explicit --reason manual_forced_exit; source/kit and old marker retained; process change cannot be RESTORED; progress events cannot be first-content latency.
- [ ] T3: Build119 identity/CI/package; concentrated affected tests, review, build and artifact verification. New IPA installation is required because Build118 has no recovery endpoint. No candidates retested until that dependency is met.

Review focus: audit-before-delete persistence, stale-marker compare-and-clear, manual reason not fabricated as native root cause, heartbeat lifecycle cleanup, and zero impact on numerical output/benchmarked native math. Progress overhead is shared by all candidates and still requires device measurement.

## Resumption checkpoint

T1/T2 implementation and local Python validations complete; real Swift store regression added and queued for Apple CI. T3 local affected validation: 47 Python tests plus codec parity pass; final independent review has no critical/important findings. Markdown audit presentation minor deferred; structured JSON is authoritative. Build/artifact/device steps remain pending.
