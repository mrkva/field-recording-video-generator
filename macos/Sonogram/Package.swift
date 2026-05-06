// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Sonogram",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "Sonogram",
            path: "Sources/Sonogram"
        )
    ]
)
