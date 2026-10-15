import AppKit

/// Opens a server in macOS Screen Sharing through a `vnc://` URL.
enum Connector {
    static let screenSharingID = "com.apple.ScreenSharing"

    /// RFC 3986 unreserved characters; everything else in a user name or password is percent-encoded.
    private static let unreserved = CharacterSet(
        charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")

    static func encode(_ s: String) -> String {
        s.addingPercentEncoding(withAllowedCharacters: unreserved) ?? s
    }

    /// `vnc://user:password@host:port`, or without the password when there is none.
    static func url(for server: Server, password: String?) -> URL? {
        var credentials = encode(server.username)
        if let password, !password.isEmpty { credentials += ":" + encode(password) }
        return URL(string: "vnc://\(credentials)@\(server.host):\(server.port)")
    }

    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    /// Opens the URL with Screen Sharing itself, so another app registered for `vnc://` is never used.
    @MainActor
    static func connect(_ server: Server) async throws {
        guard let url = url(for: server, password: Keychain.password(for: server.id)) else {
            throw Failure(message: "Could not build a vnc:// address for \(server.name).")
        }
        guard let app = NSWorkspace.shared.urlForApplication(withBundleIdentifier: screenSharingID) else {
            throw Failure(message: "Screen Sharing was not found.")
        }
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.activates = true
        _ = try await NSWorkspace.shared.open([url], withApplicationAt: app, configuration: configuration)
    }
}
