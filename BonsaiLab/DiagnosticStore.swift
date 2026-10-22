import Foundation

/// Caller serializes access. JSON is the source of truth; Markdown is derived.
final class DiagnosticStore {
    let root: URL
    private let maxReports: Int
    private let byteLimit: Int
    private let encoder: JSONEncoder = {
        let e = JSONEncoder(); e.outputFormatting = [.prettyPrinted, .sortedKeys]; return e
    }()
    enum StoreError: Error { case invalidID, oversized, unsafeFile }
    init(root: URL, maxReports: Int = 50, byteLimit: Int = 100 * 1024 * 1024) throws {
        self.root = root.resolvingSymlinksInPath(); self.maxReports = maxReports; self.byteLimit = byteLimit
        for dir in ["CrashReports", "Diagnostics"] {
            try FileManager.default.createDirectory(at: root.appendingPathComponent(dir), withIntermediateDirectories: true)
        }
    }
    static func validID(_ id: String) -> Bool {
        (id.hasPrefix("CRASH_") || id.hasPrefix("SNAPSHOT_")) && id.count <= 96 && id.unicodeScalars.allSatisfy {
            CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-").contains($0)
        }
    }
    private func file(_ id: String, _ ext: String) throws -> URL {
        guard Self.validID(id) else { throw StoreError.invalidID }
        let dir = root.appendingPathComponent(id.hasPrefix("CRASH_") ? "CrashReports" : "Diagnostics")
        let url = dir.appendingPathComponent(id).appendingPathExtension(ext)
        guard !((try? url.resourceValues(forKeys: [.isSymbolicLinkKey]))?.isSymbolicLink ?? false),
              dir.resolvingSymlinksInPath().standardizedFileURL == dir.standardizedFileURL else { throw StoreError.unsafeFile }
        return url
    }
    func save(id: String, report: [String: DiagnosticValue]) throws {
        let json = try file(id, "json")
        let clean = DiagnosticPrivacy.clean(report)
        let data = try encoder.encode(clean)
        guard data.count <= min(byteLimit / 2, 4 * 1024 * 1024) else { throw StoreError.oversized }
        try prune(reserving: data.count * 2)
        try data.write(to: json, options: .atomic)
        let text = try renderMarkdown(id: id, report: clean)
        try text.write(to: file(id, "md"), atomically: true, encoding: .utf8)
        try prune(reserving: 0)
    }
    func read(id: String) throws -> [String: DiagnosticValue]? {
        let url = try file(id, "json")
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
        guard size <= 4 * 1024 * 1024 else { throw StoreError.oversized }
        return DiagnosticPrivacy.clean(try JSONDecoder().decode([String: DiagnosticValue].self, from: Data(contentsOf: url)))
    }
    func markdown(id: String) throws -> String? {
        guard let report = try read(id: id) else { return nil }
        return try renderMarkdown(id: id, report: report)
    }
    private func renderMarkdown(id: String, report: [String: DiagnosticValue]) throws -> String {
        var text = "# Diagnostic Report: \(id)\n\nFacts are observations; hypotheses require verification. Null means unavailable.\n\n"
        for (key, title) in [("executive_summary", "Executive Summary"), ("device_info", "Device"),
            ("app_state", "Application State"), ("memory_state", "Resource Snapshot"),
            ("stack_trace", "Stack Evidence and Symbolication"), ("operation_timeline", "Operation Timeline"),
            ("breadcrumbs", "Breadcrumbs"), ("recent_errors", "Recent Errors"),
            ("performance_snapshot", "Performance"), ("kernel_statistics", "Kernel Statistics"),
            ("configuration", "Configuration"), ("ai_analysis", "Hypotheses and Verification")] {
            let data = try encoder.encode(report[key] ?? .null)
            text += "## \(title)\n\n```json\n" + (String(data: data, encoding: .utf8) ?? "null") + "\n```\n\n"
        }
        return text + "Full source: `\(id).json`\n"
    }
    func list(crashesOnly: Bool = false) throws -> [[String: DiagnosticValue]] {
        try files().compactMap { url in
            let id = url.deletingPathExtension().lastPathComponent
            if crashesOnly && !id.hasPrefix("CRASH_") { return nil }
            guard let report = try? read(id: id) else { return nil }
            return ["crash_id": .string(id), "timestamp": report["timestamp"] ?? .null,
                    "summary": report["executive_summary"] ?? .null,
                    "files": .object(["json": .string("\(id).json"), "markdown": .string("\(id).md")])]
        }
    }
    func delete(id: String) throws {
        for ext in ["json", "md"] {
            let url = try file(id, ext)
            if FileManager.default.fileExists(atPath: url.path) { try FileManager.default.removeItem(at: url) }
        }
    }
    private func files() throws -> [URL] {
        try ["CrashReports", "Diagnostics"].flatMap { dir in
            try FileManager.default.contentsOfDirectory(at: root.appendingPathComponent(dir), includingPropertiesForKeys: [.contentModificationDateKey, .fileSizeKey, .isSymbolicLinkKey])
        }.filter { $0.pathExtension == "json" && Self.validID($0.deletingPathExtension().lastPathComponent) }
            .sorted { a, b in
                let x = (try? a.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate ?? .distantPast
                let y = (try? b.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate ?? .distantPast
                return x == y ? a.lastPathComponent < b.lastPathComponent : x < y
            }
    }
    private func prune(reserving: Int) throws {
        var urls = try files()
        var total = urls.reduce(0) { sum, url in
            sum + ((try? url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0)
                + ((try? url.deletingPathExtension().appendingPathExtension("md").resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0)
        }
        var counts = Dictionary(grouping: urls, by: { $0.deletingPathExtension().lastPathComponent.hasPrefix("CRASH_") }).mapValues(\.count)
        while let index = urls.firstIndex(where: { url in
            total + reserving > byteLimit || counts[url.lastPathComponent.hasPrefix("CRASH_"), default: 0] > maxReports
        }) {
            let url = urls.remove(at: index)
            let bytes = ((try? url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0)
                + ((try? url.deletingPathExtension().appendingPathExtension("md").resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0)
            try delete(id: url.deletingPathExtension().lastPathComponent)
            total -= bytes; counts[url.lastPathComponent.hasPrefix("CRASH_"), default: 0] -= 1
        }
    }
}
