import Foundation

func expect(_ condition: @autoclosure () -> Bool, _ message: String) {
    guard condition() else {
        fputs("FAIL: \(message)\n", stderr)
        exit(1)
    }
}

@main
struct APIKeyAuthenticationPolicyTests {
    static func main() {
        let suiteName = "BonsaiAPIKeyAuthTests-\(UUID().uuidString)"
        guard let defaults = UserDefaults(suiteName: suiteName) else {
            fatalError("Could not create isolated UserDefaults suite")
        }
        defer { defaults.removePersistentDomain(forName: suiteName) }
        
        expect(LocalAPIAuthenticationPolicy.isRequired(defaults: defaults),
               "new installs must default to authentication enabled")
        expect(!LocalAPIAuthenticationPolicy.isAuthorized(required: true, expectedAPIKey: "secret", authorizationHeader: nil, apiKeyHeader: nil),
               "missing key must be rejected")
        expect(!LocalAPIAuthenticationPolicy.isAuthorized(required: true, expectedAPIKey: "secret", authorizationHeader: "Bearer wrong", apiKeyHeader: "wrong"),
               "wrong key must be rejected")
        expect(LocalAPIAuthenticationPolicy.isAuthorized(required: true, expectedAPIKey: "secret", authorizationHeader: "Bearer secret", apiKeyHeader: nil),
               "correct Bearer key must be accepted")
        expect(LocalAPIAuthenticationPolicy.isAuthorized(required: true, expectedAPIKey: "secret", authorizationHeader: nil, apiKeyHeader: "secret"),
               "correct X-API-Key must be accepted")
        expect(LocalAPIAuthenticationPolicy.isAuthorized(required: false, expectedAPIKey: "secret", authorizationHeader: nil, apiKeyHeader: nil),
               "disabled authentication must allow requests without headers")
        expect(LocalAPIAuthenticationPolicy.isAuthorized(required: false, expectedAPIKey: "secret", authorizationHeader: "Bearer wrong", apiKeyHeader: "wrong"),
               "disabled authentication must not validate a key")
        LocalAPIAuthenticationPolicy.setRequired(false, defaults: defaults)
        expect(!LocalAPIAuthenticationPolicy.isRequired(defaults: defaults), "disabled preference must persist")
        LocalAPIAuthenticationPolicy.setRequired(true, defaults: defaults)
        expect(LocalAPIAuthenticationPolicy.isRequired(defaults: defaults), "re-enabled preference must persist")
        expect(!LocalAPIAuthenticationPolicy.isAuthorized(required: true, expectedAPIKey: "", authorizationHeader: "Bearer ", apiKeyHeader: ""),
               "empty server key must never authorize")
        print("PASS API Key auth policy: default-on, missing/wrong/correct keys, disabled mode, persistence")
    }
}
