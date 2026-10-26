import Foundation
@main struct KVPolicyTests {
    static func main() throws {
        for context in [256,4096,4097,8192,16383,16384,32768,65536] {
            precondition(KVCachePolicy.q8.resolved(context: context) == .q8)
        }
        precondition(KVCachePolicy.legacy.resolved(context:4096) == .f16)
        precondition(KVCachePolicy.legacy.resolved(context:8192) == .q8)
        precondition(KVCachePolicy.legacy.resolved(context:16384) == .q4)
        precondition(KVCachePolicy.legacy.resolved(context:32768) == .q4)
        precondition(BenchmarkSessionMode.q8Baseline.initial == BenchmarkConfiguration(context:16384,batch:8,kv:"Q8_0",flags:64))
        precondition(BenchmarkSessionMode.q8Baseline.permits(.init(context:16384,batch:8,kv:"Q8_0",flags:64)))
        for bad in [BenchmarkConfiguration(context:16384,batch:8,kv:"Q4_0",flags:64),
                    .init(context:32768,batch:8,kv:"Q8_0",flags:64),
                    .init(context:16384,batch:16,kv:"Q8_0",flags:64),
                    .init(context:16384,batch:8,kv:"Q8_0",flags:128)] {
            precondition(!BenchmarkSessionMode.q8Baseline.permits(bad))
        }
        precondition(BenchmarkSessionMode.q8Baseline.operationTimeout(stage: "capacity") == 14400)
        precondition(BenchmarkSessionMode.q8Baseline.operationTimeout(stage: "formal") == 1800)
        precondition(BenchmarkSessionMode.full.operationTimeout(stage: "capacity") == 1800)
        precondition(BenchmarkSessionMode.quickPrefill.operationTimeout(stage: "capacity") == 1800)
        print("Build126 fixed KV boundaries, unchanged legacy and restricted Q8 baseline: PASS")
    }
}
