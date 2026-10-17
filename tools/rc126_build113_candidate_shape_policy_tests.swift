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

print("PASS Build113 candidate-only B16 shape trial and fallback lifecycle")
    }
}
