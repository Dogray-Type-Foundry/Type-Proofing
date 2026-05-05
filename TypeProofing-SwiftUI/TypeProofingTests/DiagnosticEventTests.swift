import XCTest
@testable import TypeProofing

final class DiagnosticEventTests: XCTestCase {
    func testDiagnosticDetailsAcceptJSONScalarValues() {
        let event = DiagnosticEvent.fromDictionary([
            "level": "debug",
            "category": "worker",
            "message": "debug details",
            "details": [
                "string": "value",
                "integer": 42,
                "boolean": true,
                "null": NSNull(),
                "array": ["a", "b"],
                "object": ["key": "value"],
            ],
            "timestamp": "2026-05-05T23:00:00",
        ])

        XCTAssertEqual(event?.details["string"], "value")
        XCTAssertEqual(event?.details["integer"], "42")
        XCTAssertEqual(event?.details["boolean"], "true")
        XCTAssertEqual(event?.details["null"], "null")
        XCTAssertEqual(event?.details["array"], #"["a","b"]"#)
        XCTAssertEqual(event?.details["object"], #"{"key":"value"}"#)
    }
}
