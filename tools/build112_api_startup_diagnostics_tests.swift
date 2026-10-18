import Foundation

func expect(_ condition: @autoclosure () -> Bool, _ message: String) {
    guard condition() else {
        fputs("FAIL: \(message)\n", stderr)
        exit(1)
    }
}

@main
struct Build112APIStartupDiagnosticsTests {
    static func main() {
        let suiteName = "BonsaiAPIStartupTests-\(UUID().uuidString)"
        guard let defaults = UserDefaults(suiteName: suiteName) else {
            fatalError("Could not create isolated UserDefaults suite")
        }
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let pq2Attempt = RC126APIStartupLifecycle.begin(
            build: "112",
            modelIdentity: "Ternary-Bonsai-2-27B-PQ2_0.gguf",
            modelFormat: "GGUF",
            defaults: defaults
        )
        RC126APIStartupLifecycle.mark("BACKEND_PREWARM_DONE", defaults: defaults)
        RC126APIStartupLifecycle.mark("MODEL_LOAD_BEGIN", defaults: defaults)

        let failedAttempt = RC126APIStartupLifecycle.begin(
            build: "112",
            modelIdentity: "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
            modelFormat: "GGUF",
            defaults: defaults
        )
        expect(pq2Attempt != failedAttempt, "every startup attempt must have a unique ID")
        expect(defaults.string(forKey: RC126APIStartupLifecycle.previousIncompleteKey) == "MODEL_LOAD_BEGIN",
               "interrupted model load must preserve its incomplete stage")
        expect(defaults.string(forKey: RC126APIStartupLifecycle.modelIdentityKey) == "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
               "current attempt must record the selected model filename")
        RC126APIStartupLifecycle.mark("MODEL_LOAD_BEGIN", defaults: defaults)
        RC126APIStartupLifecycle.fail(
            NSError(domain: "BonsaiStartupTest", code: 7,
                    userInfo: [NSLocalizedDescriptionKey: "simulated model/context failure"]),
            defaults: defaults
        )
        expect(defaults.string(forKey: RC126APIStartupLifecycle.stateKey) == "FAILED",
               "caught startup failure must become terminal FAILED")
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastSuccessfulStageKey) == "BACKEND_PREWARM_DONE",
               "last successful stage must not be overwritten by a failing stage")
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastFailureStageKey) == "MODEL_LOAD_BEGIN",
               "failure record must preserve the exact stage")
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastFailureErrorKey) == "simulated model/context failure",
               "failure record must preserve the actual error")
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastFailureAttemptIDKey) == failedAttempt,
               "failure must remain associated with its own attempt ID")
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastFailureModelIdentityKey) == "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
               "failure must remain associated with its model filename")
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastFailureModelFormatKey) == "GGUF",
               "failure must preserve the model file format")
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastFailureOutcomeKey) == "FAILED",
               "failure outcome must be persisted")
        expect(defaults.double(forKey: RC126APIStartupLifecycle.lastFailureStartedAtKey) > 0,
               "failure record must retain its attempt start time")

        let recoveryAttempt = RC126APIStartupLifecycle.begin(
            build: "112",
            modelIdentity: "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
            modelFormat: "GGUF",
            defaults: defaults
        )
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastFailureStageKey) == "MODEL_LOAD_BEGIN"
            && defaults.string(forKey: RC126APIStartupLifecycle.lastFailureAttemptIDKey) == failedAttempt
            && defaults.string(forKey: RC126APIStartupLifecycle.lastFailureModelIdentityKey) == "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
            "new attempt must not erase prior failure evidence; preserve the previous failure evidence")
        RC126APIStartupLifecycle.mark("LISTENER_READY", defaults: defaults)
        RC126APIStartupLifecycle.ready(defaults: defaults)
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastSuccessfulStageKey) == "READY",
               "successful listener readiness must be recorded")
        expect(defaults.string(forKey: RC126APIStartupLifecycle.recoveryAttemptIDKey) == recoveryAttempt,
               "successful recovery must record its own attempt ID")
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastRecoveredFailureAttemptIDKey) == failedAttempt,
               "recovery must point to the exact failed attempt it followed")

        let history = RC126APIStartupLifecycle.attemptHistory(defaults: defaults)
        expect(history.count == 3, "each model startup attempt must have an independent history record")
        let failedRecord = history.first(where: {
            ($0["startup_attempt_id"] as? String) == failedAttempt
        })
        expect((failedRecord?["outcome"] as? String) == "FAILED"
            && (failedRecord?["model_identity_at_attempt"] as? String) == "Ternary-Bonsai-2-27B-PTQ1_0.gguf"
            && (failedRecord?["failure_stage"] as? String) == "MODEL_LOAD_BEGIN",
            "later successful startup must not rewrite the prior failed attempt")
        let recoveryRecord = history.first(where: {
            ($0["startup_attempt_id"] as? String) == recoveryAttempt
        })
        expect((recoveryRecord?["outcome"] as? String) == "READY"
            && (recoveryRecord?["recovered_failure_attempt_id"] as? String) == failedAttempt,
            "history must link recovery to the exact prior failure")
        let crashSuiteName = "BonsaiPTQ1AB16Recovery-\(UUID().uuidString)"
        guard let crashDefaults = UserDefaults(suiteName: crashSuiteName) else {
            fatalError("Could not create isolated recovery UserDefaults suite")
        }
        defer { crashDefaults.removePersistentDomain(forName: crashSuiteName) }
        crashDefaults.set(true, forKey: "BonsaiBuild113PTQ1TensorOpsAB16Enabled")
        crashDefaults.set("16384", forKey: "BonsaiRC1235APIContextProfile")
        crashDefaults.set("CANDIDATE", forKey: "BonsaiRC126Phase2CNextLaunchArm")
        crashDefaults.set("IN_PROGRESS", forKey: RC126APIStartupLifecycle.outcomeKey)
        crashDefaults.set("MODEL_LOAD_BEGIN", forKey: RC126APIStartupLifecycle.stateKey)
        crashDefaults.set("Ternary-Bonsai-2-27B-PTQ1_0.gguf", forKey: RC126APIStartupLifecycle.modelIdentityKey)
        crashDefaults.set("MODEL_07_CONTEXT_CREATE_BEGIN", forKey: "BonsaiLabLastStage")
        crashDefaults.set(16_384, forKey: "BonsaiBuild81ContextCreateAttempt")
        crashDefaults.set(false, forKey: "BonsaiBuild81ContextCreateCompleted")
        crashDefaults.set(16, forKey: "BonsaiBuild82EngineContextBatch")
        crashDefaults.set(16, forKey: "BonsaiBuild82EngineContextUBatch")
        crashDefaults.set("MODEL_07_CONTEXT_CREATE_BEGIN", forKey: RC126APIStartupLifecycle.lastFailureStageKey)
        expect(RC126APIStartupLifecycle.recoverInterruptedPTQ1AB16IfNeeded(defaults: crashDefaults),
               "interrupted PTQ1 16K/B16 native context creation must auto-recover")
        expect(!crashDefaults.bool(forKey: "BonsaiBuild113PTQ1TensorOpsAB16Enabled"),
               "recovery must turn off the PTQ1 experimental shape")
        expect(crashDefaults.string(forKey: "BonsaiRC1235APIContextProfile") == "8192",
               "recovery must restore the last known 8K context selection")
        expect(crashDefaults.string(forKey: "BonsaiRC126Phase2CNextLaunchArm") == "BASELINE",
               "recovery must prevent an experimental TensorOps candidate retry")
        expect(crashDefaults.string(forKey: RC126APIStartupLifecycle.lastFailureStageKey) == "MODEL_07_CONTEXT_CREATE_BEGIN",
               "recovery must preserve the original failure stage")
        expect((crashDefaults.string(forKey: RC126APIStartupLifecycle.ptq1AB16RecoveryNoticeKey) ?? "").contains("8192/B8"),
               "recovery must leave a user-visible explanation")
        crashDefaults.set("FAILED", forKey: RC126APIStartupLifecycle.outcomeKey)
        crashDefaults.set(true, forKey: "BonsaiBuild113PTQ1TensorOpsAB16Enabled")
        crashDefaults.set("16384", forKey: "BonsaiRC1235APIContextProfile")
        expect(!RC126APIStartupLifecycle.recoverInterruptedPTQ1AB16IfNeeded(defaults: crashDefaults),
               "terminal failures must not be mistaken for an unhandled native crash")
        print("PASS Build112 startup evidence and PTQ1 16K/B16 interrupted-startup recovery")
    }
}
