import Foundation

enum APIReasoningModePolicy {
    static let userDefaultsKey = "BonsaiLocalAPIThinkingModeEnabled"
    static let supportedEfforts: Set<String> = [
        "none", "minimal", "low", "medium", "high", "xhigh"
    ]

    static func defaultEffort(thinkingEnabled: Bool) -> String {
        thinkingEnabled ? "medium" : "none"
    }

    static func resolve(
        requestValue: Any?,
        requestWasPresent: Bool,
        thinkingEnabled: Bool
    ) -> String? {
        guard requestWasPresent else {
            return defaultEffort(thinkingEnabled: thinkingEnabled)
        }
        guard let requested = requestValue as? String else { return nil }

        let normalized = requested.lowercased()
        return supportedEfforts.contains(normalized) ? normalized : nil
    }
}
