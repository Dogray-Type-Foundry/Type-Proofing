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
                        } else if state.isFinalPDFStale {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundStyle(.yellow)
                        } else {
                            Image(systemName: "wand.and.rays")
                        }
                        Text("Generate Final PDF")
                    }
                    .frame(maxWidth: .infinity)
                }
                .controlSize(.large)
                .buttonStyle(.borderedProminent)
                .tint(state.isFinalPDFStale ? .orange : nil)
                .help(state.isFinalPDFStale ? "Final PDF is out of sync with current settings" : "Generate Final PDF")
                .disabled(engine.isGenerating || state.enabledFontPaths.isEmpty)

                if engine.isGenerating {
                    GenerationProgressView(progress: engine.generationProgress) {
                        engine.cancelGeneration()
                    }
                } else {
                    ProofRunSummaryCompact(summary: state.makeRunSummary())
                }

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
            .accessibilityIdentifier("sidebar-tabs")

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
                                        state.schedulePersistPublic(notifyPreview: false)
                                        state.previewCoordinator?.proofEnableChanged(proofID: option.id)
                                    }
                                ),
                                isLast: option.id == visibleProofs.last?.id,
                                isSelected: state.selectedProof == option.id,
                                onRemove: {
                                    state.removeProofOption(at: IndexSet(integer: index))
                                },
                                onTap: {
                                    state.selectedProof = option.id
                                    state.requestPreviewNavigation(to: option.id)
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
                .accessibilityIdentifier("add-proof-button")
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
                .frame(maxWidth: .infinity, alignment: .topLeading)
            }
            .onDrop(of: [.fileURL], isTargeted: nil) { providers in
                FontFileDropHandler.handle(providers, state: state, engine: engine)
                return true
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
                .accessibilityIdentifier("add-fonts-button")
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
        state.previewCoordinator?.pauseForFinalGeneration()
        state.persistState()
        let config = state.buildProofConfig()
        let capturedFingerprint = config.fingerprint()
        engine.refreshRunSummary(config: config)
        // Clear previous results before generating
        state.finalPDFPath = nil
        state.finalSections = []
        // Yield so the UI can show the cleared state before blocking on Python
        await Task.yield()
        if let result = await engine.generateProof(config: config) {
            state.finalPDFPath = result.path
            state.finalSections = result.sections
            state.currentPDFPath = result.path
            state.proofSections = result.sections
            if state.previewPDFPath == nil {
                state.previewPDFPath = result.path
                state.previewSections = result.sections
            }
            state.refreshCurrentConfigFingerprint()
            if state.currentConfigFingerprint == capturedFingerprint {
                state.finalGeneratedConfigFingerprint = capturedFingerprint
            }
        }
        state.previewCoordinator?.resumeAfterFinalGeneration()
    }
}

// MARK: - Run Summary

private struct ProofRunSummaryCompact: View {
    let summary: ProofRunSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                Label("\(summary.fontCount)", systemImage: "textformat")
                Label("\(summary.enabledProofCount)", systemImage: "doc.text")
                Label("\(summary.totalAxisInstances)", systemImage: "slider.horizontal.3")
            }
            .font(.caption)
            .foregroundStyle(.secondary)

            if let warning = summary.warnings.first {
                Label(warning, systemImage: "exclamationmark.triangle")
                    .font(.caption2)
                    .foregroundStyle(.orange)
                    .lineLimit(2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct GenerationProgressView: View {
    let progress: GenerationProgress?
    let onCancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            if let progress {
                Text(progress.proofName)
                    .font(.caption)
                    .lineLimit(1)
                ProgressView(
                    value: Double(progress.proofIndex),
                    total: Double(max(progress.proofCount, 1))
                )
                Text("Font \(progress.fontIndex)/\(max(progress.fontCount, 1))")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            } else {
                ProgressView()
                    .controlSize(.small)
            }
            Button("Cancel", action: onCancel)
                .controlSize(.small)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
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
                  let uuid = UUID(uuidString: draggedID)
            else { return }
            Task { @MainActor in
                guard let fromIndex = state.proofOptions.firstIndex(where: { $0.id == uuid }) else { return }
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
