import ProofCore
import SwiftUI

/// Shared row component used by both Fonts and Proofs lists in the sidebar.
/// Ensures identical layout, padding, and divider treatment.
struct SidebarListRow<Detail: View>: View {
    let name: String
    @Binding var enabled: Bool
    let isLast: Bool
    let badge: String?
    let isLocked: Bool
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
        isLocked: Bool = false,
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
        self.isLocked = isLocked
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
                        .checkboxToggleStyle()
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

                    if isLocked {
                        Image(systemName: "lock.fill")
                            .font(.system(size: 9))
                            .foregroundStyle(.orange)
                            .help("Locked — this section has annotations")
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

/// A text field that commits on Enter or when focus moves elsewhere, and
/// cancels on Escape (macOS). Clicks on the row or reselection are also
/// committed by the row itself (see `onTapGesture`/`onChange(of: isSelected)`).
private struct InlineRenameField: View {
    @Binding var text: String
    let onCommit: () -> Void
    let onCancel: () -> Void

    @FocusState private var isFocused: Bool

    var body: some View {
        let field = TextField("", text: $text)
            .textFieldStyle(.roundedBorder)
            .lineLimit(1)
            .focused($isFocused)
            .onSubmit(onCommit)
            .onAppear { isFocused = true }
            .onChange(of: isFocused) { focused in
                if !focused { onCommit() }
            }
        #if os(macOS)
        field.onExitCommand(perform: onCancel)
        #else
        field
        #endif
    }
}
