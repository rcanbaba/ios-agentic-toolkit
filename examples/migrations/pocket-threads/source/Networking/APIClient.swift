import Foundation

struct RequestConfiguration {
    let path: APIPath
    let body: [String: Any]?
}

final class APIClient {
    static let shared = APIClient()

    public func fetchThreads() async throws -> [Thread] {
        try await perform(RequestConfiguration(path: .threads, body: nil))
    }

    func fetchMessages(threadId: String) async throws -> [Message] {
        try await perform(RequestConfiguration(path: .messages, body: ["id": threadId]))
    }

    func sendMessage(threadId: String, text: String) async throws -> Message {
        // Retried once by the caller on failure.
        try await perform(RequestConfiguration(path: .send, body: ["id": threadId, "text": text]))
    }

    func markThreadRead(threadId: String) async throws {
        _ = try await perform(RequestConfiguration(path: .markRead, body: ["id": threadId]))
    }

    func updateNotificationPreferences(_ prefs: NotificationPreferences) async throws {
        _ = try await perform(RequestConfiguration(path: .notificationPrefs, body: prefs.asDictionary))
    }

    func deleteAccount() async throws {
        _ = try await perform(RequestConfiguration(path: .deleteAccount, body: nil))
    }

    private func perform<T>(_ configuration: RequestConfiguration) async throws -> T {
        fatalError("network layer omitted in this fixture")
    }
}

extension APIClient {
    internal func reportMessage(messageId: String, reason: String) async throws {
        _ = try await perform(RequestConfiguration(path: .report, body: ["id": messageId, "reason": reason]))
    }
}
