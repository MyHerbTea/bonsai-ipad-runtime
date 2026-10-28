import Foundation

/// Resolves the process-global Metal Tensor setting before the first backend init.
/// CANDIDATE may enable TensorOps only for an explicitly eligible model/shape.
/// PQ2_0 uses the existing NAX gate; PTQ1_0 requires its separate 16K/B16 gate.
enum Build113MetalTensorPolicy {
    static func effectiveDisabled(
        requestedDisabled: Bool,
        launchArmRawValue: String?,
        allowNAXCandidate: Bool = false
    ) -> Bool {
        if launchArmRawValue == "CANDIDATE" {
            return !allowNAXCandidate
        }
        return requestedDisabled
    }

    static func m8Eligible(enabled: Bool, isPTQ1: Bool, context: Int, batch: Int, ubatch: Int) -> Bool {
        enabled && isPTQ1 && context == 16_384 && batch == 8 && ubatch == 8
    }

    /// A backend registry is process-global; changing the effective mode in-process requires restart.
    static func requiresRestart(latchedDisabled: Bool?, effectiveDisabled: Bool) -> Bool {
        guard let latchedDisabled else { return false }
        return latchedDisabled != effectiveDisabled
    }
}
