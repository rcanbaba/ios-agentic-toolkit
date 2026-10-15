import AppKit

/// The Password button: raise the server's Screen Sharing window and type its password + Return.
@MainActor
enum PasswordTyping {
    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    static func typePassword(for server: Server) async throws {
        guard AXIsProcessTrusted() else {
            throw Failure(message: "VNCBar needs the Accessibility permission to type. Open VNCBar and press Grant.")
        }
        guard let password = Keychain.password(for: server.id), !password.isEmpty else {
            throw Failure(message: "No password is saved for \(server.name).")
        }
        guard let app = ScreenSharing.app else {
            throw Failure(message: "Screen Sharing is not running. Connect first.")
        }
        let window = ScreenSharing.window(for: server, in: ScreenSharing.windows(of: app))
            ?? ScreenSharing.mainWindow(of: app)
        guard let window else { throw Failure(message: "Screen Sharing has no open window.") }

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
