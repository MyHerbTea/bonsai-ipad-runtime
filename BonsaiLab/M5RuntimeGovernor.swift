import Foundation

/// Small M5 runtime policy for the 32K text path.
/// Build112 deliberately ignores the historical Build93/94 experiment state:
/// B16 is the default, a startup failure falls back to B8, a second startup
/// failure falls back to SAFE4, and a successful B8 text request re-arms B16.
/// Batch is still a context-creation parameter; it never changes mid-request.
enum M5RuntimeProfile: String, CaseIterable {
    case safe4 = "SAFE4"
    case balanced8 = "BALANCED8"
    case performance16 = "PERFORMANCE16"
    case turbo24 = "TURBO24"
    case legacy32 = "LEGACY32"

    var batch: Int {
        switch self {
        case .safe4: return 4
        case .balanced8: return 8
        case .performance16: return 16
        case .turbo24: return 24
        case .legacy32: return 32
        }
    }

    var ubatch: Int { batch }
}

struct M5RuntimeDecision {
    let profile: M5RuntimeProfile
    let reason: String
}

enum M5RuntimeGovernor {
    static let profileKey = "BonsaiBuild106ActiveGovernorProfile"
    static let reasonKey = "BonsaiBuild106ActiveGovernorReason"
    static let sourceKey = "BonsaiBuild106GovernorSource"

    /// Build112 state is intentionally independent of the old Build94
    /// certification/checkpoint state. This prevents stale SAFE4 state from
    /// blocking the new performance-default path.
    static let fallbackKey = "BonsaiBuild112FallbackProfile"
    static let candidateTrialBuildSHAKey = "BonsaiBuild113NaxCandidateTrialBuildSHA"
    static let candidateTrialPendingKey = "BonsaiBuild113NaxCandidateTrialPending"
    static let candidateTrialStateKey = "BonsaiBuild113NaxCandidateTrialState"
    static let candidateTrialPreviousFallbackKey = "BonsaiBuild113NaxCandidateTrialPreviousFallback"
    static let candidateTrialFailureKey = "BonsaiBuild113NaxCandidateTrialFailure"

    /// Explicit candidate selection authorizes one bounded B16 shape trial.
    /// Existing fallback evidence is recorded, never erased at trial start.
    static func scheduleCandidateShapeTrial(
        buildSHA: String,
        defaults: UserDefaults = .standard
    ) {
        if defaults.string(forKey: candidateTrialBuildSHAKey) == buildSHA,
           defaults.string(forKey: candidateTrialStateKey) == "ATTEMPTING_B16" {
            return
        }
        defaults.set(buildSHA, forKey: candidateTrialBuildSHAKey)
        defaults.set(true, forKey: candidateTrialPendingKey)
        defaults.set("PENDING", forKey: candidateTrialStateKey)
        defaults.set(
            defaults.string(forKey: fallbackKey) ?? "NONE",
            forKey: candidateTrialPreviousFallbackKey
        )
        defaults.removeObject(forKey: candidateTrialFailureKey)
        defaults.synchronize()
    }

    /// A changed App source identity permits one new candidate-only attempt.
    /// A failed attempt is not silently retried on every process launch.
    static func beginCandidateShapeTrialIfPending(
        buildSHA: String,
        candidate: Bool,
        defaults: UserDefaults = .standard
    ) -> Bool {
        guard candidate else { return false }
        if defaults.string(forKey: candidateTrialBuildSHAKey) != buildSHA {
            scheduleCandidateShapeTrial(buildSHA: buildSHA, defaults: defaults)
        }
        guard defaults.bool(forKey: candidateTrialPendingKey) else {
            return false
        }
        defaults.set(false, forKey: candidateTrialPendingKey)
        defaults.set("ATTEMPTING_B16", forKey: candidateTrialStateKey)
        defaults.synchronize()
        return true
    }

    static func isCandidateShapeTrialAttempting(
        buildSHA: String,
        defaults: UserDefaults = .standard
    ) -> Bool {
        defaults.string(forKey: candidateTrialBuildSHAKey) == buildSHA
            && defaults.string(forKey: candidateTrialStateKey) == "ATTEMPTING_B16"
    }

    private static func recordCandidateShapeTrialFailure(
        buildSHA: String,
        state: String,
        failure: String,
        defaults: UserDefaults
    ) {
        guard isCandidateShapeTrialAttempting(buildSHA: buildSHA, defaults: defaults) else {
            return
        }
        let previous = defaults.string(forKey: candidateTrialPreviousFallbackKey) ?? "NONE"
        let fallback: M5RuntimeProfile =
            previous == M5RuntimeProfile.safe4.rawValue
                ? .safe4
                : .balanced8
        defaults.set(fallback.rawValue, forKey: fallbackKey)
        defaults.set(fallback.rawValue, forKey: profileKey)
        defaults.set(
            "build113_candidate_b16_\(state.lowercased())_preserved_\(previous.lowercased())",
            forKey: reasonKey
        )
        defaults.set("build113_candidate_shape_trial", forKey: sourceKey)
        defaults.set(state, forKey: candidateTrialStateKey)
        defaults.set(failure, forKey: candidateTrialFailureKey)
        defaults.synchronize()
    }

    static func noteCandidateShapeTrialStartupFailure(
        buildSHA: String,
        defaults: UserDefaults = .standard
    ) {
        recordCandidateShapeTrialFailure(
            buildSHA: buildSHA,
            state: "STARTUP_FAILED",
            failure: "candidate_b16_startup_failed",
            defaults: defaults
        )
    }

    static func noteCandidateShapeTrialInferenceFailure(
        buildSHA: String,
        defaults: UserDefaults = .standard
    ) {
        recordCandidateShapeTrialFailure(
            buildSHA: buildSHA,
            state: "INFERENCE_FAILED",
            failure: "candidate_b16_inference_failed",
            defaults: defaults
        )
    }

    /// Only a real successful long-prefill request may re-arm B16 and clear
    /// the old sticky fallback. The previous value remains in the audit fields.
    static func noteCandidateShapeTrialTextSuccess(
        promptTokens: Int,
        buildSHA: String,
        defaults: UserDefaults = .standard
    ) {
        guard promptTokens >= 512,
              isCandidateShapeTrialAttempting(buildSHA: buildSHA, defaults: defaults)
        else { return }
        let previous = defaults.string(forKey: candidateTrialPreviousFallbackKey) ?? "NONE"
        defaults.set("LONG_PREFILL_SUCCESS", forKey: candidateTrialStateKey)
        defaults.set(
            "build113_candidate_b16_long_prefill_succeeded_after_\(previous.lowercased())",
            forKey: reasonKey
        )
        defaults.set("build113_candidate_long_prefill", forKey: sourceKey)
        defaults.set(M5RuntimeProfile.performance16.rawValue, forKey: profileKey)
        defaults.removeObject(forKey: fallbackKey)
        defaults.removeObject(forKey: candidateTrialFailureKey)
        defaults.synchronize()
    }

    static func candidateShapeTrialSnapshot(
        buildSHA: String,
        defaults: UserDefaults = .standard
    ) -> [String: Any] {
        [
            "schema": "bonsai-build113-nax-shape-trial-v1",
            "app_source_sha": buildSHA,
            "recorded_app_source_sha": defaults.string(forKey: candidateTrialBuildSHAKey) ?? "none",
            "state": defaults.string(forKey: candidateTrialStateKey) ?? "NOT_STARTED",
            "pending": defaults.bool(forKey: candidateTrialPendingKey),
            "previous_fallback_profile": defaults.string(forKey: candidateTrialPreviousFallbackKey) ?? "NONE",
            "active_governor_profile": defaults.string(forKey: profileKey) ?? "unknown",
            "active_fallback_profile": defaults.string(forKey: fallbackKey) ?? "NONE",
            "failure": defaults.string(forKey: candidateTrialFailureKey) ?? "none"
        ]
    }

    static func decide(
        context: Int,
        defaults: UserDefaults = .standard
    ) -> M5RuntimeDecision {
        guard context == 32_768 else {
            return M5RuntimeDecision(
                profile: .balanced8,
                reason: "non_32k_existing_policy"
            )
        }

        switch defaults.string(forKey: fallbackKey) {
        case M5RuntimeProfile.safe4.rawValue:
            return M5RuntimeDecision(
                profile: .safe4,
                reason: "build112_b8_startup_failed"
            )
        case M5RuntimeProfile.balanced8.rawValue:
            return M5RuntimeDecision(
                profile: .balanced8,
                reason: "build112_b16_startup_failed"
            )
        default:
            return M5RuntimeDecision(
                profile: .performance16,
                reason: "build112_b16_default"
            )
        }
    }

    static func persist(
        _ decision: M5RuntimeDecision,
        source: String,
        defaults: UserDefaults = .standard
    ) {
        defaults.set(decision.profile.rawValue, forKey: profileKey)
        defaults.set(decision.reason, forKey: reasonKey)
        defaults.set(source, forKey: sourceKey)
        defaults.synchronize()
    }

    /// Called only when model/context startup fails after the selected
    /// profile has been persisted. Ordinary inference failures do not call it.
    static func noteStartupFailure(
        defaults: UserDefaults = .standard
    ) {
        let active =
            M5RuntimeProfile(
                rawValue:
                    defaults.string(forKey: profileKey)
                    ?? M5RuntimeProfile.performance16.rawValue
            ) ?? .performance16

        let next: M5RuntimeProfile
        switch active {
        case .performance16:
            next = .balanced8
        case .balanced8:
            next = .safe4
        default:
            next = .safe4
        }

        defaults.set(next.rawValue, forKey: fallbackKey)
        defaults.set(next.rawValue, forKey: profileKey)
        defaults.set(
            "build112_\(active.rawValue.lowercased())_startup_failed",
            forKey: reasonKey
        )
        defaults.synchronize()
    }

    /// A real successful text request on the B8 recovery path proves the
    /// recovered runtime is usable. The next process launch may try B16 again.
    static func noteTextSuccess(
        promptTokens: Int,
        defaults: UserDefaults = .standard
    ) {
        guard promptTokens >= 200 else { return }
        let active =
            defaults.string(forKey: profileKey)
            ?? M5RuntimeProfile.performance16.rawValue
        if active == M5RuntimeProfile.balanced8.rawValue {
            defaults.set(
                "build112_b16_default",
                forKey: reasonKey
            )
            defaults.removeObject(forKey: fallbackKey)
            defaults.synchronize()
        }
    }

    static func snapshot(
        context: Int,
        activeBatch: Int,
        activeUBatch: Int,
        defaults: UserDefaults = .standard
    ) -> [String: Any] {
        let decision = decide(context: context, defaults: defaults)
        let fallback =
            defaults.string(forKey: fallbackKey) ?? "NONE"

        return [
            "schema": "bonsai-build112-m5-governor-v1",
            "selection_boundary": "llama_context_creation",
            "mid_request_batch_switch_supported": false,
            "device_target": "iPad Pro M5 12GB",
            "context": context,
            "profile": defaults.string(forKey: profileKey)
                ?? decision.profile.rawValue,
            "decision_reason":
                defaults.string(forKey: reasonKey)
                ?? decision.reason,
            "source":
                defaults.string(forKey: sourceKey)
                ?? "build112",
            "active_batch": activeBatch,
            "active_ubatch": activeUBatch,
            "fallback_profile": fallback,
            "sticky_fallback": fallback != "NONE",
            "pending_candidate": false,
            "launch_arm": decision.profile.rawValue,
            "fallback_boundary": "next_process_launch",
            "sequence_max": 1,
            "kv_reuse": "disabled",
            "auto_turbo24": false,
            "device_certified": false
        ]
    }
}
