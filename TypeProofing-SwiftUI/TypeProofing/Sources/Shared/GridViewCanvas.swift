import ProofCore
import SwiftUI
import PDFKit

// MARK: - GridViewCanvas

struct GridViewCanvas: View {
    let pdfPath: String
    let sections: [ProofSection]
    let pdfCoordinator: PDFViewCoordinator
    @EnvironmentObject var page: PageState
    @EnvironmentObject var annotations: AnnotationStore

    @State private var document: PDFDocument?

    var body: some View {
        ScrollView {
            if let document, document.pageCount > 0 {
                let pageCount = document.pageCount
                let sectionMap = buildSectionMap(pageCount: pageCount)
                let annotatedPages = annotations.annotatedPages(in: sections)

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 180), spacing: 12)], spacing: 12) {
                    ForEach(0..<pageCount, id: \.self) { pageIndex in
                        VStack(spacing: 0) {
                            if let sectionName = sectionMap[pageIndex] {
                                Text(sectionName)
                                    .font(.system(size: 11, weight: .medium))
                                    .tracking(0.88)
                                    .foregroundStyle(.secondary)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.bottom, 4)
                            }

                            Button {
                                // The PDFView doesn't exist while grid mode is
                                // showing; the coordinator navigates once the
                                // remounted view finishes loading the document.
                                pdfCoordinator.pendingPageIndex = pageIndex
                                page.viewMode = .page
                            } label: {
                                GridThumbnailView(document: document, pageIndex: pageIndex)
                            }
                            .buttonStyle(.plain)
                            .overlay(alignment: .topTrailing) {
                                if annotatedPages.contains(pageIndex) {
                                    AnnotationBadgeDot()
                                }
                            }

                            Text("\(pageIndex + 1)")
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(.tertiary)
                                .padding(.top, 2)
                        }
                    }
                }
                .padding(16)
            } else {
                Text("No pages to display")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .softScrollEdgeEffect()
        .onAppear { loadDocument() }
        .onChange(of: pdfPath) { _ in loadDocument() }
    }

    private func loadDocument() {
        let url = URL(fileURLWithPath: pdfPath)
        document = PDFDocument(url: url)
    }

    private func buildSectionMap(pageCount: Int) -> [Int: String] {
        var map: [Int: String] = [:]
        for section in sections {
            let idx = min(max(section.firstPage, 0), pageCount - 1)
            map[idx] = section.name
        }
        return map
    }
}

/// Marks an annotated page in the grid view and the thumbnail strip. The
/// hairline ring keeps it visible over dark page content.
struct AnnotationBadgeDot: View {
    var body: some View {
        Circle()
            .fill(.red)
            .frame(width: 8, height: 8)
            .overlay(Circle().stroke(.white, lineWidth: 1))
            .padding(4)
    }
}

private struct GridThumbnailView: View {
    let document: PDFDocument
    let pageIndex: Int

    var body: some View {
        if let page = document.page(at: pageIndex) {
            let bounds = page.bounds(for: .mediaBox)
            let aspect = bounds.width / max(bounds.height, 1)
            let image = page.thumbnail(of: CGSize(width: 360, height: 360 / aspect), for: .mediaBox)
            Image(platformImage: image)
                .resizable()
                .aspectRatio(aspect, contentMode: .fit)
                .clipShape(RoundedRectangle(cornerRadius: 4))
                .overlay(
                    RoundedRectangle(cornerRadius: 4)
                        .stroke(Color.primary.opacity(0.1), lineWidth: 0.5)
                )
        }
    }
}

