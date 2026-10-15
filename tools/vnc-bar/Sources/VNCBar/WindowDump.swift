import AppKit
import ApplicationServices

/// `VNCBar --dump-windows`: prints Screen Sharing's windows and their element tree (role, subrole,
/// title, description, and for text fields only the length of the value), to see which dialog is
/// showing when automation does not behave. Field contents are never printed.
@MainActor
enum WindowDump {
    static func run() -> Int32 {
        guard AXIsProcessTrusted() else {
            print("the process running this command needs the Accessibility permission")
            return 2
        }
        guard let app = ScreenSharing.app else {
            print("Screen Sharing is not running")
            return 1
        }
        for window in ScreenSharing.windows(of: app) {
            dump(window.element, depth: 0)
        }
        return 0
    }

    private static func dump(_ element: AXUIElement, depth: Int) {
        let role: String = ScreenSharing.attribute(element, kAXRoleAttribute) ?? "?"
        let subrole: String? = ScreenSharing.attribute(element, kAXSubroleAttribute)
        let title: String? = ScreenSharing.attribute(element, kAXTitleAttribute)
        let description: String? = ScreenSharing.attribute(element, kAXDescriptionAttribute)
        var line = String(repeating: "  ", count: depth) + role
        if let subrole { line += " [\(subrole)]" }
        if let title, !title.isEmpty { line += " title=\"\(title)\"" }
        if let description, !description.isEmpty { line += " desc=\"\(description)\"" }
        if role == kAXTextFieldRole as String || subrole == kAXSecureTextFieldSubrole as String {
            let value: String? = ScreenSharing.attribute(element, kAXValueAttribute)
            line += " value=<\(value?.count ?? 0) chars>"
        } else if role == kAXRadioButtonRole as String || role == kAXCheckBoxRole as String {
            let value: NSNumber? = ScreenSharing.attribute(element, kAXValueAttribute)
            line += " value=\(value?.intValue ?? -1)"
        }
        print(line)
        guard depth < 8 else { return }
        let children: [AXUIElement] = ScreenSharing.attribute(element, kAXChildrenAttribute) ?? []
        for child in children { dump(child, depth: depth + 1) }
    }
}
