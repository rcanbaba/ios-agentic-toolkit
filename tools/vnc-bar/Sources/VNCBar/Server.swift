import Foundation

/// One remote Mac. The password is never part of this type; it lives in the Keychain under `id`.
struct Server: Codable, Identifiable, Hashable, Sendable {
    var id = UUID()
    var name: String
    var host: String
    var port: Int = Server.defaultPort
    var username: String
    /// Title of the Screen Sharing window this server opened last time, learned on connect.
    var windowTitle: String?

    static let defaultPort = 5900

    var address: String { "\(username)@\(host):\(port)" }
}

/// The parts of a pasted address: `vnc://user:pass@host:port`, `host:port` or `host`.
struct ParsedAddress: Equatable, Sendable {
    var host: String
    var port: Int?
    var username: String?
    var password: String?

    init(host: String, port: Int? = nil, username: String? = nil, password: String? = nil) {
        self.host = host
        self.port = port
        self.username = username
        self.password = password
    }

    static func parse(_ text: String) -> ParsedAddress? {
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.lowercased().hasPrefix("vnc://") {
            guard let url = URLComponents(string: text), let host = url.host, isHost(host) else { return nil }
            return ParsedAddress(host: host, port: url.port, username: nonEmpty(url.user), password: nonEmpty(url.password))
        }
        if let colon = text.lastIndex(of: ":") {
            let host = String(text[..<colon])
            guard let port = Int(text[text.index(after: colon)...]), (1...65535).contains(port), isHost(host),
                  !host.contains(":") else { return nil }
            return ParsedAddress(host: host, port: port)
        }
        return isHost(text) ? ParsedAddress(host: text) : nil
    }

    private static func isHost(_ s: String) -> Bool {
        !s.isEmpty && !s.contains(where: { $0.isWhitespace || "/@?#".contains($0) })
    }

    private static func nonEmpty(_ s: String?) -> String? {
        s.flatMap { $0.isEmpty ? nil : $0 }
    }
}
