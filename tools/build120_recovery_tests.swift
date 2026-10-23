import Foundation

@main struct APICancelRecoveryTests {
    static func main() throws {
        let input = try Data(contentsOf: URL(fileURLWithPath: "tools/fixtures/build120_cancel_evidence.json"))
        let proof = try JSONSerialization.jsonObject(with: input) as! [String: Any]
        let marker = proof["acknowledged_marker"] as! [String: Any]
        let suite = "Build120-" + UUID().uuidString
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = try DiagnosticStore(root: root)
        let source = String(repeating: "b", count: 40)
        let body: [String: Any] = ["reason": "operator_confirmed_api_cancel", "expected_source_git_sha": source,
            "expected_process_id": "new-process", "expected_interruption": marker, "api_cancel_evidence": proof]
        let legacy: [String: Any] = ["batch": 16, "flags": 0]
        defaults.set(legacy, forKey: "BonsaiBenchmarkInterrupted")
        func reset() { defaults.set(marker, forKey: BenchmarkInterruptionRecovery.key) }
        func read(_ id: String) throws -> [String: Any]? { try store.read(id: id)?.mapValues(\.foundation) }
        func save(_ reason: String, _ fields: [String: Any]) throws -> String {
            precondition(reason == "operator_confirmed_api_cancel")
            try store.save(id: "SNAPSHOT_test", report: ["operator_acknowledgement": .from(fields)])
            return "SNAPSHOT_test"
        }
        reset()
        let id = try BenchmarkInterruptionRecovery.acknowledge(defaults: defaults, source: source, process: "new-process",
            body: body, readAudit: read, saveAudit: save)
        precondition(id == "SNAPSHOT_test" && defaults.dictionary(forKey: BenchmarkInterruptionRecovery.key) == nil)
        precondition(NSDictionary(dictionary: defaults.dictionary(forKey: "BonsaiBenchmarkInterrupted")!).isEqual(to: legacy))
        var badBodies: [[String: Any]] = []
        for key in ["reason", "expected_source_git_sha", "expected_process_id", "api_cancel_evidence", "expected_interruption"] {
            var bad = body; bad[key] = "wrong"; badBodies.append(bad)
        }
        var changedProof = proof
        var cancelled = proof["cancel"] as! [String: Any]; cancelled["cancelled"] = false
        changedProof["cancel"] = cancelled
        var bad = body; bad["api_cancel_evidence"] = changedProof; badBodies.append(bad)
        cancelled["cancelled"] = 1; changedProof["cancel"] = cancelled
        bad["api_cancel_evidence"] = changedProof; badBodies.append(bad)
        var missingID = marker; missingID.removeValue(forKey: "interruption_id")
        bad = body; bad["expected_interruption"] = missingID; badBodies.append(bad)
        for badBody in badBodies {
            reset()
            do {
                _ = try BenchmarkInterruptionRecovery.acknowledge(defaults: defaults, source: source, process: "new-process",
                    body: badBody, readAudit: read) { _, _ in preconditionFailure("invalid proof saved") }
                preconditionFailure("invalid proof accepted")
            } catch { precondition(defaults.dictionary(forKey: BenchmarkInterruptionRecovery.key) != nil) }
        }
        enum Failure: Error { case disk }
        for mode in ["save", "read", "mismatch", "changed_marker"] {
            reset()
            do {
                _ = try BenchmarkInterruptionRecovery.acknowledge(defaults: defaults, source: source, process: "new-process",
                    body: body, readAudit: { _ in
                        if mode == "read" { throw Failure.disk }
                        if mode == "mismatch" { return [:] }
                        return try read("SNAPSHOT_test")
                    }) { reason, fields in
                        if mode == "save" { throw Failure.disk }
                        let saved = try save(reason, fields)
                        if mode == "changed_marker" {
                            var other = marker; other["interruption_id"] = UUID().uuidString
                            defaults.set(other, forKey: BenchmarkInterruptionRecovery.key)
                        }
                        return saved
                    }
                preconditionFailure("failure removed quarantine")
            } catch { precondition(defaults.dictionary(forKey: BenchmarkInterruptionRecovery.key) != nil) }
        }
        print("Build120 API cancellation validation, real audit readback, marker race and B16 retention: PASS")
    }
}
