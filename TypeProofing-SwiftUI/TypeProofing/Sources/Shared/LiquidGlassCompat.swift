import ProofCore
import SwiftUI

// Liquid Glass is a macOS 26 design feature. These helpers apply it on macOS 26+
// and fall back to materials / standard styles on earlier systems (down to macOS 13),
// so the app keeps the full glass look where available without dropping older OSes.
extension View {
    /// Liquid-glass background in a rounded rectangle on macOS 26+, material fallback otherwise.
    /// The glass is applied as a background layer, not wrapped around the content:
    /// `glassEffect` on a container breaks all SwiftUI drop targets inside it
    /// (drags start but validateDrop/performDrop never fire).
    @ViewBuilder
    func liquidGlassRect(cornerRadius: CGFloat) -> some View {
        if #available(macOS 26, iOS 26, *) {
            background(Color.clear.glassEffect(.regular.tint(.clear), in: .rect(cornerRadius: cornerRadius)))
        } else {
            background(.regularMaterial, in: RoundedRectangle(cornerRadius: cornerRadius))
        }
    }

    /// Liquid-glass background in a capsule on macOS 26+, material fallback otherwise.
    @ViewBuilder
    func liquidGlassCapsule() -> some View {
        if #available(macOS 26, iOS 26, *) {
            glassEffect(.regular, in: .capsule)
        } else {
            background(.regularMaterial, in: Capsule())
        }
    }

    /// Prominent glass button style on macOS 26+, prominent bordered style otherwise.
    @ViewBuilder
    func glassProminentButtonStyle() -> some View {
        if #available(macOS 26, iOS 26, *) {
            buttonStyle(.glassProminent)
        } else {
            buttonStyle(.borderedProminent)
        }
    }

    /// Soft scroll-edge effect on macOS 26+, no-op on earlier systems.
    @ViewBuilder
    func softScrollEdgeEffect() -> some View {
        if #available(macOS 26, iOS 26, *) {
            scrollEdgeEffectStyle(.soft, for: .all)
        } else {
            self
        }
    }
}
