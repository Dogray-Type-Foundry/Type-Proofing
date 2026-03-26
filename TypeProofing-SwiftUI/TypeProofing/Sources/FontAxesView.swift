import SwiftUI
import CompactSlider

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
    @Binding var values: [Double]

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
                HoverIconButton(systemName: "plus", size: 10, action: addHandle)

                // Remove handle (only if > 1)
                HoverIconButton(systemName: "minus", size: 10, action: removeHandle)
                    .disabled(values.count <= 1)
            }

            // Slider with instance markers and value labels overlay
            ZStack(alignment: .bottom) {
                CompactSlider(values: $values, in: axis.minValue...axis.maxValue)
                    .compactSliderOptionsByAdding(.scrollWheel, .tapToSlide)
                    .frame(height: 24)

                // Instance markers on the track
                if !axis.instanceValues.isEmpty {
                    InstanceMarkers(
                        instanceValues: axis.instanceValues,
                        range: axis.minValue...axis.maxValue
                    )
                }
            }

            // Editable value labels under handles
            EditableHandleLabels(
                values: $values,
                range: axis.minValue...axis.maxValue,
                usePrecision: usePrecision
            )
        }
    }

    private var valuesSummary: String {
        values.sorted().map { formatValue($0) }.joined(separator: ", ")
    }

    private func formatValue(_ v: Double) -> String {
        if usePrecision {
            return String(format: "%.2f", v)
        }
        return String(Int(v.rounded()))
    }

    private func addHandle() {
        let sorted = values.sorted()
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

        values.append(bestMid)
        values.sort()
    }

    private func removeHandle() {
        guard values.count > 1 else { return }
        if !axis.instanceValues.isEmpty {
            let sorted = values.sorted()
            var worstIdx = sorted.count - 1
            var worstDist = 0.0
            for (i, v) in sorted.enumerated() {
                let minDist = axis.instanceValues.map { abs($0 - v) }.min() ?? 0
                if minDist > worstDist { worstDist = minDist; worstIdx = i }
            }
            if let idx = values.firstIndex(of: sorted[worstIdx]) {
                values.remove(at: idx)
            }
        } else {
            values.removeLast()
        }
    }
}

// MARK: - Editable value labels positioned under each handle

private struct EditableHandleLabels: View {
    @Binding var values: [Double]
    let range: ClosedRange<Double>
    let usePrecision: Bool

    @State private var editingIndex: Int? = nil
    @State private var editText: String = ""

    var body: some View {
        GeometryReader { geo in
            let width = geo.size.width
            let span = range.upperBound - range.lowerBound
            let sorted = values.sorted()
            ForEach(Array(sorted.enumerated()), id: \.offset) { idx, val in
                let fraction = span > 0 ? (val - range.lowerBound) / span : 0.5
                let x = fraction * width
                if editingIndex == idx {
                    TextField("", text: $editText, onCommit: { commitEdit(sortedIndex: idx) })
                        .textFieldStyle(.plain)
                        .font(.system(size: 9).monospacedDigit())
                        .multilineTextAlignment(.center)
                        .frame(width: 48, height: 14)
                        .background(Color(nsColor: .controlBackgroundColor))
                        .cornerRadius(2)
                        .position(x: x, y: 7)
                } else {
                    HoverValueLabel(text: formatValue(val)) {
                        editText = formatValue(val)
                        editingIndex = idx
                    }
                    .position(x: x, y: 6)
                }
            }
        }
        .frame(height: 14)
    }

    private func commitEdit(sortedIndex: Int) {
        defer { editingIndex = nil }
        guard let parsed = Double(editText) else { return }
        let clamped = min(max(parsed, range.lowerBound), range.upperBound)

        // Find the original index of the sorted value we're editing
        let sorted = values.sorted()
        guard sortedIndex < sorted.count else { return }
        let oldValue = sorted[sortedIndex]
        if let origIdx = values.firstIndex(of: oldValue) {
            values[origIdx] = clamped
            values.sort()
        }
    }

    private func formatValue(_ v: Double) -> String {
        if usePrecision {
            return String(format: "%.2f", v)
        }
        return String(Int(v.rounded()))
    }
}

// MARK: - Instance position markers on the track

private struct InstanceMarkers: View {
    let instanceValues: [Double]
    let range: ClosedRange<Double>

    var body: some View {
        GeometryReader { geo in
            let width = geo.size.width
            let span = range.upperBound - range.lowerBound
            ForEach(instanceValues, id: \.self) { val in
                let fraction = (val - range.lowerBound) / span
                let x = fraction * width
                Rectangle()
                    .fill(Color.orange)
                    .frame(width: 2, height: 10)
                    .position(x: x, y: geo.size.height - 5)
            }
        }
        .allowsHitTesting(false)
    }
}
