// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "VNCBar",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "VNCBar", path: "Sources/VNCBar"),
        .testTarget(name: "VNCBarTests", dependencies: ["VNCBar"], path: "Tests/VNCBarTests"),
    ]
)
