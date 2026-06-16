import SwiftUI
import AppKit

struct FontAxesView: View {
    let font: FontInfo
    @Binding var axisValues: [String: [Double]]

    var body: some View {
        VStack(spacing: 8) {
            ForEach(font.axes) { axis in
                AxisSliderRow(axis: axis, values: Binding(
                    get: { axisValues[axis.id] ?? [axis.defaultValue] },
                    set: { axisValues[axis.id] = $0 }
                ))
            }
        }
        .padding(.leading, 8)
    }
}

// MARK: - Per-axis slider row

private struct AxisSliderRow: View {
    let axis: FontAxis
    /// The persisted store. Writing here republishes app state (and triggers a
    /// font-style refresh), so we only touch it when an edit is committed.
    @Binding var values: [Double]

    /// Live values driving the slider/labels. Dragging mutates only this local
    /// state so the gesture stays smooth; `values` is committed on release.
    @State private var localValues: [Double]

    /// The handle the user last touched (dragged, added, or tapped a label for).
    /// Indexes into `localValues`. The remove button targets this one.
    @State private var selectedIndex: Int? = nil

    /// Window-level mouse-down monitor, installed only while something is selected,
    /// used to deselect on a click anywhere outside the selected handle.
    @State private var deselectMonitor: Any? = nil

    /// Drag bookkeeping: the handle grabbed at press (nil = press missed all
    /// handles), and whether the current drag has begun.
    @State private var draggingIndex: Int? = nil
    @State private var dragBegan = false

    private let trackHeight: CGFloat = 24

    init(axis: FontAxis, values: Binding<[Double]>) {
        self.axis = axis
        self._values = values
        self._localValues = State(initialValue: values.wrappedValue)
    }

    /// Range < 50 → 2 decimals; otherwise whole numbers
    private var usePrecision: Bool {
        (axis.maxValue - axis.minValue) < 50
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            // Header: axis name, values summary, add/remove buttons
            HStack(spacing: 4) {
                Text(axis.name)
                    .font(.caption)
                Spacer()
                Text(valuesSummary)
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .lineLimit(1)

                // Add handle
                AxisStepperButton(systemName: "plus", action: addHandle)

                // Remove handle (only if > 1)
                AxisStepperButton(systemName: "minus", action: removeHandle)
                    .disabled(localValues.count <= 1)
            }

            // Multi-handle track. One drag gesture covers the whole area: it grabs
            // the handle nearest the press and moves only that one (so dragging past
            // another never disturbs it), and it claims every drag so none leaks to
            // the row's reorder `.onDrag`.
            GeometryReader { geo in
                let width = geo.size.width
                ZStack(alignment: .leading) {
                    // Track line
                    Capsule()
                        .fill(Color.secondary.opacity(0.25))
                        .frame(height: 4)
                        .frame(maxHeight: .infinity, alignment: .center)

                    // Instance (master) notches
                    ForEach(axis.instanceValues, id: \.self) { value in
                        Rectangle()
                            .fill(Color.orange)
                            .frame(width: 2, height: 10)
                            .position(x: xPosition(for: value, width: width), y: trackHeight - 5)
                    }

                    // Handles (visual only; the gesture below drives them)
                    ForEach(localValues.indices, id: \.self) { index in
                        handleView(index: index)
                            .position(x: xPosition(for: localValues[index], width: width), y: trackHeight / 2)
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .contentShape(Rectangle())
                .coordinateSpace(name: "track")
                .gesture(
                    DragGesture(minimumDistance: 0, coordinateSpace: .named("track"))
                        .onChanged { value in
                            if !dragBegan {
                                dragBegan = true
                                draggingIndex = grabHandle(nearX: value.startLocation.x, width: width)
                                if let index = draggingIndex { selectedIndex = index }
                            }
                            if let index = draggingIndex {
                                setValue(index: index, toX: value.location.x, width: width)
                            }
                        }
                        .onEnded { value in
                            let moved = abs(value.translation.width) > 2
                            if moved {
                                if draggingIndex != nil { commit() }
                            } else {
                                // A click: select the nearest handle, or deselect on a miss.
                                selectNearestHandle(toX: value.location.x, width: width)
                            }
                            dragBegan = false
                            draggingIndex = nil
                        }
                )
            }
            .frame(height: trackHeight)

            // Editable value labels under handles
            EditableHandleLabels(
                values: editingBinding,
                selectedIndex: $selectedIndex,
                range: axis.minValue...axis.maxValue,
                usePrecision: usePrecision
            )
        }
        .onChange(of: values) { newValues in
            // Resync when the store changes externally (font switch, reset).
            if localValues != newValues { localValues = newValues }
        }
        .onChange(of: selectedIndex) { newValue in
            // Only watch for outside clicks while a handle is actually selected.
            if newValue == nil { removeDeselectMonitor() } else { installDeselectMonitor() }
        }
        .onDisappear { removeDeselectMonitor() }
    }

    private func installDeselectMonitor() {
        guard deselectMonitor == nil else { return }
        deselectMonitor = NSEvent.addLocalMonitorForEvents(matching: [.leftMouseDown]) { event in
            // Clear the selection on any click. Clicks that land on this slider are
            // re-selected by its own gesture (on release / first drag), so only
            // clicks elsewhere in the app actually stick as a deselect.
            selectedIndex = nil
            return event
        }
    }

    private func removeDeselectMonitor() {
        if let monitor = deselectMonitor {
            NSEvent.removeMonitor(monitor)
            deselectMonitor = nil
        }
    }

    /// Pushes the live values to the persisted store (no-op if unchanged).
    private func commit() {
        if values != localValues { values = localValues }
    }

    /// Label edits are discrete, so they update local state and commit at once.
    private var editingBinding: Binding<[Double]> {
        Binding(
            get: { localValues },
            set: { localValues = $0; commit() }
        )
    }

    /// Maps an axis value to its x position on a track of the given width.
    private func xPosition(for value: Double, width: CGFloat) -> CGFloat {
        let span = axis.maxValue - axis.minValue
        guard span > 0 else { return width / 2 }
        return CGFloat((value - axis.minValue) / span) * width
    }

    /// Moves one handle to the dragged x.
    private func setValue(index: Int, toX x: CGFloat, width: CGFloat) {
        guard width > 0, index < localValues.count else { return }
        let span = axis.maxValue - axis.minValue
        let fraction = min(max(x / width, 0), 1)
        localValues[index] = axis.minValue + Double(fraction) * span
    }

    /// The handle nearest the press, if it's within grabbing range.
    private func grabHandle(nearX x: CGFloat, width: CGFloat) -> Int? {
        let grabSlop: CGFloat = 16
        guard width > 0, !localValues.isEmpty else { return nil }
        var best: Int? = nil
        var bestDist = CGFloat.greatestFiniteMagnitude
        for (i, v) in localValues.enumerated() {
            let dist = abs(xPosition(for: v, width: width) - x)
            if dist < bestDist { bestDist = dist; best = i }
        }
        return bestDist <= grabSlop ? best : nil
    }

    /// The handle drawn on the track. The selected one is a bold, wider accent
    /// capsule with a white border; the rest are muted thin bars.
    @ViewBuilder
    private func handleView(index: Int) -> some View {
        if selectedIndex == index {
            Capsule()
                .fill(Color.accentColor)
                .frame(width: 8, height: trackHeight)
                .overlay(Capsule().strokeBorder(.white, lineWidth: 1.5))
        } else {
            Capsule()
                .fill(Color.accentColor.opacity(0.5))
                .frame(width: 3, height: trackHeight)
        }
    }

    /// Selects the handle nearest the click, or deselects when the click lands on
    /// empty track (further than `hitSlop` points from any handle).
    private func selectNearestHandle(toX x: CGFloat, width: CGFloat) {
        let hitSlop: CGFloat = 12
        guard width > 0, !localValues.isEmpty else { selectedIndex = nil; return }
        let span = axis.maxValue - axis.minValue
        var best = 0
        var bestDist = CGFloat.greatestFiniteMagnitude
        for (i, v) in localValues.enumerated() {
            let handleX = CGFloat((v - axis.minValue) / span) * width
            let dist = abs(handleX - x)
            if dist < bestDist { bestDist = dist; best = i }
        }
        selectedIndex = bestDist <= hitSlop ? best : nil
    }

    private var valuesSummary: String {
        localValues.sorted().map { formatValue($0) }.joined(separator: ", ")
    }

    private func formatValue(_ v: Double) -> String {
        if usePrecision {
            return String(format: "%.2f", v)
        }
        return String(Int(v.rounded()))
    }

    private func addHandle() {
        let sorted = localValues.sorted()
        var bestMid = (axis.minValue + axis.maxValue) / 2
        var bestGap = 0.0

        if let first = sorted.first {
            let gap = first - axis.minValue
            if gap > bestGap { bestGap = gap; bestMid = axis.minValue + gap / 2 }
        }
        for i in 0..<(sorted.count - 1) {
            let gap = sorted[i + 1] - sorted[i]
            if gap > bestGap { bestGap = gap; bestMid = sorted[i] + gap / 2 }
        }
        if let last = sorted.last {
            let gap = axis.maxValue - last
            if gap > bestGap { bestGap = gap; bestMid = last + gap / 2 }
        }

        let snapThreshold = (axis.maxValue - axis.minValue) * 0.05
        if let nearest = axis.instanceValues.min(by: { abs($0 - bestMid) < abs($1 - bestMid) }),
           abs(nearest - bestMid) < snapThreshold {
            bestMid = nearest
        }

        localValues.append(bestMid)
        selectedIndex = localValues.count - 1
        commit()
    }

    private func removeHandle() {
        guard localValues.count > 1 else { return }
        let idx = selectedIndex ?? (localValues.count - 1)
        guard idx < localValues.count else { return }
        localValues.remove(at: idx)
        selectedIndex = min(idx, localValues.count - 1)
        commit()
    }
}

// MARK: - Add/remove handle button

/// A bordered icon button with a generous hit area that highlights on hover.
private struct AxisStepperButton: View {
    let systemName: String
    let action: () -> Void
    @Environment(\.isEnabled) private var isEnabled
    @State private var isHovered = false

    var body: some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(foreground)
                .frame(width: 18, height: 18)
                .background(
                    RoundedRectangle(cornerRadius: 4)
                        .fill(isHovered && isEnabled ? Color.accentColor.opacity(0.15) : .clear)
                )
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { isHovered = $0 }
    }

    private var foreground: Color {
        guard isEnabled else { return .secondary.opacity(0.4) }
        return isHovered ? .accentColor : .secondary
    }
}

// MARK: - Editable value labels positioned under each handle

private struct EditableHandleLabels: View {
    @Binding var values: [Double]
    @Binding var selectedIndex: Int?
    let range: ClosedRange<Double>
    let usePrecision: Bool

    @State private var editingIndex: Int? = nil
    @State private var editText: String = ""

    var body: some View {
        GeometryReader { geo in
            let width = geo.size.width
            let span = range.upperBound - range.lowerBound
            // Iterate real indices; each label is positioned by its value, so
            // display order doesn't matter and index identity stays stable.
            ForEach(Array(values.enumerated()), id: \.offset) { idx, val in
                let fraction = span > 0 ? (val - range.lowerBound) / span : 0.5
                let x = fraction * width
                if editingIndex == idx {
                    TextField("", text: $editText, onCommit: { commitEdit(index: idx) })
                        .textFieldStyle(.plain)
                        .font(.system(size: 9).monospacedDigit())
                        .multilineTextAlignment(.center)
                        .frame(width: 48, height: 14)
                        .background(Color(nsColor: .controlBackgroundColor))
                        .cornerRadius(2)
                        .position(x: x, y: 7)
                } else if selectedIndex == idx {
                    Text(formatValue(val))
                        .font(.system(size: 9, weight: .semibold).monospacedDigit())
                        .foregroundStyle(.white)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(Capsule().fill(Color.accentColor))
                        .onTapGesture { startEditing(idx, val) }
                        .position(x: x, y: 6)
                } else {
                    HoverValueLabel(text: formatValue(val)) {
                        selectedIndex = idx
                        startEditing(idx, val)
                    }
                    .position(x: x, y: 6)
                }
            }
        }
        .frame(height: 14)
    }

    private func startEditing(_ index: Int, _ value: Double) {
        editText = formatValue(value)
        editingIndex = index
    }

    private func commitEdit(index: Int) {
        defer { editingIndex = nil }
        guard let parsed = Double(editText), index < values.count else { return }
        values[index] = min(max(parsed, range.lowerBound), range.upperBound)
    }

    private func formatValue(_ v: Double) -> String {
        if usePrecision {
            return String(format: "%.2f", v)
        }
        return String(Int(v.rounded()))
    }
}
