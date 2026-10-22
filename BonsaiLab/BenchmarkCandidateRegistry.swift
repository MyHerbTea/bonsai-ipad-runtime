import Foundation

struct BenchmarkConfiguration: Equatable, Sendable {
    let context: Int
    let batch: Int
    let kv: String
    let flags: Int
    func isValid(capabilities: Int) -> Bool {
        [8192, 16384, 32768].contains(context) && [8, 16, 24].contains(batch)
            && ["Q4_0", "Q8_0"].contains(kv) && flags >= 0 && flags <= 7
            && flags & capabilities == flags
            && (flags & 1 == 0 || batch == 16) // custom Tensor tile needs rows divisible by 16
    }
    var identity: String { "\(flags):\(context):\(batch):\(kv)" }
    var json: [String: Any] {
        ["context": context, "batch": batch, "ubatch": batch, "kv_k": kv, "kv_v": kv,
         "flags": flags, "flash_attention": true, "sequence_max": 1, "kv_reuse": false]
    }
}

enum BenchmarkCandidateRegistry {
    static let entries: [(String, Int)] = [
        ("SAFE_BASELINE", 0), ("PTQ1_TENSOROPS", 1),
        ("PTQ1_FUSED_KERNEL", 2), ("PTQ1_LOW_OVERHEAD", 4)
    ]
    static func name(_ flags: Int) -> String {
        entries.first(where: { $0.1 == flags })?.0 ?? "PTQ1_BEST_COMBINATION"
    }
    static func json(capabilities: Int) -> [[String: Any]] {
        entries.map { ["id": $0.0, "flags": $0.1, "available": $0.1 & capabilities == $0.1] }
    }
}

/// The cancellation/status lock must remain callable while the inference actor is occupied.
final class BenchmarkSessionControl: @unchecked Sendable {
    static let shared = BenchmarkSessionControl()
    static let changed = Notification.Name("BonsaiBenchmarkSessionChanged")
    private let lock = NSLock()
    private var session: String?
    private var ordinary = 0
    private var running = false
    private var cancelled = false
    private var request = ""
    private var lastError: String?
    private var touched = ProcessInfo.processInfo.systemUptime
    func enterOrdinary() -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard session == nil else { return false }
        ordinary += 1; return true
    }
    func leaveOrdinary() { lock.lock(); ordinary = max(0, ordinary - 1); lock.unlock() }
    func beginSession() -> String? {
        lock.lock(); defer { lock.unlock() }
        guard session == nil && ordinary == 0 else { return nil }
        let id = UUID().uuidString; session = id; touched = ProcessInfo.processInfo.systemUptime
        DispatchQueue.main.async { NotificationCenter.default.post(name: Self.changed, object: nil) }
        return id
    }
    func beginOperation(session id: String, request value: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard session == id && !running else { return false }
        running = true; cancelled = false; request = value; lastError = nil
        touched = ProcessInfo.processInfo.systemUptime; return true
    }
    func finishOperation(error: String?) {
        lock.lock(); running = false; lastError = error; touched = ProcessInfo.processInfo.systemUptime; lock.unlock()
    }
    func cancel(session id: String) { lock.lock(); if session == id { cancelled = true }; lock.unlock() }
    var isCancelled: Bool { lock.lock(); defer { lock.unlock() }; return cancelled }
    var active: Bool { lock.lock(); defer { lock.unlock() }; return session != nil }
    func matches(_ id: String) -> Bool { lock.lock(); defer { lock.unlock() }; return session == id }
    func endSession(session id: String) {
        lock.lock(); defer { lock.unlock() }
        if session == id && !running {
            session = nil; cancelled = false
            DispatchQueue.main.async { NotificationCenter.default.post(name: Self.changed, object: nil) }
        }
    }
    func overdueOperation(after seconds: Double) -> String? {
        lock.lock(); defer { lock.unlock() }
        return running && ProcessInfo.processInfo.systemUptime - touched > seconds ? session : nil
    }
    func touch() { lock.lock(); touched = ProcessInfo.processInfo.systemUptime; lock.unlock() }
    func expiredSession(after seconds: Double) -> String? {
        lock.lock(); defer { lock.unlock() }
        return !running && ProcessInfo.processInfo.systemUptime - touched > seconds ? session : nil
    }
    var snapshot: [String: Any] {
        lock.lock(); defer { lock.unlock() }
        return ["session_id": session as Any? ?? NSNull(), "active": session != nil,
                "running": running, "cancelled": cancelled, "request_id": request,
                "error": lastError as Any? ?? NSNull(), "ordinary_requests": ordinary]
    }
}
