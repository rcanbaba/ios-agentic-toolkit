import AppKit
import SwiftUI

/// Owns the status item and its popover. AppKit rather than `MenuBarExtra`, because the
/// popover must be closed programmatically before keys are typed into another app.
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem?
    private let popover = NSPopover()

    func applicationDidFinishLaunching(_ notification: Notification) {
        popover.behavior = .transient
        popover.contentViewController = NSHostingController(rootView: PopoverView())

        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = item.button {
            button.image = NSImage(systemSymbolName: "display.2", accessibilityDescription: "VNCBar")
            button.target = self
            button.action = #selector(togglePopover(_:))
        }
        statusItem = item
    }

    @objc private func togglePopover(_ sender: NSStatusBarButton) {
        if popover.isShown {
            popover.performClose(sender)
        } else {
            popover.show(relativeTo: sender.bounds, of: sender, preferredEdge: .minY)
            popover.contentViewController?.view.window?.makeKey()
        }
    }
}
