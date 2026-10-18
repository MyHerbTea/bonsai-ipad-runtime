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
        precondition(Build113MetalTensorPolicy.effectiveDisabled(requestedDisabled: true, launchArmRawValue: "CANDIDATE"),
                     "candidate without explicit model/shape eligibility must stay disabled")
        precondition(!Build113MetalTensorPolicy.effectiveDisabled(requestedDisabled: true, launchArmRawValue: "CANDIDATE", allowMetalTensorCandidate: true),
                     "explicitly eligible model-specific candidate may enable TensorOps")
        precondition(Build113MetalTensorPolicy.effectiveDisabled(requestedDisabled: false, launchArmRawValue: "CANDIDATE", allowMetalTensorCandidate: false),
                     "PTQ1_0 without explicit 16K/B16 A/B eligibility remains Tensor-disabled")
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
        precondition(Build113MetalTensorPolicy.shouldTraceNativeContext(contextLength: 16_384, modelFileName: "Ternary-Bonsai-2-27B-PTQ1_0.gguf", batch: 16, ubatch: 16),
                     "PTQ1 16K/B16 must enable native context tracing before context creation")
        precondition(!Build113MetalTensorPolicy.shouldTraceNativeContext(contextLength: 16_384, modelFileName: "Ternary-Bonsai-2-27B-PTQ1_0.gguf", batch: 8, ubatch: 8),
                     "ordinary PTQ1 16K/B8 must not enable the experimental native trace")
        precondition(!Build113MetalTensorPolicy.shouldTraceNativeContext(contextLength: 16_384, modelFileName: "Ternary-Bonsai-2-27B-PQ2_0.gguf", batch: 16, ubatch: 16),
                     "PTQ1 trace extension must not alter PQ2 behavior")
        precondition(Build113MetalTensorPolicy.shouldTraceNativeContext(contextLength: 32_768, modelFileName: "any.gguf", batch: 8, ubatch: 8),
                     "existing >=32K native context tracing must remain enabled")
        print("PASS Build113 Metal Tensor policy: candidate gate, PTQ1 16K/B16 crash trace, safe fallback, restart latch")
    }
}
