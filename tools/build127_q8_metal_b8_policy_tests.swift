import Foundation

@main struct Build127Q8MetalB8PolicyTests {
    static func main() {
        let mode = BenchmarkSessionMode.q8Baseline
        let baseline = BenchmarkConfiguration(context: 16384, batch: 8, kv: "Q8_0", flags: 64)
        let candidate = BenchmarkConfiguration(context: 16384, batch: 8, kv: "Q8_0", flags: 320)
        let capabilities = 64 | 256
        precondition(candidate.isValid(capabilities: capabilities))
        precondition(mode.permits(baseline) && mode.permits(candidate))
        precondition(!BenchmarkSessionMode.full.permits(candidate))
        precondition(!BenchmarkSessionMode.quickPrefill.permits(candidate))
        precondition(!BenchmarkConfiguration(context: 8192, batch: 8, kv: "Q8_0", flags: 320).isValid(capabilities: capabilities))
        precondition(!BenchmarkConfiguration(context: 16384, batch: 16, kv: "Q8_0", flags: 320).isValid(capabilities: capabilities))
        precondition(!BenchmarkConfiguration(context: 16384, batch: 8, kv: "Q4_0", flags: 320).isValid(capabilities: capabilities))
        precondition(!BenchmarkConfiguration(context: 16384, batch: 8, kv: "Q8_0", flags: 320).isValid(capabilities: 64))
        precondition(!BenchmarkConfiguration(context: 16384, batch: 8, kv: "Q8_0", flags: 321).isValid(capabilities: 511))
        precondition(BenchmarkCandidateRegistry.flags(named: "PTQ1_METAL_B8") == 320)
        let q8 = BenchmarkCandidateRegistry.json(capabilities: capabilities)
            .first { $0["id"] as? String == "PTQ1_METAL_B8" }
        precondition(q8?["available"] as? Bool == true)
        print("Build127 Q8-only 16K/B8/flags320 policy: PASS")
    }
}