import Foundation

@main struct DiagnosticTests {
    static func require(_ check: @autoclosure () throws -> Bool) rethrows {
        let result = try check(); precondition(result)
    }
    static func main() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = try DiagnosticStore(root: root, maxReports: 2, byteLimit: 1_048_576)
        enum SimulatedFailure: Error { case diskFull }
        let journalURL = root.appendingPathComponent("session.json")
        let original = Data("previous-session-evidence".utf8)
        try original.write(to: journalURL)
        let journal = DiagnosticSessionJournal(url: journalURL)
        do { try journal.recover { throw SimulatedFailure.diskFull } } catch {}
        do {
            try journal.write(Data("new-session".utf8))
            preconditionFailure("failed recovery must block new checkpoint writes")
        } catch DiagnosticSessionJournal.JournalError.recoveryPending {}
        try require(try Data(contentsOf: journalURL) == original)
        journal.recover {}
        try journal.write(Data("recovered-new-session".utf8))
        try require(try Data(contentsOf: journalURL) == Data("recovered-new-session".utf8))
        for n in 0..<3 {
            let id = "SNAPSHOT_\(n)"
            try store.save(id: id, report: ["schema_version": .number(2), "executive_summary": .object(["crash_type": .string("synthetic")])])
        }
        try require(try store.list().count == 2)
        precondition(!DiagnosticStore.validID("../escape"))
        precondition(!DiagnosticStore.validID("CRASH_x/../../escape"))
        try require(try store.read(id: "SNAPSHOT_2")?["schema_version"] == .number(2))
        let oldReport = root.appendingPathComponent("CrashReports/CRASH_legacy.json")
        try Data("{\"api_key\":\"PRIVATE\",\"executive_summary\":{\"crash_type\":\"synthetic\"}}".utf8).write(to: oldReport)
        try require(try store.read(id: "CRASH_legacy")?["api_key"] == nil)
        try require(try store.markdown(id: "CRASH_legacy")?.contains("PRIVATE") == false)
        try store.delete(id: "CRASH_legacy")
        try require(try store.markdown(id: "SNAPSHOT_2")?.contains("synthetic") == true)
        let clean = DiagnosticPrivacy.clean(["api_key": .string("SECRET"), "request_id": .string("safe"),
            "details": .object(["prompt": .string("PRIVATE"), "count": .number(5)])])
        precondition(clean["api_key"] == nil && clean["request_id"] == .string("safe"))
        precondition(clean["details"] == .object(["count": .number(5)]))
        let bad = root.appendingPathComponent("CrashReports/CRASH_bad.json")
        try Data("broken".utf8).write(to: bad)
        try require(try store.list().count == 2)
        try store.delete(id: "SNAPSHOT_2")
        try require(try store.read(id: "SNAPSHOT_2") == nil)
        for enabled in [false, true] { for api in [false, true] { for benchmark in [false, true] {
            precondition(ScreenOnPolicy.active(enabled: enabled, api: api, benchmark: benchmark) == (enabled && (api || benchmark)))
        } } }
        precondition(HealthPolicy.warnings(availableMB: 499, thermal: 2, speed: 6.9, baseline: 10).count == 3)
        precondition(HealthPolicy.warnings(availableMB: 500, thermal: 1, speed: 7, baseline: 10).isEmpty)
        precondition(HealthPolicy.warnings(availableMB: nil, thermal: 0, speed: 1, baseline: 0).isEmpty)
        print("Build117 diagnostic storage, privacy, health and screen policies: PASS")
    }
}
