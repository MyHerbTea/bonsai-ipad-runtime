import Foundation

var fakeProfileCounts = [UInt64](repeating: 0, count: 9)
var fakeProfileAvailable = true
var fakeProfileEnabled: Int32 = -1
func BonsaiCPUTimeReset() {}
func BonsaiProfileEnable(_ enabled: Int32) { fakeProfileEnabled = enabled }
func BonsaiProfileCounter(_ index: Int32) -> UInt64 { fakeProfileCounts[Int(index)] }
func BonsaiProfileAvailable() -> Bool { fakeProfileAvailable }
func BonsaiCPUSamplingAvailable() -> Bool { false }
func BonsaiCPUSamplingCounter(_ index: Int32) -> UInt64 { 0 }
func BonsaiCPUTimeAvailable() -> Bool { true }
func BonsaiCPUTimeCounter(_ index: Int32) -> UInt64 { 0 }
final class CrashDiagnostics {
    static let shared = CrashDiagnostics()
    func updatePerformance(_ value: [String: Any]) {}
}

@main struct ProductionProfileTimingTests {
    static func main() {
        fakeProfileCounts = [UInt64](repeating: 0, count: 9)
        let profile = InferenceProfile(requestID: "r1", nativeSerialized: true, productionProfile: true)
        fakeProfileCounts[0] = 3; fakeProfileCounts[3] = 5
        fakeProfileCounts[6] = 2_000_000; fakeProfileCounts[7] = 1
        profile.recordPrefillGPU(drained: true)
        fakeProfileCounts[0] = 7; fakeProfileCounts[3] = 10
        fakeProfileCounts[6] = 5_000_000; fakeProfileCounts[7] = 2
        profile.succeeded = true; profile.finish(gpuDrained: true)
        let result = ProfilingSnapshot.shared.read()
        let prefill = result["prefill_gpu_timing"] as! [String: Any]
        precondition(prefill["available"] as? Bool == true)
        precondition(prefill["execution_ms"] as? Double == 2.0, "decode GPU time must not enter prefill")
        precondition(result["gpu_execution_ms"] as? Double == 5.0)
        precondition(prefill["ptq1_mv_r4_dispatches"] as? UInt64 == 3, "decode dispatch must not enter prefill")
        let sampling = result["cpu_ptq1_sampling"] as! [String: Any]
        precondition(sampling["available"] as? Bool == false, "stale sampling must remain unavailable")
        fakeProfileCounts = [UInt64](repeating: 0, count: 9)
        let incomplete = InferenceProfile(requestID: "r2", nativeSerialized: true, productionProfile: true)
        fakeProfileCounts[6] = 1_000_000; fakeProfileCounts[7] = 1
        incomplete.recordPrefillGPU(drained: false); incomplete.finish(gpuDrained: false)
        let missing = ProfilingSnapshot.shared.read()["prefill_gpu_timing"] as! [String: Any]
        precondition(missing["available"] as? Bool == false, "undrained data must fail closed")
        fakeProfileCounts = [UInt64](repeating: 0, count: 9)
        let control = InferenceProfile(requestID: "r3", nativeSerialized: true, productionProfile: true, collectNative: false)
        precondition(fakeProfileEnabled == 0, "control must disable native profiling")
        fakeProfileCounts[6] = 1_000_000; fakeProfileCounts[7] = 1
        control.recordPrefillGPU(drained: true); control.finish(gpuDrained: true)
        let controlResult = ProfilingSnapshot.shared.read()
        let controlGPU = controlResult["prefill_gpu_timing"] as! [String: Any]
        let controlCPU = controlResult["cpu_prefill_timing"] as! [String: Any]
        precondition(controlGPU["available"] as? Bool == false, "control must not claim GPU counters")
        precondition(controlCPU["available"] as? Bool == false, "control must not claim CPU counters")
        print("Production prefill timing boundary: PASS")
    }
}
