import ProofCore
import SwiftUI

/// App wiring shared by both platform ContentViews: engine startup,
/// persistence hooks, proof-selection relay, settings import/export, the
/// font picker, and font-file drop. Keeping this in one place means a new
/// hook is written once and exists on both platforms.
struct CoreWiring: ViewModifier {
    @EnvironmentObject var engine: ProofEngine
    @EnvironmentObject var state: AppState
    @EnvironmentObject var ui: UIState
    @EnvironmentObject var page: PageState
    @EnvironmentObject var fonts: FontState
    @EnvironmentObject var proofs: ProofState
    @EnvironmentObject var annotations: AnnotationStore

    let previewCoordinator: PreviewCoordinator
    let pdfCoordinator: any PreviewNavigationHandling

    func body(content: Content) -> some View {
        content
            .onReceive(engine.$isReady) { ready in
                if ready {
                    state.loadFromEngine(engine)
                    previewCoordinator.configure(state: state, engine: engine)
                    state.previewCoordinator = previewCoordinator
                    state.pdfCoordinator = pdfCoordinator
                    previewCoordinator.startInitialPreview()
                }
            }
            .onChange(of: page.pageFormat) { _ in
                state.schedulePersistPublic()
            }
            .onChange(of: page.showBaselines) { _ in
                state.schedulePersistPublic()
            }
            .onChange(of: page.showFooter) { _ in
                state.schedulePersistPublic()
            }
            .onChange(of: fonts.styleSourceMode) { _ in
                state.refreshFontStyles(engine: engine)
                state.schedulePersistPublic()
            }
            // Style lists and the feature list are derived from the enabled
            // fonts in order — keep them in sync when fonts are toggled,
            // reordered, or sorted (add/remove refresh directly; the repeat
            // here is idempotent).
            .onChange(of: fonts.disabledFontPaths) { _ in
                state.refreshFontStyles(engine: engine)
                state.applyAvailableFontFeatures(engine: engine)
            }
            .onChange(of: fonts.fontPaths) { _ in
                state.refreshFontStyles(engine: engine)
                state.applyAvailableFontFeatures(engine: engine)
            }
            .onChange(of: fonts.axisValuesByFont) { _ in
                if fonts.styleSourceMode == .customPositions {
                    state.scheduleRefreshFontStyles(engine: engine)
                }
            }
            .onChange(of: proofs.selectedProof) { _ in
                previewCoordinator.selectedProofChanged()
            }
            .fileImporter(
                isPresented: $ui.showSettingsImporter,
                allowedContentTypes: [.json]
            ) { result in
                if case .success(let url) = result {
                    if state.importState(from: url, engine: engine) {
                        print("Settings imported from: \(url.path)")
                    }
                }
            }
            .fileExporter(
                isPresented: Binding(
                    get: { ui.settingsExportRequest != nil },
                    set: { if !$0 { ui.settingsExportRequest = nil } }
                ),
                document: ui.settingsExportRequest.map(SettingsJSONDocument.init),
                contentType: .json,
                defaultFilename: "TypeProofing Settings"
            ) { _ in }
            .fileImporter(
                isPresented: $ui.showFontPicker,
                allowedContentTypes: fontFileContentTypes,
                allowsMultipleSelection: true
            ) { result in
                if case .success(let urls) = result {
                    let accessed = urls.filter { $0.startAccessingSecurityScopedResource() }
                    state.addFonts(urls: urls, engine: engine)
                    for url in accessed { url.stopAccessingSecurityScopedResource() }
                }
            }
            .onDrop(of: [.fileURL], isTargeted: nil) { providers in
                // Fonts are locked while annotations exist (the sidebar is
                // disabled for the same reason) — a window-level drop must
                // not slip past that and shift frozen pagination.
                guard !annotations.hasAnyAnnotations else { return false }
                FontFileDropHandler.handle(providers, state: state, engine: engine)
                return true
            }
    }
}

/// Loading / startup-error screen shown until the engine is ready.
struct EngineLoadingView: View {
    @EnvironmentObject var engine: ProofEngine

    var body: some View {
        VStack(spacing: 20) {
            if let error = engine.errorMessage {
                Label(error, systemImage: "exclamationmark.triangle")
                    .foregroundStyle(.red)
            } else {
                ProgressView("Loading…")
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
