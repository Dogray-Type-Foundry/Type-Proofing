import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject var engine: ProofEngine
    @EnvironmentObject var state: AppState


    var body: some View {
        Group {
            if !engine.isReady {
                loadingView
            } else {
                mainLayout
            }
        }
        .frame(minWidth: 900, minHeight: 600)
        .onReceive(engine.$isReady) { ready in
            if ready {
                state.loadFromEngine(engine)
            }
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
    }

    // MARK: - Loading

    private var loadingView: some View {
        VStack(spacing: 20) {
            if let error = engine.errorMessage {
                Label(error, systemImage: "exclamationmark.triangle")
                    .foregroundStyle(.red)
            } else {
                ProgressView("Initializing Python…")
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Main Layout

    private var mainLayout: some View {
        HSplitView {
            SidebarView()
                .frame(minWidth: 180, idealWidth: 220, maxWidth: 350)
            PDFViewerView()
                .frame(minWidth: 400)
            SettingsPanelView()
                .frame(minWidth: 250, idealWidth: 280, maxWidth: 350)
        }

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

// MARK: - AddProofPopover

struct AddProofPopover: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var engine: ProofEngine

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("Add Proof")
                .font(.headline)
                .padding(.bottom, 6)

            let registry = engine.getProofRegistry().filter { entry in
                !entry.isArabic || state.anyFontSupportsArabic
            }
            ForEach(registry, id: \.key) { entry in
                AddProofRow(entry: entry) {
                    state.addProofInstance(baseType: entry.key)
                    state.showAddProofSheet = false
                }
            }
        }
        .padding(12)
        .frame(width: 260)
    }
}

private struct AddProofRow: View {
    let entry: ProofRegistryEntry
    let action: () -> Void
    @State private var isHovered = false

    var body: some View {
        Button(action: action) {
            HStack {
                Text(entry.displayName)
                Spacer()
                if entry.isArabic {
                    Text("Arabic")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .contentShape(Rectangle())
            .background(
                RoundedRectangle(cornerRadius: 4)
                    .fill(isHovered ? Color.accentColor.opacity(0.12) : Color.clear)
            )
        }
        .buttonStyle(.plain)
        .onHover { isHovered = $0 }
    }
}
