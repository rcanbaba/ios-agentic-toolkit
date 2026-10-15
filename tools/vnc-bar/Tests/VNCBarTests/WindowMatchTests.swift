import Foundation
import Testing
@testable import VNCBar

@MainActor
struct WindowMatchTests {
    let store: ServerStore

    init() throws {
        let file = FileManager.default.temporaryDirectory
            .appendingPathComponent("vncbar-tests-\(UUID().uuidString)/servers.json")
        store = ServerStore(fileURL: file)
        for (name, host) in [("Build 1", "203.0.113.10"), ("Build 2", "203.0.113.11"), ("Release", "203.0.113.20")] {
            try store.save(Server(name: name, host: host, username: "alex"), password: nil)
        }
    }

    @Test func learnedTitleWins() throws {
        let release = try #require(store.server(named: "Release"))
        try store.setWindowTitle("release-mac", for: release.id)
        #expect(store.server(forWindowTitle: "release-mac")?.name == "Release")
    }

    @Test func hostThenName() {
        #expect(store.server(forWindowTitle: "203.0.113.11")?.name == "Build 2")
        #expect(store.server(forWindowTitle: "release")?.name == "Release")
    }

    @Test func neverGuessesBetweenSeveral() {
        #expect(store.server(forWindowTitle: "Build") == nil)
        #expect(store.server(forWindowTitle: "Unknown Mac") == nil)
    }

    @Test func windowTitlePersists() throws {
        let release = try #require(store.server(named: "Release"))
        try store.setWindowTitle("release-mac", for: release.id)
        #expect(ServerStore(fileURL: store.fileURL).server(named: "Release")?.windowTitle == "release-mac")
    }
}
