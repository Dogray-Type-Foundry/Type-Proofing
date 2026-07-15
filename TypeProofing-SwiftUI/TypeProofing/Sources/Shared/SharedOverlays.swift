import ProofCore
import SwiftUI

// MARK: - DiagnosticChip

// MARK: - DiagnosticChip

struct DiagnosticChip: View {
    @EnvironmentObject var proofs: ProofState

    var body: some View {
        if let option = proofs.selectedProofOption {
            let settings = proofs.proofSettingsByProof[option.name] ?? ProofSettings()
            let entry = proofs.registryByKey[option.baseType]

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

// MARK: - PDFPlaceholderView

struct PDFPlaceholderView: View {
    let hasFonts: Bool

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "doc.richtext")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text(hasFonts ? "Preview Not Ready" : "No Fonts Loaded")
                .font(.title3)
                .foregroundStyle(.secondary)
            Text(hasFonts ? "Preview fragments will appear here as they finish" : "Load fonts to start preview generation")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
