import Foundation

/// Durable, per-attempt API startup evidence. Model identity is the selected file
/// name only; no full local path, API key, or prompt is persisted here.
enum RC126APIStartupLifecycle {
    static let stateKey = "BonsaiRC126APIStartupStage"
    static let previousIncompleteKey = "BonsaiRC126APIPreviousIncompleteStage"
    static let attemptKey = "BonsaiRC126APIStartupAttempt"
    static let attemptIDKey = "BonsaiRC126APIStartupAttemptID"
    static let modelIdentityKey = "BonsaiRC126APIStartupModelIdentity"
    static let modelFormatKey = "BonsaiRC126APIStartupModelFormat"
    static let startedAtKey = "BonsaiRC126APIStartupStartedAt"
    static let failedAtKey = "BonsaiRC126APIStartupFailedAt"
    static let outcomeKey = "BonsaiRC126APIStartupOutcome"
    static let currentFailureStageKey = "BonsaiRC126APIStartupFailureStage"
    static let currentFailureReasonKey = "BonsaiRC126APIStartupFailureReason"
    static let recoveryAttemptIDKey = "BonsaiRC126APIStartupRecoveryAttemptID"
    static let historyKey = "BonsaiRC126APIStartupAttemptHistory"

    static let errorKey = "BonsaiRC126APIStartupLastError"
    static let timestampKey = "BonsaiRC126APIStartupStageTime"
    static let buildKey = "BonsaiRC126APIStartupBuild"
    static let lastSuccessfulStageKey = "BonsaiRC126APILastSuccessfulStage"
    static let lastFailureStageKey = "BonsaiRC126APILastFailureStage"
    static let lastFailureErrorKey = "BonsaiRC126APILastFailureError"
    static let lastFailureTimeKey = "BonsaiRC126APILastFailureTime"
    static let lastFailureAttemptIDKey = "BonsaiRC126APILastFailureAttemptID"
    static let lastFailureModelIdentityKey = "BonsaiRC126APILastFailureModelIdentity"
    static let lastFailureModelFormatKey = "BonsaiRC126APILastFailureModelFormat"
    static let lastFailureStartedAtKey = "BonsaiRC126APILastFailureStartedAt"
    static let lastFailureOutcomeKey = "BonsaiRC126APILastFailureOutcome"
    static let lastRecoveryAttemptIDKey = "BonsaiRC126APILastRecoveryAttemptID"
    static let lastRecoveryModelIdentityKey = "BonsaiRC126APILastRecoveryModelIdentity"
    static let lastRecoveredFailureAttemptIDKey = "BonsaiRC126APILastRecoveredFailureAttemptID"
    static let lastRecoveryTimeKey = "BonsaiRC126APILastRecoveryTime"

    private static let terminalStates: Set<String> = ["READY", "FAILED"]
    private static let historyLimit = 12

    @discardableResult
    static func begin(
        build: String,
        modelIdentity: String? = nil,
        modelFormat: String? = nil,
        defaults: UserDefaults = .standard
    ) -> String {
        if let previous = defaults.string(forKey: stateKey),
           !previous.isEmpty,
           !terminalStates.contains(previous) {
            defaults.set(previous, forKey: previousIncompleteKey)

            // A process can be killed before fail() executes. Preserve that
            // interrupted attempt with its original model and attempt ID before
            // the next begin() overwrites the current-attempt fields.
            if let previousAttemptID = defaults.string(forKey: attemptIDKey),
               !previousAttemptID.isEmpty {
                let now = Date().timeIntervalSince1970
                let reason = "Startup attempt was interrupted before reaching a terminal outcome."
                let previousModel = defaults.string(forKey: modelIdentityKey) ?? "UNAVAILABLE"
                let previousFormat = defaults.string(forKey: modelFormatKey) ?? "UNAVAILABLE"
                let previousStartedAt = defaults.double(forKey: startedAtKey)
                defaults.set(previous, forKey: currentFailureStageKey)
                defaults.set(reason, forKey: currentFailureReasonKey)
                defaults.set(now, forKey: failedAtKey)
                defaults.set("INTERRUPTED", forKey: outcomeKey)
                setLastFailure(
                    attemptID: previousAttemptID,
                    modelIdentity: previousModel,
                    modelFormat: previousFormat,
                    startedAt: previousStartedAt,
                    failedAt: now,
                    stage: previous,
                    reason: reason,
                    outcome: "INTERRUPTED",
                    defaults: defaults
                )
                updateAttemptHistory(
                    attemptID: previousAttemptID,
                    changes: [
                        "outcome": "INTERRUPTED",
                        "current_stage": previous,
                        "failed_at": now,
                        "failure_stage": previous,
                        "failure_reason": reason,
                        "updated_at": now
                    ],
                    defaults: defaults
                )
            }
        }

        let attemptID = UUID().uuidString
        let startedAt = Date().timeIntervalSince1970
        defaults.set(defaults.integer(forKey: attemptKey) + 1, forKey: attemptKey)
        defaults.set(attemptID, forKey: attemptIDKey)
        defaults.set(nonEmpty(modelIdentity), forKey: modelIdentityKey)
        defaults.set(nonEmpty(modelFormat), forKey: modelFormatKey)
        defaults.set(startedAt, forKey: startedAtKey)
        defaults.set(0.0, forKey: failedAtKey)
        defaults.set("IN_PROGRESS", forKey: outcomeKey)
        defaults.removeObject(forKey: currentFailureStageKey)
        defaults.removeObject(forKey: currentFailureReasonKey)
        defaults.removeObject(forKey: recoveryAttemptIDKey)
        defaults.set(build, forKey: buildKey)
        defaults.removeObject(forKey: errorKey)
        updateAttemptHistory(
            attemptID: attemptID,
            changes: [
                "build": build,
                "model_identity_at_attempt": nonEmpty(modelIdentity),
                "model_format_at_attempt": nonEmpty(modelFormat),
                "started_at": startedAt,
                "failed_at": 0.0,
                "outcome": "IN_PROGRESS",
                "current_stage": "BEGIN",
                "updated_at": startedAt
            ],
            defaults: defaults
        )
        mark("BEGIN", defaults: defaults)
        return attemptID
    }

    static func mark(_ stage: String, defaults: UserDefaults = .standard) {
        let now = Date().timeIntervalSince1970
        defaults.set(stage, forKey: stateKey)
        defaults.set(now, forKey: timestampKey)
        if stage == "READY" || stage.hasSuffix("_DONE") || stage.hasSuffix("_READY") {
            defaults.set(stage, forKey: lastSuccessfulStageKey)
        }
        if let attemptID = defaults.string(forKey: attemptIDKey), !attemptID.isEmpty {
            updateAttemptHistory(
                attemptID: attemptID,
                changes: ["current_stage": stage, "updated_at": now],
                defaults: defaults
            )
        }
        defaults.synchronize()
    }

    static func ready(defaults: UserDefaults = .standard) {
        let currentAttemptID = defaults.string(forKey: attemptIDKey) ?? ""
        let failedAttemptID = defaults.string(forKey: lastFailureAttemptIDKey) ?? ""
        if !currentAttemptID.isEmpty,
           !failedAttemptID.isEmpty,
           currentAttemptID != failedAttemptID {
            let recoveredModel = defaults.string(forKey: modelIdentityKey) ?? "UNAVAILABLE"
            let now = Date().timeIntervalSince1970
            defaults.set(currentAttemptID, forKey: recoveryAttemptIDKey)
            defaults.set(currentAttemptID, forKey: lastRecoveryAttemptIDKey)
            defaults.set(recoveredModel, forKey: lastRecoveryModelIdentityKey)
            defaults.set(failedAttemptID, forKey: lastRecoveredFailureAttemptIDKey)
            defaults.set(now, forKey: lastRecoveryTimeKey)
            updateAttemptHistory(
                attemptID: currentAttemptID,
                changes: [
                    "recovered_failure_attempt_id": failedAttemptID,
                    "recovery_model_identity": recoveredModel,
                    "recovery_recorded_at": now
                ],
                defaults: defaults
            )
        }
        defaults.set("READY", forKey: outcomeKey)
        if !currentAttemptID.isEmpty {
            updateAttemptHistory(
                attemptID: currentAttemptID,
                changes: ["outcome": "READY"],
                defaults: defaults
            )
        }
        mark("READY", defaults: defaults)
    }

    static func fail(_ error: Error, defaults: UserDefaults = .standard) {
        let failedStage = defaults.string(forKey: stateKey) ?? "UNKNOWN"
        let message = error.localizedDescription
        let now = Date().timeIntervalSince1970
        let attemptID = defaults.string(forKey: attemptIDKey) ?? "UNAVAILABLE"
        let modelIdentity = defaults.string(forKey: modelIdentityKey) ?? "UNAVAILABLE"
        let modelFormat = defaults.string(forKey: modelFormatKey) ?? "UNAVAILABLE"
        let startedAt = defaults.double(forKey: startedAtKey)

        defaults.set(failedStage, forKey: currentFailureStageKey)
        defaults.set(message, forKey: currentFailureReasonKey)
        defaults.set(now, forKey: failedAtKey)
        defaults.set("FAILED", forKey: outcomeKey)
        defaults.set(message, forKey: errorKey)
        setLastFailure(
            attemptID: attemptID,
            modelIdentity: modelIdentity,
            modelFormat: modelFormat,
            startedAt: startedAt,
            failedAt: now,
            stage: failedStage,
            reason: message,
            outcome: "FAILED",
            defaults: defaults
        )
        updateAttemptHistory(
            attemptID: attemptID,
            changes: [
                "outcome": "FAILED",
                "current_stage": failedStage,
                "failed_at": now,
                "failure_stage": failedStage,
                "failure_reason": message,
                "updated_at": now
            ],
            defaults: defaults
        )
        mark("FAILED", defaults: defaults)
    }

    static func attemptHistory(defaults: UserDefaults = .standard) -> [[String: Any]] {
        guard let data = defaults.data(forKey: historyKey),
              let decoded = try? JSONSerialization.jsonObject(with: data),
              let history = decoded as? [[String: Any]] else {
            return []
        }
        return history
    }

    private static func nonEmpty(_ value: String?) -> String {
        guard let value, !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return "UNAVAILABLE"
        }
        return value
    }

    private static func setLastFailure(
        attemptID: String,
        modelIdentity: String,
        modelFormat: String,
        startedAt: Double,
        failedAt: Double,
        stage: String,
        reason: String,
        outcome: String,
        defaults: UserDefaults
    ) {
        defaults.set(attemptID, forKey: lastFailureAttemptIDKey)
        defaults.set(modelIdentity, forKey: lastFailureModelIdentityKey)
        defaults.set(modelFormat, forKey: lastFailureModelFormatKey)
        defaults.set(startedAt, forKey: lastFailureStartedAtKey)
        defaults.set(failedAt, forKey: lastFailureTimeKey)
        defaults.set(stage, forKey: lastFailureStageKey)
        defaults.set(reason, forKey: lastFailureErrorKey)
        defaults.set(outcome, forKey: lastFailureOutcomeKey)
    }

    private static func updateAttemptHistory(
        attemptID: String,
        changes: [String: Any],
        defaults: UserDefaults
    ) {
        guard !attemptID.isEmpty, attemptID != "UNAVAILABLE" else { return }
        var history = attemptHistory(defaults: defaults)
        if let index = history.lastIndex(where: {
            ($0["startup_attempt_id"] as? String) == attemptID
        }) {
            var record = history[index]
            for (key, value) in changes {
                record[key] = value
            }
            history[index] = record
        } else {
            var record: [String: Any] = ["startup_attempt_id": attemptID]
            for (key, value) in changes {
                record[key] = value
            }
            history.append(record)
        }
        if history.count > historyLimit {
            history = Array(history.suffix(historyLimit))
        }
        guard let data = try? JSONSerialization.data(
            withJSONObject: history,
            options: [.sortedKeys]
        ) else { return }
        defaults.set(data, forKey: historyKey)
    }
}
