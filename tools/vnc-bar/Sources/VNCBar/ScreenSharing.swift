import AppKit
import ApplicationServices

/// Screen Sharing's windows through the Accessibility API.
@MainActor
enum ScreenSharing {
    struct Window {
        let element: AXUIElement
        let title: String
    }

    static var app: NSRunningApplication? {
        NSRunningApplication.runningApplications(withBundleIdentifier: Connector.screenSharingID).first
    }

    static func attribute<T>(_ element: AXUIElement, _ name: String) -> T? {
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success else { return nil }
        return value as? T
    }

    static func windows(of app: NSRunningApplication) -> [Window] {
        let appElement = AXUIElementCreateApplication(app.processIdentifier)
        let elements: [AXUIElement] = attribute(appElement, kAXWindowsAttribute) ?? []
        return elements.map { Window(element: $0, title: attribute($0, kAXTitleAttribute) ?? "") }
    }

    static func mainWindow(of app: NSRunningApplication) -> Window? {
        let appElement = AXUIElementCreateApplication(app.processIdentifier)
        let element: AXUIElement? = attribute(appElement, kAXFocusedWindowAttribute)
            ?? attribute(appElement, kAXMainWindowAttribute)
        return element.map { Window(element: $0, title: attribute($0, kAXTitleAttribute) ?? "") }
    }

    /// The window of `server`: by its learned title, then its host, then its name. Never a guess
    /// between several candidates.
    static func window(for server: Server, in windows: [Window]) -> Window? {
        let tests: [(String) -> Bool] = [
            { title in server.windowTitle.map { title == $0 } ?? false },
            { title in title.contains(server.host) },
            { title in title.localizedCaseInsensitiveContains(server.name) },
        ]
        for test in tests {
            let hits = windows.filter { test($0.title) }
            if hits.count == 1 { return hits[0] }
        }
        return nil
    }

    static func raise(_ window: Window, of app: NSRunningApplication) {
        app.activate()
        AXUIElementPerformAction(window.element, kAXRaiseAction as CFString)
        AXUIElementSetAttributeValue(window.element, kAXMainAttribute as CFString, kCFBooleanTrue)
    }

    /// The first element in `element`'s subtree (depth-first, at most `depth` levels) matching `test`.
    static func find(in element: AXUIElement, depth: Int = 6, _ test: (AXUIElement) -> Bool) -> AXUIElement? {
        if test(element) { return element }
        guard depth > 0 else { return nil }
        let children: [AXUIElement] = attribute(element, kAXChildrenAttribute) ?? []
        for child in children {
            if let hit = find(in: child, depth: depth - 1, test) { return hit }
        }
        return nil
    }

    static func role(_ element: AXUIElement) -> String? { attribute(element, kAXRoleAttribute) }
    static func subrole(_ element: AXUIElement) -> String? { attribute(element, kAXSubroleAttribute) }

    /// A connected session: the window shows the remote screen.
    static func isSession(_ window: Window) -> Bool {
        find(in: window.element, depth: 1) { role($0) == "AXSharedScreen" } != nil
    }

    static func isFocused(_ window: Window, of app: NSRunningApplication) -> Bool {
        guard isFrontmost(app), let focused = mainWindow(of: app) else { return false }
        return CFEqual(focused.element, window.element)
    }

    static func isFrontmost(_ app: NSRunningApplication) -> Bool {
        NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier
    }
}
