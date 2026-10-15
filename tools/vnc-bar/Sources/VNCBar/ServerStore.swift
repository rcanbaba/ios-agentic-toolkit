import Foundation
import Observation

/// The server list in `~/Library/Application Support/VNCBar/servers.json`, plus which servers
/// have a password in the Keychain. Passwords are never written to the file.
@MainActor
@Observable
final class ServerStore {
    private(set) var servers: [Server] = []
    private(set) var withPassword: Set<UUID> = []
    private(set) var loadError: String?
    let fileURL: URL

    private struct File: Codable {
        var version = 1
        var servers: [Server]
    }

    static var defaultURL: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("VNCBar/servers.json")
    }

    /// `passwordIDs` replaces the Keychain lookup (synthetic screenshots).
    init(fileURL: URL = ServerStore.defaultURL, passwordIDs: Set<UUID>? = nil) {
        self.fileURL = fileURL
        load(passwordIDs: passwordIDs)
    }

    func load(passwordIDs: Set<UUID>? = nil) {
        withPassword = passwordIDs ?? Keychain.idsWithPassword()
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return }
        do {
            servers = try JSONDecoder().decode(File.self, from: Data(contentsOf: fileURL)).servers
        } catch {
            loadError = "Could not read \(fileURL.path): \(error.localizedDescription)"
        }
    }

    func server(named name: String) -> Server? {
        servers.first { $0.name.compare(name, options: .caseInsensitive) == .orderedSame }
    }

    /// Nil if the server can be saved; otherwise what is wrong with it.
    func problem(with server: Server) -> String? {
        if server.name.trimmingCharacters(in: .whitespaces).isEmpty { return "Name is required." }
        if let other = self.server(named: server.name), other.id != server.id { return "Another server has this name." }
        if ParsedAddress.parse(server.host).map({ $0.host == server.host && $0.port == nil }) != true {
            return "Host must be a name or an IP address, without a port."
        }
        if !(1...65535).contains(server.port) { return "Port must be between 1 and 65535." }
        if server.username.isEmpty { return "Username is required." }
        return nil
    }

    /// Adds or updates a server. `password` nil keeps the stored one.
    func save(_ server: Server, password: String?) throws {
        if let problem = problem(with: server) { throw StoreError(message: problem) }
        if let password, !password.isEmpty {
            try Keychain.setPassword(password, for: server.id, label: "VNCBar: \(server.name)")
            withPassword.insert(server.id)
        }
        var updated = servers
        if let index = updated.firstIndex(where: { $0.id == server.id }) {
            updated[index] = server
        } else {
            updated.append(server)
        }
        try write(updated)
        servers = updated
    }

    /// Remembers the title of the Screen Sharing window that `id` opened (or clears it with nil).
    func setWindowTitle(_ title: String?, for id: UUID) throws {
        guard let index = servers.firstIndex(where: { $0.id == id }), servers[index].windowTitle != title else { return }
        var updated = servers
        updated[index].windowTitle = title
        try write(updated)
        servers = updated
    }

    /// The server whose Screen Sharing window has this title: learned title, then host, then name.
    /// Nil unless exactly one server matches at the first rule that matches any.
    func server(forWindowTitle title: String) -> Server? {
        let rules: [(Server) -> Bool] = [
            { $0.windowTitle == title },
            { title.contains($0.host) },
            { title.localizedCaseInsensitiveContains($0.name) },
        ]
        for rule in rules {
            let hits = servers.filter(rule)
            if !hits.isEmpty { return hits.count == 1 ? hits[0] : nil }
        }
        return nil
    }

    func delete(_ server: Server) throws {
        let updated = servers.filter { $0.id != server.id }
        try write(updated)
        servers = updated
        Keychain.deletePassword(for: server.id)
        withPassword.remove(server.id)
    }

    private func write(_ servers: [Server]) throws {
        try FileManager.default.createDirectory(at: fileURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        try encoder.encode(File(servers: servers)).write(to: fileURL, options: .atomic)
    }
}

struct StoreError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}
