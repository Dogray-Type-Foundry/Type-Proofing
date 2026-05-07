import AppKit
import Foundation
import PDFKit

enum PreviewFragmentStatus: Equatable {
    case empty
    case queued
    case generating
    case ready(path: String, pageCount: Int, sections: [ProofSection])
    case failed(message: String)
}

struct PreviewFragment {
    let proofID: ProofOption.ID
    let proofName: String
    let baseType: String
    var fingerprint: String
    var status: PreviewFragmentStatus
    var generationToken: UUID
    var cost: ProofCost
}

private enum PreviewPriority {
    case selected
    case normal
}

private struct PreviewJob {
    let token: UUID
    let proofID: ProofOption.ID
    let proofName: String
    let baseType: String
    let fullConfig: ProofConfig
    let fingerprint: String
    let cost: ProofCost
    let priority: PreviewPriority
}

private struct PlaceholderKey: Hashable {
    let pageFormat: String
    let title: String
    let message: String
    let width: Int
    let height: Int
}

@MainActor
final class PreviewCoordinator: ObservableObject {
    private weak var state: AppState?
    private weak var engine: ProofEngine?

    private var fragments: [ProofOption.ID: PreviewFragment] = [:]
    private var fastQueue: [PreviewJob] = []
    private var wordsivQueue: [PreviewJob] = []
    private var runningFast: [ProofOption.ID: Task<Void, Never>] = [:]
    private var runningWordsiv: (proofID: ProofOption.ID, task: Task<Void, Never>)?
    private var debounceTasks: [ProofOption.ID: Task<Void, Never>] = [:]
    private var globalDebounceTask: Task<Void, Never>?
    private var composeTask: Task<Void, Never>?
    private var generationPaused = false

    private let sessionDirectory = FileManager.default.temporaryDirectory
        .appendingPathComponent("type-proofing-preview")
        .appendingPathComponent(UUID().uuidString)
    private var pageDimensions: [String: PageFormatDimensions] = [:]
    private var placeholderCache: [PlaceholderKey: URL] = [:]
    private var retainedComposedURLs: [URL] = []

    private var maxFastParallelism: Int {
        min(3, max(1, ProcessInfo.processInfo.processorCount / 2))
    }

    func configure(state: AppState, engine: ProofEngine) {
        self.state = state
        self.engine = engine
        self.pageDimensions = engine.getPageFormatDimensions()
        createPreviewDirectories()
    }

    func startInitialPreview() {
        invalidateAll()
    }

    func stateChanged(debounced: Bool) {
        guard !generationPaused else { return }
        globalDebounceTask?.cancel()
        if debounced {
            globalDebounceTask = Task { [weak self] in
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                self?.invalidateAll()
            }
        } else {
            invalidateAll()
        }
    }

    func proofSettingsChanged(proofID: ProofOption.ID) {
        guard !generationPaused else { return }
        debounceTasks[proofID]?.cancel()
        debounceTasks[proofID] = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            self?.invalidateProof(proofID)
        }
    }

    func proofEnableChanged(proofID: ProofOption.ID) {
        guard let state else { return }
        if state.proofOptions.first(where: { $0.id == proofID })?.enabled == true {
            invalidateProof(proofID)
        } else {
            cancelRunning(for: proofID)
            fragments.removeValue(forKey: proofID)
            removeQueuedJobs(for: proofID)
            requestCompose(immediate: true)
        }
    }

    func proofOrderChanged() {
        requestCompose(immediate: true)
    }

    func selectedProofChanged() {
        guard let selected = state?.selectedProof else { return }
        prioritizeQueuedJob(for: selected)
        pumpQueues()
    }

    func pauseForFinalGeneration() {
        generationPaused = true
        globalDebounceTask?.cancel()
        debounceTasks.values.forEach { $0.cancel() }
        debounceTasks.removeAll()
        composeTask?.cancel()
        composeTask = nil
        fastQueue.removeAll()
        wordsivQueue.removeAll()
        cancelAllRunning()
    }

    func resumeAfterFinalGeneration() {
        generationPaused = false
        stateChanged(debounced: false)
    }

    private func invalidateAll() {
        guard let state else { return }
        state.refreshCurrentConfigFingerprint()

        cancelAllRunning()
        fastQueue.removeAll()
        wordsivQueue.removeAll()

        let enabled = state.proofOptions.filter(\.enabled)
        guard !state.enabledFontPaths.isEmpty, !enabled.isEmpty else {
            fragments.removeAll()
            state.previewPDFPath = nil
            state.previewSections = []
            return
        }

        let selectedID = state.selectedProof
        for option in enabled {
            enqueue(option: option, priority: option.id == selectedID ? .selected : .normal)
        }
        requestCompose(immediate: true)
        pumpQueues()
    }

    private func invalidateProof(_ proofID: ProofOption.ID) {
        guard let option = state?.proofOptions.first(where: { $0.id == proofID }) else { return }
        cancelRunning(for: proofID)
        removeQueuedJobs(for: proofID)
        guard option.enabled else {
            fragments.removeValue(forKey: proofID)
            requestCompose(immediate: true)
            return
        }
        enqueue(option: option, priority: option.id == state?.selectedProof ? .selected : .normal)
        requestCompose(immediate: true)
        pumpQueues()
    }

    private func enqueue(option: ProofOption, priority: PreviewPriority) {
        guard let state else { return }
        let fingerprint = state.previewFingerprint(for: option)
        if let existing = fragments[option.id],
           existing.fingerprint == fingerprint,
           case .ready = existing.status {
            return
        }

        let token = UUID()
        let cost = state.registryByKey[option.baseType]?.previewCost ?? .fast
        fragments[option.id] = PreviewFragment(
            proofID: option.id,
            proofName: option.name,
            baseType: option.baseType,
            fingerprint: fingerprint,
            status: .queued,
            generationToken: token,
            cost: cost
        )

        let job = PreviewJob(
            token: token,
            proofID: option.id,
            proofName: option.name,
            baseType: option.baseType,
            fullConfig: state.buildProofConfig(),
            fingerprint: fingerprint,
            cost: cost,
            priority: priority
        )
        if cost == .wordsiv {
            insert(job, into: &wordsivQueue)
        } else {
            insert(job, into: &fastQueue)
        }
    }

    private func insert(_ job: PreviewJob, into queue: inout [PreviewJob]) {
        if job.priority == .selected {
            queue.insert(job, at: 0)
        } else {
            queue.append(job)
        }
    }

    private func pumpQueues() {
        guard !generationPaused else { return }
        while runningFast.count < maxFastParallelism, !fastQueue.isEmpty {
            start(fastQueue.removeFirst())
        }
        if runningWordsiv == nil, !wordsivQueue.isEmpty {
            start(wordsivQueue.removeFirst())
        }
    }

    private func start(_ job: PreviewJob) {
        guard let engine else { return }
        fragments[job.proofID]?.status = .generating

        let outputDir = fragmentOutputDirectory(for: job)
        try? FileManager.default.createDirectory(at: outputDir, withIntermediateDirectories: true)
        let config = job.fullConfig.previewFragmentConfig(
            proofName: job.proofName,
            baseType: job.baseType,
            outputDir: outputDir.path
        )

        let task = Task { [weak self] in
            let result = await engine.generatePreviewFragment(
                config: config,
                timeoutSeconds: job.cost == .wordsiv ? 150 : 60
            )
            guard !Task.isCancelled else { return }
            self?.finish(job: job, result: result)
        }
        if job.cost == .wordsiv {
            runningWordsiv = (job.proofID, task)
        } else {
            runningFast[job.proofID] = task
        }
    }

    private func finish(job: PreviewJob, result: PreviewFragmentResult?) {
        if job.cost == .wordsiv {
            if runningWordsiv?.proofID == job.proofID {
                runningWordsiv = nil
            }
        } else {
            runningFast.removeValue(forKey: job.proofID)
        }

        guard var fragment = fragments[job.proofID],
              fragment.generationToken == job.token,
              fragment.fingerprint == job.fingerprint else {
            pumpQueues()
            return
        }

        if let result, !result.path.isEmpty {
            guard result.proofName == job.proofName,
                  result.baseType == job.baseType else {
                fragment.status = .failed(message: "Preview worker returned a different proof.")
                fragments[job.proofID] = fragment
                composePreview()
                pumpQueues()
                return
            }
            fragment.status = .ready(
                path: result.path,
                pageCount: max(result.pageCount, 1),
                sections: result.sections
            )
        } else {
            fragment.status = .failed(
                message: result?.errorMessage ?? "Preview fragment generation failed."
            )
        }
        fragments[job.proofID] = fragment
        requestCompose()
        pumpQueues()
    }

    private func requestCompose(immediate: Bool = false) {
        composeTask?.cancel()
        if immediate {
            composeTask = nil
            composePreview()
            return
        }

        composeTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 75_000_000)
            guard !Task.isCancelled else { return }
            self?.composePreview()
        }
    }

    private func composePreview() {
        guard let state else { return }
        let enabled = state.proofOptions.filter(\.enabled)
        guard !enabled.isEmpty, !state.enabledFontPaths.isEmpty else {
            state.previewPDFPath = nil
            state.previewSections = []
            return
        }

        let output = PDFDocument()
        var sections: [ProofSection] = []

        for option in enabled {
            sections.append(ProofSection(name: option.name, firstPage: output.pageCount))
            let status = fragments[option.id]?.status ?? .empty
            appendPages(for: option, status: status, to: output)
        }

        let url = composedDirectory()
            .appendingPathComponent("preview-\(UUID().uuidString).pdf")
        if output.pageCount > 0, output.write(to: url) {
            state.previewPDFPath = url.path
            state.previewSections = sections
            retainComposedURL(url)
        }
    }

    private func appendPages(for option: ProofOption, status: PreviewFragmentStatus, to output: PDFDocument) {
        switch status {
        case .ready(let path, _, _):
            if let document = PDFDocument(url: URL(fileURLWithPath: path)), document.pageCount > 0 {
                for index in 0..<document.pageCount {
                    if let page = document.page(at: index) {
                        let pageForOutput = (page.copy() as? PDFPage) ?? page
                        output.insert(pageForOutput, at: output.pageCount)
                    }
                }
                return
            }
            appendPlaceholder(title: option.name, message: "Preview unavailable", to: output)
        case .failed(let message):
            appendPlaceholder(title: option.name, message: message, to: output)
        case .generating:
            appendPlaceholder(title: option.name, message: "Generating preview...", to: output)
        case .queued:
            appendPlaceholder(title: option.name, message: "Queued for preview...", to: output)
        case .empty:
            appendPlaceholder(title: option.name, message: "Waiting for preview...", to: output)
        }
    }

    private func appendPlaceholder(title: String, message: String, to output: PDFDocument) {
        let dimensions = currentPageDimensions()
        let key = PlaceholderKey(
            pageFormat: state?.pageFormat ?? "A4Landscape",
            title: title,
            message: message,
            width: Int(dimensions.width.rounded()),
            height: Int(dimensions.height.rounded())
        )
        let url: URL
        if let cached = placeholderCache[key],
           FileManager.default.fileExists(atPath: cached.path) {
            url = cached
        } else {
            let newURL = placeholderDirectory()
                .appendingPathComponent("placeholder-\(UUID().uuidString).pdf")
            writePlaceholderPDF(title: title, message: message, dimensions: dimensions, to: newURL)
            placeholderCache[key] = newURL
            url = newURL
        }
        guard let document = PDFDocument(url: url), let page = document.page(at: 0) else { return }
        let pageForOutput = (page.copy() as? PDFPage) ?? page
        output.insert(pageForOutput, at: output.pageCount)
    }

    private func writePlaceholderPDF(
        title: String,
        message: String,
        dimensions: PageFormatDimensions,
        to url: URL
    ) {
        var mediaBox = CGRect(x: 0, y: 0, width: dimensions.width, height: dimensions.height)
        let data = NSMutableData()
        guard let consumer = CGDataConsumer(data: data as CFMutableData),
              let context = CGContext(consumer: consumer, mediaBox: &mediaBox, nil) else { return }

        context.beginPDFPage(nil)
        context.saveGState()
        context.translateBy(x: 0, y: dimensions.height)
        context.scaleBy(x: 1, y: -1)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(cgContext: context, flipped: true)

        let titleAttributes: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: 22, weight: .semibold),
            .foregroundColor: NSColor.labelColor,
        ]
        let messageAttributes: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: 13, weight: .regular),
            .foregroundColor: NSColor.secondaryLabelColor,
        ]
        let x: CGFloat = 48
        let y = dimensions.height / 2 - 30
        NSAttributedString(string: title, attributes: titleAttributes)
            .draw(in: CGRect(x: x, y: y, width: dimensions.width - x * 2, height: 32))
        NSAttributedString(string: message, attributes: messageAttributes)
            .draw(in: CGRect(x: x, y: y + 36, width: dimensions.width - x * 2, height: 48))

        NSGraphicsContext.restoreGraphicsState()
        context.restoreGState()
        context.endPDFPage()
        context.closePDF()
        data.write(to: url, atomically: true)
    }

    private func currentPageDimensions() -> PageFormatDimensions {
        pageDimensions[state?.pageFormat ?? "A4Landscape"]
            ?? PageFormatDimensions(width: 842, height: 595)
    }

    private func removeQueuedJobs(for proofID: ProofOption.ID) {
        fastQueue.removeAll { $0.proofID == proofID }
        wordsivQueue.removeAll { $0.proofID == proofID }
    }

    private func cancelRunning(for proofID: ProofOption.ID) {
        runningFast.removeValue(forKey: proofID)?.cancel()
        if runningWordsiv?.proofID == proofID {
            runningWordsiv?.task.cancel()
            runningWordsiv = nil
        }
    }

    private func cancelAllRunning() {
        runningFast.values.forEach { $0.cancel() }
        runningFast.removeAll()
        runningWordsiv?.task.cancel()
        runningWordsiv = nil
    }

    private func prioritizeQueuedJob(for proofID: ProofOption.ID) {
        if let index = fastQueue.firstIndex(where: { $0.proofID == proofID }) {
            let job = fastQueue.remove(at: index)
            fastQueue.insert(job, at: 0)
        }
        if let index = wordsivQueue.firstIndex(where: { $0.proofID == proofID }) {
            let job = wordsivQueue.remove(at: index)
            wordsivQueue.insert(job, at: 0)
        }
    }

    private func createPreviewDirectories() {
        try? FileManager.default.createDirectory(at: fragmentsDirectory(), withIntermediateDirectories: true)
        try? FileManager.default.createDirectory(at: placeholderDirectory(), withIntermediateDirectories: true)
        try? FileManager.default.createDirectory(at: composedDirectory(), withIntermediateDirectories: true)
    }

    private func fragmentsDirectory() -> URL {
        sessionDirectory.appendingPathComponent("fragments")
    }

    private func fragmentOutputDirectory(for job: PreviewJob) -> URL {
        fragmentsDirectory()
            .appendingPathComponent(job.proofID.uuidString)
            .appendingPathComponent(job.token.uuidString)
    }

    private func placeholderDirectory() -> URL {
        sessionDirectory.appendingPathComponent("placeholders")
    }

    private func composedDirectory() -> URL {
        sessionDirectory.appendingPathComponent("composed")
    }

    private func retainComposedURL(_ url: URL) {
        retainedComposedURLs.append(url)
        while retainedComposedURLs.count > 2 {
            let stale = retainedComposedURLs.removeFirst()
            try? FileManager.default.removeItem(at: stale)
        }
    }
}
