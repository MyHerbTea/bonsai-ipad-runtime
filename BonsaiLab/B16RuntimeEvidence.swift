import Foundation
import CryptoKit

/// Read-only proof for the existing B8/B16 creation path. No runtime tuning.
enum B16RuntimeEvidence {
    static let processID = UUID().uuidString
    private static let gate = NSLock()
    // Independent workers: a blocked provider read must not hide the other asset.
    private static let modelHashing = DispatchQueue(label: "bonsai.b16.model-identity", qos: .userInitiated)
    private static let visionHashing = DispatchQueue(label: "bonsai.b16.vision-identity", qos: .userInitiated)
    private static var native: [String: Any]?
    private static var modelIdentity: [String: Any]?
    private static var visionIdentity: [String: Any]?
    private static var visionConfigured = false
    private static var visionGeneration = UUID().uuidString
    private static var cache: [String: [String: Any]] = [:]
    private struct HashState {
        var phase = "idle"
        var bytes: Int = 0
        var total: Int = 0
        var started = ProcessInfo.processInfo.systemUptime
        var updated = ProcessInfo.processInfo.systemUptime
        var code: String?
        var osCode: Int?
        var scoped: Bool?
        var active: Bool { ["queued", "metadata", "opening", "reading", "verifying"].contains(phase) }
        var snapshot: [String: Any] {
            let now = ProcessInfo.processInfo.systemUptime
            var result: [String: Any] = ["phase": phase, "bytes_hashed": bytes, "total_bytes": total,
                "elapsed_s": max(0, now - started), "last_progress_age_s": max(0, now - updated)]
            if let code { result["error_code"] = code }
            if let osCode { result["os_error_code"] = osCode }
            if let scoped { result["security_scope_acquired"] = scoped }
            return result
        }
    }
    private static var modelState = HashState()
    private static var visionState = HashState()
    #if DEBUG
    // Deterministic blocked-read/cancellation tests; absent from the release app.
    static var beforeReadForTesting: ((String) -> Void)?
    #endif

    static func invalidate() {
        gate.lock()
        native = nil
        modelIdentity = nil
        modelState = HashState()
        gate.unlock()
    }

    static func created(parameters: [String: Any], modelURL: URL?) {
        let id = UUID().uuidString
        var values = parameters
        values["context_id"] = id
        values["text_kv_reuse"] = false
        values["observation_source"] = parameters["kv_observation_source"] ?? "successful_native_creation_parameters"
        gate.lock()
        native = values
        modelIdentity = nil
        modelState = HashState(phase: "queued")
        gate.unlock()
        guard let modelURL else {
            _ = update("model", id: id, phase: "failed", code: "NO_ASSET_URL")
            return
        }
        // Reuse exact proof only after fresh metadata matches; no path is exposed.
        if let identity = cachedIdentity(modelURL) {
            finish("model", id: id, identity: identity)
            return
        }
        modelHashing.async { hash(modelURL, asset: "model", id: id) }
    }

    static func registerVisionAsset(_ url: URL?) {
        let id = UUID().uuidString
        gate.lock()
        visionGeneration = id
        visionConfigured = url != nil
        visionIdentity = nil
        visionState = HashState(phase: url == nil ? "unconfigured" : "queued")
        gate.unlock()
        guard let url else { return }
        visionHashing.async { hash(url, asset: "vision", id: id) }
    }

    @discardableResult
    private static func update(_ asset: String, id: String, phase: String,
        bytes: Int? = nil, total: Int? = nil, code: String? = nil, osCode: Int? = nil, scoped: Bool? = nil) -> Bool {
        gate.lock()
        defer { gate.unlock() }
        guard asset == "model" ? native?["context_id"] as? String == id : visionGeneration == id else { return false }
        var state = asset == "model" ? modelState : visionState
        state.phase = phase
        state.updated = ProcessInfo.processInfo.systemUptime
        if let bytes { state.bytes = bytes }
        if let total { state.total = total }
        if let scoped { state.scoped = scoped }
        state.code = code
        state.osCode = osCode
        if asset == "model" { modelState = state } else { visionState = state }
        return true
    }

    private static func finish(_ asset: String, id: String, identity: [String: Any]) {
        gate.lock()
        defer { gate.unlock() }
        guard asset == "model" ? native?["context_id"] as? String == id : visionGeneration == id else { return }
        var state = asset == "model" ? modelState : visionState
        state.phase = "ready"
        state.bytes = identity["size_bytes"] as? Int ?? 0
        state.total = state.bytes
        state.updated = ProcessInfo.processInfo.systemUptime
        if asset == "model" { modelIdentity = identity; modelState = state }
        else { visionIdentity = identity; visionState = state }
    }

    private static func metadata(_ url: URL) throws -> URLResourceValues {
        var fresh = url
        fresh.removeAllCachedResourceValues()
        return try fresh.resourceValues(forKeys: [.fileSizeKey, .contentModificationDateKey])
    }

    private static func cachedIdentity(_ url: URL) -> [String: Any]? {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        guard let values = try? metadata(url), let size = values.fileSize,
              let date = values.contentModificationDate else { return nil }
        let key = url.path + "|" + String(size) + "|" + String(date.timeIntervalSince1970)
        gate.lock()
        defer { gate.unlock() }
        return cache[key]
    }

    private static func hash(_ url: URL, asset: String, id: String) {
        guard update(asset, id: id, phase: "metadata") else { return }
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        _ = update(asset, id: id, phase: "metadata", scoped: scoped)
        var failure = "METADATA_FAILED"
        do {
            let before = try metadata(url)
            guard let size = before.fileSize, size > 0, let date = before.contentModificationDate else {
                _ = update(asset, id: id, phase: "failed", code: "INVALID_METADATA")
                return
            }
            let key = url.path + "|" + String(size) + "|" + String(date.timeIntervalSince1970)
            gate.lock(); let cached = cache[key]; gate.unlock()
            if let cached { finish(asset, id: id, identity: cached); return }
            guard update(asset, id: id, phase: "opening", total: size) else { return }
            failure = "OPEN_FAILED"
            let handle = try FileHandle(forReadingFrom: url)
            defer { try? handle.close() }
            guard update(asset, id: id, phase: "reading") else { return }
            #if DEBUG
            beforeReadForTesting?(asset)
            #endif
            failure = "READ_FAILED"
            var sha = SHA256()
            var count = 0
            while true {
                guard update(asset, id: id, phase: "reading", bytes: count) else { return }
                // Bound Foundation/FileHandle autoreleased buffers for multi-GB assets.
                let length: Int = try autoreleasepool {
                    let data = try handle.read(upToCount: 1_048_576) ?? Data()
                    sha.update(data: data)
                    return data.count
                }
                if length == 0 { break }
                count += length
            }
            guard count == size else {
                _ = update(asset, id: id, phase: "failed", bytes: count, code: "LENGTH_MISMATCH")
                return
            }
            guard update(asset, id: id, phase: "verifying", bytes: count) else { return }
            failure = "METADATA_FAILED"
            let after = try metadata(url)
            guard after.fileSize == size, after.contentModificationDate == date else {
                _ = update(asset, id: id, phase: "failed", code: "FILE_CHANGED")
                return
            }
            let result: [String: Any] = ["sha256": sha.finalize().map { String(format: "%02x", $0) }.joined(), "size_bytes": size]
            gate.lock()
            if cache[key] == nil && cache.count >= 4, let evicted = cache.keys.sorted().first { cache.removeValue(forKey: evicted) }
            cache[key] = result
            gate.unlock()
            finish(asset, id: id, identity: result)
        } catch {
            let error = error as NSError
            // Never expose localizedDescription, URLs or user paths. False scope acquisition
            // alone is not proof of denied access (sandbox-local files need no scope).
            let denied = (error.domain == NSCocoaErrorDomain && [257, 513].contains(error.code))
                || (error.domain == NSPOSIXErrorDomain && error.code == 13)
            _ = update(asset, id: id, phase: "failed", code: denied ? "ACCESS_DENIED" : failure, osCode: error.code)
        }
    }

    static func contextIDForQualification() -> String? {
        gate.lock()
        defer { gate.unlock() }
        guard modelIdentity != nil else { return nil }
        return native?["context_id"] as? String
    }

    static func qualifiesTextCompletion(contextID: String?, batch: Int) -> Bool {
        gate.lock()
        defer { gate.unlock() }
        guard let contextID, let native, modelIdentity != nil else { return false }
        return native["context_id"] as? String == contextID
            && native["context"] as? Int == 32768
            && native["batch"] as? Int == batch
            && native["ubatch"] as? Int == batch
            && native["sequence_max"] as? Int == 1
            && native["text_kv_reuse"] as? Bool == false
    }

    static func snapshot(sourceSHA: String, buildNumber: String) -> [String: Any] {
        gate.lock()
        defer { gate.unlock() }
        var context = native
        if let modelIdentity { context?["model_identity"] = modelIdentity }
        return [
            "schema": "bonsai-b16-native-evidence-v1",
            "process_id": processID,
            "source_git_sha": sourceSHA,
            "build_number": buildNumber,
            "physical_memory_bytes": ProcessInfo.processInfo.physicalMemory,
            "operating_system": ProcessInfo.processInfo.operatingSystemVersionString,
            "startup_ready": native != nil && modelIdentity != nil && !visionState.active && (!visionConfigured || visionIdentity != nil),
            "native_context": context as Any? ?? NSNull(),
            "vision_identity": visionIdentity as Any? ?? NSNull(),
            "identity_hashing_active": modelState.active || visionState.active,
            "asset_hashing": ["model": modelState.snapshot, "vision": visionState.snapshot],
            "mid_request_batch_switch_supported": false
        ]
    }
}
