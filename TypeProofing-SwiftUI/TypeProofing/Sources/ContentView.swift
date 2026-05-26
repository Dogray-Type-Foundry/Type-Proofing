import SwiftUI
import UniformTypeIdentifiers

extension Color {
    static let dograyPurple = Color(red: 0.380, green: 0, blue: 0.878)
}

struct ContentView: View {
    @EnvironmentObject var engine: ProofEngine
    @EnvironmentObject var state: AppState
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
        .onReceive(engine.$isReady) { ready in
            if ready {
                state.loadFromEngine(engine)
                previewCoordinator.configure(state: state, engine: engine)
                state.previewCoordinator = previewCoordinator
                previewCoordinator.startInitialPreview()
            }
        }
        .onChange(of: state.pageFormat) { _ in
            state.schedulePersistPublic()
        }
        .onChange(of: state.showBaselines) { _ in
            state.schedulePersistPublic()
        }
        .onChange(of: state.selectedProof) { _ in
            previewCoordinator.selectedProofChanged()
        }
        // Add-proof popover is now presented from SidebarView
        .fileImporter(
            isPresented: $state.showSettingsImporter,
            allowedContentTypes: [.json]
        ) { result in
            if case .success(let url) = result {
                importSettings(from: url)
            }
        }
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
            if case .success(let urls) = result {
                for url in urls { _ = url.startAccessingSecurityScopedResource() }
                state.addFonts(urls: urls, engine: engine)
                for url in urls { url.stopAccessingSecurityScopedResource() }
            }
        }
        .onDrop(of: [.fileURL], isTargeted: nil) { providers in
            FontFileDropHandler.handle(providers, state: state, engine: engine)
            return true
        }
    }

    // MARK: - Loading

    private var loadingView: some View {
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

    // MARK: - Main Layout

    private var mainLayout: some View {
        HStack(spacing: 0) {
            if state.showSidebar {
                SidebarView()
                    .frame(width: state.sidebarWidth)
                    .glassEffect(.regular.tint(.clear), in: .rect(cornerRadius: 12))
                    .transition(.move(edge: .leading))
                PanelDragHandle(
                    width: $state.sidebarWidth,
                    minWidth: 180, maxWidth: 400
                )
            }
            if state.showThumbnailStrip {
                ThumbnailStripView(
                    pdfPath: state.previewPDFPath,
                    sections: state.previewSections,
                    pdfCoordinator: pdfCoordinator
                )
                .frame(width: state.thumbnailStripWidth)
                .glassEffect(.regular.tint(.clear), in: .rect(cornerRadius: 12))
                .transition(.move(edge: .leading))
                PanelDragHandle(
                    width: $state.thumbnailStripWidth,
                    minWidth: 100, maxWidth: 260
                )
            }
            ZStack(alignment: .top) {
                if let pdfPath = state.previewPDFPath {
                    switch state.viewMode {
                    case .page:
                        PDFCanvasView(
                            pdfPath: pdfPath,
                            sections: state.previewSections,
                            navigationRequest: state.previewNavigationRequest,
                            pdfCoordinator: pdfCoordinator
                        )
                    case .grid:
                        GridViewCanvas(
                            pdfPath: pdfPath,
                            sections: state.previewSections,
                            pdfCoordinator: pdfCoordinator
                        )
                    case .compare:
                        CompareViewCanvas(
                            pdfPath: pdfPath,
                            pdfCoordinator: pdfCoordinator,
                            vertical: state.compareVertical
                        )
                    }
                } else {
                    PDFPlaceholderView(hasFonts: !state.enabledFontPaths.isEmpty)
                }
                FloatingToolbar(pdfCoordinator: pdfCoordinator)
                HStack {
                    Spacer()
                    DiagnosticChip()
                }
            }
            .frame(minWidth: 400)
            if state.showInspector {
                PanelDragHandle(
                    width: $state.inspectorWidth,
                    minWidth: 240, maxWidth: 500,
                    inverted: true
                )
                SettingsPanelView()
                    .frame(width: state.inspectorWidth)
                    .glassEffect(.regular.tint(.clear), in: .rect(cornerRadius: 12))
                    .transition(.move(edge: .trailing))
            }
        }
        .padding(6)
        .background(.background)
        .animation(.easeInOut(duration: 0.25), value: state.showSidebar)
        .animation(.easeInOut(duration: 0.25), value: state.showThumbnailStrip)
        .animation(.easeInOut(duration: 0.25), value: state.showInspector)
        .toolbar {
            ToolbarItemGroup(placement: .automatic) {
                HStack(spacing: 2) {
                    Button {
                        sharePDF()
                    } label: {
                        Image(systemName: "square.and.arrow.up")
                    }
                    .help("Share PDF")
                    .disabled(state.previewPDFPath == nil)

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
                .glassEffect(.regular, in: .capsule)
            }
        }
    }

    private func sharePDF() {
        guard let pdfPath = state.previewPDFPath ?? state.finalPDFPath else { return }
        let url = URL(fileURLWithPath: pdfPath)
        guard FileManager.default.fileExists(atPath: pdfPath) else { return }
        let picker = NSSharingServicePicker(items: [url])
        guard let window = NSApp.keyWindow,
              let contentView = window.contentView else { return }
        let rect = CGRect(x: contentView.bounds.midX, y: contentView.bounds.maxY - 50, width: 1, height: 1)
        picker.show(relativeTo: rect, of: contentView, preferredEdge: .minY)
    }



    // MARK: - Settings Import

    private func importSettings(from url: URL) {
        _ = url.startAccessingSecurityScopedResource()
        defer { url.stopAccessingSecurityScopedResource() }

        guard let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            print("Failed to read settings file")
            return
        }

        // Load fonts
        if let fontsDict = json["fonts"] as? [String: Any],
           let paths = fontsDict["paths"] as? [String] {
            let validPaths = paths.filter { FileManager.default.fileExists(atPath: $0) }
            if !validPaths.isEmpty {
                state.fontPaths = validPaths
                state.loadedFonts = engine.getFontMetadata(paths: validPaths)
                state.outputDirectory = (validPaths[0] as NSString).deletingLastPathComponent

                let allFeatures = engine.getAvailableOTFeatures(path: validPaths[0])
                state.setAvailableOTFeatures(allFeatures.filter { !HIDDEN_FEATURES.contains($0) })
                state.setAvailableSubstitutionFeatures(engine.getAvailableSubstitutionFeatures(path: validPaths[0]))
            }
        }

        // Load page format
        if let format = json["page_format"] as? String {
            state.pageFormat = format
        }

        state.schedulePersistPublic()
        print("Settings imported from: \(url.path)")
    }
}

// MARK: - FloatingToolbar

struct FloatingToolbar: View {
    @EnvironmentObject var state: AppState
    @ObservedObject var pdfCoordinator: PDFViewCoordinator

    var body: some View {
        HStack(spacing: 12) {
            // Panel toggles
            HStack(spacing: 2) {
                toolbarButton("sidebar.leading", active: state.showSidebar, help: "Toggle sidebar") {
                    state.showSidebar.toggle()
                }
                toolbarButton("rectangle.split.3x1", active: state.showThumbnailStrip, help: "Toggle thumbnails") {
                    state.showThumbnailStrip.toggle()
                }
                toolbarButton("sidebar.trailing", active: state.showInspector, help: "Toggle inspector") {
                    state.showInspector.toggle()
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .glassEffect(.regular, in: .capsule)

            // View modes + grid toggles
            HStack(spacing: 2) {
                toolbarButton("doc.richtext", active: state.viewMode == .page, help: "Page view") {
                    state.viewMode = .page
                }
                toolbarButton("square.grid.2x2", active: state.viewMode == .grid, help: "Grid view") {
                    state.viewMode = .grid
                }
                toolbarButton("arrow.left.arrow.right", active: state.viewMode == .compare, help: "Compare view") {
                    state.viewMode = .compare
                }

                if state.viewMode == .compare {
                    Divider()
                        .frame(height: 16)
                        .padding(.horizontal, 4)
                    toolbarButton(
                        state.compareVertical ? "rectangle.split.1x2" : "rectangle.split.2x1",
                        active: false,
                        help: state.compareVertical ? "Side by side" : "Stacked"
                    ) {
                        state.compareVertical.toggle()
                    }
                }

                Divider()
                    .frame(height: 16)
                    .padding(.horizontal, 4)

                toolbarButton("line.3.horizontal", active: state.showBaselines, help: "Baseline grid") {
                    state.showBaselines.toggle()
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .glassEffect(.regular, in: .capsule)

            // Zoom controls
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
                        if let pct = Int(newValue), pct >= 10, pct <= 500 {
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
                    if let pct = Int(text), pct >= 10, pct <= 500 {
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
            .glassEffect(.regular, in: .capsule)
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
        pdfView.scaleFactor = max(0.1, min(pdfView.scaleFactor + delta, 5.0))
    }

    private func fitToWindow() {
        guard let pdfView = pdfCoordinator.pdfView else { return }
        pdfView.autoScales = true
    }
}

// MARK: - DiagnosticChip

struct DiagnosticChip: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        if let option = state.selectedProofOption {
            let settings = state.proofSettingsByProof[option.name] ?? ProofSettings()
            let entry = state.registryByKey[option.baseType]

            HStack(spacing: 10) {
                chipValue("\(Int(settings.fontSize))pt")
                if entry?.supportsLineHeight ?? false {
                    chipValue("\(String(format: "%.2f", settings.lineHeight))em")
                }
                if entry?.supportsCols ?? false, settings.columns > 1 {
                    chipValue("\(settings.columns)col")
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Color(white: 0.1, opacity: 0.78))
            .foregroundStyle(.white)
            .clipShape(Capsule())
            .padding(.top, 10)
            .padding(.trailing, 10)
        }
    }

    private func chipValue(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11, weight: .medium, design: .monospaced))
    }
}

// MARK: - AddProofPopover

struct AddProofPopover: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var engine: ProofEngine

    private static let customKeys: Set<String> = [
        "custom_text", "multi_style_comparison", "substitution_overview"
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 2) {
                Text("Add Proof")
                    .font(.headline)
                    .padding(.bottom, 6)

                let registry = engine.getProofRegistry()

                let latin = registry.filter { !$0.isArabic && !Self.customKeys.contains($0.key) }
                let arabic = registry.filter { $0.isArabic }
                let custom = registry.filter { Self.customKeys.contains($0.key) }

                if !latin.isEmpty {
                    proofGroupHeader("LATIN")
                    ForEach(latin, id: \.key) { entry in
                        AddProofRow(entry: entry) {
                            state.addProofInstance(baseType: entry.key)
                            state.showAddProofSheet = false
                        }
                    }
                }

                if state.anyFontSupportsArabic && !arabic.isEmpty {
                    proofGroupHeader("ARABIC")
                    ForEach(arabic, id: \.key) { entry in
                        AddProofRow(entry: entry) {
                            state.addProofInstance(baseType: entry.key)
                            state.showAddProofSheet = false
                        }
                    }
                }

                if !custom.isEmpty {
                    proofGroupHeader("CUSTOM")
                    ForEach(custom, id: \.key) { entry in
                        AddProofRow(entry: entry) {
                            state.addProofInstance(baseType: entry.key)
                            state.showAddProofSheet = false
                        }
                    }
                }
            }
            .padding(12)
        }
        .frame(width: 300)
        .frame(maxHeight: 460)
    }

    private func proofGroupHeader(_ title: String) -> some View {
        Text(title)
            .font(.system(size: 11, weight: .medium))
            .tracking(0.88)
            .foregroundStyle(.secondary)
            .padding(.top, 10)
            .padding(.bottom, 2)
    }
}

private struct AddProofRow: View {
    let entry: ProofRegistryEntry
    let action: () -> Void
    @State private var isHovered = false

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 2) {
                Text(entry.displayName)
                HStack(spacing: 0) {
                    Text(proofDescription(for: entry.key))
                        .foregroundStyle(.tertiary)
                    Spacer()
                    Text("\(entry.defaultFontSize)pt · \(entry.defaultColumns)col")
                        .foregroundStyle(.quaternary)
                }
                .font(.caption)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .contentShape(Rectangle())
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(isHovered ? Color.accentColor.opacity(0.12) : Color.clear)
            )
        }
        .buttonStyle(.plain)
        .onHover { isHovered = $0 }
    }

    private func proofDescription(for key: String) -> String {
        switch key {
        case "filtered_character_set": return "Full character set by category"
        case "spacing_proof": return "Character spacing pairs"
        case "basic_paragraph_large": return "Heading-size paragraphs"
        case "diacritic_words_large": return "Accented words at heading size"
        case "basic_paragraph_small": return "Text-size paragraphs"
        case "paired_styles_paragraph_small": return "Regular/Bold style pairing"
        case "generative_text_small": return "Random word-level text"
        case "diacritic_words_small": return "Accented words at text size"
        case "misc_paragraph_small": return "Figures, punctuation, symbols"
        case "custom_text": return "Your own text content"
        case "multi_style_comparison": return "Compare multiple styles"
        case "substitution_overview": return "OpenType substitution table"
        case "ar_character_set": return "Arabic contextual forms"
        case "ar_paragraph_large": return "Arabic heading paragraphs"
        case "fa_paragraph_large": return "Farsi heading paragraphs"
        case "ar_paragraph_small": return "Arabic text paragraphs"
        case "fa_paragraph_small": return "Farsi text paragraphs"
        case "ar_vocalization_paragraph_small": return "Arabic with vowel marks"
        case "ar_lat_mixed_paragraph_small": return "Mixed Arabic-Latin text"
        case "ar_numbers_small": return "Arabic, Farsi, Urdu numerals"
        case "ar_generative_paragraph_small": return "Arabic all combinations"
        case "fa_generative_paragraph_small": return "Farsi all combinations"
        default: return ""
        }
    }
}

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
                if hovering {
                    NSCursor.resizeLeftRight.push()
                } else {
                    NSCursor.pop()
                }
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
