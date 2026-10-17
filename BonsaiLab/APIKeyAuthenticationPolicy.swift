import Foundation

/// The single policy used by the real HTTP request path and by regression tests.
/// Missing persisted preference means authentication remains enabled for upgrades.
enum LocalAPIAuthenticationPolicy {
    static let enabledDefaultsKey = "BonsaiLocalAPIKeyAuthEnabled"

    static func isRequired(defaults: UserDefaults = .standard) -> Bool {
        guard let stored = defaults.object(forKey: enabledDefaultsKey) as? Bool else { return true }
        return stored
    }

    static func setRequired(_ required: Bool, defaults: UserDefaults = .standard) {
        defaults.set(required, forKey: enabledDefaultsKey)
    }

    static func isAuthorized(
        required: Bool,
        expectedAPIKey: String,
        authorizationHeader: String?,
        apiKeyHeader: String?
    ) -> Bool {
        guard required else { return true }
        guard !expectedAPIKey.isEmpty else { return false }
        if authorizationHeader == "Bearer \(expectedAPIKey)" { return true }
        return apiKeyHeader == expectedAPIKey
    }
}
