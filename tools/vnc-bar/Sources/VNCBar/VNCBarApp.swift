import AppKit

@main
@MainActor
enum VNCBarApp {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.accessory)  // menu bar only, no Dock icon
        withExtendedLifetime(delegate) { app.run() }
    }
}
