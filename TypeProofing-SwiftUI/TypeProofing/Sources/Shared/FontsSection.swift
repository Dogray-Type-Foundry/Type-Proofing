import ProofCore
import SwiftUI
import UniformTypeIdentifiers

struct FontsSection: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var engine: ProofEngine
    @EnvironmentObject var fonts: FontState
    @State private var dragSourceIndex: Int?
    @State private var dropTargetIndex: Int?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if !fonts.loadedFonts.isEmpty {
                FontSortBar()

                Divider()
            }

            ForEach(Array(fonts.loadedFonts.enumerated()), id: \.element.id) { index, font in
                SidebarListRow(
                    name: font.name,
                    enabled: Binding(
                        get: { !fonts.disabledFontPaths.contains(font.id) },
                        set: { enabled in
                            if enabled {
                                fonts.disabledFontPaths.remove(font.id)
                            } else {
                                fonts.disabledFontPaths.insert(font.id)
                            }
                            state.schedulePersistPublic()
                        }
                    ),
                    isLast: font.id == fonts.loadedFonts.last?.id,
                    badge: font.isVariable ? "VF" : nil,
                    onRemove: {
                        if let idx = fonts.loadedFonts.firstIndex(where: { $0.id == font.id }) {
                            state.removeFont(at: IndexSet(integer: idx), engine: engine)
                        }
                    },
                    dragProvider: {
                        dragSourceIndex = index
                        return NSItemProvider(object: font.id as NSString)
                    },
                    detail: {
                        if font.isVariable {
                            FontAxesView(
                                font: font,
                                axisValues: Binding(
                                    get: { fonts.axisValuesByFont[font.id] ?? [:] },
                                    set: {
                                        fonts.axisValuesByFont[font.id] = $0
                                        state.schedulePersistPublic()
                                    }
                                )
                            )
                        }
                    }
                )
                .reorderDropIndicator(index: index, source: dragSourceIndex, target: dropTargetIndex)
                #if os(macOS)
                .onDrop(of: [.fileURL, .text], delegate: FontDropDelegate(
                    state: state, engine: engine,
                    targetIndex: index,
                    dropTargetIndex: $dropTargetIndex
                ))
                #else
                // DropDelegate callbacks are unreliable on touch platforms.
                // Row drops handle reorder only; font-file drops from Files
                // are caught by the window-level handler in CoreWiring.
                .dropDestination(for: String.self) { items, _ in
                    dropTargetIndex = nil
                    guard let draggedID = items.first,
                          let fromIndex = fonts.loadedFonts.firstIndex(where: { $0.id == draggedID })
                    else { return false }
                    state.moveFonts(
                        from: IndexSet(integer: fromIndex),
                        to: index > fromIndex ? index + 1 : index
                    )
                    return true
                } isTargeted: { targeting in
                    if targeting {
                        dropTargetIndex = index
                    } else if dropTargetIndex == index {
                        dropTargetIndex = nil
                    }
                }
                #endif
            }

            if fonts.loadedFonts.isEmpty {
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
        FontFileDropHandler.handle(providers, state: state, engine: engine)
    }
}

enum FontFileDropHandler {
    static let fontExtensions: Set<String> = ["otf", "ttf", "woff", "woff2"]

    static func handle(_ providers: [NSItemProvider], state: AppState, engine: ProofEngine) {
        for provider in providers {
            if provider.canLoadObject(ofClass: URL.self) {
                provider.loadObject(ofClass: URL.self) { url, _ in
                    guard let url, fontExtensions.contains(url.pathExtension.lowercased()) else { return }
                    DispatchQueue.main.async {
                        addWithScope(url, state: state, engine: engine)
                    }
                }
            } else {
                provider.loadItem(forTypeIdentifier: "public.file-url", options: nil) { item, _ in
                    guard let data = item as? Data,
                          let url = URL(dataRepresentation: data, relativeTo: nil),
                          fontExtensions.contains(url.pathExtension.lowercased())
                    else { return }
                    DispatchQueue.main.async {
                        addWithScope(url, state: state, engine: engine)
                    }
                }
            }
        }
    }

    /// Bookmark creation inside `addFonts` needs the URL's security scope
    /// active — without it (iPad sandbox) the bookmark silently fails and the
    /// dropped font vanishes on relaunch.
    @MainActor
    private static func addWithScope(_ url: URL, state: AppState, engine: ProofEngine) {
        let accessed = url.startAccessingSecurityScopedResource()
        state.addFonts(urls: [url], engine: engine)
        if accessed { url.stopAccessingSecurityScopedResource() }
    }
}

// MARK: - Font Reorder + File Drop Delegate

struct FontDropDelegate: DropDelegate {
    let state: AppState
    let engine: ProofEngine
    let targetIndex: Int
    let dropTargetIndex: Binding<Int?>

    func dropEntered(info: DropInfo) {
        // Only reorder drags (not file drops from Finder) show the insertion line.
        guard !info.hasItemsConforming(to: [.fileURL]) else { return }
        dropTargetIndex.wrappedValue = targetIndex
    }

    func dropExited(info: DropInfo) {
        if dropTargetIndex.wrappedValue == targetIndex {
            dropTargetIndex.wrappedValue = nil
        }
    }

    func performDrop(info: DropInfo) -> Bool {
        dropTargetIndex.wrappedValue = nil
        // Check for file URLs first (external drag from Finder)
        if info.hasItemsConforming(to: [.fileURL]) {
            let providers = info.itemProviders(for: [.fileURL])
            // If the provider is a text reorder, handle that instead
            if providers.isEmpty || info.hasItemsConforming(to: [.text]) {
                return handleReorder(info: info)
            }
            FontFileDropHandler.handle(providers, state: state, engine: engine)
            return true
        }
        return handleReorder(info: info)
    }

    private func handleReorder(info: DropInfo) -> Bool {
        let providers = info.itemProviders(for: [.text])
        guard let provider = providers.first else { return false }
        provider.loadObject(ofClass: NSString.self) { item, _ in
            guard let draggedID = item as? String else { return }
            DispatchQueue.main.async {
                guard let fromIndex = state.fonts.loadedFonts.firstIndex(where: { $0.id == draggedID }) else { return }
                state.moveFonts(from: IndexSet(integer: fromIndex), to: targetIndex > fromIndex ? targetIndex + 1 : targetIndex)
            }
        }
        return true
    }

    func validateDrop(info: DropInfo) -> Bool {
        info.hasItemsConforming(to: [.fileURL]) || info.hasItemsConforming(to: [.text])
    }
}
