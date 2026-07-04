import SwiftUI

/// Shared row component used by both Fonts and Proofs lists in the sidebar.
/// Ensures identical layout, padding, and divider treatment.
struct SidebarListRow<Detail: View>: View {
    let name: String
    @Binding var enabled: Bool
    let isLast: Bool
    let badge: String?
    let isSelected: Bool
    let onRemove: () -> Void
    let onTap: (() -> Void)?
    let onRename: ((String) -> Void)?
    /// When set, dragging the grip handle starts a reorder drag with this item.
    let dragProvider: (() -> NSItemProvider)?
    @ViewBuilder let detail: () -> Detail

    @State private var isEditing = false
    @State private var editText = ""
    @State private var isRowHovered = false
    @State private var isRemoveHovered = false
    @State private var isNameHovered = false

    init(
        name: String,
        enabled: Binding<Bool>,
        isLast: Bool,
        badge: String? = nil,
        isSelected: Bool = false,
        onRemove: @escaping () -> Void,
        onTap: (() -> Void)? = nil,
        onRename: ((String) -> Void)? = nil,
        dragProvider: (() -> NSItemProvider)? = nil,
        @ViewBuilder detail: @escaping () -> Detail = { EmptyView() }
    ) {
        self.name = name
        self._enabled = enabled
        self.isLast = isLast
        self.badge = badge
        self.isSelected = isSelected
        self.onRemove = onRemove
        self.onTap = onTap
        self.onRename = onRename
        self.dragProvider = dragProvider
        self.detail = detail
    }

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                headerRow
                detail()
            }
            .padding(.vertical, 3)
            .padding(.horizontal, 12)
            .contentShape(Rectangle())
            .background(
                isSelected ? Color.accentColor.opacity(0.15) :
                isRowHovered ? Color.primary.opacity(0.04) : Color.clear
            )
            .cornerRadius(4)
            .onHover { isRowHovered = $0 }
            .onTapGesture {
                if isEditing { commitEditing() }
                onTap?()
            }
            .onChange(of: isSelected) { selected in
                if !selected && isEditing { commitEditing() }
            }

            if !isLast {
                Divider()
            }
        }
    }

    /// The row's top line. The whole line is the reorder drag source (the grip
    /// is just the visual affordance); the detail area below is excluded so
    /// dragging the variable-font sliders never starts a reorder.
    @ViewBuilder
    private var headerRow: some View {
        let header = HStack(spacing: 8) {
                    grip

                    Toggle("", isOn: $enabled)
                        .toggleStyle(.checkbox)
                        .labelsHidden()

                    if isEditing, onRename != nil {
                        InlineRenameField(
                            text: $editText,
                            onCommit: { commitEditing() },
                            onCancel: { isEditing = false }
                        )
                        .opacity(enabled ? 1 : 0.5)
                    } else {
                        Text(name)
                            .lineLimit(1)
                            .opacity(enabled ? 1 : 0.5)
                            .underline(onRename != nil && isNameHovered, color: .accentColor.opacity(0.5))
                            .foregroundStyle(onRename != nil && isNameHovered ? Color.accentColor : Color.primary)
                            .help(onRename != nil ? "Double-click to rename" : "")
                            .onHover { isNameHovered = $0 }
                            .onTapGesture(count: 2) {
                                if onRename != nil {
                                    editText = name
                                    isEditing = true
                                }
                            }
                    }

                    if let badge {
                        Text(badge)
                            .font(.system(size: 9.5, weight: .semibold))
                            .foregroundStyle(Color.accentColor)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 1)
                            .background(Color.accentColor.opacity(0.08))
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                    }

                    Spacer()

                    Button(role: .destructive, action: onRemove) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(isRemoveHovered ? .red : .secondary)
                    }
                    .buttonStyle(.plain)
                    .onHover { isRemoveHovered = $0 }
        }
        .contentShape(Rectangle())

        if let dragProvider {
            header.onDrag(dragProvider)
        } else {
            header
        }
    }

    private var grip: some View {
        Image(systemName: "line.3.horizontal")
            .foregroundStyle(.tertiary)
            .font(.caption)
            .help("Drag to reorder")
    }

    private func commitEditing() {
        let trimmed = editText.trimmingCharacters(in: .whitespaces)
        if !trimmed.isEmpty { onRename?(trimmed) }
        isEditing = false
    }
}

/// Insertion indicator for sidebar reorder drags: while a drag started at
/// `source` hovers over the row at `target`, draws an accent line on this row
/// showing where the item lands on drop — above when dragging up, below when
/// dragging down (mirroring the toOffset adjustment in the drop delegates).
extension View {
    @ViewBuilder
    func reorderDropIndicator(index: Int, source: Int?, target: Int?) -> some View {
        let line = Capsule()
            .fill(Color.accentColor)
            .frame(height: 2)
            .padding(.horizontal, 2)
        overlay(alignment: .top) {
            if let source, let target, target == index, target < source { line }
        }
        .overlay(alignment: .bottom) {
            if let source, let target, target == index, target > source { line }
        }
    }
}

/// A text field that commits on Enter, cancels on Escape, and commits when
/// clicking anywhere else in the window (via NSEvent local monitor).
private struct InlineRenameField: View {
    @Binding var text: String
    let onCommit: () -> Void
    let onCancel: () -> Void

    @State private var monitor: Any?
    @State private var fieldFrame: CGRect = .zero

    var body: some View {
        TextField("", text: $text, onCommit: onCommit)
            .textFieldStyle(.roundedBorder)
            .lineLimit(1)
            .onExitCommand(perform: onCancel)
            .background(GeometryReader { geo in
                Color.clear.onAppear {
                    fieldFrame = geo.frame(in: .global)
                }
                .onChange(of: geo.frame(in: .global)) { newFrame in
                    fieldFrame = newFrame
                }
            })
            .onAppear { installMonitor() }
            .onDisappear { removeMonitor() }
    }

    private func installMonitor() {
        monitor = NSEvent.addLocalMonitorForEvents(matching: .leftMouseDown) { event in
            guard let window = event.window else { return event }
            let clickInWindow = event.locationInWindow
            // Convert from window coords (bottom-left origin) to screen coords
            let clickInScreen = window.convertPoint(toScreen: clickInWindow)
            // fieldFrame is in SwiftUI global coords (top-left origin)
            // NSScreen coords are bottom-left origin, so flip Y
            if let screen = window.screen {
                let flippedY = screen.frame.height - clickInScreen.y
                let clickPoint = CGPoint(x: clickInScreen.x, y: flippedY)
                if !fieldFrame.contains(clickPoint) {
                    DispatchQueue.main.async { onCommit() }
                }
            }
            return event
        }
    }

    private func removeMonitor() {
        if let monitor { NSEvent.removeMonitor(monitor) }
        monitor = nil
    }
}
