// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "ProofCore",
    platforms: [
        .macOS(.v13),
        .iOS(.v17),
    ],
    products: [
        .library(name: "ProofCore", targets: ["ProofCore"]),
    ],
    targets: [
        .binaryTarget(
            name: "TPNative",
            path: "Binaries/TPNative.xcframework"
        ),
        .target(
            name: "ProofCore",
            dependencies: ["TPNative"],
            resources: [
                .process("Resources")
            ]
        ),
        .testTarget(
            name: "ProofCoreTests",
            dependencies: ["ProofCore"]
        ),
    ]
)
