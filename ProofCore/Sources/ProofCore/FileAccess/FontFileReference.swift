import Foundation

/// Bookmark-aware reference to a user-chosen font file.
///
/// One code path serves both platforms: on iOS, document-picker bookmarks are
/// implicitly security-scoped and re-grant sandbox access across launches; on
/// the (unsandboxed) macOS app the bookmark resolves trivially and the
/// security scope is a no-op.
public struct FontFileReference: Codable, Equatable {
    public let path: String
    public let bookmark: Data?

    /// Creates a reference for a URL the user just picked. Call while the
    /// URL's security scope is active (inside the picker/drop callback).
    public init(url: URL) {
        self.path = url.path
        self.bookmark = try? url.bookmarkData()
    }

    public init(path: String, bookmark: Data?) {
        self.path = path
        self.bookmark = bookmark
    }
}

/// Holds the resolved, security-scope-active URLs for the session's fonts.
/// Scopes stay open while a font is loaded (the engine re-reads font files
/// throughout the session) and are released when the font is removed.
@MainActor
public final class FontAccessStore {
    public static let shared = FontAccessStore()

    /// path → URL whose security scope is currently active.
    private var activeURLs: [String: URL] = [:]

    /// Re-establishes access to a referenced file. Returns true if the file
    /// is reachable at its recorded path (with the security scope started
    /// where the platform requires one).
    ///
    /// A bookmark that resolves to a *different* path means the file moved;
    /// that is treated as missing, matching the app's existing behavior of
    /// dropping fonts whose path no longer exists.
    @discardableResult
    public func restoreAccess(to ref: FontFileReference) -> Bool {
        if activeURLs[ref.path] == nil,
           let bookmark = ref.bookmark {
            var stale = false
            if let url = try? URL(resolvingBookmarkData: bookmark, bookmarkDataIsStale: &stale),
               url.path == ref.path,
               url.startAccessingSecurityScopedResource() {
                activeURLs[ref.path] = url
            }
            // On unsandboxed macOS, startAccessing returns false and plain
            // file access works — fall through to the existence check.
        }
        return FileManager.default.fileExists(atPath: ref.path)
    }

    public func releaseAccess(toPath path: String) {
        if let url = activeURLs.removeValue(forKey: path) {
            url.stopAccessingSecurityScopedResource()
        }
    }

    public func releaseAll() {
        for url in activeURLs.values { url.stopAccessingSecurityScopedResource() }
        activeURLs.removeAll()
    }
}
