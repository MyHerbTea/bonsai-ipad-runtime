import Foundation

@main struct PrefillPolicyTests {
    static func main() {
        let quick=BenchmarkSessionMode.quickPrefill
        precondition(quick.initial.batch==8 && BenchmarkSessionMode.full.initial.batch==16)
        let legacy=BenchmarkSessionMode.full.initial.json
        precondition(!BenchmarkSessionMode.quarantined(quick.initial,markers:[legacy]))
        precondition(BenchmarkSessionMode.quarantined(BenchmarkSessionMode.full.initial,markers:[legacy]))
        precondition(quick.markerKey != BenchmarkSessionMode.full.markerKey)
        for flag in [0,4,8,16] {
            let config=BenchmarkConfiguration(context:16384,batch:8,kv:"Q4_0",flags:flag)
            precondition(config.isValid(capabilities:31) && quick.permits(config))
        }
        for flag in [24,25,31,32,-1] {
            precondition(!BenchmarkConfiguration(context:16384,batch:8,kv:"Q4_0",flags:flag).isValid(capabilities:31))
        }
        precondition(!quick.permits(BenchmarkSessionMode.full.initial))
        precondition(!BenchmarkConfiguration(context:16384,batch:8,kv:"Q4_0",flags:16).isValid(capabilities:15))
        precondition(BenchmarkCandidateRegistry.flags(named:"PTQ1_CPU_NEON")==16)
        let reuse=BenchmarkConfiguration(context:16384,batch:8,kv:"Q4_0",flags:32)
        precondition(reuse.isValid(capabilities:63) && quick.permits(reuse))
        precondition(!BenchmarkConfiguration(context:16384,batch:16,kv:"Q4_0",flags:32).isValid(capabilities:63))
        precondition(!BenchmarkConfiguration(context:16384,batch:8,kv:"Q4_0",flags:33).isValid(capabilities:63))
        precondition(BenchmarkCandidateRegistry.flags(named:"PTQ1_CPU_UNPACK_REUSE")==32)
        print("Build118 CPU flags, B8 Quick scope and quarantine identity policies: PASS")
    }
}
