import Foundation

enum LabError: Error { case invalidConfig(String) }
struct BonsaiTextChatTurn: Sendable { let role: String; let text: String }
enum BenchmarkTelemetry {
    static func evidence() -> [String: Any] { ["process_id": "test"] }
    static func hardware() -> [String: Any] { ["eligible": true] }
}
actor BonsaiEngine {
    private var failRestore = false
    func setRestoreFailure(_ value: Bool) { failRestore = value }
    func benchmarkCapabilities() -> [String: Any] { ["capabilities": 7] }
    func benchmarkStart() throws -> [String: Any] { ["capabilities": 7] }
    func benchmarkConfigure(_ config: BenchmarkConfiguration) throws -> [String: Any] {
        if config.context == 32768 { throw LabError.invalidConfig("TEST_ALLOCATION_FAILURE") }
        return ["actual": config.json]
    }
    func benchmarkRestore() throws -> [String: Any] {
        if failRestore { throw LabError.invalidConfig("TEST_RESTORE_FAILURE") }; return [:]
    }
    func benchmarkTokenize(system: String, history: [BonsaiTextChatTurn], prompt: String) throws -> Int { 23 }
    func benchmarkRun(system: String, history: [BonsaiTextChatTurn], prompt: String,
        maxTokens: Int, onDelta: @escaping @Sendable (String) -> Void) async throws -> [String: Any] {
        for _ in 0..<100 {
            if BenchmarkSessionControl.shared.isCancelled { throw LabError.invalidConfig("BENCHMARK_CANCELLED") }
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        return ["text": "test"]
    }
}

@main struct ManagerBehaviorTests {
    static func main() async throws {
        let control = BenchmarkSessionControl.shared
        let engine = BonsaiEngine()
        let manager = BenchmarkSessionManager(engine: engine, beforeStart: {})
        let started = try await manager.handle("start", body: [:], onDelta: { _ in })
        let id = started["session_id"] as! String
        precondition(control.active && !control.enterOrdinary())
        do {
            _ = try await manager.handle("configure", body: ["session_id":id,"context":32768], onDelta: { _ in })
            preconditionFailure("allocation failure was hidden")
        } catch { precondition(control.active && control.snapshot["running"] as? Bool == false) }
        let running = Task { try await manager.handle("run", body: ["session_id":id,"prompt":"test","request_id":"r"], onDelta: { _ in }) }
        for _ in 0..<100 {
            if control.snapshot["running"] as? Bool == true { break }
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        _ = try await manager.handle("cancel", body: ["session_id":id], onDelta: { _ in })
        do { _ = try await running.value; preconditionFailure("cancel ignored") } catch {}
        precondition(control.snapshot["running"] as? Bool == false)
        await engine.setRestoreFailure(true)
        do { _ = try await manager.handle("restore", body: ["session_id":id], onDelta: { _ in }); preconditionFailure("restore failure ignored") } catch {}
        precondition(control.active && !control.enterOrdinary())
        await engine.setRestoreFailure(false)
        _ = try await manager.handle("restore", body: ["session_id":id], onDelta: { _ in })
        precondition(!control.active && control.enterOrdinary()); control.leaveOrdinary()
        print("Manager cancel, failed allocation, failed restore lease and successful recovery: PASS (test engine)")
    }
}
