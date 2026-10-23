import Foundation
import UIKit
import Darwin

/// All allocations and final report generation happen on a normal serial queue.
final class CrashDiagnostics: @unchecked Sendable {
    static let shared = CrashDiagnostics()
    private let queue = DispatchQueue(label: "bonsai.diagnostics.store", qos: .utility)
    private var store: DiagnosticStore?
    private var support: URL?
    private var journal: DiagnosticSessionJournal?
    private var breadcrumbs: [DiagnosticValue] = []
    private var timeline: [DiagnosticValue] = []
    private var errors: [DiagnosticValue] = []
    private var state: [String: DiagnosticValue] = [:]
    private var performance: [String: DiagnosticValue] = [:]
    private var images: DiagnosticValue = .array([])
    private var lastFlush = 0.0
    private var started = false
    private var session = UUID().uuidString
    private var failure: String?
    private var observers: [NSObjectProtocol] = []

    func start() {
        var didStart = false
        queue.sync {
            guard !started else { return }; started = true
            didStart = true
            do {
                let fm = FileManager.default
                let documents = fm.urls(for: .documentDirectory, in: .userDomainMask)[0]
                store = try DiagnosticStore(root: documents)
                let folder = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("Build117Diagnostics")
                try fm.createDirectory(at: folder, withIntermediateDirectories: true); support = folder
                let journal = DiagnosticSessionJournal(url: folder.appendingPathComponent("session.json"))
                self.journal = journal
                try journal.recover { try recover(folder: folder) }
                let imageJSON = BonsaiCrashBinaryImagesJSON() as String
                if let data = imageJSON.data(using: .utf8), let value = try? JSONDecoder().decode(DiagnosticValue.self, from: data) { images = value }
                state = ["current_operation": .string("APP_STARTED"), "session_id": .string(session)]
                try checkpoint(force: true)
                if !BonsaiCrashInstall(folder.appendingPathComponent("fatal.bin").path) { failure = "signal_capture_unavailable" }
            } catch { failure = "diagnostic_initialization_failed" }
        }
        guard didStart else { return }
        let center = NotificationCenter.default
        observers.append(center.addObserver(forName: UIApplication.didReceiveMemoryWarningNotification, object: nil, queue: .main) { _ in
            Self.shared.recordError(severity: "WARNING", type: "MEMORY_PRESSURE")
        })
        observers.append(center.addObserver(forName: ProcessInfo.thermalStateDidChangeNotification, object: nil, queue: .main) { _ in
            Self.shared.recordTimelineEvent("THERMAL_STATE_CHANGED", details: ["thermal_state": .number(Double(ProcessInfo.processInfo.thermalState.rawValue))])
        })
        HealthMonitor.shared.start()
    }
    private func stamp() -> String { ISO8601DateFormatter().string(from: Date()) }
    private func entry(_ event: String, _ metadata: [String: DiagnosticValue]) -> DiagnosticValue {
        .object(["timestamp": .string(stamp()), "uptime_seconds": .number(ProcessInfo.processInfo.systemUptime),
                 "event": .string(String(event.prefix(96))), "details": .object(DiagnosticPrivacy.clean(metadata))])
    }
    func recordBreadcrumb(_ action: String, metadata: [String: DiagnosticValue] = [:]) {
        queue.async {
            self.breadcrumbs.append(self.entry(action, metadata)); self.breadcrumbs = Array(self.breadcrumbs.suffix(100))
            self.persistSafely(force: false)
        }
    }
    func recordTimelineEvent(_ event: String, details: [String: DiagnosticValue] = [:]) {
        queue.async {
            self.timeline.append(self.entry(event, details)); self.timeline = Array(self.timeline.suffix(200))
            self.persistSafely(force: false)
        }
    }
    func recordError(severity: String, type: String) {
        queue.async {
            self.errors.append(self.entry(type, ["severity": .string(severity)])); self.errors = Array(self.errors.suffix(100))
            self.persistSafely(force: true)
        }
    }
    func updateState(_ fields: [String: DiagnosticValue], force: Bool = false) {
        queue.async {
            self.state.merge(DiagnosticPrivacy.clean(fields)) { _, new in new }
            self.persistSafely(force: force)
        }
    }
    func updatePerformance(_ value: [String: Any]) {
        let clean = DiagnosticPrivacy.clean(value.mapValues(DiagnosticValue.from))
        queue.async { self.performance = clean; self.persistSafely(force: false) }
    }
    private func persistSafely(force: Bool) {
        do { try checkpoint(force: force) } catch { failure = "checkpoint_write_failed" }
    }
    private func checkpoint(force: Bool) throws {
        guard let journal, force || ProcessInfo.processInfo.systemUptime - lastFlush >= 2 else { return }
        let value: [String: DiagnosticValue] = ["schema_version": .number(2), "timestamp": .string(stamp()),
            "app_state": .object(state), "breadcrumbs": .array(breadcrumbs), "operation_timeline": .array(timeline),
            "recent_errors": .array(errors), "binary_images": images, "performance_snapshot": .object(performance),
            "source_git_sha": .string(BonsaiCertificationBuildIdentity.sourceGitSHA),
            "device_info": .from(BenchmarkTelemetry.hardware()), "memory_state": .object(resourceState()),
            "configuration": .object(state), "kernel_statistics": performance["kernel_stats"] ?? .null,
            "app_version": .string(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "unknown")]
        try journal.write(JSONEncoder().encode(value))
        lastFlush = ProcessInfo.processInfo.systemUptime
    }
    private func recover(folder: URL) throws {
        let journal = folder.appendingPathComponent("session.json")
        var record = BonsaiCrashRecord()
        let hasSignal = BonsaiCrashRead(folder.appendingPathComponent("fatal.bin").path, &record)
        let hasJournal = FileManager.default.fileExists(atPath: journal.path)
        guard hasSignal || hasJournal else { return }
        var previous: [String: DiagnosticValue] = [:]
        if hasJournal {
            let size = (try journal.resourceValues(forKeys: [.fileSizeKey])).fileSize ?? 0
            if size < 4 * 1024 * 1024,
               let value = try? JSONDecoder().decode([String: DiagnosticValue].self, from: Data(contentsOf: journal)) {
                previous = value
            } else {
                previous["recovery_error"] = .string("previous_checkpoint_corrupt_or_oversized")
            }
        }
        previous["schema_version"] = .number(2)
        previous["recovered_at"] = .string(stamp())
        previous["timestamp_scope"] = .string("last_checkpoint_not_exact_fatal_time")
        for key in ["timestamp", "app_state", "breadcrumbs", "operation_timeline", "recent_errors", "performance_snapshot", "binary_images"] {
            if previous[key] == nil { previous[key] = .null }
        }
        previous["report_kind"] = .string(hasSignal ? "fatal_signal" : "previous_session_unclean")
        previous["executive_summary"] = .object(["crash_type": .string(hasSignal ? "SIGNAL_\(record.signal_number)" : "unknown_termination"),
            "likely_cause": .null, "ai_analysis_hint": .string("Correlate recorded events with matching UUID system crash logs. Unclean session alone does not prove a crash or OOM.")])
        previous["stack_trace"] = .object(["program_counter": hasSignal ? .string(String(format: "0x%llx", record.program_counter)) : .null,
            "fault_address": hasSignal ? .string(String(format: "0x%llx", record.fault_address)) : .null,
            "all_threads": .null, "symbolication_status": .string("requires_matching_dSYM_and_system_crash_log"),
            "availability": .string("signal_PC_only_full_stack_unavailable")])
        // Resource values belong to the last normal checkpoint, never the new process.
        previous["resource_snapshot_scope"] = .string("last_persisted_pretermination_observation_not_exact_crash_time")
        previous["device_info"] = previous["device_info"] ?? .null
        previous["memory_state"] = previous["memory_state"] ?? .null
        previous["configuration"] = previous["app_state"] ?? .object([:])
        previous["kernel_statistics"] = previous["kernel_statistics"] ?? .null
        previous["ai_analysis"] = analysis()
        let id = "CRASH_" + UUID().uuidString
        previous["crash_id"] = .string(id)
        try store?.save(id: id, report: previous)
        // Only remove checkpoint after final JSON/Markdown successfully saved.
        if hasJournal { try FileManager.default.removeItem(at: journal) }
    }
    private func analysis() -> DiagnosticValue {
        .object(["root_cause_hypothesis": .array([]), "suggested_fixes": .array([]),
            "verification_steps": .array([.string("Inspect timeline and resource trend before termination"), .string("Match binary UUID with dSYM before symbolication")]),
            "confidence": .string("insufficient_evidence"), "evidence_refs": .array([])])
    }
    func snapshot(reason: String = "manual", acknowledgement: [String: DiagnosticValue]? = nil) throws -> String {
        try queue.sync {
            guard let store else { throw DiagnosticStore.StoreError.unsafeFile }
            let id = "SNAPSHOT_" + UUID().uuidString
            var report: [String: DiagnosticValue] = ["schema_version": .number(2), "snapshot_id": .string(id), "timestamp": .string(stamp()),
                "report_kind": .string("nonfatal_snapshot"), "executive_summary": .object(["crash_type": .string("NON_FATAL"), "reason": .string(reason)]),
                "device_info": .from(BenchmarkTelemetry.hardware()), "app_state": .object(state),
                "stack_trace": .object(["all_threads": .null, "reason": .string("snapshot_not_stack_capture")]),
                "memory_state": .object(resourceState()), "breadcrumbs": .array(breadcrumbs), "operation_timeline": .array(timeline),
                "recent_errors": .array(errors), "performance_snapshot": .object(performance), "configuration": .object(state),
                "kernel_statistics": performance["kernel_stats"] ?? .null, "ai_analysis": analysis(), "binary_images": images]
            if let acknowledgement { report["operator_acknowledgement"] = .object(acknowledgement) }
            report["diagnostic_error"] = failure.map(DiagnosticValue.string) ?? .null
            try store.save(id: id, report: report); return id
        }
    }
    func resourceState() -> [String: DiagnosticValue] {
        let p = BonsaiReadSystemProbe()
        var usage = rusage()
        let hasCPU = getrusage(RUSAGE_SELF, &usage) == 0
        let cpuSeconds = Double(usage.ru_utime.tv_sec + usage.ru_stime.tv_sec)
            + Double(usage.ru_utime.tv_usec + usage.ru_stime.tv_usec) / 1_000_000
        return ["app_memory_bytes": p.phys_footprint_bytes > 0 ? .number(Double(p.phys_footprint_bytes)) : .null,
            "available_memory_bytes": p.phys_footprint_bytes > 0 ? .number(Double(p.available_bytes)) : .null,
            "process_cpu_seconds": hasCPU ? .number(cpuSeconds) : .null,
            "metal_allocated_bytes": .number(Double(p.metal_allocated_bytes)), "gpu_utilization": .null, "gpu_fragmentation": .null,
            "unavailable_reason": .string("public_counter_not_available"), "thermal_state": .number(Double(ProcessInfo.processInfo.thermalState.rawValue))]
    }
    func api(method: String, path: String, query: [String: String] = [:]) -> (Int, String, Data) {
        queue.sync {
            func json(_ status: Int, _ values: [String: DiagnosticValue]) -> (Int, String, Data) {
                (status, "application/json; charset=utf-8", (try? JSONEncoder().encode(values)) ?? Data("{}".utf8))
            }
            guard let store else { return json(503, ["error": .string("diagnostics_unavailable")]) }
            let parts = path.split(separator: "/").map(String.init)
            do {
                if parts == ["debug", "crashes"] {
                    if method == "GET" {
                        let all = try store.list(crashesOnly: true)
                        guard let limit = Int(query["limit"] ?? "20"), let offset = Int(query["offset"] ?? "0"),
                              limit > 0, limit <= 50, offset >= 0 else { return json(400, ["error": .string("invalid_pagination")]) }
                        return json(200, ["crashes": .array(all.reversed().dropFirst(min(offset, all.count)).prefix(limit).map(DiagnosticValue.object)),
                            "total": .number(Double(all.count)), "offset": .number(Double(offset)), "limit": .number(Double(limit))])
                    }
                    if method == "DELETE" {
                        for row in try store.list(crashesOnly: true) {
                            if let value = row["crash_id"], case .string(let id) = value { try store.delete(id: id) }
                        }
                        return json(200, ["status": .string("ok")])
                    }
                }
                guard (parts.count == 3 || parts.count == 4), Array(parts.prefix(2)) == ["debug", "crashes"],
                      parts[2].hasPrefix("CRASH_"), DiagnosticStore.validID(parts[2]) else {
                    return json(400, ["error": .string("invalid_report_id")])
                }
                if method == "DELETE", parts.count == 3 { try store.delete(id: parts[2]); return json(200, ["status": .string("ok")]) }
                if method == "GET", parts.count == 3, let report = try store.read(id: parts[2]) { return json(200, report) }
                if method == "GET", parts.count == 4, parts[3] == "markdown", let md = try store.markdown(id: parts[2]) {
                    return (200, "text/markdown; charset=utf-8", Data(md.utf8))
                }
                return json(404, ["error": .string("not_found")])
            } catch { return json(500, ["error": .string("diagnostic_storage_error")]) }
        }
    }
}
