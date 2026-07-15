import ProofCore
import SwiftUI

struct ContentView: View {
    @EnvironmentObject var engine: ProofEngine
    @EnvironmentObject var state: AppState
    @EnvironmentObject var ui: UIState
    @EnvironmentObject var page: PageState
    @EnvironmentObject var preview: PreviewState
    @EnvironmentObject var fonts: FontState
    @StateObject private var previewCoordinator = PreviewCoordinator()
    @StateObject private var pdfCoordinator = PDFViewCoordinator()
    @State private var columnVisibility: NavigationSplitViewVisibility = .all
    @State private var showThumbnails = false

    var body: some View {
        Group {
            if !engine.isReady {
                EngineLoadingView()
            } else {
                NavigationSplitView(columnVisibility: $columnVisibility) {
                    HStack(spacing: 0) {
                        SidebarView()
                        // Our own resize handle (fixed column width disables
                        // the system one): drag to resize, pull well past the
                        // minimum to collapse — macOS split-view behavior.
                        PanelResizeHandle(
                            width: $ui.sidebarWidth,
                            range: 180...400,
                            growsRight: true
                        ) {
                            withAnimation { columnVisibility = .detailOnly }
                        }
                    }
                    .navigationTitle("Type Proofing")
                    .navigationBarTitleDisplayMode(.inline)
                    // Flick the panel body toward its edge to hide it. Plain
                    // `.gesture` priority: sliders, reorder drags, and
                    // scrolling all claim their touches first.
                    .gesture(panelDismissFlick(direction: .left) {
                        withAnimation { columnVisibility = .detailOnly }
                    })
                    .navigationSplitViewColumnWidth(ui.sidebarWidth)
                } detail: {
                    detailPane
                        // Settings live in a trailing inspector, mirroring the
                        // macOS layout (sidebar left, settings right).
                        .inspector(isPresented: $ui.showInspector) {
                            HStack(spacing: 0) {
                                PanelResizeHandle(
                                    width: $ui.inspectorWidth,
                                    range: 240...500,
                                    growsRight: false
                                ) {
                                    ui.showInspector = false
                                }
                                SettingsPanelView()
                            }
                            .inspectorColumnWidth(ui.inspectorWidth)
                            // Flick the panel toward its edge to hide it.
                            .gesture(panelDismissFlick(direction: .right) {
                                ui.showInspector = false
                            })
                        }
                }
                .navigationSplitViewStyle(.balanced)
            }
        }
        .tint(.dograyPurple)
        .modifier(CoreWiring(
            previewCoordinator: previewCoordinator,
            pdfCoordinator: pdfCoordinator
        ))
        // "Open in Type Proofing" from Files hands over a security-scoped URL.
        .onOpenURL { url in
            let accessed = url.startAccessingSecurityScopedResource()
            state.addFonts(urls: [url], engine: engine)
            if accessed { url.stopAccessingSecurityScopedResource() }
        }
    }

    private var detailPane: some View {
        ZStack(alignment: .top) {
            HStack(spacing: 0) {
                if showThumbnails, preview.previewPDFPath != nil {
                    ThumbnailStrip(
                        sections: preview.previewSections,
                        pdfCoordinator: pdfCoordinator
                    )
                    .frame(width: 116)
                    Divider()
                }
                if let pdfPath = preview.previewPDFPath {
                    switch page.viewMode {
                    case .page:
                        PDFKitView(
                            pdfPath: pdfPath,
                            sections: preview.previewSections,
                            pdfCoordinator: pdfCoordinator
                        )
                    case .grid:
                        GridViewCanvas(
                            pdfPath: pdfPath,
                            sections: preview.previewSections,
                            pdfCoordinator: pdfCoordinator
                        )
                    case .compare:
                        CompareViewCanvas(
                            pdfPath: pdfPath,
                            pdfCoordinator: pdfCoordinator,
                            vertical: page.compareVertical
                        )
                    }
                } else {
                    PDFPlaceholderView(hasFonts: !fonts.enabledFontPaths.isEmpty)
                }
            }
            PDFFloatingToolbar(
                columnVisibility: $columnVisibility,
                showThumbnails: $showThumbnails,
                pdfCoordinator: pdfCoordinator
            )
            HStack {
                Spacer()
                VStack(alignment: .trailing, spacing: 8) {
                    shareMenuPill
                    DiagnosticChip()
                }
            }
        }
        // The nav bar's only job here was hosting share + the app menu;
        // those float over the preview now, so reclaim the space.
        .toolbar(.hidden, for: .navigationBar)
        // Edge swipes: drag inward from an edge to reveal that panel, drag
        // outward (toward the edge) to hide it.
        .overlay(alignment: .leading) {
            EdgeSwipeStrip(
                onSwipeIn: { withAnimation { columnVisibility = .all } },
                onSwipeOut: { withAnimation { columnVisibility = .detailOnly } },
                inward: .right
            )
        }
        .overlay(alignment: .trailing) {
            EdgeSwipeStrip(
                onSwipeIn: { ui.showInspector = true },
                onSwipeOut: { ui.showInspector = false },
                inward: .left
            )
        }
    }

    /// A fast horizontal flick that dismisses a side panel. Requires clear
    /// horizontal dominance and real velocity so scrolls and slow drags
    /// (including the system's divider resize) never trigger it.
    private func panelDismissFlick(
        direction: EdgeSwipeStrip.Direction,
        action: @escaping () -> Void
    ) -> some Gesture {
        DragGesture(minimumDistance: 30)
            .onEnded { value in
                let dx = value.translation.width
                let vx = value.velocity.width
                guard abs(dx) > abs(value.translation.height) * 1.5 else { return }
                switch direction {
                case .left:
                    if dx < -50, vx < -500 { action() }
                case .right:
                    if dx > 50, vx > 500 { action() }
                }
            }
    }

    /// Share + app menu, floating top-right over the preview.
    private var shareMenuPill: some View {
        HStack(spacing: 2) {
            let sharePath = preview.previewPDFPath ?? preview.finalPDFPath
            ShareLink(item: URL(fileURLWithPath: sharePath ?? "")) {
                Image(systemName: "square.and.arrow.up")
                    .frame(width: 32, height: 30)
                    .foregroundStyle(.secondary)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(preview.previewPDFPath == nil)

            // Pre-26 iPads have no menu bar; surface the app menu here too.
            Menu {
                Button("Import Settings…") { ui.showSettingsImporter = true }
                Button("Export Settings…") {
                    ui.settingsExportRequest = state.exportedSettingsJSON()
                }
                Divider()
                Button("Reset Settings", role: .destructive) { state.resetAllSettings() }
                Button("Reset Fonts", role: .destructive) { state.resetFonts() }
            } label: {
                Image(systemName: "ellipsis.circle")
                    .frame(width: 32, height: 30)
                    .foregroundStyle(.secondary)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .liquidGlassCapsule()
        .padding(.top, 10)
        .padding(.trailing, 10)
    }
}

// MARK: - PanelResizeHandle

/// Slim grab-handle on a panel's inner edge: drag to resize the column, keep
/// pulling well past the minimum width to collapse the panel entirely.
private struct PanelResizeHandle: View {
    @Binding var width: CGFloat
    let range: ClosedRange<CGFloat>
    /// true when dragging right grows the panel (leading sidebar);
    /// false when dragging right shrinks it (trailing inspector).
    let growsRight: Bool
    let onCollapse: () -> Void

    @State private var startWidth: CGFloat?

    var body: some View {
        Capsule()
            .fill(Color.secondary.opacity(0.45))
            .frame(width: 4, height: 36)
            .frame(width: 16)
            .frame(maxHeight: .infinity)
            // Negative inset widens the grabbable area (~36pt) without
            // taking more layout width from the panel.
            .contentShape(Rectangle().inset(by: -10))
            .highPriorityGesture(
                // Global coordinates: the handle itself moves while the column
                // resizes, so local-space translations feed back into the drag
                // and make the panel oscillate.
                DragGesture(minimumDistance: 1, coordinateSpace: .global)
                    .onChanged { value in
                        if startWidth == nil { startWidth = width }
                        let delta = growsRight ? value.translation.width : -value.translation.width
                        width = min(max(startWidth! + delta, range.lowerBound), range.upperBound)
                    }
                    .onEnded { value in
                        let delta = growsRight ? value.translation.width : -value.translation.width
                        let proposed = (startWidth ?? width) + delta
                        startWidth = nil
                        if proposed < range.lowerBound - 60 {
                            onCollapse()
                        }
                    }
            )
    }
}

// MARK: - EdgeSwipeStrip

/// A narrow touch strip along a screen edge that turns horizontal drags into
/// show/hide gestures for the adjacent panel.
private struct EdgeSwipeStrip: View {
    enum Direction { case left, right }

    let onSwipeIn: () -> Void
    let onSwipeOut: () -> Void
    /// The drag direction that means "reveal the panel on my edge".
    let inward: Direction

    var body: some View {
        Color.clear
            .frame(width: 22)
            .frame(maxHeight: .infinity)
            .contentShape(Rectangle())
            .highPriorityGesture(
                DragGesture(minimumDistance: 30)
                    .onEnded { value in
                        let dx = value.translation.width
                        // Ignore mostly-vertical drags (scrolling).
                        guard abs(dx) > abs(value.translation.height) else { return }
                        let inwardDrag = inward == .right ? dx > 0 : dx < 0
                        if inwardDrag {
                            onSwipeIn()
                        } else {
                            onSwipeOut()
                        }
                    }
            )
    }
}
