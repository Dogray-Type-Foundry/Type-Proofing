import SwiftUI

/// A compact bar of reorderable sort-criterion chips displayed above the font list.
/// Each chip shows the property name and an ascending/descending arrow toggle.
/// Users can add criteria from a menu, reorder by drag, and remove with X.
struct FontSortBar: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var fonts: FontState

    private var availableProperties: [FontSortProperty] {
        let used = Set(fonts.fontSortCriteria.map(\.property))
        return FontSortProperty.allCases.filter { !used.contains($0) }
    }

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: "arrow.up.arrow.down")
                .foregroundStyle(.secondary)
                .font(.caption)

            ForEach(fonts.fontSortCriteria) { criterion in
                if let index = fonts.fontSortCriteria.firstIndex(where: { $0.id == criterion.id }) {
                    SortChip(
                        criterion: $fonts.fontSortCriteria[index],
                        onRemove: {
                            fonts.fontSortCriteria.remove(at: index)
                            state.applySortCriteria()
                            state.schedulePersistPublic()
                        }
                    )
                    .onDrag {
                        NSItemProvider(object: criterion.id.uuidString as NSString)
                    }
                    .onDrop(of: [.text], delegate: SortChipDropDelegate(
                        state: state,
                        targetIndex: index
                    ))
                }
            }

            if !availableProperties.isEmpty {
                Menu {
                    ForEach(availableProperties, id: \.self) { property in
                        Button(property.rawValue) {
                            fonts.fontSortCriteria.append(
                                FontSortCriterion(property: property)
                            )
                            state.applySortCriteria()
                            state.schedulePersistPublic()
                        }
                    }
                } label: {
                    Image(systemName: "plus.circle")
                        .foregroundStyle(.secondary)
                        .font(.caption)
                }
                .menuStyle(.borderlessButton)
                .fixedSize()
            }

            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
    }
}

// MARK: - Single Chip

private struct SortChip: View {
    @Binding var criterion: FontSortCriterion
    let onRemove: () -> Void
    @EnvironmentObject var state: AppState

    var body: some View {
        HStack(spacing: 2) {
            Text(criterion.property.rawValue)
                .font(.caption2)
                .lineLimit(1)

            HoverIconButton(systemName: criterion.ascending ? "chevron.up" : "chevron.down", size: 8) {
                criterion.ascending.toggle()
                state.applySortCriteria()
                state.schedulePersistPublic()
            }

            HoverIconButton(systemName: "xmark", size: 7, hoverColor: .red) {
                onRemove()
            }
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 3)
        .background(Color.accentColor.opacity(0.12))
        .cornerRadius(4)
    }
}

// MARK: - Drop Delegate for Chip Reordering

struct SortChipDropDelegate: DropDelegate {
    let state: AppState
    let targetIndex: Int

    func performDrop(info: DropInfo) -> Bool {
        let providers = info.itemProviders(for: [.text])
        guard let provider = providers.first else { return false }
        provider.loadObject(ofClass: NSString.self) { item, _ in
            guard let draggedID = item as? String,
                  let draggedUUID = UUID(uuidString: draggedID)
            else { return }
            DispatchQueue.main.async {
                guard let fromIndex = state.fonts.fontSortCriteria.firstIndex(where: { $0.id == draggedUUID }) else {
                    return
                }
                let dest = targetIndex > fromIndex ? targetIndex + 1 : targetIndex
                state.fonts.fontSortCriteria.move(
                    fromOffsets: IndexSet(integer: fromIndex),
                    toOffset: dest
                )
                state.applySortCriteria()
                state.schedulePersistPublic()
            }
        }
        return true
    }

    func validateDrop(info: DropInfo) -> Bool {
        info.hasItemsConforming(to: [.text])
    }
}
