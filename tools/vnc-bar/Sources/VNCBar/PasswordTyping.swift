import AppKit

/// The Password button: raise the server's Screen Sharing window and type its password + Return.
@MainActor
enum PasswordTyping {
    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    /// `fallbackToFocusedWindow` is false for requests from outside the app (the URL scheme): any
    /// app or web page can open a `vncbar://` URL, so it types only into the server's own window.
    static func typePassword(for server: Server, fallbackToFocusedWindow: Bool = true) async throws {
        guard AXIsProcessTrusted() else {
            throw Failure(message: "VNCBar needs the Accessibility permission to type. Open VNCBar and press Grant.")
        }
        guard let password = Keychain.password(for: server.id), !password.isEmpty else {
            throw Failure(message: "No password is saved for \(server.name).")
        }
        guard let app = ScreenSharing.app else {
            throw Failure(message: "Screen Sharing is not running. Connect first.")
        }
        var window = ScreenSharing.window(for: server, in: ScreenSharing.windows(of: app))
        if window == nil, fallbackToFocusedWindow { window = ScreenSharing.mainWindow(of: app) }
        guard let window else { throw Failure(message: "No Screen Sharing window belongs to \(server.name).") }

        ScreenSharing.raise(window, of: app)
        for _ in 0..<20 where !ScreenSharing.isFrontmost(app) {
            try await Task.sleep(for: .milliseconds(100))
        }
        guard ScreenSharing.isFrontmost(app) else {
            throw Failure(message: "Screen Sharing did not come to the front; nothing was typed.")
        }
        try await Task.sleep(for: .milliseconds(300))
        try await Typer(keyDelay: Settings.keyDelay).type(password, pressReturn: true) { ScreenSharing.isFrontmost(app) }
    }
}
