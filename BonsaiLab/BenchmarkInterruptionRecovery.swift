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

    static func acknowledgeQ8(defaults: UserDefaults, source: String, process: String,
                              body: [String: Any], runtime: [String: Any]?,
                              readAudit: ((String) throws -> [String: Any]?)?,
                              saveAudit: (String, [String: Any]) throws -> String) throws -> String {
        let key = "BonsaiQ8BaselineInterrupted"
        let reason = "operator_reviewed_preserved_failed_result"
        let fullOperatorAbortSource = "2b4daf44ff9f8b7d2bb30f9831c53938fc7bd158"
        guard source.utf8.count == 40, source.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) || (65...70).contains($0) }),
              UUID(uuidString: process) != nil,
              body["reason"] as? String == reason,
              body["expected_source_git_sha"] as? String == source,
              let failureSource = body["failure_source_git_sha"] as? String, isGitSHA(failureSource),
              failureSource == source || failureSource == "2d5b75430ac152da7b03c0e4f0edb18b1a9ac5f2" || failureSource == fullOperatorAbortSource,
              body["expected_process_id"] as? String == process,
              let archiveSHA = body["results_zip_sha256"] as? String, isSHA256(archiveSHA),
              let reportSHA = body["report_sha256"] as? String, isSHA256(reportSHA),
              let correctionSHA = body["correction_sha256"] as? String, isSHA256(correctionSHA),
              let marker = defaults.dictionary(forKey: key),
              let expected = body["expected_interruption"] as? [String: Any], equal(marker, expected),
              marker["context"] as? Int == 16384, marker["batch"] as? Int == 8,
              marker["ubatch"] as? Int == 8, marker["kv_k"] as? String == "Q8_0",
              marker["kv_v"] as? String == "Q8_0", [64, 320].contains(marker["flags"] as? Int ?? -1),
              marker["flash_attention"] as? Bool == true, marker["sequence_max"] as? Int == 1,
              marker["kv_reuse"] as? Bool == false,
              let interruption = marker["interruption_id"] as? String, UUID(uuidString: interruption) != nil,
              let runtime, runtime["context"] as? Int == 16384,
              runtime["batch"] as? Int == 8, runtime["ubatch"] as? Int == 8,
              runtime["kv_k"] as? String == "Q8_0", runtime["kv_v"] as? String == "Q8_0",
              runtime["kv_policy"] as? String == "Q8_0",
              runtime["kv_observation_source"] as? String == "allocated_native_kv_tensors",
              runtime["kv_unified"] as? Bool == true,
              let identity = runtime["model_identity"] as? [String: Any],
              identity["sha256"] as? String == "53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3",
              let readAudit else { throw Failure.acknowledgementRejected }

        var operatorCorrection: [String: Any]?
        if failureSource == fullOperatorAbortSource {
            let requiredStatement = "这个中断是用户发起的，原因是丧失了实际的使用性，600秒了prefill仅仅只完成了40%左右。"
            guard let correction = body["operator_correction"] as? [String: Any],
                  correction["schema"] as? String == "bonsai-q8-operator-abort-correction-v1",
                  correction["operator_initiated"] as? Bool == true,
                  correction["outcome"] as? String == "OPERATOR_ABORTED_UNUSABLE_PREFILL",
                  correction["elapsed_seconds_approx"] as? Int == 600,
                  correction["prefill_progress_percent_approx"] as? Int == 40,
                  correction["user_statement"] as? String == requiredStatement,
                  correction["marker_interruption_id"] as? String == (marker["interruption_id"] as? String),
                  correction["operator_acknowledgement_token"] as? String == "ACKNOWLEDGE PRESERVED FAILED Q8",
                  correction["failure_source_git_sha"] as? String == fullOperatorAbortSource,
                  correction["failure_build_number"] as? String == "126",
                  correction["model_sha256"] as? String == (identity["sha256"] as? String),
                  let failureCapabilitiesHash = body["failure_capabilities_sha256"] as? String, isSHA256(failureCapabilitiesHash),
                  let phaseReportHash = body["phase_report_sha256"] as? String, isSHA256(phaseReportHash) else {
                throw Failure.acknowledgementRejected
            }
            operatorCorrection = correction
        } else if body["operator_correction"] != nil || body["failure_capabilities_sha256"] != nil || body["phase_report_sha256"] != nil {
            throw Failure.acknowledgementRejected
        }

        let auditFields: [String: Any] = ["operator_reason":reason, "source_git_sha":source,
            "process_id":process, "failure_source_git_sha":failureSource, "acknowledged_marker":marker, "results_zip_sha256":archiveSHA,
            "report_sha256":reportSHA, "correction_sha256":correctionSHA]
        var completeAuditFields = auditFields
        if let operatorCorrection {
            completeAuditFields["operator_correction"] = operatorCorrection
            completeAuditFields["failure_capabilities_sha256"] = body["failure_capabilities_sha256"]
            completeAuditFields["phase_report_sha256"] = body["phase_report_sha256"]
        }
        let audit = try saveAudit("operator_acknowledged_q8_interruption", completeAuditFields)
        guard !audit.isEmpty, let report = try readAudit(audit),
              let fields = report["operator_acknowledgement"] as? [String: Any], equal(fields, completeAuditFields),
              let latest = defaults.dictionary(forKey: key), equal(latest, marker) else {
            throw Failure.acknowledgementRejected
        }
        // The old result archive remains untouched; its marker is copied into a durable audit before unquarantining.
        defaults.removeObject(forKey: key)
        return audit
    }

    private static func isGitSHA(_ value: String) -> Bool {
        value.utf8.count == 40 && value.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) || (65...70).contains($0) }
    }

    private static func isSHA256(_ value: String) -> Bool {
        value.count == 64 && value.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) || (65...70).contains($0) }
    }
}
