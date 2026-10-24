# Build121: bounded CPU prefill timing only

User authorized scheme A, then B if only aggregate profiling exists. A completed512/1, prefill87.270s, only aggregate timings. No retry or ABBA. Task started2026-10-24T09:37:50Z;30-minute total budget ends10:07:50Z. Report actual progress at the deadline; never claim pending deployment complete.

Source base3d69530c27033c555e6d8a40acc3fae50ae4893a; existing checkout only. Scope: timestamps/export only; no numeric kernel, scheduling/barrier or production default changes. CPU function names in the proposed sketch do not exist. Instrument real CPU graph node groups covering original PTQ1 MUL_MAT, Hadamard/FWHT hint, other matrix and other CPU operations. Avoid timestamps on3.51e8 individual vec_dot calls.

Use one leader's elapsed interval through the EXISTING node barrier, not a sum across6 workers. Include the final-node existing terminal barrier. No extra barrier. Clearly label inclusive node-group/worker-wait wall time, not exclusive CPU utilization or guaranteed critical-path saving. Fused groups classified by leading node. Timers enabled only during benchmark prefill evaluation; disabled during generation and ordinary requests. Existing per-dot counters remain unchanged so this is not an optimization candidate.

- [ ] Write/run failing patch/clock tests, then implement opt-in C timing header and pinned-source patch.
- [ ] Add native ABI bridge and cpu_prefill timing fields to existing profiling JSON; no new endpoint/UI.
- [ ] Review once, run affected tests, build121 once in existing Apple CI and verify artifact identity. Deployment needs the user's existing signing method.
- [ ] One baseline512/1 after install; verify phase boundaries, same-source counters, elapsed denominator and restoration; classify only if timing semantics support it. Do not implement flag17 from counts or ambiguous inclusive timing.

Review: no Critical/Important implementation defects; original PTQ1/FWHT, final nodes, aborts/fusion and prefill gating checked. Limitation: only ggml-cpu executor intervals are measured; BLAS/scheduler/copies are not. A small measured percentage cannot prove all CPU<10%. Do not sum worker times or present inclusive intervals as exclusive critical-path savings. The proposed '<10% implies<8% gain' is not a general mathematical bound.

Local: timing patch test RED before implementation; pinned source/barrier/final-node test now passes; actual C/mach clock test skipped on Windows and mandatory in Apple CI.17 affected recovery/identity tests,10 shared client tests and10 documentation tests pass. No numerical candidate or flag17 implemented.
