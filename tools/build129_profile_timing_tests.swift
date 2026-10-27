import Foundation

var fakeProfileCounts = [UInt64](repeating: 0, count: 9)
var fakeProfileAvailable = true
func BonsaiCPUTimeReset() {}
func BonsaiProfileEnable(_ enabled: Int32) {}
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
        fakeProfileCounts[6] = 2_000_000; fakeProfileCounts[7] = 1
        profile.recordPrefillGPU(drained: true)
        fakeProfileCounts[6] = 5_000_000; fakeProfileCounts[7] = 2
        profile.succeeded = true; profile.finish(gpuDrained: true)
        let result = ProfilingSnapshot.shared.read()
        let prefill = result["prefill_gpu_timing"] as! [String: Any]
        precondition(prefill["available"] as? Bool == true)
        precondition(prefill["execution_ms"] as? Double == 2.0, "decode GPU time must not enter prefill")
        precondition(result["gpu_execution_ms"] as? Double == 5.0)
        let sampling = result["cpu_ptq1_sampling"] as! [String: Any]
        precondition(sampling["available"] as? Bool == false, "stale sampling must remain unavailable")
        fakeProfileCounts = [UInt64](repeating: 0, count: 9)
        let incomplete = InferenceProfile(requestID: "r2", nativeSerialized: true, productionProfile: true)
        fakeProfileCounts[6] = 1_000_000; fakeProfileCounts[7] = 1
        incomplete.recordPrefillGPU(drained: false); incomplete.finish(gpuDrained: false)
        let missing = ProfilingSnapshot.shared.read()["prefill_gpu_timing"] as! [String: Any]
        precondition(missing["available"] as? Bool == false, "undrained data must fail closed")
        print("Production prefill timing boundary: PASS")
    }
}
