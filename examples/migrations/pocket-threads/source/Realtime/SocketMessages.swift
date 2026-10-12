enum IncomingMessageType: String {
    case messageReceived = "message_received"
    case typingStarted = "typing_started"
    case threadUpdated = "thread_updated"
}

enum OutgoingActionType: String {
    case joinThread = "join_thread"
    case leaveThread = "leave_thread"
    case typing = "typing"
}
