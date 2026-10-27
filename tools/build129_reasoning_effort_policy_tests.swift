import Foundation

@main
struct Build129ReasoningModePolicyTests {
    static func main() {
        precondition(APIReasoningModePolicy.defaultEffort(thinkingEnabled: false) == "none")
        precondition(APIReasoningModePolicy.defaultEffort(thinkingEnabled: true) == "medium")
        precondition(APIReasoningModePolicy.resolve(
            requestValue: nil, requestWasPresent: false, thinkingEnabled: false
        ) == "none")
        precondition(APIReasoningModePolicy.resolve(
            requestValue: nil, requestWasPresent: false, thinkingEnabled: true
        ) == "medium")
        precondition(APIReasoningModePolicy.resolve(
            requestValue: "none", requestWasPresent: true, thinkingEnabled: true
        ) == "none")
        precondition(APIReasoningModePolicy.resolve(
            requestValue: "XHIGH", requestWasPresent: true, thinkingEnabled: false
        ) == "xhigh")
        for effort in ["none", "minimal", "low", "medium", "high", "xhigh"] {
            precondition(APIReasoningModePolicy.resolve(
                requestValue: effort, requestWasPresent: true, thinkingEnabled: false
            ) == effort)
        }
        precondition(APIReasoningModePolicy.resolve(
            requestValue: "ultra", requestWasPresent: true, thinkingEnabled: true
        ) == nil)
        precondition(APIReasoningModePolicy.resolve(
            requestValue: nil, requestWasPresent: true, thinkingEnabled: true
        ) == nil)
        precondition(APIReasoningModePolicy.resolve(
            requestValue: NSNull(), requestWasPresent: true, thinkingEnabled: true
        ) == nil)
        precondition(APIReasoningModePolicy.resolve(
            requestValue: NSNumber(value: 1), requestWasPresent: true, thinkingEnabled: false
        ) == nil)
        print("Build129 reasoning mode policy: PASS")
    }
}
