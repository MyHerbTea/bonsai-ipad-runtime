import Foundation

@main
struct Build113MetalTensorPolicyTests {
    static func main() {
        // Default API cold start and model load preserve the safe config.
        let cold = Build113MetalTensorPolicy.effectiveDisabled(requestedDisabled: true, launchArmRawValue: nil)
        let load = Build113MetalTensorPolicy.effectiveDisabled(requestedDisabled: true, launchArmRawValue: "BASELINE")
        precondition(cold && load && cold == load, "default API cold start and model load must agree")
        precondition(Build113MetalTensorPolicy.effectiveDisabled(requestedDisabled: true, launchArmRawValue: nil),
                     "ordinary API must not be promoted into candidate mode")
        precondition(!Build113MetalTensorPolicy.effectiveDisabled(requestedDisabled: false, launchArmRawValue: nil),
                     "caller config must be preserved outside candidate mode")
        precondition(!Build113MetalTensorPolicy.effectiveDisabled(requestedDisabled: true, launchArmRawValue: "CANDIDATE"),
                     "explicit CANDIDATE must enable TensorOps")
        precondition(Build113MetalTensorPolicy.effectiveDisabled(requestedDisabled: true, launchArmRawValue: "candidate"),
                     "invalid arm strings must fail safe")
        precondition(Build113MetalTensorPolicy.effectiveDisabled(requestedDisabled: true, launchArmRawValue: "UNKNOWN"),
                     "unknown arm strings must fail safe")
        precondition(Build113MetalTensorPolicy.requiresRestart(latchedDisabled: true, effectiveDisabled: false),
                     "disabled-to-enabled switch must require restart")
        precondition(Build113MetalTensorPolicy.requiresRestart(latchedDisabled: false, effectiveDisabled: true),
                     "enabled-to-disabled switch must require restart")
        precondition(!Build113MetalTensorPolicy.requiresRestart(latchedDisabled: true, effectiveDisabled: true),
                     "same mode must not require restart")
        precondition(!Build113MetalTensorPolicy.requiresRestart(latchedDisabled: nil, effectiveDisabled: false),
                     "first backend initialization has no previous latch")
        print("PASS Build113 Metal Tensor policy: default API cold start, model load, explicit CANDIDATE, safe fallback, restart latch")
    }
}
