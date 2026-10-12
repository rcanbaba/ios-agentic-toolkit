final class PushHandler {
    func handle(userInfo: [String: Any]) {
        guard let raw = userInfo["type"] as? String, let type = PushType(rawValue: raw) else { return }
        switch type {
        case .newMessage, .mention:
            if let threadId = userInfo["thread_id"] as? String {
                Router.shared.navigate(to: .thread(id: threadId))
            }
        default:
            break
        }
    }
}
