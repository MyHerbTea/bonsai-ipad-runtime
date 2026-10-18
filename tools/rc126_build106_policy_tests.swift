import Foundation

@main
struct Build112M5GovernorPolicyTests {
    static func main() {
        let suite = "Build112GovernorUnit." + UUID().uuidString
        let defaults = UserDefaults(suiteName: suite)!

        func decide(_ expected: M5RuntimeProfile) {
            let decision = M5RuntimeGovernor.decide(
                context: 32_768,
                defaults: defaults
            )
            precondition(decision.profile == expected)
            precondition(decision.profile.batch == decision.profile.ubatch)
        }

        // Historical Build106/94 state must not block the new B16 default.
        defaults.set("SAFE4", forKey: "BonsaiBuild106ActiveGovernorProfile")
        defaults.set("true", forKey: "BonsaiBuild94StickyFallback")
        decide(.performance16)
        defaults.removeObject(forKey: "BonsaiBuild94StickyFallback")

        // Build112 ignores historical Build94 arm selection: B16 is default.
        decide(.performance16)
        precondition(
            M5RuntimeGovernor.decide(
                context: 32_768,
                defaults: defaults
            ).profile == .performance16
        )

        // B16 startup failure -> B8.
        let b16 = M5RuntimeGovernor.decide(
            context: 32_768,
            defaults: defaults
        )
        M5RuntimeGovernor.persist(
            b16,
            source: "unit_test",
            defaults: defaults
        )
        M5RuntimeGovernor.noteStartupFailure(defaults: defaults)
        decide(.balanced8)

        // A successful B8 text request re-arms the B16 default.
        let b8 = M5RuntimeGovernor.decide(
            context: 32_768,
            defaults: defaults
        )
        M5RuntimeGovernor.persist(
            b8,
            source: "unit_test",
            defaults: defaults
        )
        M5RuntimeGovernor.noteTextSuccess(
            promptTokens: 200,
            defaults: defaults
        )
        decide(.performance16)

        // A second startup failure -> SAFE4.
        let b16Again = M5RuntimeGovernor.decide(
            context: 32_768,
            defaults: defaults
        )
        M5RuntimeGovernor.persist(
            b16Again,
            source: "unit_test",
            defaults: defaults
        )
        M5RuntimeGovernor.noteStartupFailure(defaults: defaults)
        let b8Again = M5RuntimeGovernor.decide(
            context: 32_768,
            defaults: defaults
        )
        M5RuntimeGovernor.persist(
            b8Again,
            source: "unit_test",
            defaults: defaults
        )
        M5RuntimeGovernor.noteStartupFailure(defaults: defaults)
        decide(.safe4)

        let state = M5RuntimeGovernor.snapshot(
            context: 32_768,
            activeBatch: 4,
            activeUBatch: 4,
            defaults: defaults
        )
        precondition(state["profile"] as? String == "SAFE4")
        precondition(state["fallback_profile"] as? String == "SAFE4")
        precondition(state["mid_request_batch_switch_supported"] as? Bool == false)
        precondition(state["sequence_max"] as? Int == 1)

        // Native crash tracing is armed for 16K/B16 only, and all >=32K.
        precondition(
            M5RuntimeGovernor.shouldEnableNativeContextTrace(
                context: 16_384,
                batch: 16,
                ubatch: 16
            )
        )
        precondition(
            !M5RuntimeGovernor.shouldEnableNativeContextTrace(
                context: 16_384,
                batch: 8,
                ubatch: 8
            )
        )
        precondition(
            M5RuntimeGovernor.shouldEnableNativeContextTrace(
                context: 32_768,
                batch: 8,
                ubatch: 8
            )
        )

        // Non-32K behavior remains unchanged.
        precondition(
            M5RuntimeGovernor.decide(
                context: 4096,
                defaults: defaults
            ).reason == "non_32k_existing_policy"
        )

        defaults.removePersistentDomain(forName: suite)
        print("PASS Build112 simple B16 default / B8 recovery / SAFE4 fallback policy")
    }
}
