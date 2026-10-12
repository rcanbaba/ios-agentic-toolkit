import Foundation

final class SocketClient {
    static let shared = SocketClient()
    var onMessage: ((IncomingMessageType, [String: Any]) -> Void)?

    func connect() {}

    func send(_ action: OutgoingActionType, payload: [String: Any]) {
        // encoding omitted
    }

    func handle(raw: [String: Any]) {
        guard let typeName = raw["type"] as? String, let type = IncomingMessageType(rawValue: typeName) else { return }
        onMessage?(type, raw)
    }
}
