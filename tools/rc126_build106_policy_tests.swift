import Foundation

@main
struct Build106M5GovernorPolicyTests {
    static func main() {
        func verify(_ arm: Build94BatchExperiment.Arm, _ expected: M5RuntimeProfile) {
            let d = M5RuntimeGovernor.decide(arm: arm, context: 32_768)
            precondition(d.profile == expected)
            precondition(d.profile.batch == d.profile.ubatch)
        }
        verify(.safe4, .safe4)
        verify(.baseline8, .balanced8)
        verify(.candidate16, .performance16)
        verify(.candidate24, .turbo24)
        verify(.candidate32, .legacy32)
        precondition(M5RuntimeGovernor.decide(arm: .candidate16, context: 4096).reason == "non_32k_existing_policy")
        let suite = "Build106GovernorUnit." + UUID().uuidString
        let defaults = UserDefaults(suiteName: suite)!
        // Cleanup after assertions; avoid top-level defer in standalone Swift compilation.
        let d = M5RuntimeGovernor.decide(arm: .baseline8, context: 32_768)
        M5RuntimeGovernor.persist(d, source: "unit_test", defaults: defaults)
        let state = M5RuntimeGovernor.snapshot(context: 32_768, activeBatch: 8, activeUBatch: 8, defaults: defaults)
        precondition(state["profile"] as? String == "BALANCED8")
        precondition(state["mid_request_batch_switch_supported"] as? Bool == false)
        precondition(state["sequence_max"] as? Int == 1)
        defaults.removePersistentDomain(forName: suite)
        print("PASS Build106 M5 Governor policy mapping and diagnostics")
    }
}
