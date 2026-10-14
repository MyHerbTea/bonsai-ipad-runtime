import Foundation

@main
struct Build110EvidenceTests {
    static func main() throws {
        let sha = String(repeating: "a", count: 40)
        func snapshot() -> [String: Any] {
            B16RuntimeEvidence.snapshot(sourceSHA: sha, buildNumber: "110")
        }
        B16RuntimeEvidence.invalidate()
        precondition(snapshot()["startup_ready"] as? Bool == false)
        let file = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try Data("abc".utf8).write(to: file)
        defer { try? FileManager.default.removeItem(at: file) }
        let bookmarkSuite = "B16BookmarkTests." + UUID().uuidString
        let bookmarkDefaults = UserDefaults(suiteName: bookmarkSuite)!
        defer { bookmarkDefaults.removePersistentDomain(forName: bookmarkSuite) }
        precondition(B16AssetBookmarks.restore(B16AssetBookmarks.modelKey, defaults: bookmarkDefaults) == nil)
        precondition(!B16AssetBookmarks.save(URL(string: "https://example.invalid/model")!, key: B16AssetBookmarks.modelKey, defaults: bookmarkDefaults))
        precondition(B16AssetBookmarks.save(file, key: B16AssetBookmarks.modelKey, defaults: bookmarkDefaults))
        precondition(B16AssetBookmarks.restore(B16AssetBookmarks.modelKey, defaults: bookmarkDefaults)?.path == file.path)
        bookmarkDefaults.set(Data([0, 1, 2]), forKey: B16AssetBookmarks.modelKey)
        precondition(B16AssetBookmarks.restore(B16AssetBookmarks.modelKey, defaults: bookmarkDefaults) == nil)
        B16RuntimeEvidence.created(parameters: [
            "context": 32768, "batch": 8, "ubatch": 8,
            "sequence_max": 1, "kv_k": "Q4_0", "kv_v": "Q4_0"
        ], modelURL: file)
        for _ in 0..<100 {
            if snapshot()["startup_ready"] as? Bool == true { break }
            Thread.sleep(forTimeInterval: 0.02)
        }
        precondition(snapshot()["startup_ready"] as? Bool == true)
        let context = snapshot()["native_context"] as! [String: Any]
        let identity = context["model_identity"] as! [String: Any]
        precondition(identity["sha256"] as? String == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        precondition(identity["size_bytes"] as? Int == 3)
        precondition(context["text_kv_reuse"] as? Bool == false)
        precondition(snapshot()["source_git_sha"] as? String == sha)
        let firstID = context["context_id"] as! String
        precondition(B16RuntimeEvidence.qualifiesTextCompletion(contextID: firstID, batch: 8))
        precondition(!B16RuntimeEvidence.qualifiesTextCompletion(contextID: firstID, batch: 16))
        for (size, sequences) in [(4096, 1), (32768, 2)] {
            B16RuntimeEvidence.created(parameters: [
                "context": size, "batch": 16, "ubatch": 16, "sequence_max": sequences
            ], modelURL: file)
            for _ in 0..<100 {
                if snapshot()["startup_ready"] as? Bool == true { break }
                Thread.sleep(forTimeInterval: 0.02)
            }
            precondition(snapshot()["startup_ready"] as? Bool == true)
            let badID = B16RuntimeEvidence.contextIDForQualification()
            precondition(!B16RuntimeEvidence.qualifiesTextCompletion(contextID: badID, batch: 16))
            precondition(!B16RuntimeEvidence.qualifiesTextCompletion(contextID: firstID, batch: 8))
        }
        B16RuntimeEvidence.created(parameters: ["context": 32768, "batch": 16, "ubatch": 16, "sequence_max": 1], modelURL: file)
        for _ in 0..<100 {
            if snapshot()["startup_ready"] as? Bool == true { break }
            Thread.sleep(forTimeInterval: 0.02)
        }
        precondition(snapshot()["startup_ready"] as? Bool == true)
        precondition(B16RuntimeEvidence.qualifiesTextCompletion(contextID: B16RuntimeEvidence.contextIDForQualification(), batch: 16))
        let visionFile = file.appendingPathExtension("vision")
        try Data("vision".utf8).write(to: visionFile)
        defer { try? FileManager.default.removeItem(at: visionFile) }
        B16RuntimeEvidence.registerVisionAsset(visionFile)
        for _ in 0..<100 {
            if snapshot()["identity_hashing_active"] as? Bool == false { break }
            Thread.sleep(forTimeInterval: 0.02)
        }
        precondition(snapshot()["startup_ready"] as? Bool == true)
        B16RuntimeEvidence.invalidate()
        B16RuntimeEvidence.created(parameters: ["context": 32768, "batch": 16, "ubatch": 16, "sequence_max": 1], modelURL: file)
        precondition(snapshot()["startup_ready"] as? Bool == true, "Unchanged model proof must survive Vision hashing without new full-file IO")
        try Data("abcd".utf8).write(to: file)
        B16RuntimeEvidence.created(parameters: ["context": 32768, "batch": 16, "ubatch": 16, "sequence_max": 1], modelURL: file)
        for _ in 0..<100 {
            if snapshot()["startup_ready"] as? Bool == true { break }
            Thread.sleep(forTimeInterval: 0.02)
        }
        precondition(snapshot()["startup_ready"] as? Bool == true)
        let changedIdentity = (snapshot()["native_context"] as! [String: Any])["model_identity"] as! [String: Any]
        precondition(changedIdentity["sha256"] as? String == "88d4266fd4e6338d13b845fcf289579d209c897823b9217da3e161936f031589")
        precondition(changedIdentity["size_bytes"] as? Int == 4, "Changed asset must not reuse stale proof")
        B16RuntimeEvidence.registerVisionAsset(file.appendingPathExtension("missing"))
        for _ in 0..<100 {
            if snapshot()["identity_hashing_active"] as? Bool == false { break }
            Thread.sleep(forTimeInterval: 0.02)
        }
        precondition(snapshot()["startup_ready"] as? Bool == false)
        B16RuntimeEvidence.registerVisionAsset(nil)
        B16RuntimeEvidence.created(parameters: ["context": 32768, "batch": 16], modelURL: nil)
        precondition(snapshot()["startup_ready"] as? Bool == false)
        precondition((snapshot()["native_context"] as! [String: Any])["context_id"] as? String != firstID)
        B16RuntimeEvidence.invalidate()
        Thread.sleep(forTimeInterval: 0.05)
        precondition(snapshot()["native_context"] is NSNull)
        precondition(snapshot()["startup_ready"] as? Bool == false)
        let encoded = try JSONSerialization.data(withJSONObject: snapshot())
        precondition(!String(decoding: encoded, as: UTF8.self).contains(file.path))
        print("PASS Build110 successful-context identity, stream SHA, stale/absent identity, invalidation and privacy")
    }
}
