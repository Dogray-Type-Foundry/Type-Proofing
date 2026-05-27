import SwiftUI
import AppKit
import CoreText

enum AppFont {
    // Base descriptor loaded once from bundle
    private static let baseDescriptor: CTFontDescriptor? = {
        guard let path = Bundle.main.path(forResource: "SetsGroteskVF", ofType: "ttf") else { return nil }
        let url = URL(fileURLWithPath: path) as CFURL
        guard let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url) as? [CTFontDescriptor],
              let desc = descriptors.first else { return nil }
        return desc
    }()

    private static let wghtID = FontLoader.axisTagToID("wght")
    private static let opszID = FontLoader.axisTagToID("opsz")

    private static let bodyVariations: [Int: Double] = [wghtID: 350, opszID: 8]
    private static let titleVariations: [Int: Double] = [wghtID: 650, opszID: 18]

    // NSFont cache keyed by (size, isTitle)
    private static var nsFontCache: [String: NSFont] = [:]
    private static let cacheLock = NSLock()

    private static func cachedNSFont(size: CGFloat, variations: [Int: Double], key: String) -> NSFont? {
        cacheLock.lock()
        defer { cacheLock.unlock() }
        if let cached = nsFontCache[key] { return cached }
        guard let desc = baseDescriptor else { return nil }
        let baseFont = CTFontCreateWithFontDescriptor(desc, size, nil)
        let attrs: [String: Any] = [kCTFontVariationAttribute as String: variations]
        let newDesc = CTFontDescriptorCreateCopyWithAttributes(
            CTFontCopyFontDescriptor(baseFont), attrs as CFDictionary
        )
        let font = CTFontCreateWithFontDescriptor(newDesc, size, nil) as NSFont
        nsFontCache[key] = font
        return font
    }

    // Body text: wght 350, opsz 8
    static func swiftUI(size: CGFloat) -> Font {
        guard let ns = cachedNSFont(size: size, variations: bodyVariations, key: "b\(size)") else {
            return .system(size: size)
        }
        return Font(ns)
    }

    static func nsFont(size: CGFloat) -> NSFont {
        cachedNSFont(size: size, variations: bodyVariations, key: "b\(size)") ?? .systemFont(ofSize: size)
    }

    // Title text: wght 650, opsz 18
    static func titleSwiftUI(size: CGFloat) -> Font {
        guard let ns = cachedNSFont(size: size, variations: titleVariations, key: "t\(size)") else {
            return .system(size: size)
        }
        return Font(ns)
    }

    static func titleNSFont(size: CGFloat) -> NSFont {
        cachedNSFont(size: size, variations: titleVariations, key: "t\(size)") ?? .systemFont(ofSize: size)
    }

    // Semantic sizes — body style (wght:350, opsz:8)
    static let body       = swiftUI(size: 13)
    static let subheadline = swiftUI(size: 11)
    static let caption    = swiftUI(size: 10)
    static let caption2   = swiftUI(size: 9)

    // Semantic sizes — title style (wght:650, opsz:18)
    static let largeTitle = titleSwiftUI(size: 26)
    static let title      = titleSwiftUI(size: 22)
    static let title2     = titleSwiftUI(size: 17)
    static let title3     = titleSwiftUI(size: 15)
    static let headline   = titleSwiftUI(size: 13)
}

// Walks the AppKit view tree once, then coalesces further
// requests so the tree is walked at most once per run-loop cycle.
private struct AppKitFontInjector: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let v = NSView(frame: .zero)
        v.setAccessibilityElement(false)
        return v
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        Self.scheduleApply(for: nsView.window)
    }

    private static var pending = false

    fileprivate static func scheduleApply(for window: NSWindow?) {
        guard !pending, let window else { return }
        pending = true
        DispatchQueue.main.async {
            pending = false
            guard let root = window.contentView else { return }
            apply(to: root)
        }
    }

    private static func apply(to view: NSView) {
        if let seg = view as? NSSegmentedControl {
            seg.font = AppFont.nsFont(size: seg.font?.pointSize ?? NSFont.systemFontSize)
        } else if let popup = view as? NSPopUpButton {
            popup.font = AppFont.nsFont(size: popup.font?.pointSize ?? NSFont.smallSystemFontSize)
        } else if let btn = view as? NSButton, !(view is NSPopUpButton), !(view is NSSegmentedControl) {
            btn.font = AppFont.nsFont(size: btn.font?.pointSize ?? NSFont.systemFontSize)
        }
        for child in view.subviews {
            apply(to: child)
        }
    }
}

extension View {
    func injectAppFont() -> some View {
        self.background(AppKitFontInjector())
    }
}
