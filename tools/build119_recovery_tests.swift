import Foundation

@main struct RecoveryTests {
    static func main() throws {
        let suite="Build119-"+UUID().uuidString
        let defaults=UserDefaults(suiteName:suite)!
        defer { defaults.removePersistentDomain(forName:suite) }
        var quick=BenchmarkSessionMode.quickPrefill.initial.json
        quick["interruption_id"] = "12345678-1234-1234-1234-123456789012"
        let source = String(repeating: "a", count: 40)
        let legacy=BenchmarkSessionMode.full.initial.json
        defaults.set(quick,forKey:BenchmarkInterruptionRecovery.key)
        defaults.set(legacy,forKey:"BonsaiBenchmarkInterrupted")
        let body:[String:Any]=["reason":"manual_forced_exit","expected_source_git_sha":source, "expected_process_id":"process", "expected_interruption":quick]
        for key in ["reason","expected_source_git_sha","expected_process_id","expected_interruption"] {
            var invalid=body;invalid[key]="wrong"
            do {
                _ = try BenchmarkInterruptionRecovery.acknowledge(defaults:defaults,source:source,process:"process",body:invalid) { _, _ in preconditionFailure("invalid acknowledgement saved") }
                preconditionFailure("invalid acknowledgement accepted")
            } catch { precondition(defaults.dictionary(forKey:BenchmarkInterruptionRecovery.key) != nil) }
        }
        var newer = quick; newer["interruption_id"] = "newer-fault"
        defaults.set(newer,forKey:BenchmarkInterruptionRecovery.key)
        do {
            _ = try BenchmarkInterruptionRecovery.acknowledge(defaults:defaults,source:source,process:"process",body:body) { _, _ in preconditionFailure("stale marker audited") }
            preconditionFailure("stale marker acknowledged")
        } catch {}
        defaults.set(quick,forKey:BenchmarkInterruptionRecovery.key)
        enum DiskFailure: Error {case failed}
        do {
            _ = try BenchmarkInterruptionRecovery.acknowledge(defaults:defaults,source:source,process:"process",body:body) { _, _ in throw DiskFailure.failed }
            preconditionFailure("audit failure ignored")
        } catch { precondition(defaults.dictionary(forKey:BenchmarkInterruptionRecovery.key) != nil) }
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = try DiagnosticStore(root: root)
        let failingStore = try DiagnosticStore(root: root.appendingPathComponent("tiny"), byteLimit: 2)
        do {
            _ = try BenchmarkInterruptionRecovery.acknowledge(defaults:defaults,source:source,process:"process",body:body) { _, fields in
                try failingStore.save(id: "SNAPSHOT_failure", report: ["operator_acknowledgement": .from(fields)])
                return "SNAPSHOT_failure"
            }
            preconditionFailure("real store failure ignored")
        } catch { precondition(defaults.dictionary(forKey:BenchmarkInterruptionRecovery.key) != nil) }
        let id=try BenchmarkInterruptionRecovery.acknowledge(defaults:defaults,source:source,process:"process",body:body) { reason, fields in
            precondition(defaults.dictionary(forKey:BenchmarkInterruptionRecovery.key) != nil)
            precondition(reason.contains("operator_confirmed_manual_forced_exit"))
            precondition(fields["source_git_sha"] as? String == source)
            try store.save(id: "SNAPSHOT_test", report: ["operator_acknowledgement": .from(fields)])
            let saved = try store.read(id: "SNAPSHOT_test")!
            let audit = saved["operator_acknowledgement"]!.foundation as! [String: Any]
            precondition(audit["source_git_sha"] as? String == source)
            precondition(audit["operator_reason"] as? String == "manual_forced_exit")
            precondition(audit["process_id"] as? String == "process")
            let restored = audit["acknowledged_marker"] as! [String: Any]
            precondition(NSDictionary(dictionary: restored).isEqual(to: quick))
            return "SNAPSHOT_test"
        }
        precondition(id=="SNAPSHOT_test" && defaults.dictionary(forKey:BenchmarkInterruptionRecovery.key)==nil)
        precondition(defaults.dictionary(forKey:"BonsaiBenchmarkInterrupted")?["batch"] as? Int==16)
        let control=BenchmarkSessionControl()
        let session=control.beginSession()!
        precondition(control.beginOperation(session:session,request:"run"))
        control.progress(stage:"PREFILL",completed:8,total:512)
        control.progress(stage:"PREFILL",completed:513,total:512)
        precondition((control.snapshot["progress"] as? [String:Any])?["completed"] as? Int==8)
        control.progress(stage:"DECODE",completed:16,total:256)
        precondition((control.snapshot["progress"] as? [String:Any])?["stage"] as? String=="DECODE")
        control.finishOperation(error:nil);control.endSession(session:session)
        print("Build119 exact audited acknowledgement, failed storage retention and bounded progress: PASS")
    }
}
