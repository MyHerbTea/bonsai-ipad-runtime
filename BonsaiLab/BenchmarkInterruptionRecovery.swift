import Foundation

enum BenchmarkInterruptionRecovery {
    enum Failure: Error { case acknowledgementRejected }
    static let key = "BonsaiQuickPrefillInterrupted"
    static func acknowledge(defaults: UserDefaults, source: String, process: String,
                            body: [String: Any], saveAudit: (String, [String: Any]) throws -> String) throws -> String {
        guard !source.isEmpty, !process.isEmpty,
              body["reason"] as? String == "manual_forced_exit",
              body["expected_source_git_sha"] as? String == source,
              body["expected_process_id"] as? String == process,
              let marker = defaults.dictionary(forKey: key),
              let expected = body["expected_interruption"] as? [String: Any],
              marker["batch"] as? Int == 8, marker["context"] as? Int == 16384,
              let actualData = try? JSONSerialization.data(withJSONObject: marker, options: [.sortedKeys]),
              let expectedData = try? JSONSerialization.data(withJSONObject: expected, options: [.sortedKeys]),
              actualData == expectedData else { throw Failure.acknowledgementRejected }
        let reason = "operator_confirmed_manual_forced_exit"
        let auditFields: [String: Any] = ["operator_reason":"manual_forced_exit", "source_git_sha":source,
                                        "process_id":process, "acknowledged_marker":marker]
        // The snapshot must be durably saved before the pending marker is removed.
        let audit = try saveAudit(reason, auditFields)
        guard !audit.isEmpty else { throw Failure.acknowledgementRejected }
        defaults.removeObject(forKey: key)
        return audit
    }
}
