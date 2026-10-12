enum APIPath: String {
    case threads = "/threads"
    case messages = "/threads/{id}/messages"
    case send = "/threads/{id}/send"
    case markRead = "/threads/{id}/read"
    case notificationPrefs = "/me/notifications"
    case deleteAccount = "/me/delete"
    case report = "/messages/{id}/report"
}
