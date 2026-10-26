import Foundation
/// Main-model PTQ1_0 weights are independent of context-allocation policy.
enum KVCachePolicy: String, Sendable {
    case legacy = "legacy"
    case f16 = "F16"
    case q8 = "Q8_0"
    case q4 = "Q4_0"
    func resolved(context: Int) -> KVCachePolicy {
        guard self == .legacy else { return self }
        return context >= 16_384 ? .q4 : (context > 4096 ? .q8 : .f16)
    }
}
