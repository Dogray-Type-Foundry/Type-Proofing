import SwiftUI

// MARK: - DefaultFontPicker (Custom Text proof)

/// Picker that lets the user select the "default" font/style for Custom Text proof.
/// For VFs, each named instance appears as a separate option.
struct DefaultFontPicker: View {
    @EnvironmentObject var state: AppState
    @Binding var defaultFontPath: String
    @Binding var defaultFontAxisDict: [String: Double]?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Default Font")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Picker("", selection: selectedStyleBinding) {
                Text("Auto (first font)").tag(-1)
                ForEach(state.fontStylesByFamily, id: \.familyName) { group in
                    Section(group.familyName) {
                        ForEach(group.styles) { style in
                            Text(style.styleName).tag(style.index)
                        }
                    }
                }
            }
            .labelsHidden()
        }
    }

    private var selectedStyleBinding: Binding<Int> {
        Binding(
            get: {
                guard !defaultFontPath.isEmpty else { return -1 }
                // Find matching style by path + coordinates
                if let match = state.fontStyles.first(where: {
                    $0.fontPath == defaultFontPath && $0.coordinates == defaultFontAxisDict
                }) {
                    return match.index
                }
                // Fall back to matching just by path
                if let match = state.fontStyles.first(where: { $0.fontPath == defaultFontPath }) {
                    return match.index
                }
                return -1
            },
            set: { newIndex in
                if newIndex == -1 {
                    defaultFontPath = ""
                    defaultFontAxisDict = nil
                } else if let style = state.fontStyles.first(where: { $0.index == newIndex }) {
                    defaultFontPath = style.fontPath
                    defaultFontAxisDict = style.coordinates
                }
            }
        )
    }
}

// MARK: - MultiStyleFontList (Multi-Style Comparison proof)

/// Grouped checkbox list of all font styles with family-level group toggles.
struct MultiStyleFontList: View {
    @EnvironmentObject var state: AppState
    @Binding var enabledStyleIndices: [String: Bool]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Fonts & Styles")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            if state.fontStyles.isEmpty {
                Text("Load fonts to see available styles")
                    .foregroundStyle(.tertiary)
                    .font(.caption)
            } else {
                ForEach(state.fontStylesByFamily, id: \.familyName) { group in
                    FamilyGroupView(
                        familyName: group.familyName,
                        styles: group.styles,
                        enabledStyleIndices: $enabledStyleIndices
                    )
                }
            }
        }
    }
}

// MARK: - FamilyGroupView

/// A collapsible family group with a header toggle and individual style toggles.
private struct FamilyGroupView: View {
    let familyName: String
    let styles: [FontStyleEntry]
    @Binding var enabledStyleIndices: [String: Bool]
    @State private var isExpanded = true

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            // Family header — chevron to expand/collapse, toggle to enable/disable all
            HStack(spacing: 4) {
                Button {
                    withAnimation(.easeInOut(duration: 0.15)) {
                        isExpanded.toggle()
                    }
                } label: {
                    Image(systemName: isExpanded ? "chevron.down" : "chevron.right")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .frame(width: 10, height: 16)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)

                Toggle(isOn: familyToggleBinding) {
                    Text(familyName)
                        .font(.caption)
                        .fontWeight(.semibold)
                }
                .toggleStyle(.checkbox)
            }

            // Individual style toggles
            if isExpanded {
                ForEach(styles) { style in
                    Toggle(isOn: styleBinding(for: style.index)) {
                        Text(style.styleName)
                            .font(.caption)
                    }
                    .toggleStyle(.checkbox)
                    .padding(.leading, 20)
                }
            }
        }
    }

    private var familyToggleBinding: Binding<Bool> {
        Binding(
            get: {
                styles.allSatisfy { isStyleEnabled($0.index) }
            },
            set: { enabled in
                for style in styles {
                    enabledStyleIndices[String(style.index)] = enabled
                }
            }
        )
    }

    private func styleBinding(for index: Int) -> Binding<Bool> {
        let key = String(index)
        return Binding(
            get: { isStyleEnabled(index) },
            set: { enabledStyleIndices[key] = $0 }
        )
    }

    private func isStyleEnabled(_ index: Int) -> Bool {
        enabledStyleIndices[String(index)] ?? true  // default to enabled
    }
}
