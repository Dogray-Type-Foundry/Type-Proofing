import SwiftUI

/// A plain-styled label button that highlights on hover.
struct HoverButton: View {
    let title: String
    let systemImage: String
    let action: () -> Void
    @State private var isHovered = false

    init(_ title: String, systemImage: String, action: @escaping () -> Void) {
        self.title = title
        self.systemImage = systemImage
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            Label(title, systemImage: systemImage)
                .foregroundStyle(isHovered ? .primary : .secondary)
        }
        .buttonStyle(.plain)
        .onHover { isHovered = $0 }
        .help(title)
    }
}

/// A small icon button that changes color on hover.
struct HoverIconButton: View {
    let systemName: String
    let size: CGFloat
    let hoverColor: Color
    let action: () -> Void
    @State private var isHovered = false

    init(systemName: String, size: CGFloat = 10, hoverColor: Color = .accentColor, action: @escaping () -> Void) {
        self.systemName = systemName
        self.size = size
        self.hoverColor = hoverColor
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: size, weight: .bold))
                .foregroundStyle(isHovered ? hoverColor : .secondary)
        }
        .buttonStyle(.plain)
        .onHover { isHovered = $0 }
    }
}

/// A small tappable value label that highlights on hover.
struct HoverValueLabel: View {
    let text: String
    let action: () -> Void
    @State private var isHovered = false

    var body: some View {
        Text(text)
            .font(.system(size: 9).monospacedDigit())
            .foregroundStyle(isHovered ? .primary : .secondary)
            .underline(isHovered, color: .accentColor.opacity(0.5))
            .onHover { isHovered = $0 }
            .onTapGesture(perform: action)
    }
}
