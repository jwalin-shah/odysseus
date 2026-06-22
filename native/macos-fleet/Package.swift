// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "FleetViewer",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "FleetViewer", targets: ["FleetViewerApp"])
    ],
    targets: [
        .target(
            name: "FleetCore",
            path: "Sources/FleetCore"
        ),
        .executableTarget(
            name: "FleetViewerApp",
            dependencies: ["FleetCore"],
            path: "Sources/FleetViewerApp"
        )
    ]
)
