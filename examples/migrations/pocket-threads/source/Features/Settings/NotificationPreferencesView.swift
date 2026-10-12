import SwiftUI

struct NotificationPreferencesView: View {
    @State private var prefs = NotificationPreferences()

    var body: some View {
        Form {
            Toggle("New messages", isOn: $prefs.newMessages)
            Toggle("Mentions", isOn: $prefs.mentions)
        }
        .onChange(of: prefs) { value in
            Task { try? await APIClient.shared.updateNotificationPreferences(value) }
        }
    }
}
