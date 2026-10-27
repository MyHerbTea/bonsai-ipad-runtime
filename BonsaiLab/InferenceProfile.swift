import Foundation

final class ProfilingSnapshot: @unchecked Sendable {
    static let shared = ProfilingSnapshot()
    private let lock = NSLock()
    private var value: [String: Any] = ["schema_version": 2, "availability": "no_completed_inference"]
    func publish(_ snapshot: [String: Any]) { lock.lock(); value = snapshot; lock.unlock() }
    func read() -> [String: Any] { lock.lock(); defer { lock.unlock() }; return value }
}

/// Mutated only on the owning inference actor. Native counters require serialized GPU work.
final class InferenceProfile {
    let requestID: String
    private let before: [UInt64]
    private let nativeSerialized: Bool
    private let productionProfile: Bool
    private let collectNative: Bool
    private let start = ProcessInfo.processInfo.systemUptime
    private var prep = 0.0
    private var decode = 0.0
    private var read = 0.0
    private var prefillCalls = 0
    private var tokenCalls = 0
    private var prefillGPU: [String: Any] = ["available": false, "reason": "boundary_not_recorded"]
    var succeeded = false
    init(requestID: String, nativeSerialized: Bool, productionProfile: Bool = false, collectNative: Bool = true) {
        self.requestID = requestID
        self.nativeSerialized = nativeSerialized
        self.productionProfile = productionProfile
        self.collectNative = collectNative
        if nativeSerialized { BonsaiCPUTimeReset() }
        BonsaiProfileEnable(collectNative ? 1 : 0)
        before = (0..<9).map { BonsaiProfileCounter(Int32($0)) }
    }
    func batchPrepared(since began: Double) { prep += (ProcessInfo.processInfo.systemUptime - began) * 1000 }
    func decoded(since began: Double, prefill: Bool) {
        decode += (ProcessInfo.processInfo.systemUptime - began) * 1000
        if prefill { prefillCalls += 1 } else { tokenCalls += 1 }
    }
    // Caller synchronizes before reading completion handlers and records whether
    // the native submitted/terminal counters agree. This snapshot is prefill-only.
    func recordPrefillGPU(drained: Bool) {
        let after = (0..<9).map { BonsaiProfileCounter(Int32($0)) }
        let monotonic = !zip(before, after).contains { $0.1 < $0.0 }
        let count = monotonic ? after[7] - before[7] : 0
        let available = collectNative && nativeSerialized && BonsaiProfileAvailable() && drained && monotonic && count > 0
        prefillGPU = ["available": available, "command_buffers": count,
            "execution_ms": available ? Double(after[6] - before[6]) / 1e6 as Any : NSNull(),
            "ptq1_mv_r4_dispatches": available ? after[0] - before[0] as Any : NSNull(),
            "ptq1_mv_r5_dispatches": available ? after[1] - before[1] as Any : NSNull(),
            "fwht_dispatches": available ? after[2] - before[2] as Any : NSNull(),
            "total_dispatches": available ? after[3] - before[3] as Any : NSNull(),
            "m1_operations": available ? after[4] - before[4] as Any : NSNull(),
            "m_gt1_operations": available ? after[5] - before[5] as Any : NSNull(),
            "scope": "prefill_command_buffer_execution_sum_may_overlap",
            "drained": drained]
    }
    func readResult(since began: Double) { read += (ProcessInfo.processInfo.systemUptime - began) * 1000 }
    func finish(gpuDrained: Bool) {
        let after = (0..<9).map { BonsaiProfileCounter(Int32($0)) }
        let reset = zip(before, after).contains { $0.1 < $0.0 }
        let delta = zip(before, after).map { $0.1 >= $0.0 ? $0.1 - $0.0 : 0 }
        let available = collectNative && BonsaiProfileAvailable() && !reset && nativeSerialized && gpuDrained
        let count: (Int) -> Any = { available ? delta[$0] as Any : NSNull() }
        let gpu: Any = available && delta[7] > 0 ? Double(delta[6]) / 1e6 : NSNull()
        let total = prefillCalls + tokenCalls
        let stats: [String: Any] = ["ptq1_mv_r4_dispatches": count(0), "ptq1_mv_r5_dispatches": count(1),
            "fwht_dispatches": count(2), "total_dispatches": count(3),
            "other_dispatches": available ? delta[3] - min(delta[3], delta[0] + delta[1] + delta[2]) as Any : NSNull(),
            "m1_operations": count(4), "m_gt1_operations": count(5),
            "scope": "request_delta_of_context_counters;matrix_operations_not_tokens"]
        let snapshot: [String: Any] = ["schema_version": 2, "request_id": requestID, "completed": succeeded,
            "prefill_gpu_timing": prefillGPU,
            "cpu_prefill_timing": cpuPrefillTiming(available: available),
            "cpu_ptq1_sampling": productionProfile ? ["available": false, "valid": false, "unavailable": "not_measured_in_production_profile"] : cpuSampling(available: available),
            "timestamp": ISO8601DateFormatter().string(from: Date()), "wall_ms": (ProcessInfo.processInfo.systemUptime - start) * 1000,
            "breakdown": ["batch_prep_ms": prep, "decode_call_ms": decode, "metal_submit_ms": available ? Double(delta[8]) / 1e6 as Any : NSNull(),
                "gpu_wait_ms": NSNull(), "result_read_ms": read],
            "gpu_execution_ms": gpu, "gpu_time_source": available && delta[7] > 0 ? "sum_command_buffer_GPUStartTime_GPUEndTime;may_overlap" : "unavailable",
            "kernel_stats": stats, "thermal_state": ProcessInfo.processInfo.thermalState.rawValue,
            "coverage": ["prefill_decode_call_fraction": total > 0 ? Double(prefillCalls)/Double(total) : 0,
                         "decode_call_fraction": total > 0 ? Double(tokenCalls)/Double(total) : 0,
                         "source": "llama_decode_invocations_not_time_fraction"],
            "availability": available ? "native_counters_available" : "native_profile_ABI_missing_reset_or_concurrent_scope_not_excluded",
            "unavailable": ["gpu_wait_ms": "no_separate_public_wait_boundary"],
            "timing_relationship": "decode_call_ms includes backend submission and synchronization; do not sum overlapping stages"]
        ProfilingSnapshot.shared.publish(snapshot)
        CrashDiagnostics.shared.updatePerformance(snapshot)
    }
    private func cpuSampling(available: Bool) -> [String: Any] {
        guard available && BonsaiCPUSamplingAvailable() else {
            return ["available": false, "valid": false, "unavailable": "requires_serialized_drained_benchmark_scope"]
        }
        let c = (0..<18).map { BonsaiCPUSamplingCounter(Int32($0)) }
        let ready = available && BonsaiCPUSamplingAvailable()
        let rawU = Double(c[4]), rawD = Double(c[5])
        let correction = Double(c[6]) * Double(c[3])
        let u = max(0, rawU - correction), d = max(0, rawD - correction)
        let overhead = (rawU + rawD) > 0 ? 2 * correction / (rawU + rawD) : 1
        let rate = c[0] > 0 ? Double(c[1]) / Double(c[0]) : 0
        let expected = c[7] > 0 ? 1 / Double(c[7]) : 0
        let valid = ready && c[9] == 0 && c[1] >= 1000 && c[11] >= 50 && overhead <= 0.20 && expected > 0 && abs(rate / expected - 1) <= 0.20 && u + d > 0
        return ["available": ready, "valid": valid, "counting_on": c[8] == 1,
                "sampling_enabled": c[7] > 0, "reuse_rows": c[13], "reuse_unpacked_blocks": c[14], "reuse_logical_dot_calls": c[15],
                "pair_chunks": c[16], "pair_rows": c[17], "sample_period": c[7], "observed_sample_rate": rate, "seen_calls": c[0], "sampled_calls": c[1],
                "seen_blocks": c[2], "sampled_blocks": c[3], "timer_interval_overhead_ns": c[6],
                "unpack_raw_ns": c[4], "dotprod_raw_ns": c[5], "timer_correction_fraction": overhead,
                "worker_slots": c[10], "min_worker_samples": c[11], "overflow": c[9], "graph_worker_flushes": c[12],
                "unpack_sampled_ratio": valid ? u / (u + d) as Any : NSNull(),
                "dotprod_sampled_ratio": valid ? d / (u + d) as Any : NSNull(),
                "unpack_raw_ratio": rawU + rawD > 0 ? rawU / (rawU + rawD) as Any : NSNull(),
                "scope": "baseline_prefill_sampled_worker_intervals;not_wall_fraction;compiler_perturbation_not_excluded",
                "validity_rule": "samples>=1000;min_worker>=50;rate_within_20pct;timer_correction<=20pct;no_overflow"]
    }
    private func cpuPrefillTiming(available: Bool) -> [String: Any] {
        let ready = available && BonsaiCPUTimeAvailable()
        let ns = (0..<4).map { BonsaiCPUTimeCounter(Int32($0)) }
        let nodes = (4..<8).map { BonsaiCPUTimeCounter(Int32($0)) }
        return ["available": ready, "scope": "prefill_only_cpu_node_group_leader_wall_through_existing_barrier;includes_worker_wait;fused_by_leading_node",
                "coverage": "ggml_cpu_executor_only;excludes_BLAS_scheduler_backend_copies",
                "sum_worker_times": false, "not_exclusive_critical_path": true,
                "ptq1_matmul_ms": ready ? Double(ns[0])/1e6 as Any : NSNull(),
                "fwht_ms": ready ? Double(ns[1])/1e6 as Any : NSNull(),
                "other_matmul_ms": ready ? Double(ns[2])/1e6 as Any : NSNull(),
                "other_cpu_ms": ready ? Double(ns[3])/1e6 as Any : NSNull(),
                "total_cpu_node_wall_ms": ready ? Double(ns.reduce(0,+))/1e6 as Any : NSNull(),
                "node_counts": ready ? nodes as Any : NSNull()]
    }
}
