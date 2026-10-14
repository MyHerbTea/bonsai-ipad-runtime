import Foundation

/// Keep user-selected assets accessible across the process restarts required by B16.
enum B16AssetBookmarks {
    static let modelKey = "BonsaiBuild110ModelBookmark"
    static let visionKey = "BonsaiBuild110VisionBookmark"
    static let projectorKey = "BonsaiBuild110ProjectorBookmark"

    @discardableResult
    static func save(_ url: URL, key: String, defaults: UserDefaults = .standard) -> Bool {
        guard url.isFileURL else { return false }
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? url.bookmarkData(options: .minimalBookmark,
            includingResourceValuesForKeys: nil, relativeTo: nil) else { return false }
        defaults.set(data, forKey: key)
        return true
    }

    static func restore(_ key: String, defaults: UserDefaults = .standard) -> URL? {
        guard let data = defaults.data(forKey: key) else { return nil }
        var stale = false
        guard let url = try? URL(resolvingBookmarkData: data, options: .withoutUI,
            relativeTo: nil, bookmarkDataIsStale: &stale) else { return nil }
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        guard url.isFileURL, FileManager.default.fileExists(atPath: url.path) else { return nil }
        if stale { save(url, key: key, defaults: defaults) }
        return url
    }
}
