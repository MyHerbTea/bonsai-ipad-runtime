import Foundation

@main struct Build128Q8OperatorAbortTests {
    static let source = String(repeating: "f", count: 40)
    static let failedSource = "2b4daf44ff9f8b7d2bb30f9831c53938fc7bd158"
    static let model = "53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3"
    static let process = UUID().uuidString
    static let marker: [String: Any] = ["context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0",
        "flags":64,"flash_attention":true,"sequence_max":1,"kv_reuse":false,"interruption_id":"00000000-0000-4000-8000-000000000128"]
    static let runtime: [String: Any] = ["context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0",
        "kv_observation_source":"allocated_native_kv_tensors","kv_policy":"Q8_0","kv_unified":true,
        "model_identity":["sha256":model]]
    static let correction: [String: Any] = [
        "schema":"bonsai-q8-operator-abort-correction-v1", "operator_initiated":true,
        "outcome":"OPERATOR_ABORTED_UNUSABLE_PREFILL", "elapsed_seconds_approx":600,
        "prefill_progress_percent_approx":40,
        "user_statement":"这个中断是用户发起的，原因是丧失了实际的使用性，600秒了prefill仅仅只完成了40%左右。",
        "marker_interruption_id":"00000000-0000-4000-8000-000000000128",
        "operator_acknowledgement_token":"ACKNOWLEDGE PRESERVED FAILED Q8",
        "failure_source_git_sha":failedSource, "failure_build_number":"126", "model_sha256":model]

    static func defaults() -> UserDefaults {
        let suite = "build128-q8-operator-abort-\(UUID().uuidString)"
        let store = UserDefaults(suiteName:suite)!
        store.removePersistentDomain(forName:suite)
        return store
    }
    static func payload(includeCorrection: Bool = true, correction: [String: Any]? = nil) -> [String: Any] {
        var body: [String: Any] = ["reason":"operator_reviewed_preserved_failed_result",
            "expected_source_git_sha":source,"failure_source_git_sha":failedSource,"expected_process_id":process,
            "expected_interruption":marker,"results_zip_sha256":String(repeating:"b",count:64),
            "report_sha256":String(repeating:"c",count:64),"correction_sha256":String(repeating:"d",count:64),
            "failure_capabilities_sha256":String(repeating:"e",count:64),"phase_report_sha256":String(repeating:"a",count:64)]
        if includeCorrection { body["operator_correction"] = correction ?? Self.correction }
        return body
    }
    static func expectRejected(_ body: [String: Any], _ label: String) {
        let store = defaults(); store.set(marker,forKey:"BonsaiQ8BaselineInterrupted")
        do {
            _ = try BenchmarkInterruptionRecovery.acknowledgeQ8(defaults:store,source:source,process:process,
                body:body,runtime:runtime,readAudit:{ _ in nil },saveAudit:{ _,_ in "should-not-save" })
            preconditionFailure("accepted: \(label)")
        } catch { }
        precondition(store.dictionary(forKey:"BonsaiQ8BaselineInterrupted") != nil,"rejection preserves Q8 marker")
    }
    static func main() throws {
        let store = defaults(); store.set(marker,forKey:"BonsaiQ8BaselineInterrupted")
        var saved: [String: Any]?
        let body = payload()
        let audit = try BenchmarkInterruptionRecovery.acknowledgeQ8(defaults:store,source:source,process:process,
            body:body,runtime:runtime,readAudit:{ _ in saved.map { ["operator_acknowledgement":$0] } },
            saveAudit:{ _,fields in saved=fields; return "audit-full-abort" })
        precondition(audit == "audit-full-abort")
        precondition(store.dictionary(forKey:"BonsaiQ8BaselineInterrupted") == nil)
        precondition(BenchmarkInterruptionRecovery.equal(saved?["operator_correction"] as? [String: Any] ?? [:],correction))
        precondition(saved?["failure_capabilities_sha256"] as? String == String(repeating:"e",count:64))

        expectRejected(payload(includeCorrection:false),"full operator abort requires correction")
        var wrongElapsed = correction; wrongElapsed["elapsed_seconds_approx"] = 599
        expectRejected(payload(correction:wrongElapsed),"operator timing is fixed to the reported observation")
        var wrongReason = correction; wrongReason["user_statement"] = "different statement"
        expectRejected(payload(correction:wrongReason),"operator statement is preserved exactly")
        var wrongEvidence = payload(); wrongEvidence["phase_report_sha256"] = "bad"
        expectRejected(wrongEvidence,"phase report digest is required")
        print("Q8 Full operator abort: accepted exact Build126 correction; 4 rejection cases PASS")
    }
}
