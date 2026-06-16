import SwiftUI

// MARK: - DefaultFontPicker (Custom Text proof)

/// Picker that lets the user select the "default" font/style for Custom Text proof.
/// For VFs, each named instance appears as a separate option.
struct DefaultFontPicker: View {
    @EnvironmentObject var fonts: FontState
    @Binding var defaultFontPath: String
    @Binding var defaultFontAxisDict: [String: Double]?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Default Font")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Picker("", selection: selectedStyleBinding) {
                Text("Auto (first font)").tag(-1)
                ForEach(fonts.fontStylesByFamily, id: \.familyName) { group in
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
                if let match = fonts.fontStyles.first(where: {
                    $0.fontPath == defaultFontPath && $0.coordinates == defaultFontAxisDict
                }) {
                    return match.index
                }
                if let match = fonts.fontStyles.first(where: { $0.fontPath == defaultFontPath }) {
                    return match.index
                }
                return -1
            },
            set: { newIndex in
                if newIndex == -1 {
                    defaultFontPath = ""
                    defaultFontAxisDict = nil
                } else if let style = fonts.fontStyles.first(where: { $0.index == newIndex }) {
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
    @EnvironmentObject var fonts: FontState
    @Binding var enabledStyleIndices: [String: Bool]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Fonts & Styles")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            if fonts.loadedFonts.contains(where: \.isVariable) {
                Picker("", selection: $fonts.styleSourceMode) {
                    Text("Named Instances").tag(StyleSourceMode.namedInstances)
                    Text("Custom Positions").tag(StyleSourceMode.customPositions)
                }
                .pickerStyle(.segmented)
                .labelsHidden()
            }

            if fonts.fontStyles.isEmpty {
                Text("Load fonts to see available styles")
                    .foregroundStyle(.tertiary)
                    .font(.caption)
            } else {
                ForEach(fonts.fontStylesByFamily, id: \.familyName) { group in
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

// MARK: - StylePairingSection (Style Pairing proof)

/// Automatic/Manual mode picker for the Style Pairing proof. Manual mode
/// edits a list of weighted mixes of 2–4 fonts/instances.
struct StylePairingSection: View {
    @EnvironmentObject var fonts: FontState
    @Binding var pairingMode: String
    @Binding var manualPairings: [ManualPairing]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Pairing")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Picker("", selection: $pairingMode) {
                Text("Automatic").tag("automatic")
                Text("Manual").tag("manual")
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .onChange(of: pairingMode) { newMode in
                if newMode == "manual" && manualPairings.isEmpty && fonts.fontStyles.count >= 2 {
                    addPairing()
                }
            }

            if pairingMode == "automatic" {
                Text("Pairs each style with its natural partner: Regular with Bold, upright with italic, or variable weight/italic axes.")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            } else if fonts.fontStyles.count < 2 {
                Text("Load at least 2 fonts or styles to create pairings")
                    .foregroundStyle(.tertiary)
                    .font(.caption)
            } else {
                ForEach($manualPairings) { $pairing in
                    ManualPairingEditor(
                        pairing: $pairing,
                        index: manualPairings.firstIndex(where: { $0.id == pairing.id }) ?? 0,
                        onRemove: { manualPairings.removeAll { $0.id == pairing.id } }
                    )
                }

                Button {
                    addPairing()
                } label: {
                    Label("Add Pairing", systemImage: "plus")
                        .font(.caption)
                }
                .buttonStyle(.borderless)
            }
        }
    }

    private func addPairing() {
        var pairing = ManualPairing()
        pairing.styles = fonts.fontStyles.prefix(2).map { PairingStyleRef(from: $0) }
        manualPairings.append(pairing)
    }
}

extension PairingStyleRef {
    init(from style: FontStyleEntry) {
        self.init(
            fontPath: style.fontPath,
            coordinates: style.coordinates,
            weight: 50,
            label: "\(style.familyName) \(style.styleName)"
        )
    }
}

// MARK: - ManualPairingEditor

private struct ManualPairingEditor: View {
    @EnvironmentObject var fonts: FontState
    @Binding var pairing: ManualPairing
    let index: Int
    let onRemove: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Pairing \(index + 1)")
                    .font(.caption)
                    .fontWeight(.semibold)
                Spacer()
                Button(action: onRemove) {
                    Image(systemName: "trash")
                        .font(.caption)
                }
                .buttonStyle(.borderless)
            }

            ForEach($pairing.styles) { $style in
                PairingStyleRow(
                    style: $style,
                    normalizedPercent: normalizedPercent(for: style),
                    canRemove: pairing.styles.count > 2,
                    onRemove: { pairing.styles.removeAll { $0.id == style.id } }
                )
            }

            if pairing.styles.count < 4 {
                Button {
                    addStyle()
                } label: {
                    Label("Add Style", systemImage: "plus")
                        .font(.caption)
                }
                .buttonStyle(.borderless)
            }
        }
        .padding(8)
        .background(
            RoundedRectangle(cornerRadius: 6)
                .fill(Color.primary.opacity(0.04))
        )
    }

    private func normalizedPercent(for style: PairingStyleRef) -> Double {
        let total = pairing.styles.map(\.weight).reduce(0, +)
        guard total > 0 else { return 1.0 / Double(pairing.styles.count) }
        return style.weight / total
    }

    private func addStyle() {
        // Prefer a style not already in the mix so the new row is useful.
        let used = Set(pairing.styles.map { "\($0.fontPath)|\($0.coordinates?.description ?? "")" })
        let candidate = fonts.fontStyles.first {
            !used.contains("\($0.fontPath)|\($0.coordinates?.description ?? "")")
        } ?? fonts.fontStyles.first
        guard let candidate else { return }
        pairing.styles.append(PairingStyleRef(from: candidate))
    }
}

// MARK: - PairingStyleRow

private struct PairingStyleRow: View {
    @EnvironmentObject var fonts: FontState
    @Binding var style: PairingStyleRef
    let normalizedPercent: Double
    let canRemove: Bool
    let onRemove: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 4) {
                Picker("", selection: selectedStyleBinding) {
                    if selectedStyleBinding.wrappedValue == -1 {
                        Text(style.label.isEmpty ? "Select style" : "\(style.label) (missing)").tag(-1)
                    }
                    // Flat list with full names: legacy-named statics often
                    // report subfamily as just "Regular"/"Bold" with the style
                    // baked into the family name, so grouped rows showing only
                    // the subfamily are indistinguishable.
                    ForEach(fonts.fontStyles) { entry in
                        Text("\(entry.familyName) \(entry.styleName)").tag(entry.index)
                    }
                }
                .labelsHidden()

                if canRemove {
                    Button(action: onRemove) {
                        Image(systemName: "minus.circle")
                            .font(.caption)
                    }
                    .buttonStyle(.borderless)
                }
            }

            HStack(spacing: 6) {
                Slider(value: $style.weight, in: 0...100, step: 1)
                    .controlSize(.small)
                Text("\(Int((normalizedPercent * 100).rounded()))%")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(.tertiary)
                    .frame(width: 36, alignment: .trailing)
            }
        }
    }

    private var selectedStyleBinding: Binding<Int> {
        Binding(
            get: {
                if let match = fonts.fontStyles.first(where: {
                    $0.fontPath == style.fontPath && $0.coordinates == style.coordinates
                }) {
                    return match.index
                }
                return -1
            },
            set: { newIndex in
                if let entry = fonts.fontStyles.first(where: { $0.index == newIndex }) {
                    style.fontPath = entry.fontPath
                    style.coordinates = entry.coordinates
                    style.label = "\(entry.familyName) \(entry.styleName)"
                }
            }
        )
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
