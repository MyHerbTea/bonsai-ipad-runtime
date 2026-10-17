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

        RC126APIStartupLifecycle.begin(build: "112", defaults: defaults)
        RC126APIStartupLifecycle.mark("BACKEND_PREWARM_DONE", defaults: defaults)
        RC126APIStartupLifecycle.mark("MODEL_LOAD_BEGIN", defaults: defaults)
        RC126APIStartupLifecycle.begin(build: "112", defaults: defaults)
        expect(defaults.string(forKey: RC126APIStartupLifecycle.previousIncompleteKey) == "MODEL_LOAD_BEGIN",
               "interrupted model load must preserve its incomplete stage")
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
        RC126APIStartupLifecycle.begin(build: "112", defaults: defaults)
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastFailureStageKey) == "MODEL_LOAD_BEGIN"
            && defaults.string(forKey: RC126APIStartupLifecycle.lastFailureErrorKey) == "simulated model/context failure",
            "new attempt must not erase prior failure evidence")
        RC126APIStartupLifecycle.mark("LISTENER_READY", defaults: defaults)
        RC126APIStartupLifecycle.ready(defaults: defaults)
        expect(defaults.string(forKey: RC126APIStartupLifecycle.lastSuccessfulStageKey) == "READY",
               "successful listener readiness must be recorded")
        print("PASS Build112 API startup lifecycle: interrupted stage, last success, last failure and error persist")
    }
}
