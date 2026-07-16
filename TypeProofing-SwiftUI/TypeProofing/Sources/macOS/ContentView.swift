import ProofCore
import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject var engine: ProofEngine
    @EnvironmentObject var state: AppState
    @EnvironmentObject var ui: UIState
    @EnvironmentObject var page: PageState
    @EnvironmentObject var preview: PreviewState
    @EnvironmentObject var fonts: FontState
    @StateObject private var previewCoordinator = PreviewCoordinator()
    @StateObject private var pdfCoordinator = PDFViewCoordinator()

    var body: some View {
        Group {
            if !engine.isReady {
                loadingView
            } else {
                mainLayout
            }
        }
        .frame(minWidth: 900, minHeight: 600)
        .tint(.dograyPurple)
        .modifier(CoreWiring(
            previewCoordinator: previewCoordinator,
            pdfCoordinator: pdfCoordinator
        ))
    }

    // MARK: - Loading

    private var loadingView: some View {
        EngineLoadingView()
    }

    // MARK: - Main Layout

    private var mainLayout: some View {
        HStack(spacing: 0) {
            if ui.showSidebar {
                SidebarView()
                    .frame(width: ui.sidebarWidth)
                    .liquidGlassRect(cornerRadius: 12)
                    .transition(.move(edge: .leading))
                PanelDragHandle(
                    width: $ui.sidebarWidth,
                    minWidth: 180, maxWidth: 400
                )
            }
            if ui.showThumbnailStrip {
                ThumbnailStripView(
                    pdfPath: preview.previewPDFPath,
                    sections: preview.previewSections,
                    pdfCoordinator: pdfCoordinator
                )
                .frame(width: ui.thumbnailStripWidth)
                .liquidGlassRect(cornerRadius: 12)
                .transition(.move(edge: .leading))
                PanelDragHandle(
                    width: $ui.thumbnailStripWidth,
                    minWidth: 100, maxWidth: 260
                )
            }
            ZStack(alignment: .top) {
                if let pdfPath = preview.previewPDFPath {
                    switch page.viewMode {
                    case .page:
                        PDFCanvasView(
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
                FloatingToolbar(pdfCoordinator: pdfCoordinator)
                HStack {
                    Spacer()
                    DiagnosticChip()
                }
            }
            .frame(minWidth: 400)
            if ui.showInspector {
                PanelDragHandle(
                    width: $ui.inspectorWidth,
                    minWidth: 240, maxWidth: 500,
                    inverted: true
                )
                SettingsPanelView()
                    .frame(width: ui.inspectorWidth)
                    .liquidGlassRect(cornerRadius: 12)
                    .transition(.move(edge: .trailing))
            }
        }
        .padding(6)
        .background(.background)
        .animation(.easeInOut(duration: 0.25), value: ui.showSidebar)
        .animation(.easeInOut(duration: 0.25), value: ui.showThumbnailStrip)
        .animation(.easeInOut(duration: 0.25), value: ui.showInspector)
        .toolbar {
            ToolbarItemGroup(placement: .automatic) {
                HStack(spacing: 2) {
                    let sharePath = preview.previewPDFPath ?? preview.finalPDFPath
                    ShareLink(item: URL(fileURLWithPath: sharePath ?? "")) {
                        Image(systemName: "square.and.arrow.up")
                    }
                    .help("Share PDF")
                    .disabled(preview.previewPDFPath == nil)

                    Button {} label: {
                        Image(systemName: "arrow.left.arrow.right")
                    }
                    .help("Compare (coming soon)")
                    .disabled(true)

                    Button {} label: {
                        Image(systemName: "clock")
                    }
                    .help("Version history (coming soon)")
                    .disabled(true)
                }
                .liquidGlassCapsule()
            }
        }
    }
}

// MARK: - FloatingToolbar

struct FloatingToolbar: View {
    @EnvironmentObject var ui: UIState
    @EnvironmentObject var page: PageState
    @ObservedObject var pdfCoordinator: PDFViewCoordinator

    var body: some View {
        HStack(spacing: 12) {
            HStack(spacing: 2) {
                toolbarButton("sidebar.leading", active: ui.showSidebar, help: "Toggle sidebar") {
                    ui.showSidebar.toggle()
                }
                toolbarButton("rectangle.split.3x1", active: ui.showThumbnailStrip, help: "Toggle thumbnails") {
                    ui.showThumbnailStrip.toggle()
                }
                toolbarButton("sidebar.trailing", active: ui.showInspector, help: "Toggle inspector") {
                    ui.showInspector.toggle()
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .liquidGlassCapsule()

            HStack(spacing: 2) {
                toolbarButton("doc.richtext", active: page.viewMode == .page, help: "Page view") {
                    page.viewMode = .page
                }
                toolbarButton("square.grid.2x2", active: page.viewMode == .grid, help: "Grid view") {
                    page.viewMode = .grid
                }
                toolbarButton("arrow.left.arrow.right", active: page.viewMode == .compare, help: "Compare view") {
                    page.viewMode = .compare
                }

                if page.viewMode == .compare {
                    Divider()
                        .frame(height: 16)
                        .padding(.horizontal, 4)
                    toolbarButton(
                        page.compareVertical ? "rectangle.split.1x2" : "rectangle.split.2x1",
                        active: false,
                        help: page.compareVertical ? "Side by side" : "Stacked"
                    ) {
                        page.compareVertical.toggle()
                    }
                }

                Divider()
                    .frame(height: 16)
                    .padding(.horizontal, 4)

                toolbarButton("line.3.horizontal", active: page.showBaselines, help: "Baseline grid") {
                    page.showBaselines.toggle()
                }
                toolbarButton("text.append", active: page.showFooter, help: page.showFooter ? "Hide footer" : "Show footer") {
                    page.showFooter.toggle()
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .liquidGlassCapsule()

            HStack(spacing: 2) {
                Button { zoom(by: -0.1) } label: {
                    Image(systemName: "minus")
                        .frame(width: 32, height: 28)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .help("Zoom out")

                TextField("", text: Binding(
                    get: { "\(pdfCoordinator.zoomPercent)" },
                    set: { newValue in
                        if let pct = Int(newValue), pct >= 10, pct <= 800 {
                            pdfCoordinator.pdfView?.autoScales = false
                            pdfCoordinator.pdfView?.scaleFactor = CGFloat(pct) / 100.0
                        }
                    }
                ))
                .font(.system(size: 11, design: .monospaced))
                .textFieldStyle(.plain)
                .frame(width: 34)
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .onSubmit {
                    let text = "\(pdfCoordinator.zoomPercent)"
                    if let pct = Int(text), pct >= 10, pct <= 800 {
                        pdfCoordinator.pdfView?.autoScales = false
                        pdfCoordinator.pdfView?.scaleFactor = CGFloat(pct) / 100.0
                    }
                }
                Text("%")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(.tertiary)

                Button { zoom(by: 0.1) } label: {
                    Image(systemName: "plus")
                        .frame(width: 32, height: 28)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .help("Zoom in")

                Button { fitToWindow() } label: {
                    Image(systemName: "arrow.up.left.and.arrow.down.right")
                        .frame(width: 32, height: 28)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .help("Fit to window")
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .liquidGlassCapsule()
        }
        .padding(.top, 10)
    }

    private func toolbarButton(_ systemImage: String, active: Bool, help: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .frame(width: 24, height: 24)
                .foregroundStyle(active ? Color.accentColor : .secondary)
        }
        .buttonStyle(.plain)
        .help(help)
    }

    private func zoom(by delta: CGFloat) {
        guard let pdfView = pdfCoordinator.pdfView else { return }
        pdfView.autoScales = false
        pdfView.scaleFactor = max(0.1, min(pdfView.scaleFactor + delta, 8.0))
    }

    private func fitToWindow() {
        guard let pdfView = pdfCoordinator.pdfView else { return }
        pdfView.autoScales = true
    }
}

// MARK: - AddProofPopover
// MARK: - Panel Drag Handle

struct PanelDragHandle: View {
    @Binding var width: CGFloat
    var minWidth: CGFloat = 140
    var maxWidth: CGFloat = 500
    var inverted: Bool = false
    @State private var startWidth: CGFloat?

    var body: some View {
        Color.clear
            .frame(width: 6)
            .contentShape(Rectangle())
            .onHover { hovering in
                #if os(macOS)
                if hovering {
                    NSCursor.resizeLeftRight.push()
                } else {
                    NSCursor.pop()
                }
                #endif
            }
            .gesture(
                DragGesture(coordinateSpace: .global)
                    .onChanged { value in
                        if startWidth == nil { startWidth = width }
                        let delta = inverted ? -value.translation.width : value.translation.width
                        width = max(minWidth, min(startWidth! + delta, maxWidth))
                    }
                    .onEnded { _ in
                        startWidth = nil
                    }
            )
    }
}
