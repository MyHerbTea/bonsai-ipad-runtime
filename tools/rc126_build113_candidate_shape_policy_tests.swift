import Foundation

func expect(_ condition: @autoclosure () -> Bool, _ message: String) {
    guard condition() else {
        fputs("FAIL: \(message)\n", stderr)
        exit(1)
    }
}

@main
enum CandidateShapePolicyTestRunner {
    static func main() {
let suiteName = "BonsaiBuild113CandidateShapeTests.\(UUID().uuidString)"
guard let defaults = UserDefaults(suiteName: suiteName) else {
    fatalError("Could not create isolated defaults suite")
}
defer { defaults.removePersistentDomain(forName: suiteName) }

let appSHA = "test-app-source-sha"
defaults.set("SAFE4", forKey: M5RuntimeGovernor.fallbackKey)
defaults.set("SAFE4", forKey: M5RuntimeGovernor.profileKey)

expect(
    M5RuntimeGovernor.beginCandidateShapeTrialIfPending(
        buildSHA: appSHA, candidate: true, defaults: defaults
    ),
    "new candidate source must get exactly one B16 shape trial"
)
expect(
    defaults.string(forKey: M5RuntimeGovernor.candidateTrialStateKey) == "ATTEMPTING_B16",
    "trial must record its attempted state"
)
expect(
    defaults.string(forKey: M5RuntimeGovernor.fallbackKey) == "SAFE4",
    "starting a candidate trial must not clear historical SAFE4"
)
expect(
    !M5RuntimeGovernor.beginCandidateShapeTrialIfPending(
        buildSHA: appSHA, candidate: true, defaults: defaults
    ),
    "the same failed trial must not auto-repeat on every launch"
)

M5RuntimeGovernor.noteCandidateShapeTrialStartupFailure(
    buildSHA: appSHA, defaults: defaults
)
expect(
    defaults.string(forKey: M5RuntimeGovernor.fallbackKey) == "SAFE4",
    "failed candidate trial must preserve the more conservative SAFE4 fallback"
)
expect(
    defaults.string(forKey: M5RuntimeGovernor.candidateTrialStateKey) == "STARTUP_FAILED",
    "startup failure must be explicit"
)

M5RuntimeGovernor.scheduleCandidateShapeTrial(buildSHA: appSHA, defaults: defaults)
expect(
    M5RuntimeGovernor.beginCandidateShapeTrialIfPending(
        buildSHA: appSHA, candidate: true, defaults: defaults
    ),
    "explicit re-arm must permit a deliberate retry"
)
M5RuntimeGovernor.noteCandidateShapeTrialTextSuccess(
    promptTokens: 199, buildSHA: appSHA, defaults: defaults
)
expect(
    defaults.string(forKey: M5RuntimeGovernor.fallbackKey) == "SAFE4",
    "short Smoke success must not clear fallback"
)
M5RuntimeGovernor.noteCandidateShapeTrialTextSuccess(
    promptTokens: 512, buildSHA: appSHA, defaults: defaults
)
expect(
    defaults.string(forKey: M5RuntimeGovernor.fallbackKey) == nil,
    "successful long prefill may clear the historical fallback"
)
expect(
    defaults.string(forKey: M5RuntimeGovernor.profileKey) == "PERFORMANCE16",
    "successful long prefill must re-arm B16"
)
expect(
    defaults.string(forKey: M5RuntimeGovernor.candidateTrialStateKey) == "LONG_PREFILL_SUCCESS",
    "success must be explicitly recorded"
)
expect(
    defaults.string(forKey: M5RuntimeGovernor.candidateTrialPreviousFallbackKey) == "SAFE4",
    "previous fallback must remain auditable after recovery"
)

let nextSHA = "next-app-source-sha"
expect(
    M5RuntimeGovernor.beginCandidateShapeTrialIfPending(
        buildSHA: nextSHA, candidate: true, defaults: defaults
    ),
    "a different App source identity must receive its own one-shot candidate trial"
)
M5RuntimeGovernor.noteCandidateShapeTrialInferenceFailure(
    buildSHA: nextSHA, defaults: defaults
)
expect(
    defaults.string(forKey: M5RuntimeGovernor.fallbackKey) == "BALANCED8",
    "candidate inference failure without prior fallback must restore B8"
)
expect(
    defaults.string(forKey: M5RuntimeGovernor.candidateTrialStateKey) == "INFERENCE_FAILED",
    "inference failure must be explicit"
)

// Native tracing is scoped to the shape that needs diagnosis.
expect(
    !M5RuntimeGovernor.shouldEnableNativeContextTrace(
        context: 8_192, batch: 8, ubatch: 8
    ),
    "8K/B8 baseline must not enable high-volume native tracing"
)
expect(
    !M5RuntimeGovernor.shouldEnableNativeContextTrace(
        context: 16_384, batch: 8, ubatch: 8
    ),
    "16K/B8 baseline must not enable high-volume native tracing"
)
expect(
    M5RuntimeGovernor.shouldEnableNativeContextTrace(
        context: 16_384, batch: 16, ubatch: 16
    ),
    "16K/B16 shape-only trial must enable native trace before context creation"
)
expect(
    !M5RuntimeGovernor.shouldEnableNativeContextTrace(
        context: 16_384, batch: 16, ubatch: 8
    ),
    "mixed 16K/B16/UBatch8 must not qualify as the isolated shape trial"
)
expect(
    M5RuntimeGovernor.shouldEnableNativeContextTrace(
        context: 32_768, batch: 8, ubatch: 8
    ),
    "the existing >=32K native trace path must remain enabled"
)

let phase2DNextKey = "test.phase2d.next"
let phase2DStateKey = "test.phase2d.state"
let phase2DFailureKey = "test.phase2d.failure"
defaults.set("CANDIDATE16", forKey: phase2DNextKey)
defaults.set("PENDING", forKey: phase2DStateKey)
expect(
    M5RuntimeGovernor.resolvePhase2DShapeTrialArm(
        nextArmKey: phase2DNextKey,
        stateKey: phase2DStateKey,
        failureKey: phase2DFailureKey,
        defaults: defaults
    ) == "CANDIDATE16",
    "an explicitly scheduled one-shot trial must be available on the next process"
)
expect(
    M5RuntimeGovernor.beginPhase2DShapeTrialIfPending(
        nextArmKey: phase2DNextKey,
        stateKey: phase2DStateKey,
        failureKey: phase2DFailureKey,
        defaults: defaults
    ),
    "the pending shape trial must be consumed once"
)
expect(
    defaults.string(forKey: phase2DNextKey) == "BASELINE8",
    "the next process must already be pinned to B8 before native initialization"
)
expect(
    M5RuntimeGovernor.resolvePhase2DShapeTrialArm(
        nextArmKey: phase2DNextKey,
        stateKey: phase2DStateKey,
        failureKey: phase2DFailureKey,
        defaults: defaults
    ) == "BASELINE8",
    "an interrupted candidate must automatically resolve to B8"
)
expect(
    defaults.string(forKey: phase2DStateKey) == "RECOVERED_AFTER_INTERRUPTED_STARTUP",
    "interrupted shape trial recovery must be explicit"
)

defaults.set("CANDIDATE16", forKey: phase2DNextKey)
defaults.set("PENDING", forKey: phase2DStateKey)
expect(
    M5RuntimeGovernor.beginPhase2DShapeTrialIfPending(
        nextArmKey: phase2DNextKey,
        stateKey: phase2DStateKey,
        failureKey: phase2DFailureKey,
        defaults: defaults
    ),
    "a deliberate new trial can be armed after recovery"
)
M5RuntimeGovernor.finishPhase2DShapeTrial(
    state: "COMPLETED_SUCCESS",
    nextArmKey: phase2DNextKey,
    stateKey: phase2DStateKey,
    failureKey: phase2DFailureKey,
    defaults: defaults
)
expect(
    M5RuntimeGovernor.resolvePhase2DShapeTrialArm(
        nextArmKey: phase2DNextKey,
        stateKey: phase2DStateKey,
        failureKey: phase2DFailureKey,
        defaults: defaults
    ) == "BASELINE8",
    "a successful one-shot shape trial must return the next process to B8"
)

print("PASS Build113 candidate B16 lifecycle and 16K native trace policy")
    }
}
