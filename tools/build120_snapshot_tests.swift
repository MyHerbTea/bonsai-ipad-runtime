import Foundation

@main struct SnapshotTests {
    static func main() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = try DiagnosticStore(root: root)
        let audit: [String: DiagnosticValue] = ["operator_reason": .string("operator_confirmed_api_cancel"),
            "source_git_sha": .string(String(repeating: "a", count: 40))]
        try store.save(id: "SNAPSHOT_old", report: ["operator_acknowledgement": .object(audit)])
        let json = DiagnosticSnapshotAPI.handle(store: store, method: "GET", path: "/debug/snapshots/SNAPSHOT_old")
        precondition(json.0 == 200)
        let decoded = try JSONDecoder().decode([String: DiagnosticValue].self, from: json.2)
        precondition(decoded["operator_acknowledgement"] == .object(audit))
        let md = DiagnosticSnapshotAPI.handle(store: store, method: "GET", path: "/debug/snapshots/SNAPSHOT_old/markdown")
        precondition(md.0 == 200 && String(data: md.2, encoding: .utf8)!.contains("operator_confirmed_api_cancel"))
        for method in ["DELETE", "POST", "PUT"] {
            precondition(DiagnosticSnapshotAPI.handle(store: store, method: method, path: "/debug/snapshots/SNAPSHOT_old").0 == 405)
        }
        for path in ["/debug/snapshots", "/debug/snapshots/CRASH_old", "/debug/snapshots/SNAPSHOT_x/../../escape", "/debug/snapshots/SNAPSHOT_old/extra", "/debug/snapshots//SNAPSHOT_old", "/debug/snapshots/SNAPSHOT_old/"] {
            precondition(DiagnosticSnapshotAPI.handle(store: store, method: "GET", path: path).0 == 400)
        }
        precondition(DiagnosticSnapshotAPI.handle(store: store, method: "GET", path: "/debug/snapshots/SNAPSHOT_missing").0 == 404)
        precondition(try store.read(id: "SNAPSHOT_old") != nil)
        print("Build120 real snapshot JSON/Markdown export and read-only routing: PASS")
    }
}
