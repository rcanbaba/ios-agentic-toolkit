import SwiftUI

struct ReportSheet: View {
    let messageId: String
    @State private var reason = ""

    var body: some View {
        Form {
            TextField("Reason", text: $reason)
            Button("Submit") {
                Task { try? await APIClient.shared.reportMessage(messageId: messageId, reason: reason) }
            }
        }
    }
}
