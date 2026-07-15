import ProofCore
import SwiftUI

extension Color {
    static let dograyPurple = Color(red: 0.380, green: 0, blue: 0.878)
}


struct AddProofPopover: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var engine: ProofEngine
    @EnvironmentObject var fonts: FontState
    @EnvironmentObject var ui: UIState

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
                            ui.showAddProofSheet = false
                        }
                    }
                }

                if fonts.anyFontSupportsArabic && !arabic.isEmpty {
                    proofGroupHeader("ARABIC")
                    ForEach(arabic, id: \.key) { entry in
                        AddProofRow(entry: entry) {
                            state.addProofInstance(baseType: entry.key)
                            ui.showAddProofSheet = false
                        }
                    }
                }

                if !custom.isEmpty {
                    proofGroupHeader("CUSTOM")
                    ForEach(custom, id: \.key) { entry in
                        AddProofRow(entry: entry) {
                            state.addProofInstance(baseType: entry.key)
                            ui.showAddProofSheet = false
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
