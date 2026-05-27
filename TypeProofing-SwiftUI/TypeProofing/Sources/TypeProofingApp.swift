import SwiftUI

@main
struct TypeProofingApp: App {
    @StateObject private var engine = ProofEngine()
    @StateObject private var appState = AppState()

    var body: some Scene {
        Window("Type Proofing", id: "main") {
            ContentView()
                .environmentObject(engine)
                .environmentObject(appState)
                .environmentObject(appState.fonts)
                .environmentObject(appState.proofs)
                .environmentObject(appState.preview)
                .environmentObject(appState.page)
                .environmentObject(appState.ui)
                .environmentObject(appState.output)
        }
        .commands {
            CommandGroup(after: .newItem) {
                Button("Import Settings…") {
                    appState.ui.showSettingsImporter = true
                }
                Divider()
                Button("Reset Settings") {
                    appState.resetAllSettings()
                }
                .disabled(!engine.isReady || !appState.proofs.isRegistryLoaded)
                Button("Reset Fonts") {
                    appState.resetFonts()
                }
                .disabled(!engine.isReady || !appState.proofs.isRegistryLoaded)
            }
        }
    }
}
