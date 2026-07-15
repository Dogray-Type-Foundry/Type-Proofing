import CoreGraphics

#if canImport(AppKit)
import AppKit

typealias PlatformColor = NSColor
typealias PlatformFont = NSFont

/// Makes `cg` the thread's current graphics context so AppKit/UIKit-backed
/// drawing (NSLayoutManager, NSAttributedString.draw) lands in it. The
/// context is assumed to be flipped (top-left origin) by the caller.
func pushGraphicsContext(_ cg: CGContext) {
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(cgContext: cg, flipped: true)
}

func popGraphicsContext() {
    NSGraphicsContext.restoreGraphicsState()
}

extension PlatformColor {
    static func fromCG(_ cgColor: CGColor) -> PlatformColor {
        NSColor(cgColor: cgColor) ?? .black
    }
    static var platformLabel: PlatformColor { .labelColor }
    static var platformSecondaryLabel: PlatformColor { .secondaryLabelColor }
}

#else
import UIKit

typealias PlatformColor = UIColor
typealias PlatformFont = UIFont

func pushGraphicsContext(_ cg: CGContext) {
    UIGraphicsPushContext(cg)
}

func popGraphicsContext() {
    UIGraphicsPopContext()
}

extension PlatformColor {
    static func fromCG(_ cgColor: CGColor) -> PlatformColor {
        UIColor(cgColor: cgColor)
    }
    static var platformLabel: PlatformColor { .label }
    static var platformSecondaryLabel: PlatformColor { .secondaryLabel }
}
#endif
