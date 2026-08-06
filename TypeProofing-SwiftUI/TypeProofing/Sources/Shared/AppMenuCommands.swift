import ProofCore
import SwiftUI

/// The app's custom menu items, shared verbatim: the macOS menu bar and the
/// iPadOS 26 menu bar are both populated from this.
struct AppMenuCommands: Commands {
    let appState: AppState
    // Plain `let` references never re-evaluate a Commands body — the menu
    // would keep its at-launch disabled state forever. Observing here is what
    // un-greys the items once the engine and registry load.
    @ObservedObject var engine: ProofEngine
    @ObservedObject var proofs: ProofState
    @ObservedObject var annotations: AnnotationStore

    private var notReady: Bool {
        !engine.isReady || !proofs.isRegistryLoaded
    }

    var body: some Commands {
        CommandGroup(after: .newItem) {
            // Import/Reset Fonts swap settings or fonts under frozen
            // pagination, so they are blocked while annotations exist —
            // matching the in-app menu. Reset Settings stays enabled as the
            // escape hatch (it discards annotations along with everything).
            Button("Import Settings…") {
                appState.ui.showSettingsImporter = true
            }
            .disabled(notReady || annotations.hasAnyAnnotations)
            Button("Export Settings…") {
                appState.ui.settingsExportRequest = appState.exportedSettingsJSON()
            }
            .disabled(notReady)
            Divider()
            Button("Reset Settings") {
                appState.resetAllSettings()
            }
            .disabled(notReady)
            Button("Reset Fonts") {
                appState.resetFonts()
            }
            .disabled(notReady || annotations.hasAnyAnnotations)
        }
    }
}
