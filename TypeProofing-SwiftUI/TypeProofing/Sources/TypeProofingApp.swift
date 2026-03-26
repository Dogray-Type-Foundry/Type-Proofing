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
        }
        .commands {
            CommandGroup(after: .newItem) {
                Button("Import Settings…") {
                    appState.showSettingsImporter = true
                }
                Divider()
                Button("Reset Settings") {
                    appState.resetAllSettings()
                }
                Button("Reset Fonts") {
                    appState.resetFonts()
                }
            }
        }
    }
}
