import Foundation

/// Resolves the process-global Metal Tensor setting before the first backend init.
/// Only an explicit CANDIDATE launch arm may override the safe caller configuration.
enum Build113MetalTensorPolicy {
    static func effectiveDisabled(requestedDisabled: Bool, launchArmRawValue: String?) -> Bool {
        guard launchArmRawValue == "CANDIDATE" else { return requestedDisabled }
        return false
    }

    /// A backend registry is process-global; changing the effective mode in-process requires restart.
    static func requiresRestart(latchedDisabled: Bool?, effectiveDisabled: Bool) -> Bool {
        guard let latchedDisabled else { return false }
        return latchedDisabled != effectiveDisabled
    }
}
