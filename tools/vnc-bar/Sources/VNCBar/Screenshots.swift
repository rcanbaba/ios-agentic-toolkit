import AppKit
import SwiftUI

/// `VNCBar --render-screenshots <dir>`: renders the popover's screens offscreen with synthetic
/// servers (documentation addresses), in light and dark, for the docs. Never touches real data.
@MainActor
enum Screenshots {
    static func render(into directory: URL) -> Int32 {
        _ = NSApplication.shared
        let file = FileManager.default.temporaryDirectory
            .appendingPathComponent("vncbar-screenshots-\(UUID().uuidString)/servers.json")
        let demo = [
            Server(name: "Build Mac 1", host: "203.0.113.10", port: 15944, username: "ci", windowTitle: "build-01"),
            Server(name: "Build Mac 2", host: "203.0.113.11", port: 15944, username: "ci"),
            Server(name: "Release Mac", host: "203.0.113.20", port: 5900, username: "release"),
            Server(name: "Device Lab", host: "198.51.100.7", port: 15950, username: "qa"),
        ]
        let seed = ServerStore(fileURL: file, passwordIDs: [])
        for server in demo { try? seed.save(server, password: nil) }
        let store = ServerStore(fileURL: file, passwordIDs: Set(demo.dropLast().map(\.id)))
        let accessibility = Accessibility(isTrusted: true)

        let screens: [(String, AnyView)] = [
            ("servers", AnyView(PopoverView(store: store, accessibility: accessibility, connect: { _ in }, typePassword: { _ in }))),
            ("editor", AnyView(ServerEditor(store: store, target: .existing(store.servers[0]), done: {}).padding().frame(width: 380))),
            ("settings", AnyView(SettingsView(done: {}).padding().frame(width: 380))),
        ]
        do {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            for (name, view) in screens {
                for (suffix, appearance) in [("light", NSAppearance.Name.aqua), ("dark", .darkAqua)] {
                    let png = try snapshot(view, appearance: NSAppearance(named: appearance)!)
                    try png.write(to: directory.appendingPathComponent("\(name)-\(suffix).png"))
                }
            }
        } catch {
            print("could not render: \(error.localizedDescription)")
            return 1
        }
        try? FileManager.default.removeItem(at: file.deletingLastPathComponent())
        print("rendered \(screens.count * 2) screenshots into \(directory.path)")
        return 0
    }

    private static func snapshot(_ view: AnyView, appearance: NSAppearance) throws -> Data {
        let framed = view
            .background(Color(nsColor: .windowBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.primary.opacity(0.12)))
            .padding(1)
        let host = NSHostingView(rootView: framed)
        host.appearance = appearance
        host.frame.size = host.fittingSize
        let window = NSWindow(contentRect: host.frame, styleMask: .borderless, backing: .buffered, defer: false)
        window.isOpaque = false
        window.backgroundColor = .clear
        window.contentView = host
        window.appearance = appearance
        host.layoutSubtreeIfNeeded()
        guard let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds) else {
            throw StoreError(message: "no bitmap")
        }
        host.cacheDisplay(in: host.bounds, to: rep)
        guard let png = rep.representation(using: .png, properties: [:]) else { throw StoreError(message: "no PNG") }
        return png
    }
}
