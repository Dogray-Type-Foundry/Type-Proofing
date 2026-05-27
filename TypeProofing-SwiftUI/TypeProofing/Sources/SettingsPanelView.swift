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

// MARK: - InspectorGroup

struct InspectorGroup<Content: View>: View {
    let icon: String
    let title: String
    let onReset: (() -> Void)?
    @State private var isExpanded = true
    @ViewBuilder let content: () -> Content

    init(icon: String, title: String, onReset: (() -> Void)? = nil, @ViewBuilder content: @escaping () -> Content) {
        self.icon = icon
        self.title = title
        self.onReset = onReset
        self.content = content
    }

    var body: some View {
        VStack(spacing: 0) {
            Button(action: { withAnimation(.easeInOut(duration: 0.2)) { isExpanded.toggle() } }) {
                HStack(spacing: 8) {
                    Image(systemName: icon)
                    Text(title)
                        .font(.system(size: 11, weight: .medium))
                        .textCase(.uppercase)
                        .tracking(0.88)
                    Spacer()
                    if let onReset {
                        Button("reset", action: onReset)
                            .font(.caption.monospaced())
                            .foregroundStyle(.quaternary)
                    }
                    Image(systemName: "chevron.down")
                        .rotationEffect(isExpanded ? .zero : .degrees(-90))
                }
                .foregroundStyle(.secondary)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if isExpanded {
                VStack(alignment: .leading, spacing: 6) {
                    content()
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 12)
            }
        }
    }
}

// MARK: - SettingsPanelView

struct SettingsPanelView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var engine: ProofEngine
    @State private var selectedTab: SettingsPanelTab = .settings

    var body: some View {
        VStack(spacing: 0) {
            Picker("", selection: $selectedTab) {
                ForEach(SettingsPanelTab.allCases, id: \.self) { tab in
                    Text(tab.rawValue).tag(tab)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .padding([.horizontal, .top], 10)

            Divider()
                .padding(.top, 8)

            switch selectedTab {
            case .settings:
                settingsContent
            case .diagnostics:
                DiagnosticsPanelView()
            }
        }
    }

    private var settingsContent: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                if let option = state.selectedProofOption {
                    let entry = state.selectedRegistryEntry

                    Text(option.name)
                        .font(.headline)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)

                    // MARK: Typography Group (always shown)

                    InspectorGroup(icon: "textformat.size", title: "Typography") {
                        NumericSetting(
                            label: "Size",
                            value: state.selectedProofSettings.fontSize,
                            range: 4...200,
                            step: 1,
                            unit: "pt"
                        )

                        if option.baseType == "filtered_character_set" {
                            Toggle("Auto-size (fit category in one page)", isOn: state.selectedProofSettings.autoSize)
                                .toggleStyle(.checkbox)
                                .font(.caption)
                        } else if entry?.isMultiStyle ?? false {
                            Toggle("Auto-size (fit longest line)", isOn: state.selectedProofSettings.autoSize)
                                .toggleStyle(.checkbox)
                                .font(.caption)
                        }

                        if entry?.supportsLineHeight ?? false {
                            NumericSetting(
                                label: "Line Height",
                                value: state.selectedProofSettings.lineHeight,
                                range: 0.5...5.0,
                                step: 0.05,
                                unit: "em"
                            )
                        }

                        if entry?.supportsFormatting ?? false {
                            NumericSetting(
                                label: "Tracking",
                                value: state.selectedProofSettings.tracking,
                                range: -20...100,
                                step: 0.1
                            )
                        }
                    }

                    // MARK: Layout Group

                    if (entry?.supportsCols ?? false) || (entry?.supportsFormatting ?? false) {
                        Divider()

                        InspectorGroup(icon: "rectangle.split.3x1", title: "Layout") {
                            if entry?.supportsCols ?? false {
                                NumericSetting(
                                    label: "Columns",
                                    value: state.selectedProofSettings.columns,
                                    range: 1...6,
                                    step: 1
                                )
                                NumericSetting(
                                    label: "Column Gap",
                                    value: state.selectedProofSettings.columnGap,
                                    range: 0...100,
                                    step: 1,
                                    unit: "pt"
                                )
                            }

                            if entry?.supportsFormatting ?? false {
                                AlignmentPicker(alignment: state.selectedProofSettings.alignment)
                                DirectionPicker(direction: state.selectedProofSettings.direction)
                                if entry?.supportsHyphenation ?? false {
                                    Toggle("Hyphenation", isOn: state.selectedProofSettings.hyphenation)
                                        .toggleStyle(.switch)
                                        .controlSize(.small)
                                }
                                if state.anyFontSupportsOpbd {
                                    Toggle("Hanging Punctuation", isOn: state.selectedProofSettings.hangingPunctuation)
                                        .toggleStyle(.switch)
                                        .controlSize(.small)
                                }
                            }
                        }
                    }

                    // MARK: Paragraph Group

                    if (entry?.hasParagraphs ?? false) {
                        Divider()

                        InspectorGroup(icon: "text.alignleft", title: "Paragraph") {
                            NumericSetting(
                                label: "Paragraphs",
                                value: state.selectedProofSettings.paragraphs,
                                range: 1...20,
                                step: 1
                            )

                            if entry?.supportsFormatting ?? false {
                                NumericSetting(
                                    label: "Indent",
                                    value: state.selectedProofSettings.paragraphIndent,
                                    range: 0...10,
                                    step: 0.5,
                                    unit: "em"
                                )
                                NumericSetting(
                                    label: "Spacing",
                                    value: state.selectedProofSettings.paragraphSpace,
                                    range: 0...5,
                                    step: 0.1,
                                    unit: "em"
                                )
                            }
                        }
                    }

                    Divider()

                    // MARK: Remaining Sections (unchanged)

                    VStack(alignment: .leading, spacing: 10) {
                        if (entry?.hasCategories ?? false) || option.baseType == "substitution_overview" {
                            if entry?.hasCategories ?? false {
                                CategoryCheckboxes(categories: state.selectedProofSettings.categories)
                            }
                            if option.baseType == "substitution_overview" {
                                SubstitutionCheckboxes(features: state.selectedProofSettings.substitutionFeatures)
                            }
                            Divider()
                        }

                        if entry?.hasCustomText ?? false {
                            if option.baseType == "custom_text" {
                                TextPresetsSection(customText: state.selectedProofSettings.customText)
                            }

                            CustomTextSection(
                                text: state.selectedProofSettings.customText,
                                markupEnabled: state.selectedProofSettings.markupEnabled,
                                generateOnce: state.selectedProofSettings.generateOnce,
                                showGenerateOnce: !(entry?.isMultiStyle ?? false)
                            )

                            if !(entry?.isMultiStyle ?? false) && state.selectedProofSettings.generateOnce.wrappedValue {
                                DefaultFontPicker(
                                    defaultFontPath: state.selectedProofSettings.defaultFontPath,
                                    defaultFontAxisDict: state.selectedProofSettings.defaultFontAxisDict
                                )
                            }

                            Divider()
                        }

                        if entry?.isMultiStyle ?? false {
                            MultiStyleFontList(
                                enabledStyleIndices: state.selectedProofSettings.enabledStyleIndices
                            )
                            Toggle("Show fallback glyphs for missing characters", isOn: state.selectedProofSettings.showFallback)
                                .toggleStyle(.checkbox)
                            Divider()
                        }

                        if option.baseType != "substitution_overview" {
                            OTFeaturesSection(
                                features: state.selectedProofSettings.otFeatures,
                                isSpacingProof: option.baseType == "spacing_proof",
                                fontPath: state.enabledFontPaths.first
                            )
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)

                } else {
                    Text("Select a proof to see settings")
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
        }
        .scrollEdgeEffectStyle(.soft, for: .all)
    }
}

private enum SettingsPanelTab: String, CaseIterable {
    case settings = "Settings"
    case diagnostics = "Diagnostics"
}

private struct DiagnosticsPanelView: View {
    @EnvironmentObject var engine: ProofEngine
    @State private var filter: DiagnosticFilter = .all

    private var filteredEvents: [DiagnosticEvent] {
        engine.diagnostics.filter { event in
            switch filter {
            case .all:
                return true
            case .errors:
                return event.level == "error"
            case .warnings:
                return event.level == "warning"
            case .debug:
                return event.level == "debug"
            }
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Toggle("Debug Mode", isOn: $engine.debugMode)
                .toggleStyle(.switch)
                .controlSize(.small)

            Picker("", selection: $filter) {
                ForEach(DiagnosticFilter.allCases, id: \.self) { filter in
                    Text(filter.rawValue).tag(filter)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()

            if filteredEvents.isEmpty {
                Text("No diagnostics")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(filteredEvents) { event in
                            DiagnosticRow(event: event)
                        }
                    }
                    .padding(.vertical, 4)
                }
                .scrollEdgeEffectStyle(.soft, for: .all)
            }
        }
        .padding()
    }
}

private enum DiagnosticFilter: String, CaseIterable {
    case all = "All"
    case errors = "Errors"
    case warnings = "Warnings"
    case debug = "Debug"
}

private struct DiagnosticRow: View {
    let event: DiagnosticEvent

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 5) {
                Image(systemName: icon)
                    .foregroundStyle(color)
                Text(event.category)
                    .font(.caption)
                    .fontWeight(.semibold)
                Spacer()
                if !event.timestamp.isEmpty {
                    Text(event.timestamp)
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }
            Text(event.message)
                .font(.caption)
                .fixedSize(horizontal: false, vertical: true)
            if let proofName = event.proofName, !proofName.isEmpty {
                Text(proofName)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            if let fontPath = event.fontPath, !fontPath.isEmpty {
                Text((fontPath as NSString).lastPathComponent)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(8)
        .background(
            RoundedRectangle(cornerRadius: 6)
                .fill(Color.secondary.opacity(0.08))
        )
    }

    private var icon: String {
        switch event.level {
        case "error": return "xmark.octagon.fill"
        case "warning": return "exclamationmark.triangle.fill"
        case "debug": return "terminal"
        default: return "info.circle"
        }
    }

    private var color: Color {
        switch event.level {
        case "error": return .red
        case "warning": return .orange
        case "debug": return .purple
        default: return .secondary
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

    @State private var isDragging = false
    @State private var dragStartValue: Double = 0

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
                .onHover { hovering in
                    if hovering {
                        NSCursor.resizeLeftRight.push()
                    } else {
                        NSCursor.pop()
                    }
                }
                .gesture(
                    DragGesture(minimumDistance: 3)
                        .onChanged { gesture in
                            if !isDragging {
                                isDragging = true
                                dragStartValue = value
                                NSCursor.hide()
                            }
                            let multiplier: Double
                            if NSEvent.modifierFlags.contains(.shift) {
                                multiplier = 3.0
                            } else if NSEvent.modifierFlags.contains(.option) {
                                multiplier = 0.05
                            } else {
                                multiplier = 0.3
                            }
                            let delta = Double(gesture.translation.width) * step * multiplier
                            let raw = min(max(dragStartValue + delta, range.lowerBound), range.upperBound)
                            let snap = step >= 1 ? (raw * 10).rounded() / 10 : (raw / step).rounded() * step
                            value = snap
                        }
                        .onEnded { _ in
                            isDragging = false
                            NSCursor.unhide()
                        }
                )
            Spacer()
            HStack(spacing: 4) {
                HStack(spacing: 0) {
                    TextField("", value: $value, format: .number)
                        .font(.system(.body, design: .monospaced))
                        .textFieldStyle(.plain)
                        .frame(width: 50)
                        .padding(.horizontal, 9)
                        .padding(.vertical, 5)
                    if let unit {
                        Text(unit)
                            .font(.system(size: 10.5, design: .monospaced))
                            .foregroundStyle(.tertiary)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 5)
                            .background(Color.primary.opacity(0.03))
                    }
                }
                .background(Color.white.opacity(0.55))
                .clipShape(RoundedRectangle(cornerRadius: 7))
                .overlay(RoundedRectangle(cornerRadius: 7).stroke(Color.primary.opacity(0.12), lineWidth: 0.5))

                VStack(spacing: 0) {
                    Button {
                        value = min(value + step, range.upperBound)
                    } label: {
                        Image(systemName: "chevron.up")
                            .font(.system(size: 8, weight: .bold))
                            .frame(width: 18, height: 14)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    Divider().frame(width: 12)
                    Button {
                        value = max(value - step, range.lowerBound)
                    } label: {
                        Image(systemName: "chevron.down")
                            .font(.system(size: 8, weight: .bold))
                            .frame(width: 18, height: 14)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                }
                .foregroundStyle(.secondary)
                .background(Color.white.opacity(0.35))
                .clipShape(RoundedRectangle(cornerRadius: 5))
                .overlay(RoundedRectangle(cornerRadius: 5).stroke(Color.primary.opacity(0.1), lineWidth: 0.5))
            }
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

// MARK: - TextPresetsSection

struct TextPresetsSection: View {
    @Binding var customText: String
    @EnvironmentObject var engine: ProofEngine
    @EnvironmentObject var state: AppState

    private static let pangrams = """
    The quick brown fox jumps over the lazy dog.
    Pack my box with five dozen liquor jugs.
    How vexingly quick daft zebras jump.
    Waltz, nymph, for quick jigs vex Bud.
    Sphinx of black quartz, judge my vow.
    Crazy Fredericka bought many very exquisite opal jewels.
    Grumpy wizards make toxic brew for the evil queen and jack.
    Jackdaws love my big sphinx of quartz.
    """

    private static let diacritics = """
    Ångström Böhm Çelik Dürr Ëlde Frühling Gödel Hölderlin Île José Kühn Löwe Müller Nürnberg Ökologie Pärnu Québec Röntgen Schröder Töpfer Über Västerås Wörther Xérès Yvré Zürich
    àbcèfghìjklmnòpqrstùvwxyz
    áéíóúàèìòù äëïöü âêîôû ãñõ åø çšž ðþ ŀ ñ
    Ąą Ćć Ęę Łł Ńń Óó Śś Źź Żż
    Ăă Ââ Îî Șș Țț
    Āā Ēē Ģģ Ķķ Ļļ Ņņ
    """

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Sample Text")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            FlowLayout(spacing: 4) {
                presetButton("Pangrams") { customText = Self.pangrams }
                presetButton("Punctuation") { customText = PremadeTexts.additionalSmallText }
                presetButton("Diacritics") { customText = Self.diacritics }
                presetButton("Word-o-mat") {
                    guard let path = state.enabledFontPaths.first else { return }
                    customText = engine.generateWordomat(fontPath: path)
                }
                presetButton("Clipboard") {
                    if let str = NSPasteboard.general.string(forType: .string) {
                        customText = str
                    }
                }
            }
        }
    }

    private func presetButton(_ label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(label)
                .font(.system(size: 10.5))
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
        }
        .buttonStyle(.plain)
        .background(Color.white.opacity(0.55))
        .clipShape(Capsule())
        .overlay(Capsule().stroke(Color.primary.opacity(0.12), lineWidth: 0.5))
    }
}

private struct FlowLayout: Layout {
    var spacing: CGFloat = 4

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > width && x > 0 {
                y += rowHeight + spacing
                x = 0
                rowHeight = 0
            }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return CGSize(width: width, height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x: CGFloat = bounds.minX
        var y: CGFloat = bounds.minY
        var rowHeight: CGFloat = 0
        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > bounds.maxX && x > bounds.minX {
                y += rowHeight + spacing
                x = bounds.minX
                rowHeight = 0
            }
            subview.place(at: CGPoint(x: x, y: y), proposal: .unspecified)
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}

// MARK: - DirectionPicker

struct DirectionPicker: View {
    @Binding var direction: String

    private let options: [(value: String, icon: String, label: String)] = [
        ("ltr", "arrow.right", "Left to Right"),
        ("auto", "arrow.left.and.right", "Auto (follow script)"),
        ("rtl", "arrow.left", "Right to Left"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Direction")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Picker("", selection: $direction) {
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
    var fontPath: String?

    private let columns = [GridItem(.flexible()), GridItem(.flexible())]

    @State private var cachedVariations: [String: Double]?
    @State private var cachedSamples: [String: String] = [:]
    @State private var cachedFontPath: String?

    private func refreshOTCache() {
        guard fontPath != cachedFontPath else { return }
        cachedFontPath = fontPath
        cachedVariations = computeDefaultVariations()
        cachedSamples = computeFeatureSamples(variations: cachedVariations)
    }

    private func computeDefaultVariations() -> [String: Double]? {
        guard let path = fontPath else { return nil }
        guard let ctFont = FontLoader.makeFont(path: path, size: 13, features: nil, variations: nil) else { return nil }
        guard let axes = CTFontCopyVariationAxes(ctFont) as? [[String: Any]] else { return nil }
        var defaults: [String: Double] = [:]
        for axis in axes {
            guard let identifier = axis[kCTFontVariationAxisIdentifierKey as String] as? Int,
                  let defaultValue = axis[kCTFontVariationAxisDefaultValueKey as String] as? Double else { continue }
            let tag = FontLoader.axisIDToTag(identifier)
            defaults[tag] = defaultValue
        }
        return defaults.isEmpty ? nil : defaults
    }

    private func computeFeatureSamples(variations: [String: Double]?) -> [String: String] {
        guard let path = fontPath else { return [:] }
        let subs = SubstitutionBridge.getSubstitutions(fontPath: path)
        let baseFont = FontLoader.makeFont(path: path, size: 13, features: nil, variations: variations)

        var samples: [String: String] = [:]
        for feature in subs {
            let tag = feature.tag
            switch tag {
            case "calt":
                samples[tag] = pickCaltSample(feature.entries)
            case "ordn", "sinf", "subs", "sups", "numr", "dnom":
                if let entry = feature.entries.first, !entry.inputText.isEmpty {
                    samples[tag] = "x" + String(entry.inputText.prefix(3))
                }
            case "case":
                samples[tag] = pickCaseSample(feature.entries)
            case "frac":
                samples[tag] = "1/2"
            case "tnum", "pnum", "onum", "lnum":
                break
            default:
                if let entry = feature.entries.first, !entry.inputText.isEmpty {
                    samples[tag] = String(entry.inputText.prefix(4))
                }
            }
        }

        if let font = baseFont {
            if samples["mark"] == nil {
                let mark = findCombiningMark(in: font)
                if let m = mark { samples["mark"] = "a\(m)" }
            }
            if samples["mkmk"] == nil {
                let marks = findTwoCombiningMarks(in: font)
                if marks.count == 2 { samples["mkmk"] = "a\(marks[0])\(marks[1])" }
            }
        }

        return samples
    }

    private func pickCaltSample(_ entries: [SubstitutionBridge.Entry]) -> String? {
        let viable = entries.filter { !$0.inputText.isEmpty }
        if viable.isEmpty { return nil }

        func buildSample(_ e: SubstitutionBridge.Entry) -> String {
            var s = ""
            if !e.backtrackText.isEmpty { s += String(e.backtrackText.suffix(2)) }
            s += String(e.inputText.prefix(3))
            if !e.lookaheadText.isEmpty { s += String(e.lookaheadText.prefix(2)) }
            return s
        }

        let alphabetic = viable.filter { $0.inputText.first?.isLetter == true }
        let pool = alphabetic.isEmpty ? viable : alphabetic

        let lowercaseWithLowercaseCtx = pool.first { e in
            guard let first = e.inputText.first, first.isLowercase else { return false }
            let ctx = e.backtrackText + e.lookaheadText
            return !ctx.isEmpty && ctx.contains(where: { $0.isLowercase })
        }
        if let e = lowercaseWithLowercaseCtx { return buildSample(e) }

        let uppercaseWithUppercaseCtx = pool.first { e in
            guard let first = e.inputText.first, first.isUppercase else { return false }
            let ctx = e.backtrackText + e.lookaheadText
            return !ctx.isEmpty && ctx.contains(where: { $0.isUppercase })
        }
        if let e = uppercaseWithUppercaseCtx { return buildSample(e) }

        if let e = pool.first(where: { !($0.backtrackText + $0.lookaheadText).isEmpty }) {
            return buildSample(e)
        }
        return buildSample(pool[0])
    }

    private func pickCaseSample(_ entries: [SubstitutionBridge.Entry]) -> String? {
        let viable = entries.filter { !$0.inputText.isEmpty }
        if viable.isEmpty { return nil }

        let preferredContexts: [Character] = ["\u{00BF}", "[", "-"]
        let inputTexts = Set(viable.map { String($0.inputText.prefix(1)) })

        for ctx in preferredContexts {
            if inputTexts.contains(String(ctx)) {
                return String(ctx) + "H"
            }
        }
        return String(viable[0].inputText.prefix(2)) + "H"
    }

    private static let combiningMarks: [Character] = [
        "\u{0301}", "\u{0300}", "\u{0302}", "\u{030C}",
        "\u{0308}", "\u{0303}", "\u{0307}", "\u{0327}",
        "\u{0306}", "\u{030A}", "\u{0304}", "\u{030B}",
    ]

    private func findCombiningMark(in font: CTFont) -> Character? {
        Self.combiningMarks.first { FontLoader.fontContains(font, characters: String($0)) }
    }

    private func findTwoCombiningMarks(in font: CTFont) -> [Character] {
        var found: [Character] = []
        for mark in Self.combiningMarks {
            if FontLoader.fontContains(font, characters: String(mark)) {
                found.append(mark)
                if found.count == 2 { break }
            }
        }
        return found
    }

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
                LazyVGrid(columns: columns, spacing: 5) {
                    ForEach($features) { $feature in
                        OTFeaturePill(
                            feature: $feature,
                            forceOff: isSpacingProof && feature.tag == "kern",
                            fontPath: fontPath,
                            defaultVariations: cachedVariations,
                            featureSample: cachedSamples[feature.tag]
                        )
                    }
                }
            }
        }
        .onAppear { refreshOTCache() }
        .onChange(of: fontPath) { _ in refreshOTCache() }
    }
}

// MARK: - OTFeaturePill

private struct OTFeaturePill: View {
    @Binding var feature: OTFeature
    var forceOff: Bool = false
    var fontPath: String?
    var defaultVariations: [String: Double]?
    var featureSample: String?

    private var isActive: Bool { !forceOff && feature.enabled }

    @State private var cachedFeatureFont: Font?
    @State private var cachedPillFontPath: String?

    private func refreshFeatureFont() {
        guard fontPath != cachedPillFontPath else { return }
        cachedPillFontPath = fontPath
        guard let path = fontPath else {
            cachedFeatureFont = nil
            return
        }
        guard let ctFont = FontLoader.makeFont(
            path: path, size: 13,
            features: [feature.tag: true],
            variations: defaultVariations
        ) else {
            cachedFeatureFont = nil
            return
        }
        cachedFeatureFont = Font(ctFont as NSFont)
    }

    var body: some View {
        Button {
            if !forceOff { feature.enabled.toggle() }
        } label: {
            HStack(spacing: 6) {
                Circle()
                    .fill(isActive ? Color.dograyPurple : Color.primary.opacity(0.15))
                    .frame(width: 5, height: 5)
                Text(forceOff ? "\(feature.tag) (off)" : feature.tag)
                    .font(.system(size: 10.5, weight: .medium, design: .monospaced))
                Spacer()
                Text(featureSample ?? fallbackSampleText(for: feature.tag))
                    .font(cachedFeatureFont ?? .system(size: 13))
                    .foregroundStyle(isActive ? .white.opacity(0.9) : Color.secondary)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(isActive ? Color.dograyPurple : Color.secondary.opacity(0.08))
            .foregroundStyle(isActive ? Color.white : Color.primary)
            .clipShape(RoundedRectangle(cornerRadius: 7))
            .overlay(RoundedRectangle(cornerRadius: 7)
                .stroke(isActive ? Color.clear : Color.primary.opacity(0.1), lineWidth: 0.5))
        }
        .buttonStyle(.plain)
        .disabled(forceOff)
        .onAppear { refreshFeatureFont() }
        .onChange(of: fontPath) { _ in refreshFeatureFont() }
    }

    private func fallbackSampleText(for tag: String) -> String {
        switch tag {
        case "kern": return "AV"
        case "liga": return "fi"
        case "calt": return "e.g"
        case "dlig": return "st"
        case "ccmp": return "a\u{0308}"
        case "mark": return "a\u{0301}"
        case "mkmk": return "a\u{0302}\u{0301}"
        case "tnum", "pnum": return "123"
        case "onum", "lnum": return "123"
        case "frac": return "1/2"
        case "numr": return "x123"
        case "dnom": return "x123"
        case "sinf": return "x1"
        case "sups": return "x1"
        case "subs": return "x1"
        case "ordn": return "x1a"
        case "smcp": return "Abc"
        case "c2sc": return "ABC"
        case "swsh": return "Q"
        case "locl": return "Abc"
        case "rlig": return "\u{0644}\u{0627}"
        case "rclt": return "Abc"
        case "aalt": return "Aa"
        case "zero": return "0"
        case "case": return "H()"
        case "cpsp": return "AB"
        case "salt": return "a"
        case "titl": return "Abc"
        case "cswh": return "e"
        default:
            if tag.hasPrefix("ss") { return "a" }
            if tag.hasPrefix("cv") { return "a" }
            return "Aa"
        }
    }
}
