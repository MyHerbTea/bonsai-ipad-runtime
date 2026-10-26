import Foundation

@main struct Build126Q8InterruptionRecoveryTests {
    static let source = String(repeating: "f", count: 40)
    static let predecessor = "2d5b75430ac152da7b03c0e4f0edb18b1a9ac5f2"
    static let process = UUID().uuidString
    static let marker: [String: Any] = ["context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0",
        "flags":64,"flash_attention":true,"sequence_max":1,"kv_reuse":false,"interruption_id":UUID().uuidString]
    static let runtime: [String: Any] = ["context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0",
        "kv_observation_source":"allocated_native_kv_tensors","kv_policy":"Q8_0","kv_unified":true,
        "model_identity":["sha256":"53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3"]]

    static func defaults() -> UserDefaults {
        let suite = "build126-q8-recovery-\(UUID().uuidString)"
        let store = UserDefaults(suiteName:suite)!
        store.removePersistentDomain(forName:suite)
        return store
    }
    static func payload(marker: [String: Any]? = nil, source: String? = nil, process: String? = nil) -> [String: Any] {
        ["reason":"operator_reviewed_preserved_failed_result",
         "expected_source_git_sha":source ?? self.source,"failure_source_git_sha":predecessor,"expected_process_id":process ?? self.process,
         "expected_interruption":marker ?? self.marker,"results_zip_sha256":String(repeating:"b",count:64),
         "report_sha256":String(repeating:"c",count:64),"correction_sha256":String(repeating:"d",count:64)]
    }
    static func expectRejected(_ work: () throws -> Void, _ message: String) {
        do { try work(); preconditionFailure("accepted: \(message)") } catch { }
    }
    static func rejectedCase(_ modify: ([String: Any]) -> [String: Any], _ label: String, runtime: [String: Any]? = nil) {
        let store = defaults(); store.set(marker, forKey:"BonsaiQ8BaselineInterrupted")
        let request = modify(payload())
        expectRejected({
            _ = try BenchmarkInterruptionRecovery.acknowledgeQ8(defaults:store,source:source,process:process,
                body:request,runtime:runtime ?? self.runtime,readAudit:{ _ in ["operator_acknowledgement":request] },
                saveAudit:{ _,_ in "audit" })
        }, label)
        precondition(store.dictionary(forKey:"BonsaiQ8BaselineInterrupted") != nil,"rejection preserves marker: \(label)")
    }
    static func main() throws {
        let store = defaults(); store.set(marker, forKey:"BonsaiQ8BaselineInterrupted")
        let oldQuick: [String: Any] = ["context":16384,"batch":8,"kv":"Q4_0"]
        store.set(oldQuick,forKey:"BonsaiQuickPrefillInterrupted")
        var saved: [String: Any]?
        let audit = try BenchmarkInterruptionRecovery.acknowledgeQ8(defaults:store,source:source,process:process,
            body:payload(),runtime:runtime,readAudit:{ id in id == "audit-1" ? ["operator_acknowledgement":saved!] : nil },
            saveAudit:{ _,fields in saved=fields; return "audit-1" })
        precondition(audit == "audit-1")
        precondition(store.dictionary(forKey:"BonsaiQ8BaselineInterrupted") == nil)
        precondition(BenchmarkInterruptionRecovery.equal(store.dictionary(forKey:"BonsaiQuickPrefillInterrupted")!,oldQuick))
        precondition(saved?["results_zip_sha256"] as? String == String(repeating:"b",count:64))

        rejectedCase({ var x=$0; x.removeValue(forKey:"results_zip_sha256"); return x },"requires result archive hash")
        rejectedCase({ var x=$0; x["expected_process_id"]="stale"; return x },"rejects stale process")
        rejectedCase({ var x=$0; x["correction_sha256"]="bad"; return x },"rejects malformed correction hash")
        rejectedCase({ var x=$0; x["failure_source_git_sha"]="bad"; return x },"rejects invalid failed source SHA")
        var wrongRuntime=runtime; wrongRuntime["kv_k"]="Q4_0"
        rejectedCase({ $0 },"requires observed Q8 runtime",runtime:wrongRuntime)
        let readbackStore=defaults(); readbackStore.set(marker,forKey:"BonsaiQ8BaselineInterrupted")
        expectRejected({
            _ = try BenchmarkInterruptionRecovery.acknowledgeQ8(defaults:readbackStore,source:source,process:process,
                body:payload(),runtime:runtime,readAudit:{ _ in nil },saveAudit:{ _,_ in "audit-missing-readback" })
        },"requires audit readback")
        precondition(readbackStore.dictionary(forKey:"BonsaiQ8BaselineInterrupted") != nil)
        let mismatchStore=defaults(); mismatchStore.set(marker,forKey:"BonsaiQ8BaselineInterrupted")
        expectRejected({
            _ = try BenchmarkInterruptionRecovery.acknowledgeQ8(defaults:mismatchStore,source:source,process:process,
                body:payload(),runtime:runtime,readAudit:{ _ in ["operator_acknowledgement":["wrong":true]] },saveAudit:{ _,_ in "audit-wrong-readback" })
        },"requires matching audit readback")
        precondition(mismatchStore.dictionary(forKey:"BonsaiQ8BaselineInterrupted") != nil)
        let saveStore=defaults(); saveStore.set(marker,forKey:"BonsaiQ8BaselineInterrupted")
        expectRejected({
            _ = try BenchmarkInterruptionRecovery.acknowledgeQ8(defaults:saveStore,source:source,process:process,
                body:payload(),runtime:runtime,readAudit:{ _ in nil },saveAudit:{ _,_ in "" })
        },"requires durable audit")
        precondition(saveStore.dictionary(forKey:"BonsaiQ8BaselineInterrupted") != nil)
        print("Build126 Q8 interruption recovery: 9 cases PASS")
    }
}
