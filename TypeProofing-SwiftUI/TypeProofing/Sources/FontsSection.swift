import SwiftUI
import UniformTypeIdentifiers

struct FontsSection: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var engine: ProofEngine

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if !state.loadedFonts.isEmpty {
                FontSortBar()

                Divider()
            }

            ForEach(Array(state.loadedFonts.enumerated()), id: \.element.id) { index, font in
                SidebarListRow(
                    name: font.name,
                    enabled: Binding(
                        get: { !state.disabledFontPaths.contains(font.id) },
                        set: { enabled in
                            if enabled {
                                state.disabledFontPaths.remove(font.id)
                            } else {
                                state.disabledFontPaths.insert(font.id)
                            }
                            state.schedulePersistPublic()
                        }
                    ),
                    isLast: font.id == state.loadedFonts.last?.id,
                    badge: font.isVariable ? "Variable" : nil,
                    onRemove: {
                        if let idx = state.loadedFonts.firstIndex(where: { $0.id == font.id }) {
                            state.removeFont(at: IndexSet(integer: idx), engine: engine)
                        }
                    }
                ) {
                    if font.isVariable {
                        FontAxesView(
                            font: font,
                            axisValues: Binding(
                                get: { state.axisValuesByFont[font.id] ?? [:] },
                                set: {
                                    state.axisValuesByFont[font.id] = $0
                                    state.schedulePersistPublic()
                                }
                            )
                        )
                    }
                }
                .onDrag {
                    NSItemProvider(object: font.id as NSString)
                }
                .onDrop(of: [.fileURL, .text], delegate: FontDropDelegate(
                    state: state, engine: engine,
                    targetIndex: index
                ))
            }

            if state.loadedFonts.isEmpty {
                Text("Drop font files here or click + Fonts")
                    .foregroundStyle(.tertiary)
                    .font(.caption)
                    .padding(.horizontal, 12)

                Color.clear
                    .frame(height: 40)
                    .onDrop(of: [.fileURL], isTargeted: nil) { providers in
                        handleFileDrop(providers)
                        return true
                    }
            }
        }
        .onDrop(of: [.fileURL], isTargeted: nil) { providers in
            handleFileDrop(providers)
            return true
        }
    }

    private func handleFileDrop(_ providers: [NSItemProvider]) {
        let fontExtensions: Set<String> = ["otf", "ttf", "woff", "woff2"]
        for provider in providers {
            provider.loadItem(forTypeIdentifier: "public.file-url", options: nil) { item, _ in
                guard let data = item as? Data,
                      let url = URL(dataRepresentation: data, relativeTo: nil),
                      fontExtensions.contains(url.pathExtension.lowercased())
                else { return }
                DispatchQueue.main.async {
                    state.addFonts(urls: [url], engine: engine)
                }
            }
        }
    }
}

// MARK: - Font Reorder + File Drop Delegate

struct FontDropDelegate: DropDelegate {
    let state: AppState
    let engine: ProofEngine
    let targetIndex: Int

    private static let fontExtensions: Set<String> = ["otf", "ttf", "woff", "woff2"]

    func performDrop(info: DropInfo) -> Bool {
        // Check for file URLs first (external drag from Finder)
        if info.hasItemsConforming(to: [.fileURL]) {
            let providers = info.itemProviders(for: [.fileURL])
            // If the provider is a text reorder, handle that instead
            if providers.isEmpty || info.hasItemsConforming(to: [.text]) {
                return handleReorder(info: info)
            }
            for provider in providers {
                provider.loadItem(forTypeIdentifier: "public.file-url", options: nil) { item, _ in
                    guard let data = item as? Data,
                          let url = URL(dataRepresentation: data, relativeTo: nil),
                          Self.fontExtensions.contains(url.pathExtension.lowercased())
                    else { return }
                    DispatchQueue.main.async {
                        state.addFonts(urls: [url], engine: engine)
                    }
                }
            }
            return true
        }
        return handleReorder(info: info)
    }

    private func handleReorder(info: DropInfo) -> Bool {
        let providers = info.itemProviders(for: [.text])
        guard let provider = providers.first else { return false }
        provider.loadObject(ofClass: NSString.self) { item, _ in
            guard let draggedID = item as? String,
                  let fromIndex = state.loadedFonts.firstIndex(where: { $0.id == draggedID })
            else { return }
            DispatchQueue.main.async {
                state.moveFonts(from: IndexSet(integer: fromIndex), to: targetIndex > fromIndex ? targetIndex + 1 : targetIndex)
            }
        }
        return true
    }

    func validateDrop(info: DropInfo) -> Bool {
        info.hasItemsConforming(to: [.fileURL]) || info.hasItemsConforming(to: [.text])
    }
}
