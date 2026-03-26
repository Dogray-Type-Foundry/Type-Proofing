import SwiftUI
import UniformTypeIdentifiers

enum SidebarTab: String, CaseIterable {
    case fonts = "Fonts"
    case proofs = "Proofs"
}

struct SidebarView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var engine: ProofEngine
    @State private var selectedTab: SidebarTab = .fonts

    var body: some View {
        VStack(spacing: 0) {
            // MARK: - Controls (always visible)

            VStack(spacing: 10) {
                // Generate button — full width
                Button {
                    Task { await generateProof() }
                } label: {
                    HStack(spacing: 6) {
                        if engine.isGenerating {
                            ProgressView()
                                .controlSize(.small)
                        } else {
                            Image(systemName: "wand.and.rays")
                        }
                        Text("Generate")
                    }
                    .frame(maxWidth: .infinity)
                }
                .controlSize(.large)
                .buttonStyle(.borderedProminent)
                .help("Generate Proof")
                .disabled(engine.isGenerating || state.enabledFontPaths.isEmpty)

                // Page format + Grid on one line
                HStack(spacing: 8) {
                    Picker("", selection: $state.pageFormat) {
                        ForEach(state.pageFormats, id: \.self) { format in
                            Text(format).tag(format)
                        }
                    }
                    .labelsHidden()
                    .fixedSize()

                    Spacer()

                    Toggle(isOn: $state.showBaselines) {
                        Label("Grid", systemImage: "grid")
                            .font(.caption)
                    }
                    .toggleStyle(.switch)
                    .controlSize(.mini)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)

            Divider()

            // MARK: - Tab Picker

            Picker("", selection: $selectedTab) {
                ForEach(SidebarTab.allCases, id: \.self) { tab in
                    Text(tab.rawValue).tag(tab)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .padding(.horizontal, 10)
            .padding(.vertical, 6)

            // MARK: - Tab Content

            switch selectedTab {
            case .proofs:
                proofsTab
            case .fonts:
                fontsTab
            }
        }
    }

    // MARK: - Proofs Tab

    /// Proof options filtered by script support.
    private var visibleProofs: [ProofOption] {
        if state.anyFontSupportsArabic { return state.proofOptions }
        return state.proofOptions.filter { option in
            !(state.registryByKey[option.baseType]?.isArabic ?? false)
        }
    }

    private var proofsTab: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(visibleProofs) { option in
                        if let index = state.proofOptions.firstIndex(where: { $0.id == option.id }) {
                            SidebarListRow(
                                name: option.name,
                                enabled: Binding(
                                    get: { state.proofOptions[index].enabled },
                                    set: { newValue in
                                        state.proofOptions[index].enabled = newValue
                                        state.schedulePersistPublic()
                                    }
                                ),
                                isLast: option.id == visibleProofs.last?.id,
                                isSelected: state.selectedProof == option.id,
                                onRemove: {
                                    state.removeProofOption(at: IndexSet(integer: index))
                                },
                                onTap: {
                                    state.selectedProof = option.id
                                },
                                onRename: { newName in
                                    state.proofOptions[index].name = newName
                                    state.schedulePersistPublic()
                                }
                            )
                            .onDrag {
                                NSItemProvider(object: option.id.uuidString as NSString)
                            }
                            .onDrop(of: [.text], delegate: ProofDropDelegate(
                                state: state,
                                targetIndex: index
                            ))
                        }
                    }
                }
                .padding(.vertical, 4)
            }

            Divider()

            HStack {
                HoverButton("Add Proof", systemImage: "plus") {
                    state.showAddProofSheet = true
                }
                .popover(isPresented: $state.showAddProofSheet, arrowEdge: .top) {
                    AddProofPopover()
                }

                Spacer()
            }
            .padding(8)
        }
    }

    // MARK: - Fonts Tab

    private var fontsTab: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 4) {
                    FontsSection()
                }
                .padding(.vertical, 4)
            }

            Divider()

            PDFOutputSection()
                .padding(.horizontal, 12)
                .padding(.vertical, 8)

            Divider()

            HStack {
                HoverButton("Add Fonts", systemImage: "plus") {
                    state.showFontPicker = true
                }
                Spacer()
            }
            .padding(8)
            .fileImporter(
                isPresented: $state.showFontPicker,
                allowedContentTypes: [
                    UTType(filenameExtension: "otf") ?? .data,
                    UTType(filenameExtension: "ttf") ?? .data,
                    UTType(filenameExtension: "woff") ?? .data,
                    UTType(filenameExtension: "woff2") ?? .data,
                ],
                allowsMultipleSelection: true
            ) { result in
                switch result {
                case .success(let urls):
                    let accessed = urls.filter { $0.startAccessingSecurityScopedResource() }
                    state.addFonts(urls: accessed, engine: engine)
                    for url in accessed {
                        url.stopAccessingSecurityScopedResource()
                    }
                case .failure(let error):
                    print("Font import error: \(error)")
                }
            }
        }
    }

    // MARK: - Generate

    private func generateProof() async {
        state.persistState()
        let config = state.buildProofConfig()
        // Clear previous results before generating
        state.currentPDFPath = nil
        state.proofSections = []
        // Yield so the UI can show the cleared state before blocking on Python
        await Task.yield()
        if let result = await engine.generateProof(config: config) {
            state.currentPDFPath = result.path
            state.proofSections = result.sections
        }
    }
}

// MARK: - Proof Reorder Drop Delegate

struct ProofDropDelegate: DropDelegate {
    let state: AppState
    let targetIndex: Int

    func performDrop(info: DropInfo) -> Bool {
        let providers = info.itemProviders(for: [.text])
        guard let provider = providers.first else { return false }
        provider.loadObject(ofClass: NSString.self) { item, _ in
            guard let draggedID = item as? String,
                  let uuid = UUID(uuidString: draggedID),
                  let fromIndex = state.proofOptions.firstIndex(where: { $0.id == uuid })
            else { return }
            DispatchQueue.main.async {
                state.moveProofOptions(
                    from: IndexSet(integer: fromIndex),
                    to: targetIndex > fromIndex ? targetIndex + 1 : targetIndex
                )
            }
        }
        return true
    }

    func validateDrop(info: DropInfo) -> Bool {
        info.hasItemsConforming(to: [.text])
    }
}
