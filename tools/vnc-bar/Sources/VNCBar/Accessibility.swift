import AppKit
import ApplicationServices
import Observation

/// Whether VNCBar may post key events and read other apps' windows (System Settings →
/// Privacy & Security → Accessibility). The grant is tied to the code signature, which is why
/// build.sh signs with a stable identity.
@MainActor
@Observable
final class Accessibility {
    private(set) var isTrusted: Bool
    private var poll: Timer?

    init(isTrusted: Bool = AXIsProcessTrusted()) {
        self.isTrusted = isTrusted
    }

    func refresh() {
        isTrusted = AXIsProcessTrusted()
        if isTrusted { poll?.invalidate(); poll = nil }
    }

    /// Shows the system prompt (once per app) and opens the settings pane, then watches for the grant.
    func request() {
        let options = ["AXTrustedCheckOptionPrompt": true] as CFDictionary
        isTrusted = AXIsProcessTrustedWithOptions(options)
        guard !isTrusted else { return }
        if let pane = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
            NSWorkspace.shared.open(pane)
        }
        poll?.invalidate()
        poll = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
            MainActor.assumeIsolated { self.refresh() }
        }
    }
}
