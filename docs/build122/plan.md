# Build122: sampled PTQ1 costs and counting on/off/on

User approved corrected design and exactly three512/1 requests. Start2026-10-24T12:38:12Z,30-minute target deadline13:08:12Z; stop expanding and report actual stage at limit. Existing checkout/branch only, base3bc4a080580ade14b0ea1519659a61adb009d414. No numerical optimization/flag17.

Implement baseline-only low-rate sampling1/10000 calls, random starting offset per graph/thread, matched unpack/dot block intervals, TLS accumulation merged into per-worker slots before existing terminal barrier. No per-dot shared profiling totals. Preserve original unsampled baseline loop, counter position and arithmetic. Sampled clone retains operation order; report compiler/timing perturbation limits and calibration fraction; ratios are sampled thread intervals, never shares of the old32.47s wall time.

Counting control affects only benchmark atomic RMW counters, common sampler settings across arms. Production flags=-1 unchanged. On/off/on uses one IPA and identical512/1 workload, no warmups or auto-retry. Report actual counts, sampling rate/blocks, calibrated/raw unpack-dot ratios; clock overhead high or sampleinsufficient means attribution unavailable. Counter overhead=(on1+on2)/2-off;absolute drift>5s means unstable and no automatic ABBA.

- [ ] Native patch/TLS sampler/control plus tests: exact sampled-clone parity, on/off counts, rate/reset, disabled phase, thread flush, clock calibration.
- [ ] Existing API run input counting on/off, bridge and profiling export; no new route/UI. Original helper math unchanged.
- [ ] One focused review, affected tests, same-source AppleCI/IPA identity verification, user cover-install, three requests and restoration check.
- [ ] Separate sampling ratios, whole-prefill and CPU-matrix wall deltas, residual/wait scope. No fabricated exhaustive pie chart or production speedup from disabling benchmark-only counters.
