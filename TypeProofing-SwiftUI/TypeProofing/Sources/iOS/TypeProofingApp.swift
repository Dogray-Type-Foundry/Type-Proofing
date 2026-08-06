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
            AppMenuCommands(appState: appState, engine: engine, proofs: appState.proofs, annotations: appState.annotations)
        }
        // Persistence is debounced by 3s; iOS has no willTerminate moment,
        // so flush whenever the app leaves the foreground. Include .inactive:
        // force-quitting from the app switcher can kill the process without a
        // .background transition.
        .onChange(of: scenePhase) { _, phase in
            if phase == .background || phase == .inactive {
                appState.flushPendingPersist()
            }
        }
    }
}
