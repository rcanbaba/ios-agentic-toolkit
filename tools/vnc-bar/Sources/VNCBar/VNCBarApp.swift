import AppKit

@main
@MainActor
enum VNCBarApp {
    static func main() {
        let args = CommandLine.arguments
        if args.count == 3, args[1] == "--check-leak" {
            exit(LeakCheck.run(serverName: args[2]))
        }
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.accessory)  // menu bar only, no Dock icon
        withExtendedLifetime(delegate) { app.run() }
    }
}
