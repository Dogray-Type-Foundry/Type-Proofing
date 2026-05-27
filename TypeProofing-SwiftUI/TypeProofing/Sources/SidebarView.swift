import SwiftUI
import UniformTypeIdentifiers

struct SidebarView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var engine: ProofEngine
    @EnvironmentObject var fonts: FontState
    @EnvironmentObject var ui: UIState
    @EnvironmentObject var page: PageState
    @EnvironmentObject var preview: PreviewState

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 0) {
                    fontsSection
                    Divider().padding(.horizontal, 12)
                    SidebarProofsSection()
                }
                .padding(.horizontal, 4)
            }
            .scrollEdgeEffectStyle(.soft, for: .all)

            Divider()
            outputSection
            Divider()
            generateSection
        }
    }

    // MARK: - Fonts Section

    private var fontsSection: some View {
        VStack(spacing: 0) {
            CollapsibleSectionHeader(
                title: "FONTS",
                detail: "\(fonts.loadedFonts.count) loaded",
                expanded: $ui.fontsSectionExpanded
            )

            if ui.fontsSectionExpanded {
                VStack(alignment: .leading, spacing: 4) {
                    FontsSection()
                }
                .padding(.vertical, 4)
                .frame(maxWidth: .infinity, alignment: .topLeading)

                HStack {
                    HoverButton("Add Fonts", systemImage: "plus") {
                        ui.showFontPicker = true
                    }
                    .accessibilityIdentifier("add-fonts-button")
                    Spacer()
                }
                .padding(.horizontal, 8)
                .padding(.bottom, 8)
            }
        }
    }

    // MARK: - Output Section

    private var outputSection: some View {
        VStack(spacing: 0) {
            CollapsibleSectionHeader(title: "OUTPUT", detail: nil, expanded: $ui.outputSectionExpanded)

            if ui.outputSectionExpanded {
                VStack(spacing: 8) {
                    PDFOutputSection()

                    Picker("", selection: $page.pageFormat) {
                        ForEach(page.pageFormats, id: \.self) { format in
                            Text(format).tag(format)
                        }
                    }
                    .labelsHidden()
                    .fixedSize()
                }
                .padding(.horizontal, 12)
                .padding(.bottom, 8)
            }
        }
    }

    // MARK: - Generate Section

    private var generateSection: some View {
        VStack(spacing: 10) {
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
            .buttonStyle(.glassProminent)
            .tint(state.isFinalPDFStale ? .orange : .dograyPurple)
            .help(state.isFinalPDFStale ? "Final PDF is out of sync with current settings" : "Generate Final PDF")
            .disabled(engine.isGenerating || fonts.enabledFontPaths.isEmpty)

            if engine.isGenerating {
                GenerationProgressView(progress: engine.generationProgress) {
                    engine.cancelGeneration()
                }
            } else {
                ProofRunSummaryCompact(summary: state.cachedRunSummary)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
    }

    // MARK: - Generate

    private func generateProof() async {
        state.previewCoordinator?.pauseForFinalGeneration()
        state.persistState()
        let config = state.buildProofConfig()
        let capturedFingerprint = config.fingerprint()
        engine.refreshRunSummary(config: config)
        preview.finalPDFPath = nil
        preview.finalSections = []
        await Task.yield()
        if let result = await engine.generateProof(config: config) {
            preview.finalPDFPath = result.path
            preview.finalSections = result.sections
            preview.currentPDFPath = result.path
            preview.proofSections = result.sections
            if preview.previewPDFPath == nil {
                preview.previewPDFPath = result.path
                preview.previewSections = result.sections
            }
            state.refreshCurrentConfigFingerprint()
            if preview.currentConfigFingerprint == capturedFingerprint {
                preview.finalGeneratedConfigFingerprint = capturedFingerprint
            }
        }
        state.previewCoordinator?.resumeAfterFinalGeneration()
    }
}

// MARK: - Proofs Section (isolated observation)

private struct SidebarProofsSection: View {
    @EnvironmentObject var proofs: ProofState
    @EnvironmentObject var fonts: FontState
    @EnvironmentObject var state: AppState
    @EnvironmentObject var ui: UIState

    private var visibleProofs: [ProofOption] {
        if fonts.anyFontSupportsArabic { return proofs.proofOptions }
        return proofs.proofOptions.filter { option in
            !(proofs.registryByKey[option.baseType]?.isArabic ?? false)
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            CollapsibleSectionHeader(
                title: "PROOFS",
                detail: "\(proofs.proofOptions.filter(\.enabled).count) of \(visibleProofs.count)",
                expanded: $ui.proofsSectionExpanded
            )

            if ui.proofsSectionExpanded {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(visibleProofs) { option in
                        if let index = proofs.proofOptions.firstIndex(where: { $0.id == option.id }) {
                            SidebarListRow(
                                name: option.name,
                                enabled: Binding(
                                    get: { proofs.proofOptions[index].enabled },
                                    set: { newValue in
                                        proofs.proofOptions[index].enabled = newValue
                                        state.schedulePersistPublic(notifyPreview: false)
                                        state.previewCoordinator?.proofEnableChanged(proofID: option.id)
                                    }
                                ),
                                isLast: option.id == visibleProofs.last?.id,
                                isSelected: proofs.selectedProof == option.id,
                                onRemove: {
                                    state.removeProofOption(at: IndexSet(integer: index))
                                },
                                onTap: {
                                    proofs.selectedProof = option.id
                                    state.requestPreviewNavigation(to: option.id)
                                },
                                onRename: { newName in
                                    proofs.proofOptions[index].name = newName
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

                HStack {
                    HoverButton("Add Proof", systemImage: "plus") {
                        ui.showAddProofSheet = true
                    }
                    .accessibilityIdentifier("add-proof-button")
                    .popover(isPresented: $ui.showAddProofSheet, arrowEdge: .top) {
                        AddProofPopover()
                    }
                    Spacer()
                }
                .padding(.horizontal, 8)
                .padding(.bottom, 8)
            }
        }
    }
}

// MARK: - Collapsible Section Header

struct CollapsibleSectionHeader: View {
    let title: String
    let detail: String?
    @Binding var expanded: Bool

    var body: some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                expanded.toggle()
            }
        } label: {
            HStack {
                Image(systemName: "chevron.right")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(.quaternary)
                    .rotationEffect(expanded ? .degrees(90) : .zero)
                Text(title)
                    .font(.system(size: 11, weight: .medium))
                    .tracking(0.88)
                    .foregroundStyle(.secondary)
                Spacer()
                if let detail {
                    Text(detail)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.tertiary)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
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
                guard let fromIndex = state.proofs.proofOptions.firstIndex(where: { $0.id == uuid }) else { return }
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
