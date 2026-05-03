import SwiftUI
import AppKit

// MARK: - PlainTextEditor (no smart quotes/dashes)

/// NSTextView-backed editor with all automatic text substitutions disabled.
struct PlainTextEditor: NSViewRepresentable {
    @Binding var text: String

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSTextView.scrollableTextView()
        guard let textView = scrollView.documentView as? NSTextView else { return scrollView }

        textView.isAutomaticQuoteSubstitutionEnabled = false
        textView.isAutomaticDashSubstitutionEnabled = false
        textView.isAutomaticTextReplacementEnabled = false
        textView.isAutomaticSpellingCorrectionEnabled = false
        textView.isRichText = false
        textView.font = NSFont.monospacedSystemFont(ofSize: NSFont.systemFontSize, weight: .regular)
        textView.isEditable = true
        textView.isSelectable = true
        textView.allowsUndo = true
        textView.delegate = context.coordinator
        textView.string = text

        return scrollView
    }

    func updateNSView(_ nsView: NSScrollView, context: Context) {
        guard let textView = nsView.documentView as? NSTextView else { return }
        if textView.string != text {
            textView.string = text
        }
    }

    class Coordinator: NSObject, NSTextViewDelegate {
        var parent: PlainTextEditor
        init(_ parent: PlainTextEditor) { self.parent = parent }

        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            parent.text = textView.string
        }
    }
}

// MARK: - SettingsPanelView

struct SettingsPanelView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var engine: ProofEngine

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                if let option = state.selectedProofOption {
                    let entry = state.selectedRegistryEntry

                    Text(option.name)
                        .font(.headline)

                    // Font size — always shown
                    NumericSetting(
                        label: "Size",
                        value: state.selectedProofSettings.fontSize,
                        range: 4...200,
                        step: 1,
                        unit: "pt"
                    )

                    // Auto-size for charset (fit category in one page) or multi-style (fit in one line)
                    if option.baseType == "filtered_character_set" {
                        Toggle("Auto-size (fit category in one page)", isOn: state.selectedProofSettings.autoSize)
                            .toggleStyle(.checkbox)
                            .font(.caption)
                    } else if entry?.isMultiStyle ?? false {
                        Toggle("Auto-size (fit longest line)", isOn: state.selectedProofSettings.autoSize)
                            .toggleStyle(.checkbox)
                            .font(.caption)
                    }

                    // Line height — for proofs that support it (not charset/spacing)
                    if entry?.supportsLineHeight ?? false {
                        NumericSetting(
                            label: "Line Height",
                            value: state.selectedProofSettings.lineHeight,
                            range: 0.5...5.0,
                            step: 0.05,
                            unit: "em"
                        )
                    }

                    // Columns — for proofs that support it (incl. spacing)
                    if entry?.supportsCols ?? false {
                        NumericSetting(
                            label: "Columns",
                            value: state.selectedProofSettings.columns,
                            range: 1...6,
                            step: 1
                        )
                    }

                    // Tracking — only for proofs that support formatting
                    if entry?.supportsFormatting ?? false {
                        NumericSetting(
                            label: "Tracking",
                            value: state.selectedProofSettings.tracking,
                            range: -20...100,
                            step: 0.1
                        )
                    }

                    // Paragraphs — only for proofs that have them
                    if entry?.hasParagraphs ?? false {
                        NumericSetting(
                            label: "Paragraphs",
                            value: state.selectedProofSettings.paragraphs,
                            range: 1...20,
                            step: 1
                        )
                    }

                    // Alignment — only for proofs that support formatting
                    if entry?.supportsFormatting ?? false {
                        AlignmentPicker(alignment: state.selectedProofSettings.alignment)
                    }

                    Divider()

                    // Character categories (if applicable)
                    if (entry?.hasCategories ?? false) || option.baseType == "substitution_overview" {
                        if entry?.hasCategories ?? false {
                            CategoryCheckboxes(categories: state.selectedProofSettings.categories)
                        }
                        if option.baseType == "filtered_character_set" ||
                            option.baseType == "spacing_proof" ||
                            option.baseType == "multi_style_comparison" ||
                            option.baseType == "substitution_overview" {
                            SubstitutionCheckboxes(features: state.selectedProofSettings.substitutionFeatures)
                        }
                        Divider()
                    }

                    // Custom text (if applicable)
                    if entry?.hasCustomText ?? false {
                        CustomTextSection(
                            text: state.selectedProofSettings.customText,
                            markupEnabled: state.selectedProofSettings.markupEnabled,
                            generateOnce: state.selectedProofSettings.generateOnce,
                            showGenerateOnce: !(entry?.isMultiStyle ?? false)
                        )

                        // Default font picker for Custom Text (non-multi-style) when generateOnce
                        if !(entry?.isMultiStyle ?? false) && state.selectedProofSettings.generateOnce.wrappedValue {
                            DefaultFontPicker(
                                defaultFontPath: state.selectedProofSettings.defaultFontPath,
                                defaultFontAxisDict: state.selectedProofSettings.defaultFontAxisDict
                            )
                        }

                        Divider()
                    }

                    // Multi-style font/style selection
                    if entry?.isMultiStyle ?? false {
                        MultiStyleFontList(
                            enabledStyleIndices: state.selectedProofSettings.enabledStyleIndices
                        )
                        Divider()
                    }

                    if option.baseType != "substitution_overview" {
                        OTFeaturesSection(
                            features: state.selectedProofSettings.otFeatures,
                            isSpacingProof: option.baseType == "spacing_proof"
                        )
                    }

                } else {
                    Text("Select a proof to see settings")
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .padding()
        }
    }
}

// MARK: - PDFOutputSection

struct PDFOutputSection: View {
    @EnvironmentObject var state: AppState
    @State private var showFolderPicker = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("PDF Output")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Picker("", selection: $state.useCustomOutputLocation) {
                Text("First font's folder").tag(false)
                Text("Custom location").tag(true)
            }
            .pickerStyle(.radioGroup)
            .labelsHidden()

            if state.useCustomOutputLocation {
                HStack {
                    Text(state.customOutputLocation.isEmpty ? "No folder selected" : (state.customOutputLocation as NSString).lastPathComponent)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .foregroundStyle(state.customOutputLocation.isEmpty ? .tertiary : .primary)
                        .font(.caption)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    Button("Browse…") {
                        showFolderPicker = true
                    }
                    .controlSize(.small)
                }
                .fileImporter(
                    isPresented: $showFolderPicker,
                    allowedContentTypes: [.folder]
                ) { result in
                    if case .success(let url) = result {
                        _ = url.startAccessingSecurityScopedResource()
                        state.customOutputLocation = url.path
                        state.schedulePersistPublic()
                    }
                }
            } else {
                HStack {
                    Text(state.outputDirectory.isEmpty ? " " : (state.outputDirectory as NSString).lastPathComponent)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .foregroundStyle(.tertiary)
                        .font(.caption)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    // Invisible button to reserve same space as "Browse…"
                    Button("Browse…") {}
                        .controlSize(.small)
                        .hidden()
                }
            }
        }
    }
}

// MARK: - NumericSetting

struct NumericSetting: View {
    let label: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let step: Double
    let unit: String?

    init(label: String, value: Binding<Double>, range: ClosedRange<Double>, step: Double = 1, unit: String? = nil) {
        self.label = label
        self._value = value
        self.range = range
        self.step = step
        self.unit = unit
    }

    // Convenience for Int bindings
    init(label: String, value: Binding<Int>, range: ClosedRange<Int>, step: Int = 1, unit: String? = nil) {
        self.label = label
        self._value = Binding(
            get: { Double(value.wrappedValue) },
            set: { value.wrappedValue = Int($0) }
        )
        self.range = Double(range.lowerBound)...Double(range.upperBound)
        self.step = Double(step)
        self.unit = unit
    }

    var body: some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
            TextField("", value: $value, format: .number)
                .frame(width: 60)
                .textFieldStyle(.roundedBorder)
            if let unit {
                Text(unit)
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .frame(width: 18, alignment: .leading)
            }
            Stepper("", value: $value, in: range, step: step)
                .labelsHidden()
        }
    }
}

// MARK: - AlignmentPicker

struct AlignmentPicker: View {
    @Binding var alignment: String

    private let options: [(value: String, icon: String, label: String)] = [
        ("left", "text.alignleft", "Left"),
        ("center", "text.aligncenter", "Center"),
        ("right", "text.alignright", "Right"),
        ("justified", "text.justify.leading", "Justified"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Alignment")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Picker("", selection: $alignment) {
                ForEach(options, id: \.value) { option in
                    Image(systemName: option.icon)
                        .help(option.label)
                        .tag(option.value)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
        }
    }
}

// MARK: - CategoryCheckboxes

struct CategoryCheckboxes: View {
    @Binding var categories: CategorySettings

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Categories")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Toggle("Uppercase", isOn: $categories.uppercaseBase)
                .toggleStyle(.checkbox)
            Toggle("Lowercase", isOn: $categories.lowercaseBase)
                .toggleStyle(.checkbox)
            Toggle("Numbers & Symbols", isOn: $categories.numbersSymbols)
                .toggleStyle(.checkbox)
            Toggle("Punctuation", isOn: $categories.punctuation)
                .toggleStyle(.checkbox)
            Toggle("Accented", isOn: $categories.accented)
                .toggleStyle(.checkbox)
        }
    }
}

// MARK: - SubstitutionCheckboxes

struct SubstitutionCheckboxes: View {
    @Binding var features: [SubstitutionFeature]

    private let columns = [GridItem(.flexible()), GridItem(.flexible())]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("OpenType Substitutions")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .padding(.top, 4)
            if features.isEmpty {
                Text("Load a font with GSUB substitutions to see categories")
                    .foregroundStyle(.tertiary)
                    .font(.caption)
            } else {
                LazyVGrid(columns: columns, alignment: .leading, spacing: 4) {
                    ForEach($features) { $feature in
                        Toggle(feature.tag, isOn: $feature.enabled)
                            .toggleStyle(.checkbox)
                    }
                }
            }
        }
    }
}

// MARK: - CustomTextSection

struct CustomTextSection: View {
    @Binding var text: String
    @Binding var markupEnabled: Bool
    @Binding var generateOnce: Bool
    let showGenerateOnce: Bool
    @State private var showMarkupHelp = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Custom Text")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            PlainTextEditor(text: $text)
                .frame(minHeight: 150)
                .border(Color.secondary.opacity(0.3))
            HStack {
                Toggle("Enable Markup", isOn: $markupEnabled)
                    .toggleStyle(.checkbox)
                Button {
                    showMarkupHelp.toggle()
                } label: {
                    Image(systemName: "questionmark.circle")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .help("Markup syntax help")
                .popover(isPresented: $showMarkupHelp, arrowEdge: .trailing) {
                    MarkupHelpPopover()
                }
            }
            if showGenerateOnce {
                Toggle("Generate Once (use default font only)", isOn: $generateOnce)
                    .toggleStyle(.checkbox)
            }
        }
    }
}

// MARK: - MarkupHelpPopover

private struct MarkupHelpPopover: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                Text("Markup Syntax")
                    .font(.headline)

                Group {
                    syntaxRow("# Heading", "Large heading")
                    syntaxRow("## Subheading", "Smaller heading")
                    syntaxRow("**bold**", "Bold text")
                    syntaxRow("*italic*", "Italic text")
                    syntaxRow("***bold italic***", "Bold + italic")
                }

                Divider()

                Text("Attribute Spans")
                    .font(.subheadline)
                    .fontWeight(.semibold)

                Group {
                    syntaxRow("[text]{size:24}", "Custom font size")
                    syntaxRow("[text]{style:Bold}", "Named font style")
                    syntaxRow("[text]{wght:700}", "Variable font axis")
                    syntaxRow("[text]{color:#FF0000}", "Text color (hex)")
                    syntaxRow("[text]{tracking:2}", "Custom tracking")
                    syntaxRow("[text]{feat:smcp,onum}", "OpenType features")
                }

                Text("Combine attributes with commas:")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("[text]{size:18, wght:600, color:#333}")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(.secondary)

                Divider()

                Text("Breaks")
                    .font(.subheadline)
                    .fontWeight(.semibold)

                Group {
                    syntaxRow("#pagebreak()", "Page break (on its own line)")
                    syntaxRow("#colbreak()", "Column break (on its own line)")
                }

                Divider()

                Text("Escaping")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("Use \\ before special characters: \\* \\# \\[ \\] \\{ \\}")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            .padding()
        }
        .frame(width: 300, height: 420)
    }

    private func syntaxRow(_ syntax: String, _ description: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(syntax)
                .font(.system(.caption, design: .monospaced))
                .frame(width: 160, alignment: .leading)
            Text(description)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

// MARK: - OTFeaturesSection

struct OTFeaturesSection: View {
    @Binding var features: [OTFeature]
    var isSpacingProof: Bool = false

    private let columns = [GridItem(.flexible()), GridItem(.flexible())]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("OpenType Features")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            if features.isEmpty {
                Text("Load a font to see available features")
                    .foregroundStyle(.tertiary)
                    .font(.caption)
            } else {
                LazyVGrid(columns: columns, alignment: .leading, spacing: 4) {
                    ForEach($features) { $feature in
                        if isSpacingProof && feature.tag == "kern" {
                            Toggle("kern (always off)", isOn: .constant(false))
                                .toggleStyle(.checkbox)
                                .disabled(true)
                        } else {
                            Toggle(feature.tag, isOn: $feature.enabled)
                                .toggleStyle(.checkbox)
                        }
                    }
                }
            }
        }
    }
}
