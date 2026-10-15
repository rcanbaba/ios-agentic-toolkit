import AppKit
import SwiftUI

/// Owns the status item and its popover. AppKit rather than `MenuBarExtra`, because the
/// popover must be closed programmatically before keys are typed into another app.
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem?
    private let popover = NSPopover()
    private let store = ServerStore()

    func applicationDidFinishLaunching(_ notification: Notification) {
        EditMenu.install()
        popover.behavior = .transient
        let host = NSHostingController(rootView: PopoverView(store: store, connect: { [weak self] in self?.connect($0) }))
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
        Task {
            do {
                try await Connector.connect(server)
            } catch {
                let alert = NSAlert()
                alert.messageText = "Could not connect to \(server.name)"
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
            NSApp.activate()  // an accessory app must be active for its text fields to take input
            popover.show(relativeTo: sender.bounds, of: sender, preferredEdge: .minY)
            popover.contentViewController?.view.window?.makeKey()
        }
    }
}
