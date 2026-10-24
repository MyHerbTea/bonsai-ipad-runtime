import Foundation

/// An operator statement bound to retained files, not a signed server cancellation receipt.
struct BenchmarkCancellationEvidence: Decodable {
    struct State: Decodable {
        let session_id: String?
        let request_id: String
        let active: Bool
        let running: Bool
        let cancelled: Bool
        let ordinary_requests: Int
    }
    struct Model: Decodable, Equatable { let sha256: String; let size_bytes: Int64 }
    struct Runtime: Decodable, Equatable {
        let context: Int, batch: Int, ubatch: Int, gpu_layers: Int, sequence_max: Int
        let threads: Int, threads_batch: Int
        let kv_k: String, kv_v: String
        let mmap: Bool, text_kv_reuse: Bool, flash_attention: Bool, kv_unified: Bool
        let offload_kqv: Bool, op_offload: Bool, swa_full: Bool
        let model_identity: Model
        var production: Bool {
            context == 16384 && batch == 8 && ubatch == 8 && sequence_max == 1 && gpu_layers > 0 &&
            kv_k == "Q4_0" && kv_v == "Q4_0" && mmap && !text_kv_reuse && flash_attention &&
            threads > 0 && threads_batch > 0 &&
            model_identity.sha256 == "53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3" &&
            model_identity.size_bytes == 5946648928
        }
    }
    struct Identity: Decodable {
        let source_git_sha: String, process_id: String, build_number: String
        let native_context: Runtime?
    }
    struct Observation: Decodable { let state: State; let evidence: Identity }
    let schema: String, provenance: String, report_status: String, restoration: String
    let before: Observation, cancel: State, after: Observation
    let original_runtime: Runtime
    let files_sha256: [String: String]

    static func decode<T: Decodable>(_ value: [String: Any], as type: T.Type) throws -> T {
        try JSONDecoder().decode(type, from: JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]))
    }
    static func hex(_ value: String, count: Int) -> Bool {
        value.count == count && value.allSatisfy { "0123456789abcdef".contains($0) }
    }
    static func validate(_ fields: [String: Any], marker: [String: Any], runtime: [String: Any]?) throws {
        let proof = try decode(fields, as: Self.self)
        let a = proof.before, c = proof.cancel, z = proof.after
        guard let proofMarker = fields["acknowledged_marker"] as? [String: Any],
              BenchmarkInterruptionRecovery.equal(proofMarker, marker),
              let afterFields = fields["after"] as? [String: Any],
              let afterState = afterFields["state"] as? [String: Any], afterState["session_id"] is NSNull,
              let runtime, let actual = try? decode(runtime, as: Runtime.self),
              proof.schema == "bonsai-operator-api-cancel-v1",
              proof.provenance == "operator_supplied_files_not_server_receipt",
              proof.report_status == "INCOMPLETE", proof.restoration == "RESTORED",
              hex(a.evidence.source_git_sha, count: 40), UUID(uuidString: a.evidence.process_id) != nil,
              !a.evidence.build_number.isEmpty, a.evidence.build_number.allSatisfy({ $0.isASCII && $0.isNumber }),
              a.evidence.source_git_sha == z.evidence.source_git_sha,
              a.evidence.process_id == z.evidence.process_id, a.evidence.build_number == z.evidence.build_number,
              let session = a.state.session_id, UUID(uuidString: session) != nil,
              !a.state.request_id.isEmpty, a.state.request_id.utf8.count <= 128,
              a.state.request_id.allSatisfy({ $0.isASCII && ($0.isLetter || $0.isNumber || "_-".contains($0)) }),
              a.state.active, a.state.running, !a.state.cancelled, a.state.ordinary_requests == 0,
              c.session_id == session, c.request_id == a.state.request_id,
              c.active, c.running, c.cancelled, c.ordinary_requests == 0,
              !z.state.active, !z.state.running, !z.state.cancelled,
              z.state.session_id == nil, z.state.ordinary_requests == 0,
              proof.original_runtime.production, z.evidence.native_context == proof.original_runtime,
              actual == proof.original_runtime,
              Set(proof.files_sha256.keys) == Set(["before", "cancel", "after", "report"]),
              proof.files_sha256.values.allSatisfy({ hex($0, count: 64) }) else {
            throw BenchmarkInterruptionRecovery.Failure.acknowledgementRejected
        }
    }
}
