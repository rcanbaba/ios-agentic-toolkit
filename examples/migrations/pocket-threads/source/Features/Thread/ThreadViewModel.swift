import Foundation

@MainActor
final class ThreadViewModel: ObservableObject {
    let threadId: String
    @Published var messages: [Message] = []
    @Published var peerIsTyping = false
    @Published var isSending = false
    @Published var sendError: String?

    init(threadId: String) { self.threadId = threadId }

    func open() async {
        messages = (try? await APIClient.shared.fetchMessages(threadId: threadId)) ?? []
        SocketClient.shared.send(.joinThread, payload: ["id": threadId])
        SocketClient.shared.onMessage = { [weak self] type, payload in
            switch type {
            case .messageReceived:
                if let message = Message(payload: payload) { self?.messages.append(message) }
            case .typingStarted:
                self?.peerIsTyping = true
            default:
                break
            }
        }
        try? await APIClient.shared.markThreadRead(threadId: threadId)
    }

    func send(_ text: String) async {
        isSending = true
        defer { isSending = false }
        do {
            let message = try await APIClient.shared.sendMessage(threadId: threadId, text: text)
            messages.append(message)
            sendError = nil
        } catch {
            // one silent retry, then surface the error
            if let message = try? await APIClient.shared.sendMessage(threadId: threadId, text: text) {
                messages.append(message)
            } else {
                sendError = "Could not send"
            }
        }
    }

    func typing() {
        SocketClient.shared.send(.typing, payload: ["id": threadId])
    }

    func report(_ message: Message) {
        Router.shared.present(ReportSheet(messageId: message.id))
    }

    func close() {
        SocketClient.shared.send(.leaveThread, payload: ["id": threadId])
    }
}
