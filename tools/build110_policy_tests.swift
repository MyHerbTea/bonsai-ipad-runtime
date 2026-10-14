import Foundation

@main
struct Build110PolicyTests {
    static func main() {
        let suite = "BonsaiBuild110Tests." + UUID().uuidString
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        Build94BatchExperiment.resetForTests()
        defaults.set(true, forKey: Build94BatchExperiment.baselineOKKey)
        defaults.set(true, forKey: Build94BatchExperiment.confirmedKey)
        defaults.set(true, forKey: Build94BatchExperiment.preferB16Key)
        defaults.set(Build94BatchExperiment.Arm.candidate16.rawValue, forKey: Build94BatchExperiment.nextKey)
        Build94BatchExperiment.bindCertificationIdentity("new-source", defaults: defaults)
        precondition(!defaults.bool(forKey: Build94BatchExperiment.baselineOKKey))
        precondition(!defaults.bool(forKey: Build94BatchExperiment.confirmedKey))
        precondition(!Build94BatchExperiment.scheduleNext(.candidate16, acknowledgeRecovery: false, defaults: defaults))
        precondition(Build94BatchExperiment.select(context: 32768, defaults: defaults) == .baseline8)
        Build94BatchExperiment.noteTextSuccess(promptTokens: 199, defaults: defaults)
        precondition(!defaults.bool(forKey: Build94BatchExperiment.baselineOKKey))
        Build94BatchExperiment.noteTextSuccess(promptTokens: 200, defaults: defaults)
        precondition(Build94BatchExperiment.scheduleNext(.candidate16, acknowledgeRecovery: false, defaults: defaults))
        Build94BatchExperiment.resetForTests()
        Build94BatchExperiment.bindCertificationIdentity("new-source", defaults: defaults)
        precondition(Build94BatchExperiment.select(context: 32768, defaults: defaults) == .candidate16)
        precondition(defaults.bool(forKey: Build94BatchExperiment.pendingKey))
        Build94BatchExperiment.noteTextSuccess(promptTokens: 200, defaults: defaults)
        precondition(!defaults.bool(forKey: Build94BatchExperiment.pendingKey))
        precondition(defaults.bool(forKey: Build94BatchExperiment.confirmedKey))
        precondition(!Build94BatchExperiment.scheduleNext(.candidate32, acknowledgeRecovery: false, defaults: defaults))
        // Incomplete trials and safety fallback survive source changes.
        defaults.set(true, forKey: Build94BatchExperiment.pendingKey)
        defaults.set(true, forKey: Build94BatchExperiment.fallbackKey)
        Build94BatchExperiment.bindCertificationIdentity("another-source", defaults: defaults)
        precondition(defaults.bool(forKey: Build94BatchExperiment.pendingKey))
        precondition(defaults.bool(forKey: Build94BatchExperiment.fallbackKey))
        Build94BatchExperiment.resetForTests()
        precondition(Build94BatchExperiment.select(context: 32768, defaults: defaults) == .safe4)
        precondition(!Build94BatchExperiment.scheduleNext(.baseline8, acknowledgeRecovery: false, defaults: defaults))
        print("PASS Build110 source qualification, real B8 success, B16 pending/confirmed, B32 denial and sticky recovery")
    }
}
