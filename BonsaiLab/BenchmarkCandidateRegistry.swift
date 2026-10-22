import Foundation

enum BenchmarkModelAdmission {
    // Compare candidates using the already loaded production model placement.
    // A request value of 99 is not a native full-offload measurement, and the
    // validated 16K production path intentionally requests 56 GPU layers.
    static func accepts(gpuLayers: Int, mmap: Bool) -> Bool {
        gpuLayers > 0 && mmap
    }
}

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
        ("PTQ1_MV_R5", 2), ("PTQ1_BATCH_REUSE", 4)
    ]
    static func flags(named name: String) -> Int? {
        if name == "PTQ1_FUSED_KERNEL" { return 2 }
        if name == "PTQ1_LOW_OVERHEAD" { return 4 }
        return entries.first(where: { $0.0 == name })?.1
    }
    static func optimizationTarget(_ flags: Int) -> String {
        flags == 2 ? "DECODE_FOCUSED" : flags == 1 ? "PREFILL_FOCUSED" : "BALANCED"
    }
    static func description(_ flags: Int) -> String {
        switch flags {
        case 0: return "安全基线：继承 Prism 原始实现，无实验优化"
        case 1: return "PTQ1 TensorOps：面向满足 tile 形状的 prefill；收益待真机验证"
        case 2: return "PTQ1 MatVec Row-5：SIMD 组从4行到5行；M=1 decode、K%128==0；预期1–3%为待验证假设，不适用于B16大矩阵prefill"
        case 4: return "PTQ1 Batch Reuse：复用CPU batch输入数组减少分配；不改变GPU调度、command buffer或同步点；预期端到端<1%为待验证假设"
        default: return "组合候选：需独立ABBA验证"
        }
    }
    static func name(_ flags: Int) -> String {
        entries.first(where: { $0.1 == flags })?.0 ?? "PTQ1_BEST_COMBINATION"
    }
    static func json(capabilities: Int) -> [[String: Any]] {
        entries.map { ["id": $0.0, "flags": $0.1, "available": $0.1 & capabilities == $0.1,
                      "optimization_target": optimizationTarget($0.1), "description": description($0.1)] }
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
