import Foundation

/// `vncbar://connect/<server name>` and `vncbar://type/<server name>` (name percent-encoded).
/// The URL never carries a password.
struct AppURL: Equatable {
    enum Action: String {
        case connect
        case type
    }

    let action: Action
    let serverName: String

    init(action: Action, serverName: String) {
        self.action = action
        self.serverName = serverName
    }

    init?(_ url: URL) {
        guard url.scheme?.lowercased() == "vncbar",
              let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let action = components.host.flatMap({ Action(rawValue: $0.lowercased()) }) else { return nil }
        let name = String(components.path.drop(while: { $0 == "/" }))
        guard !name.isEmpty, !name.contains("/") else { return nil }
        self.action = action
        serverName = name
    }
}
