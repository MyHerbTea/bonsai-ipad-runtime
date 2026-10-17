import Foundation

/// Durable API startup lifecycle evidence. The current stage is written before
/// risky work; success and failure evidence survives process termination.
enum RC126APIStartupLifecycle {
    static let stateKey = "BonsaiRC126APIStartupStage"
    static let previousIncompleteKey = "BonsaiRC126APIPreviousIncompleteStage"
    static let attemptKey = "BonsaiRC126APIStartupAttempt"
    static let errorKey = "BonsaiRC126APIStartupLastError"
    static let timestampKey = "BonsaiRC126APIStartupStageTime"
    static let buildKey = "BonsaiRC126APIStartupBuild"
    static let lastSuccessfulStageKey = "BonsaiRC126APILastSuccessfulStage"
    static let lastFailureStageKey = "BonsaiRC126APILastFailureStage"
    static let lastFailureErrorKey = "BonsaiRC126APILastFailureError"
    static let lastFailureTimeKey = "BonsaiRC126APILastFailureTime"

    private static let terminalStates: Set<String> = ["READY", "FAILED"]

    static func begin(build: String, defaults: UserDefaults = .standard) {
        if let previous = defaults.string(forKey: stateKey),
           !previous.isEmpty,
           !terminalStates.contains(previous) {
            defaults.set(previous, forKey: previousIncompleteKey)
        }
        defaults.set(defaults.integer(forKey: attemptKey) + 1, forKey: attemptKey)
        defaults.set(build, forKey: buildKey)
        defaults.removeObject(forKey: errorKey)
        mark("BEGIN", defaults: defaults)
    }

    static func mark(_ stage: String, defaults: UserDefaults = .standard) {
        defaults.set(stage, forKey: stateKey)
        defaults.set(Date().timeIntervalSince1970, forKey: timestampKey)
        if stage == "READY" || stage.hasSuffix("_DONE") || stage.hasSuffix("_READY") {
            defaults.set(stage, forKey: lastSuccessfulStageKey)
        }
        defaults.synchronize()
    }

    static func ready(defaults: UserDefaults = .standard) {
        mark("READY", defaults: defaults)
    }

    static func fail(_ error: Error, defaults: UserDefaults = .standard) {
        let failedStage = defaults.string(forKey: stateKey) ?? "UNKNOWN"
        let message = error.localizedDescription
        defaults.set(failedStage, forKey: lastFailureStageKey)
        defaults.set(message, forKey: lastFailureErrorKey)
        defaults.set(Date().timeIntervalSince1970, forKey: lastFailureTimeKey)
        defaults.set(message, forKey: errorKey)
        mark("FAILED", defaults: defaults)
    }
}
