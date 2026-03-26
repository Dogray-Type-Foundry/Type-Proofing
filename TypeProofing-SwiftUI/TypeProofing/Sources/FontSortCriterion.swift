import Foundation

enum FontSortProperty: String, CaseIterable, Codable {
    case familyName = "Family"
    case weight = "Weight"
    case width = "Width"
    case slant = "Slant"
    case opticalSize = "Optical Size"

    /// Extract the comparable value from a FontInfo.
    func value(for font: FontInfo) -> Double {
        switch self {
        case .familyName: return 0  // handled separately as string comparison
        case .weight:     return Double(font.weight)
        case .width:      return Double(font.width)
        case .slant:      return font.slant
        case .opticalSize: return font.opticalSize
        }
    }

    func stringValue(for font: FontInfo) -> String {
        switch self {
        case .familyName: return font.familyName.lowercased()
        default:          return ""
        }
    }
}

struct FontSortCriterion: Identifiable, Equatable, Codable {
    let id: UUID
    var property: FontSortProperty
    var ascending: Bool

    init(property: FontSortProperty, ascending: Bool = true) {
        self.id = UUID()
        self.property = property
        self.ascending = ascending
    }
}

// MARK: - Multi-level Sort

extension Array where Element == FontInfo {
    /// Sort fonts by an ordered list of criteria. First criterion is the primary
    /// sort key; subsequent criteria break ties from the previous level.
    func sorted(by criteria: [FontSortCriterion]) -> [FontInfo] {
        guard !criteria.isEmpty else { return self }

        return sorted { a, b in
            for criterion in criteria {
                let result: ComparisonResult
                if criterion.property == .familyName {
                    let aVal = criterion.property.stringValue(for: a)
                    let bVal = criterion.property.stringValue(for: b)
                    if aVal == bVal { continue }
                    result = aVal < bVal ? .orderedAscending : .orderedDescending
                } else {
                    let aVal = criterion.property.value(for: a)
                    let bVal = criterion.property.value(for: b)
                    if aVal == bVal { continue }
                    result = aVal < bVal ? .orderedAscending : .orderedDescending
                }

                if criterion.ascending {
                    return result == .orderedAscending
                } else {
                    return result == .orderedDescending
                }
            }
            return false // equal on all criteria, maintain relative order
        }
    }
}
