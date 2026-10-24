import Foundation

enum BenchmarkInterruptionRecovery {
    enum Failure: Error { case acknowledgementRejected }
    static let key = "BonsaiQuickPrefillInterrupted"
    static func equal(_ a: [String: Any], _ b: [String: Any]) -> Bool {
        guard let x = try? JSONSerialization.data(withJSONObject: a, options: [.sortedKeys]),
              let y = try? JSONSerialization.data(withJSONObject: b, options: [.sortedKeys]) else { return false }
        return x == y
    }
    static func acknowledge(defaults: UserDefaults, source: String, process: String,
                            body: [String: Any], runtime: [String: Any]? = nil,
                            readAudit: ((String) throws -> [String: Any]?)? = nil,
                            saveAudit: (String, [String: Any]) throws -> String) throws -> String {
        guard !source.isEmpty, !process.isEmpty,
              let operatorReason = body["reason"] as? String,
              ["manual_forced_exit", "operator_confirmed_api_cancel"].contains(operatorReason),
              body["expected_source_git_sha"] as? String == source,
              body["expected_process_id"] as? String == process,
              let marker = defaults.dictionary(forKey: key),
              let expected = body["expected_interruption"] as? [String: Any],
              marker["batch"] as? Int == 8, marker["context"] as? Int == 16384,
              equal(marker, expected) else { throw Failure.acknowledgementRejected }
        var auditFields: [String: Any] = ["operator_reason":operatorReason, "source_git_sha":source,
                                         "process_id":process, "acknowledged_marker":marker]
        if operatorReason == "operator_confirmed_api_cancel" {
            guard let interruption = marker["interruption_id"] as? String, UUID(uuidString: interruption) != nil,
                  let proof = body["api_cancel_evidence"] as? [String: Any], readAudit != nil else {
                throw Failure.acknowledgementRejected
            }
            try BenchmarkCancellationEvidence.validate(proof, marker: marker, runtime: runtime)
            auditFields["api_cancel_evidence"] = proof
        }
        let reason = operatorReason == "manual_forced_exit" ? "operator_confirmed_manual_forced_exit" : operatorReason
        // The snapshot must be durably saved before the pending marker is removed.
        let audit = try saveAudit(reason, auditFields)
        guard !audit.isEmpty else { throw Failure.acknowledgementRejected }
        if let readAudit {
            guard let report = try readAudit(audit), let fields = report["operator_acknowledgement"] as? [String: Any],
                  equal(fields, auditFields) else { throw Failure.acknowledgementRejected }
        }
        guard let latest = defaults.dictionary(forKey: key), equal(latest, marker) else {
            throw Failure.acknowledgementRejected
        }
        defaults.removeObject(forKey: key)
        return audit
    }
}
