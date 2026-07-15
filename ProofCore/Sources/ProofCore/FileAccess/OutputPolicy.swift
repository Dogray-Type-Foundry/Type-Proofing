import Foundation

/// Default directory for generated PDFs, given the source font's path.
///
/// macOS keeps the historical behavior of writing next to the font. iOS
/// renders into the app's Documents container — a sandboxed app can't write
/// next to arbitrary user files; hand-off happens via exporter/ShareLink.
public func defaultOutputDirectory(forFontAt fontPath: String) -> String {
    #if os(macOS)
    return (fontPath as NSString).deletingLastPathComponent
    #else
    let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    let dir = docs.appendingPathComponent("Proofs", isDirectory: true)
    try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    return dir.path
    #endif
}
