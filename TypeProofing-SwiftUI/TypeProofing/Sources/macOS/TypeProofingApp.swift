import ProofCore
import SwiftUI
import UniformTypeIdentifiers

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
                .environmentObject(appState.annotations)
        }
        .commands {
            AppMenuCommands(appState: appState, engine: engine, proofs: appState.proofs, annotations: appState.annotations)
        }
    }
}
