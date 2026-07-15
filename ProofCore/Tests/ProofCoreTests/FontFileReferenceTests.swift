import XCTest
@testable import ProofCore

final class FontFileReferenceTests: XCTestCase {

    private var tempFile: URL!

    override func setUpWithError() throws {
        tempFile = FileManager.default.temporaryDirectory
            .appendingPathComponent("FontFileReferenceTests-\(UUID().uuidString).ttf")
        try Data("stub".utf8).write(to: tempFile)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: tempFile)
    }

    func testReferenceCreatesBookmark() {
        let ref = FontFileReference(url: tempFile)
        XCTAssertEqual(ref.path, tempFile.path)
        XCTAssertNotNil(ref.bookmark)
    }

    func testCodableRoundTrip() throws {
        let ref = FontFileReference(url: tempFile)
        let data = try JSONEncoder().encode(ref)
        let decoded = try JSONDecoder().decode(FontFileReference.self, from: data)
        XCTAssertEqual(decoded, ref)
    }

    @MainActor
    func testRestoreAccessSucceedsForExistingFile() {
        let ref = FontFileReference(url: tempFile)
        XCTAssertTrue(FontAccessStore.shared.restoreAccess(to: ref))
        FontAccessStore.shared.releaseAccess(toPath: ref.path)
    }

    @MainActor
    func testRestoreAccessFailsForMissingFile() throws {
        let ref = FontFileReference(url: tempFile)
        try FileManager.default.removeItem(at: tempFile)
        XCTAssertFalse(FontAccessStore.shared.restoreAccess(to: ref))
    }

    @MainActor
    func testRestoreAccessWithoutBookmarkFallsBackToPathCheck() {
        let ref = FontFileReference(path: tempFile.path, bookmark: nil)
        XCTAssertTrue(FontAccessStore.shared.restoreAccess(to: ref))
        FontAccessStore.shared.releaseAccess(toPath: ref.path)
    }
}
