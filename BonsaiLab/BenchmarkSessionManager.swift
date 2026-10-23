import Foundation

final class BenchmarkSessionManager: @unchecked Sendable {
    private let engine: BonsaiEngine
    private let beforeStart: @Sendable () async -> Void
    private let control = BenchmarkSessionControl.shared
    private var watchdog: Task<Void, Never>?
    init(engine: BonsaiEngine, beforeStart: @escaping @Sendable () async -> Void) {
        self.engine = engine; self.beforeStart = beforeStart
        watchdog = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 30_000_000_000)
                guard let self else { return }
                if let id = self.control.overdueOperation(after: 1800) { self.control.cancel(session: id) }
                if let id = self.control.expiredSession(after: 300) {
                    await self.restoreAbandonedSession(id)
                }
            }
        }
    }
    deinit { watchdog?.cancel() }
    func restoreAbandonedSession(_ id: String) async {
        _ = try? await handle("restore", body: ["session_id": id, "preserve_interrupted": true], onDelta: { _ in })
    }
    func handle(_ command: String, body: [String: Any],
                onDelta: @escaping @Sendable (String) -> Void) async throws -> [String: Any] {
        if command == "status" { return ["schema": 1, "state": control.snapshot,
            "evidence": BenchmarkTelemetry.evidence(), "hardware": BenchmarkTelemetry.hardware()] }
        if command == "capabilities" { return await engine.benchmarkCapabilities() }
        if command == "acknowledge_interruption" {
            guard let id = control.beginSession(), control.beginOperation(session: id, request: command) else {
                throw LabError.invalidConfig("BENCHMARK_OR_INFERENCE_BUSY")
            }
            defer { control.finishOperation(error: nil); control.endSession(session: id) }
            return try await engine.acknowledgeQuickInterruption(body)
        }
        if command == "start" {
            guard let mode = BenchmarkSessionMode(rawValue: body["mode"] as? String ?? "full"),
                  body["mode"] == nil || body["mode"] is String else {
                throw LabError.invalidConfig("INVALID_BENCHMARK_MODE")
            }
            guard let id = control.beginSession(), control.beginOperation(session: id, request: "start") else {
                throw LabError.invalidConfig("BENCHMARK_OR_INFERENCE_BUSY")
            }
            do {
                await beforeStart()
                var result = try await engine.benchmarkStart(mode: mode)
                control.finishOperation(error: nil)
                result["session_id"] = id; result["state"] = control.snapshot
                return result
            } catch {
                // A failed restore retains the lease to prevent unsafe ordinary inference.
                let restored = (try? await engine.benchmarkRestore(preserveInterrupted: mode == .quickPrefill)) != nil
                control.finishOperation(error: String(describing: error))
                if restored { control.endSession(session: id) }
                throw error
            }
        }
        guard let id = body["session_id"] as? String, control.matches(id) else {
            throw LabError.invalidConfig("INVALID_BENCHMARK_SESSION")
        }
        if command == "cancel" {
            control.cancel(session: id)
            return ["schema": 1, "state": control.snapshot]
        }
        guard ["configure", "run", "tokenize", "restore"].contains(command),
              control.beginOperation(session: id, request: body["request_id"] as? String ?? command) else {
            throw LabError.invalidConfig("BENCHMARK_BUSY_OR_UNKNOWN_COMMAND")
        }
        do {
            var result: [String: Any]
            switch command {
            case "configure":
                let named = (body["candidate"] ?? body["id"]) as? String
                if let named, BenchmarkCandidateRegistry.flags(named: named) == nil { throw LabError.invalidConfig("UNKNOWN_CANDIDATE") }
                let config = BenchmarkConfiguration(context: body["context"] as? Int ?? 16384,
                    batch: body["batch"] as? Int ?? 16, kv: body["kv"] as? String ?? "Q4_0",
                    flags: named.flatMap(BenchmarkCandidateRegistry.flags(named:)) ?? body["flags"] as? Int ?? 0)
                result = try await engine.benchmarkConfigure(config)
            case "restore": result = try await engine.benchmarkRestore(preserveInterrupted: body["preserve_interrupted"] as? Bool ?? false)
            default:
                guard let prompt = body["prompt"] as? String, prompt.utf8.count <= 1_000_000 else {
                    throw LabError.invalidConfig("INVALID_BENCHMARK_PROMPT")
                }
                let system = body["system"] as? String ?? "You are a helpful assistant."
                let history = (body["history"] as? [[String: String]] ?? []).compactMap { item -> BonsaiTextChatTurn? in
                    guard let role = item["role"], ["user", "assistant"].contains(role), let text = item["text"] else { return nil }
                    return BonsaiTextChatTurn(role: role, text: text)
                }
                if command == "tokenize" {
                    result = ["schema": 1, "prompt_tokens": try await engine.benchmarkTokenize(system: system, history: history, prompt: prompt)]
                } else {
                    let maxTokens = body["max_tokens"] as? Int ?? 128
                    guard maxTokens > 0 && maxTokens <= 8192 else { throw LabError.invalidConfig("INVALID_OUTPUT_BUDGET") }
                    result = try await engine.benchmarkRun(system: system, history: history, prompt: prompt,
                        maxTokens: maxTokens, onDelta: onDelta)
                }
            }
            control.finishOperation(error: nil)
            if command == "restore" { control.endSession(session: id) }
            result["state"] = control.snapshot
            return result
        } catch {
            control.finishOperation(error: String(describing: error))
            throw error
        }
    }
}
