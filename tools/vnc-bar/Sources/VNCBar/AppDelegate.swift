import AppKit
import Carbon.HIToolbox
import SwiftUI

/// Owns the status item and its popover. AppKit rather than `MenuBarExtra`, because the
/// popover must be closed programmatically before keys are typed into another app.
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem?
    private let popover = NSPopover()
    private let store = ServerStore()
    private let accessibility = Accessibility()
    private var hotKey: HotKey?

    func applicationDidFinishLaunching(_ notification: Notification) {
        EditMenu.install()
        hotKey = HotKey(keyCode: kVK_ANSI_P, modifiers: controlKey | optionKey) { [weak self] in self?.hotKeyPressed() }
        popover.behavior = .transient
        let host = NSHostingController(rootView: PopoverView(store: store, accessibility: accessibility,
                                                         connect: { [weak self] in self?.connect($0) },
                                                         typePassword: { [weak self] in self?.typePassword($0) }))
        host.sizingOptions = .preferredContentSize  // the popover follows list ⇄ editor size changes
        popover.contentViewController = host

        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = item.button {
            button.image = NSImage(systemSymbolName: "display.2", accessibilityDescription: "VNCBar")
            button.target = self
            button.action = #selector(togglePopover(_:))
        }
        statusItem = item
    }

    private func connect(_ server: Server) {
        popover.performClose(nil)
        run("Could not connect to \(server.name)") { [store] in try await ConnectFlow.connect(server, store: store) }
    }

    private func typePassword(_ server: Server) {
        popover.performClose(nil)
        run("Could not type the password for \(server.name)") { try await PasswordTyping.typePassword(for: server) }
    }

    /// ⌃⌥P: only when Screen Sharing is in front and its focused window belongs to exactly one
    /// server; otherwise beep and type nothing.
    private func hotKeyPressed() {
        guard let app = ScreenSharing.app, ScreenSharing.isFrontmost(app),
              let window = ScreenSharing.mainWindow(of: app),
              let server = store.server(forWindowTitle: window.title) else {
            NSSound.beep()
            return
        }
        typePassword(server)
    }

    private func run(_ failureTitle: String, _ work: @escaping @MainActor () async throws -> Void) {
        Task {
            do {
                try await work()
            } catch {
                NSSound.beep()
                let alert = NSAlert()
                alert.messageText = failureTitle
                alert.informativeText = error.localizedDescription
                NSApp.activate()
                alert.runModal()
            }
        }
    }

    @objc private func togglePopover(_ sender: NSStatusBarButton) {
        if popover.isShown {
            popover.performClose(sender)
        } else {
            accessibility.refresh()
            NSApp.activate()  // an accessory app must be active for its text fields to take input
            popover.show(relativeTo: sender.bounds, of: sender, preferredEdge: .minY)
            popover.contentViewController?.view.window?.makeKey()
        }
    }
}
