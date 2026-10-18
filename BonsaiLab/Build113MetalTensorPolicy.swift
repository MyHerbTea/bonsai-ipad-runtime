import Foundation

/// Resolves the process-global Metal Tensor setting before the first backend init.
/// CANDIDATE may enable TensorOps only for a model/shape explicitly admitted by the caller;
/// native dispatch retains independent actual GGML type and matrix-shape gates.
enum Build113MetalTensorPolicy {
    static func effectiveDisabled(
        requestedDisabled: Bool,
        launchArmRawValue: String?,
        allowMetalTensorCandidate: Bool = false
    ) -> Bool {
        if launchArmRawValue == "CANDIDATE" {
            return !allowMetalTensorCandidate
        }
        return requestedDisabled
    }

    /// A backend registry is process-global; changing the effective mode in-process requires restart.
    static func requiresRestart(latchedDisabled: Bool?, effectiveDisabled: Bool) -> Bool {
        guard let latchedDisabled else { return false }
        return latchedDisabled != effectiveDisabled
    }
}
