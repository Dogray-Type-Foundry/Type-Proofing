import ProofCore
import SwiftUI

/// The app's custom menu items, shared verbatim: the macOS menu bar and the
/// iPadOS 26 menu bar are both populated from this.
struct AppMenuCommands: Commands {
    let appState: AppState
    let engine: ProofEngine

    private var notReady: Bool {
        !engine.isReady || !appState.proofs.isRegistryLoaded
    }

    var body: some Commands {
        CommandGroup(after: .newItem) {
            Button("Import Settings…") {
                appState.ui.showSettingsImporter = true
            }
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
            .disabled(notReady)
        }
    }
}
