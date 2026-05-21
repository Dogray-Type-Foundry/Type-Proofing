import XCTest
import TPNative

final class NativeLibTests: XCTestCase {

    func testVersion() {
        let version = String(cString: tp_version())
        XCTAssertEqual(version, "0.1.0")
    }

    func testFontInfoRoundtrip() throws {
        let url = Bundle(for: type(of: self)).url(forResource: "SetsGroteskVF", withExtension: "ttf")
            ?? URL(fileURLWithPath: NSString(string: "~/local/github/Type-Proofing/SetsGroteskVF.ttf").expandingTildeInPath)
        let data = try Data(contentsOf: url)

        let info = data.withUnsafeBytes { buf -> UnsafeMutablePointer<TPFontInfo>? in
            guard let base = buf.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return nil }
            return tp_load_font(base, UInt(buf.count))
        }
        XCTAssertNotNil(info)

        let family = String(cString: info!.pointee.family_name)
        XCTAssert(family.contains("Sets Grotesk"), "Got: \(family)")
        XCTAssertTrue(info!.pointee.is_variable)

        tp_free_font_info(info)
    }

    func testWordSivTextGeneration() {
        let wsv = wsv_create(987654)
        XCTAssertNotNil(wsv)

        let glyphs = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,;:!?-"
        let sep = " "
        let result = wsv_text(wsv, glyphs, 2, 0.0, 0.0, sep)
        XCTAssertNotNil(result)

        let text = String(cString: result!)
        XCTAssertFalse(text.isEmpty)

        wsv_free_string(result)
        wsv_free(wsv)
    }
}
