# Build118 CPU PTQ1 candidates and batch8 comparison

User requests implementation of the optimization proposals followed by one concentrated comparison, without further design questions. Work stays in the explicitly selected iPad27B workspace, overriding AGENTS' older directory prescription. Existing checkout is clean; branch codex/build118-prefill-candidates starts at Build117 5e9c055.

Goal: reduce CPU work in PTQ1 dot products without changing weights, quantization, model placement, precision, output policy or production defaults. ARM currently aliases PTQ1 to generic code; a matched Build116 CPU sampling report includes this dot function. This is a hypothesis, not proof of an end-to-end bottleneck or a crash cause.

Implement independent lookup-decode (flag8) and ARM NEON decode/dot (flag16) candidates. Keep original scalar path as baseline, existing batch-reuse flag4 as comparator, and reject simultaneous8+16. Preserve original float scale accumulation order and exact integer dot results. Record real per-request CPU candidate call counts; do not invent GPU timings.

Alternative approaches considered: change GPU placement (changes model load/memory and lacks current bottleneck proof); retune Metal R5 (mostly decode, weak prefill leverage); optimize the confirmed CPU code path (selected as a bounded experiment). No performance winner is presumed.

Add explicit quick_prefill session at B8/16K/Q4 with normal exclusive lease and restoration. Full still defaults to B16. Enforce quarantines server-side before any context mutation; Quick uses a separate pending marker, never overwrites or clears legacy BonsaiBenchmarkInterrupted. Incomplete Quick requests remain quarantined. Do not retry the old B16 fault or change production batch.

Reuse existing Python identity, numerical, telemetry, ABBA and export code in a new prefill_compare entry. Default one Quick ABBA round per flags4/8/16, prompt512/output128, existing warmups. Emit drift, prefill/TTFT/decode, memory, output/logit parity and actual CPU hits in one comparison table; single-round results are exploratory, no promotion. Optional5 rounds confirms a candidate without running configuration tuning. Any unknown request outcome ends this run, does not replay. Preserve reports and fail closed on absent ABI, identity mismatch, active session, quarantine or missing coverage.

Build118 CI applies one additional patch to the same pinned Prism, runs actual portable-C and arm64-NEON arithmetic tests and Swift/Python policy tests, builds one IPA with all switches, and retains matching symbols. Use the same IPA for all comparisons. Keep Build117 and its original ZIPs intact. Device numbers remain NOT_RUN until the new IPA is installed; Windows cannot execute it.

Acceptance: exhaustive all256 encoded byte decode parity, signed Q8 extremes/random blocks and multi-block float parity, actual candidate hit counters/disable, invalid mask rejection, old and Quick quarantine preservation, start failure lease recovery, no replay on uncertain responses, reporting without promotion, same-source IPA/kit/symbol hashes. User asked for concentrated validation after implementation; tests are authored with the contracts and executed together at the end.
