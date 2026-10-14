import Foundation
import CryptoKit

/// Read-only proof for the existing B8/B16 creation path. No runtime tuning.
enum B16RuntimeEvidence {
    static let processID = UUID().uuidString
    private static let gate = NSLock()
    private static let hashing = DispatchQueue(label: "bonsai.b16.asset-identity", qos: .utility)
    private static var native: [String: Any]?
    private static var modelIdentity: [String: Any]?
    private static var visionIdentity: [String: Any]?
    private static var visionHashingActive = false
    private static var visionConfigured = false
    private static var visionGeneration = UUID().uuidString
    private static var cache: [String: [String: Any]] = [:]

    static func invalidate() {
        gate.lock()
        native = nil
        modelIdentity = nil
        gate.unlock()
    }

    static func created(parameters: [String: Any], modelURL: URL?) {
        let id = UUID().uuidString
        var values = parameters
        values["context_id"] = id
        values["text_kv_reuse"] = false
        values["observation_source"] = "successful_native_creation_parameters"
        gate.lock()
        native = values
        modelIdentity = nil
        gate.unlock()
        guard let modelURL else { return }
        // Model and Vision identities must coexist across Vision context rebuilds.
        if let identity = cachedIdentity(modelURL) {
            gate.lock()
            if native?["context_id"] as? String == id { modelIdentity = identity }
            gate.unlock()
            return
        }
        hashing.async {
            guard let digest = fileIdentity(modelURL) else { return }
            gate.lock()
            if native?["context_id"] as? String == id {
                modelIdentity = digest
            }
            gate.unlock()
        }
    }

    static func registerVisionAsset(_ url: URL?) {
        let generation = UUID().uuidString
        gate.lock()
        visionGeneration = generation
        visionConfigured = url != nil
        visionIdentity = nil
        visionHashingActive = url != nil
        gate.unlock()
        guard let url else { return }
        hashing.async {
            let digest = fileIdentity(url)
            gate.lock()
            if visionGeneration == generation {
                visionIdentity = digest
                visionHashingActive = false
            }
            gate.unlock()
        }
    }

    private static func cachedIdentity(_ url: URL) -> [String: Any]? {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        var freshURL = url
        freshURL.removeAllCachedResourceValues()
        guard let values = try? freshURL.resourceValues(forKeys: [.fileSizeKey, .contentModificationDateKey]),
              let size = values.fileSize, let date = values.contentModificationDate else { return nil }
        let key = url.path + "|" + String(size) + "|" + String(date.timeIntervalSince1970)
        gate.lock()
        defer { gate.unlock() }
        return cache[key]
    }

    private static func fileIdentity(_ url: URL) -> [String: Any]? {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        var freshURL = url
        freshURL.removeAllCachedResourceValues()
        guard let before = try? freshURL.resourceValues(forKeys: [.fileSizeKey, .contentModificationDateKey]),
              let size = before.fileSize, size > 0,
              let date = before.contentModificationDate else { return nil }
        let key = url.path + "|" + String(size) + "|" + String(date.timeIntervalSince1970)
        gate.lock()
        let cached = cache[key]
        gate.unlock()
        if let cached { return cached }
        guard let handle = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? handle.close() }
        var sha = SHA256()
        do {
            while let data = try handle.read(upToCount: 1_048_576), !data.isEmpty {
                sha.update(data: data)
            }
        } catch { return nil }
        freshURL.removeAllCachedResourceValues()
        guard let after = try? freshURL.resourceValues(forKeys: [.fileSizeKey, .contentModificationDateKey]),
              after.fileSize == size, after.contentModificationDate == date else { return nil }
        let result: [String: Any] = [
            "sha256": sha.finalize().map { String(format: "%02x", $0) }.joined(),
            "size_bytes": size
        ]
        gate.lock()
        if cache[key] == nil && cache.count >= 4, let evicted = cache.keys.sorted().first {
            cache.removeValue(forKey: evicted)
        }
        cache[key] = result
        gate.unlock()
        return result
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
            "startup_ready": native != nil && modelIdentity != nil && !visionHashingActive && (!visionConfigured || visionIdentity != nil),
            "native_context": context as Any? ?? NSNull(),
            "vision_identity": visionIdentity as Any? ?? NSNull(),
            "identity_hashing_active": (native != nil && modelIdentity == nil) || visionHashingActive,
            "mid_request_batch_switch_supported": false
        ]
    }
}
