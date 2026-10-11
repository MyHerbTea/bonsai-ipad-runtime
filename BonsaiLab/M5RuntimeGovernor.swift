import Foundation

/// M5 iPad 12GB / Bonsai 27B launcher. llama n_batch and n_ubatch are
/// context-creation parameters, NOT parameters switchable per HTTP request.
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

/// Build94 selects an arm first; this policy cannot bypass certification,
/// opt-in or sticky recovery and only selects a launch-time runtime shape.
enum M5RuntimeGovernor {
    static let profileKey = "BonsaiBuild106ActiveGovernorProfile"
    static let reasonKey = "BonsaiBuild106ActiveGovernorReason"
    static let sourceKey = "BonsaiBuild106GovernorSource"

    static func decide(arm: Build94BatchExperiment.Arm, context: Int) -> M5RuntimeDecision {
        if context != 32_768 {
            return M5RuntimeDecision(profile: .balanced8, reason: "non_32k_existing_policy")
        }
        switch arm {
        case .safe4:
            return M5RuntimeDecision(profile: .safe4, reason: "sticky_or_recovery_safe4")
        case .baseline8:
            return M5RuntimeDecision(profile: .balanced8, reason: "build105_safe_baseline8")
        case .candidate16:
            return M5RuntimeDecision(profile: .performance16, reason: "build94_certification_gated_b16")
        case .candidate24:
            return M5RuntimeDecision(profile: .turbo24, reason: "build94_certification_gated_b24")
        case .candidate32:
            // Retains older Build102 explicit, separately consent-gated arm.
            return M5RuntimeDecision(profile: .legacy32, reason: "legacy_explicit_b32_experiment")
        }
    }

    static func persist(
        _ decision: M5RuntimeDecision, source: String,
        defaults: UserDefaults = .standard
    ) {
        defaults.set(decision.profile.rawValue, forKey: profileKey)
        defaults.set(decision.reason, forKey: reasonKey)
        defaults.set(source, forKey: sourceKey)
        defaults.synchronize()
    }

    static func snapshot(
        context: Int, activeBatch: Int, activeUBatch: Int,
        defaults: UserDefaults = .standard
    ) -> [String: Any] {
        let launch = Build94BatchExperiment.snapshot(defaults: defaults)
        return [
            "schema": "bonsai-build106-m5-governor-v1",
            "selection_boundary": "llama_context_creation",
            "mid_request_batch_switch_supported": false,
            "device_target": "iPad Pro M5 12GB",
            "context": context,
            "profile": defaults.string(forKey: profileKey) ?? "NOT_SELECTED",
            "decision_reason": defaults.string(forKey: reasonKey) ?? "none",
            "source": defaults.string(forKey: sourceKey) ?? "none",
            "active_batch": activeBatch,
            "active_ubatch": activeUBatch,
            "sticky_fallback": launch["sticky_fallback"] ?? false,
            "pending_candidate": launch["pending"] ?? false,
            "launch_arm": launch["active_arm"] ?? "NOT_SELECTED",
            "fallback_boundary": "next_process_launch",
            "sequence_max": 1,
            "kv_reuse": "disabled",
            "auto_turbo24": false,
            "device_certified": false
        ]
    }
}
