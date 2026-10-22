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
    private let start = ProcessInfo.processInfo.systemUptime
    private var prep = 0.0
    private var decode = 0.0
    private var read = 0.0
    private var prefillCalls = 0
    private var tokenCalls = 0
    var succeeded = false
    init(requestID: String, nativeSerialized: Bool) {
        self.requestID = requestID
        self.nativeSerialized = nativeSerialized
        BonsaiProfileEnable(1)
        before = (0..<9).map { BonsaiProfileCounter(Int32($0)) }
    }
    func batchPrepared(since began: Double) { prep += (ProcessInfo.processInfo.systemUptime - began) * 1000 }
    func decoded(since began: Double, prefill: Bool) {
        decode += (ProcessInfo.processInfo.systemUptime - began) * 1000
        if prefill { prefillCalls += 1 } else { tokenCalls += 1 }
    }
    func readResult(since began: Double) { read += (ProcessInfo.processInfo.systemUptime - began) * 1000 }
    func finish(gpuDrained: Bool) {
        let after = (0..<9).map { BonsaiProfileCounter(Int32($0)) }
        let reset = zip(before, after).contains { $0.1 < $0.0 }
        let delta = zip(before, after).map { $0.1 >= $0.0 ? $0.1 - $0.0 : 0 }
        let available = BonsaiProfileAvailable() && !reset && nativeSerialized && gpuDrained
        let count: (Int) -> Any = { available ? delta[$0] as Any : NSNull() }
        let gpu: Any = available && delta[7] > 0 ? Double(delta[6]) / 1e6 : NSNull()
        let total = prefillCalls + tokenCalls
        let stats: [String: Any] = ["ptq1_mv_r4_dispatches": count(0), "ptq1_mv_r5_dispatches": count(1),
            "fwht_dispatches": count(2), "total_dispatches": count(3),
            "other_dispatches": available ? delta[3] - min(delta[3], delta[0] + delta[1] + delta[2]) as Any : NSNull(),
            "m1_operations": count(4), "m_gt1_operations": count(5),
            "scope": "request_delta_of_context_counters;matrix_operations_not_tokens"]
        let snapshot: [String: Any] = ["schema_version": 2, "request_id": requestID, "completed": succeeded,
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
}
