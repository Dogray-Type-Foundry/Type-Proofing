import ProofCore
import SwiftUI

@main
struct TypeProofingApp: App {
    @StateObject private var engine = ProofEngine()
    @StateObject private var appState = AppState()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
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
            AppMenuCommands(appState: appState, engine: engine)
        }
        // Persistence is debounced by 3s; iOS has no willTerminate moment,
        // so flush whenever the app leaves the foreground.
        .onChange(of: scenePhase) { _, phase in
            if phase == .background {
                appState.flushPendingPersist()
            }
        }
    }
}
