import AppKit
import ApplicationServices

/// Connect, then (when auto-type is on) walk Screen Sharing's dialogs and log in to the remote Mac:
///
/// 1. Note Screen Sharing's windows, open `vnc://user@host:port`.
/// 2. In windows that were not there before: choose Continue on the connection-type dialog (only
///    while its first option, Standard, is selected); type the password into an authentication
///    dialog once; stop at the first window that shows a remote screen.
/// 3. Learn that window's title for the server, wait the login delay, and type the password +
///    Return into it, only while it is the focused window.
///
/// Nothing is typed when no new session window appears (the server was already open), so a
/// password is never typed into a session that is already logged in.
@MainActor
enum ConnectFlow {
    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    static func connect(_ server: Server, store: ServerStore) async throws {
        let before = ScreenSharing.app.map { ScreenSharing.windows(of: $0).map(\.element) } ?? []
        try await Connector.connect(server)
        guard Settings.autoType, let password = Keychain.password(for: server.id), !password.isEmpty else { return }
        guard AXIsProcessTrusted() else {
            throw Failure(message: "Connected, but typing the password needs the Accessibility permission.")
        }

        let session = try await waitForSession(password: password, before: before)
        try? store.setWindowTitle(session.window.title, for: server.id)

        try await Task.sleep(for: Settings.loginDelay)
        ScreenSharing.raise(session.window, of: session.app)
        for _ in 0..<20 where !ScreenSharing.isFocused(session.window, of: session.app) {
            try await Task.sleep(for: .milliseconds(100))
        }
        try await Typer(keyDelay: Settings.keyDelay).type(password, pressReturn: true) {
            ScreenSharing.isFocused(session.window, of: session.app)
        }
    }

    private static func waitForSession(password: String, before: [AXUIElement]) async throws
        -> (app: NSRunningApplication, window: ScreenSharing.Window) {
        var deadline = ContinuousClock.now + .seconds(20)
        var choseType = false
        var typedAuth = false
        while ContinuousClock.now < deadline {
            try await Task.sleep(for: .milliseconds(250))
            guard let app = ScreenSharing.app else { continue }
            let fresh = ScreenSharing.windows(of: app).filter { w in !before.contains { CFEqual($0, w.element) } }

            if let session = fresh.first(where: ScreenSharing.isSession) {
                return (app, session)
            }
            for window in fresh {
                if !choseType, Settings.autoChooseStandard, pressContinueIfStandard(in: window) {
                    choseType = true
                    deadline = ContinuousClock.now + .seconds(20)
                } else if let field = ScreenSharing.find(in: window.element, { ScreenSharing.subrole($0) == kAXSecureTextFieldSubrole }) {
                    guard !typedAuth else {
                        throw Failure(message: "Screen Sharing asked for the password again; the saved password may be wrong.")
                    }
                    typedAuth = true
                    ScreenSharing.raise(window, of: app)
                    AXUIElementSetAttributeValue(field, kAXFocusedAttribute as CFString, kCFBooleanTrue)
                    try await Task.sleep(for: .milliseconds(300))
                    try await Typer(keyDelay: Settings.keyDelay).type(password, pressReturn: true) {
                        ScreenSharing.isFocused(window, of: app)
                    }
                    deadline = ContinuousClock.now + .seconds(20)
                }
            }
        }
        throw Failure(message: "No new Screen Sharing window appeared within 20 seconds, so nothing was typed. "
                      + "If this server was already open, use Password or ⌃⌥P in its window.")
    }

    /// The connection-type dialog: a radio group whose first option is selected, and a Continue
    /// (default) button. Pressed through Accessibility, not with keys.
    private static func pressContinueIfStandard(in window: ScreenSharing.Window) -> Bool {
        guard let group = ScreenSharing.find(in: window.element, { ScreenSharing.role($0) == kAXRadioGroupRole }) else {
            return false
        }
        let radios: [AXUIElement] = ScreenSharing.attribute(group, kAXChildrenAttribute) ?? []
        guard let first = radios.first, (ScreenSharing.attribute(first, kAXValueAttribute) as NSNumber?)?.intValue == 1 else {
            return false
        }
        let button: AXUIElement? = ScreenSharing.attribute(window.element, kAXDefaultButtonAttribute)
            ?? ScreenSharing.find(in: window.element) { element in
                ScreenSharing.role(element) == kAXButtonRole
                    && (ScreenSharing.attribute(element, kAXDescriptionAttribute) as String?) == "Continue"
            }
        guard let button else { return false }
        return AXUIElementPerformAction(button, kAXPressAction as CFString) == .success
    }
}
