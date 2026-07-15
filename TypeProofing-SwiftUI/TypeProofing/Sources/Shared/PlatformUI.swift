import SwiftUI
import UniformTypeIdentifiers
#if os(macOS)
import AppKit
#else
import UIKit
#endif

/// Every font file type the app can load. Shared so the pickers can't drift
/// (the two previous inline lists disagreed: woff/woff2 vs ttc).
let fontFileContentTypes: [UTType] = ["otf", "ttf", "ttc", "woff", "woff2"].map {
    UTType(filenameExtension: $0) ?? .data
}

// Small cross-platform UI helpers, mirroring ProofCore's PlatformShims at the
// view layer. Keep entries tiny — anything bigger becomes a platform-split
// file pair.

extension View {
    /// Checkbox toggle on macOS; the platform-default style elsewhere.
    @ViewBuilder
    func checkboxToggleStyle() -> some View {
        #if os(macOS)
        toggleStyle(.checkbox)
        #else
        self
        #endif
    }

    /// Radio-group picker on macOS; the platform-default style elsewhere.
    @ViewBuilder
    func radioGroupPickerStyle() -> some View {
        #if os(macOS)
        pickerStyle(.radioGroup)
        #else
        self
        #endif
    }
}

#if os(macOS)
typealias PlatformImage = NSImage
#else
typealias PlatformImage = UIImage
#endif

extension Image {
    init(platformImage: PlatformImage) {
        #if os(macOS)
        self.init(nsImage: platformImage)
        #else
        self.init(uiImage: platformImage)
        #endif
    }
}

extension Color {
    /// The platform's standard background for small editable fields.
    static var platformControlBackground: Color {
        #if os(macOS)
        Color(nsColor: .controlBackgroundColor)
        #else
        Color(uiColor: .secondarySystemBackground)
        #endif
    }
}

/// Puts a string on the platform pasteboard.
func copyToPasteboard(_ string: String) {
    #if os(macOS)
    NSPasteboard.general.clearContents()
    NSPasteboard.general.setString(string, forType: .string)
    #else
    UIPasteboard.general.string = string
    #endif
}

/// Reads a string from the platform pasteboard.
func pasteboardString() -> String? {
    #if os(macOS)
    NSPasteboard.general.string(forType: .string)
    #else
    UIPasteboard.general.string
    #endif
}
